"""
scheduler_functions.py — Встроенный планировщик промодаты
=========================================================
Встроенный тик-планировщик. Windows Task Scheduler управляется
через app.py (schtasks), эта модуль только запускает пайплайн.
"""

import threading
import logging
from datetime import datetime

SCHEDULER_DEFAULTS = {
    "scheduler_enabled": False,
    "scheduler_time": "08:00",
    # Дни теперь управляются через Windows Task Scheduler
    # но сохраняем для fallback внутреннего планировщика
    "scheduler_days": ["mon", "tue", "wed", "thu", "fri"],
    "scheduler_steps": ["download", "process", "query1", "query2", "macros"],
    "scheduler_auto_month": True,
    "scheduler_month_from": 1,
    "scheduler_year_from": 2026,
    "scheduler_month_to": 1,
    "scheduler_year_to": 2026,
    "scheduler_category": "Масло",
    "scheduler_win_task": False,  # True = задача зарегистрирована в Windows
    "scheduler_last_run": "",
    "scheduler_last_status": "",
}

DAY_MAP = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


class PromodateScheduler:
    def __init__(self, get_config_fn, save_config_fn, run_pipeline_fn, emit_fn):
        self._get_config = get_config_fn
        self._save_config = save_config_fn
        self._run_pipeline = run_pipeline_fn
        self._emit = emit_fn
        self._thread = None
        self._stop = threading.Event()
        self._running_lock = threading.Lock()
        self._last_fired_dt = (
            None  # datetime(year,month,day,hour,minute) последнего срабатывания
        )

    def start(self):
        # Если поток уже работает — не создаём дублирующий
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="PromodateScheduler"
        )
        self._thread.start()
        logging.info("Планировщик промодаты (re)запущен")

    def stop(self):
        self._stop.set()
        # Ждём завершения потока (макс 2 сек) чтобы start() мог сразу создать новый
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        self._thread = None

    def _loop(self):
        logging.info("Планировщик: поток запущен")
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception as e:
                logging.error(f"Scheduler tick error: {e}")
            self._stop.wait(20)  # 20 сек — точнее ловим начало минуты
        logging.info("Планировщик: поток остановлен")

    def _tick(self):
        cfg = self._get_config()
        if not cfg.get("scheduler_enabled", False):
            return

        now = datetime.now()

        # Проверяем день недели
        allowed = [DAY_MAP[d] for d in cfg.get("scheduler_days", []) if d in DAY_MAP]
        if now.weekday() not in allowed:
            return

        # Парсим время запуска
        try:
            sh, sm = map(int, cfg.get("scheduler_time", "08:00").split(":"))
        except Exception:
            return

        # Проверяем что сейчас та самая минута (окно 59 секунд)
        sched_dt = now.replace(hour=sh, minute=sm, second=0, microsecond=0)
        if abs((now - sched_dt).total_seconds()) > 59:
            return

        # Уже срабатывали на эту минуту?
        fire_key = sched_dt  # datetime без секунд — уникальный ключ
        if self._last_fired_dt == fire_key:
            return

        self._last_fired_dt = fire_key
        logging.info(f"Планировщик: срабатывание в {now.strftime('%H:%M:%S')}")
        self._fire(cfg)

    def _fire(self, cfg):
        steps = cfg.get("scheduler_steps", list(SCHEDULER_DEFAULTS["scheduler_steps"]))
        now = datetime.now()
        if cfg.get("scheduler_auto_month", True):
            date_from = date_to = None
            mf = mt = now.month
            yf = yt = now.year
        else:
            date_from = cfg.get("scheduler_date_from") or None
            date_to = cfg.get("scheduler_date_to") or None
            mf = int(cfg.get("scheduler_month_from", now.month))
            yf = int(cfg.get("scheduler_year_from", now.year))
            mt = int(cfg.get("scheduler_month_to", now.month))
            yt = int(cfg.get("scheduler_year_to", now.year))
        self._emit(
            "scheduler_fired", {"time": now.strftime("%H:%M"), "date": str(now.date())}
        )
        threading.Thread(
            target=self._execute,
            args=(cfg, steps, mf, yf, mt, yt, date_from, date_to),
            daemon=True,
        ).start()

    def _execute(self, cfg, steps, mf, yf, mt, yt, date_from=None, date_to=None):
        with self._running_lock:
            ts = datetime.now().isoformat(timespec="seconds")
            self._update_status(cfg, "running", ts)
            try:
                self._run_pipeline(
                    cfg, steps, mf, yf, mt, yt, date_from=date_from, date_to=date_to
                )
                self._update_status(cfg, "success", ts)
                self._emit("scheduler_done", {"status": "success", "ts": ts})
            except Exception as e:
                logging.error(f"Планировщик ошибка: {e}")
                self._update_status(cfg, "error", ts)
                self._emit(
                    "scheduler_done", {"status": "error", "error": str(e), "ts": ts}
                )

    def _update_status(self, cfg, status, ts):
        try:
            data = self._get_config()
            data["scheduler_last_run"] = ts
            data["scheduler_last_status"] = status
            self._save_config(data)
        except Exception as e:
            logging.error(f"Ошибка сохранения статуса: {e}")

    def run_now(
        self,
        cfg,
        steps=None,
        mf=None,
        yf=None,
        mt=None,
        yt=None,
        date_from=None,
        date_to=None,
    ):
        now = datetime.now()
        if steps is None:
            steps = cfg.get(
                "scheduler_steps", list(SCHEDULER_DEFAULTS["scheduler_steps"])
            )
        if mf is None:
            mf = now.month
        if yf is None:
            yf = now.year
        if mt is None:
            mt = mf
        if yt is None:
            yt = yf
        threading.Thread(
            target=self._execute,
            args=(cfg, steps, mf, yf, mt, yt, date_from, date_to),
            daemon=True,
        ).start()
