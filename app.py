# ruff: noqa: E402
"""
EFKO FlowManager — pywebview backend
pip install pywebview
"""

# ═══════════════════════════════════════════════════════════════════════════
# СПЛЭШ — САМЫЕ ПЕРВЫЕ СТРОКИ, до любых импортов
# ═══════════════════════════════════════════════════════════════════════════
import tkinter as tk


def _make_splash():
    W, H = 400, 240
    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")
    root.configure(bg="#1e8c42")

    c = tk.Canvas(root, width=W, height=H, bg="#1e8c42", highlightthickness=0)
    c.pack(fill="both", expand=True)

    for i in range(48):
        t = i / 48
        r = int(0x18 + (0x30 - 0x18) * t)
        g = int(0x8C + (0xC7 - 0x8C) * t)
        b = int(0x3A + (0x55 - 0x3A) * t)
        y0, y1 = int(H * i / 48), int(H * (i + 1) / 48) + 1
        c.create_rectangle(0, y0, W, y1, fill=f"#{r:02x}{g:02x}{b:02x}", outline="")

    cx, cy = W // 2, 72
    c.create_oval(
        cx - 28, cy - 28, cx + 28, cy + 28, fill="#2aaa52", outline="#aaffbb", width=1
    )
    c.create_line(
        cx - 13,
        cy + 2,
        cx - 3,
        cy + 12,
        cx + 14,
        cy - 9,
        fill="white",
        width=3,
        capstyle="round",
        joinstyle="round",
    )

    c.create_text(
        W // 2 - 1,
        124,
        text="Flow",
        font=("Segoe UI", 26, "bold"),
        fill="#ffffff",
        anchor="e",
    )
    c.create_text(
        W // 2 - 1,
        124,
        text="Manager",
        font=("Segoe UI", 26),
        fill="#aaeebb",
        anchor="w",
    )
    c.create_text(
        W // 2, 150, text="EFKO  ·  v3.0", font=("Segoe UI", 9), fill="#88ccaa"
    )

    bx1, by1, bx2, by2 = 50, 178, W - 50, 183
    c.create_rectangle(bx1, by1, bx2, by2, fill="#2aaa52", outline="")
    bar = c.create_rectangle(bx1, by1, bx1, by2, fill="white", outline="")
    hint = c.create_text(
        W // 2, 200, text="Запуск…", font=("Segoe UI", 9), fill="#88ccaa"
    )

    root.lift()
    root.focus_force()
    root.update()

    def set_progress(pct, text=""):
        try:
            w = (bx2 - bx1) * min(pct, 100) / 100
            c.coords(bar, bx1, by1, bx1 + w, by2)
            if text:
                c.itemconfigure(hint, text=text)
            root.update()
        except Exception:
            pass

    def close():
        try:
            root.destroy()
        except Exception:
            pass

    return set_progress, close


_splash_set, _splash_close = _make_splash()
_splash_set(8, "Загрузка модулей…")

# ── Тяжёлые импорты ───────────────────────────────────────────────────────
import webview
import threading
import json
import os
import logging
from pathlib import Path
from datetime import datetime

_splash_set(18, "Базовые модули…")

from promodate_functions import (
    FILTER_OPTIONS,
    download_files_thread,
    clear_download_folder,
    clear_output_folder,
    process_files_thread,
    refresh_power_query_files,
    run_stage_query1,
    run_stage_query2,
    run_stage_macros,
)

_splash_set(35, "Загрузка функций промодаты…")

from sku_matcher_functions import run_matching, save_to_reference

_splash_set(50, "SKU Matcher…")

from competitors_functions import refresh_competitors_pipeline

_splash_set(62, "Модуль конкурентов…")

from nielsen_functions import process_nielsen

_splash_set(74, "Nielsen…")

from production_functions import run_production, MONTH_LABELS

_splash_set(82, "Модуль производства…")

from price_comparison_functions import run_comparison as run_price_comparison

_splash_set(90, "Модуль сравнения цен…")

from scheduler_functions import PromodateScheduler, SCHEDULER_DEFAULTS

CONFIG_FILE = "config.json"


# ── Logger ────────────────────────────────────────────────────────────────


def setup_logger():
    log_path = os.path.join(os.getcwd(), "flowmanager.log")
    logging.basicConfig(
        filename=log_path,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        encoding="utf-8",
    )


# ── Config ────────────────────────────────────────────────────────────────


def load_config() -> dict:
    defaults = {
        "output_folder": "",
        "pq_file1": "",
        "pq_file2": "",
        "macro1": "ExtendDatesAndFormulas",
        "macro2": "ExtendDatesAndFormulas_MNZ",
        "olap_file": "",
        "competitors_file": "",
        "nielsen_input": "",
        "nielsen_output": "",
        "nielsen_format": "csv",
        "nielsen_category": "Масло",
        "query_refresh_file": "",
        "prod_svod_folder": "",
        "prod_npk_file": "",
        "prod_tolyatti": "",
        "prod_target": "",
        "prod_mapping": "",
        "prod_year": str(datetime.now().year),
        "prod_month": MONTH_LABELS[datetime.now().month - 1],
        # ── Сравнение цен ──
        "pc_kuper_file": "",
        "pc_promo_file": "",
        "pc_sprav_file": "",
        "pc_output_file": "",
        "pc_threshold": 0.5,
        # ──────────────────
        "dark_theme": False,
    }
    for k, v in SCHEDULER_DEFAULTS.items():
        if k not in defaults:
            defaults[k] = v
    if not os.path.exists(CONFIG_FILE):
        return defaults
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k in defaults:
            if k in data:
                defaults[k] = data[k]
    except Exception as e:
        logging.error(f"Config load error: {e}")
    return defaults


def save_config_data(data: dict):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Config save error: {e}")


# ── Mock helpers ──────────────────────────────────────────────────────────


class _SV:
    def __init__(self, v):
        self._v = v

    def get(self):
        return str(self._v) if self._v is not None else ""


class _MB:
    def __init__(self, api):
        self._api = api

    def showinfo(self, title, msg):
        self._api._emit("toast", {"type": "success", "message": str(msg)})

    def showwarning(self, title, msg):
        self._api._emit("toast", {"type": "warning", "message": str(msg)})

    def showerror(self, title, msg):
        self._api._emit("toast", {"type": "error", "message": str(msg)})

    def askyesno(self, title, msg):
        try:
            return bool(
                self._api._window.evaluate_js(f"confirm({json.dumps(str(msg))})")
            )
        except Exception:
            return False

    def askokcancel(self, title, msg):
        return self.askyesno(title, msg)


# ═════════════════════════════════════════════════════════════════════════════
# API exposed to JS
# ═════════════════════════════════════════════════════════════════════════════


class Api:
    def __init__(self):
        self._window = None
        self._stop_event = threading.Event()
        self._mb = _MB(self)
        self._last_competitors_file = None
        self._scheduler = PromodateScheduler(
            get_config_fn=load_config,
            save_config_fn=save_config_data,
            run_pipeline_fn=self._run_scheduled_pipeline,
            emit_fn=self._emit,
        )
        self._scheduler.start()

    # ── Push events ───────────────────────────────────────────────────────────

    def _emit(self, event_type, data=None):
        if self._window:
            try:
                payload = json.dumps({"type": event_type, "data": data})
                self._window.evaluate_js(f"window.__pyEvent({payload})")
            except Exception as e:
                logging.error(f"emit error [{event_type}]: {e}")

    def _log(self, msg):
        logging.info(msg)
        self._emit("log", str(msg))

    def _progress(self, done, total):
        self._emit("progress", {"done": done, "total": total})

    def _set_title(self, text):
        self._emit("set_title", str(text))

    # ── Config ────────────────────────────────────────────────────────────────

    def get_config(self):
        return load_config()

    def save_config(self, data):
        save_config_data(data)
        return True

    def get_filter_options(self):
        return list(FILTER_OPTIONS.keys())

    def get_month_labels(self):
        return MONTH_LABELS

    # ── File dialogs ──────────────────────────────────────────────────────────

    def browse_file(self):
        result = self._window.create_file_dialog(
            webview.FileDialog.OPEN,
            file_types=("Excel Files (*.xlsx;*.xlsm)", "All Files (*.*)"),
        )
        return result[0] if result else None

    def browse_save_file(self):
        result = self._window.create_file_dialog(
            webview.FileDialog.SAVE,
            save_filename="kuper_vs_promo.xlsx",
            file_types=("Excel Files (*.xlsx)",),
        )
        return result if result else None

    def browse_folder(self):
        result = self._window.create_file_dialog(webview.FileDialog.FOLDER)
        return result[0] if result else None

    # ── Utilities ─────────────────────────────────────────────────────────────

    def open_folder(self, path):
        if path and os.path.isdir(path):
            try:
                os.startfile(path)
            except Exception as e:
                self._emit("toast", {"type": "error", "message": str(e)})
        return True

    def open_file(self, path):
        if path and os.path.isfile(path):
            try:
                os.startfile(path)
            except Exception as e:
                self._emit("toast", {"type": "error", "message": str(e)})
        return True

    def stop(self):
        self._stop_event.set()
        self._emit("toast", {"type": "warning", "message": "Операция остановлена"})
        self._emit("set_title", "")
        return True

    def clear_downloads(self):
        threading.Thread(
            target=clear_download_folder, args=(self._log, self._mb), daemon=True
        ).start()
        return True

    def clear_output(self, path):
        threading.Thread(
            target=clear_output_folder,
            args=(_SV(path), self._log, self._mb),
            daemon=True,
        ).start()
        return True

    def open_last_competitors_file(self):
        if self._last_competitors_file:
            self.open_file(self._last_competitors_file)
        else:
            self._emit(
                "toast", {"type": "warning", "message": "Последний файл не найден"}
            )
        return True

    def get_csv_count(self, folder):
        if folder and os.path.isdir(folder):
            return len(list(Path(folder).glob("*.csv")))
        return 0

    # ── Download ──────────────────────────────────────────────────────────────

    def start_download(self, p):
        self._stop_event.clear()

        def _w():
            download_files_thread(
                _SV(p.get("month_from", "")),
                _SV(p.get("year_from",  "")),
                _SV(p.get("month_to",   "")),
                _SV(p.get("year_to",    "")),
                self._log,
                self._mb,
                progress_callback=self._progress,
                set_title=self._set_title,
                date_from_str=p.get("date_from") or None,
                date_to_str=p.get("date_to")     or None,
            )
            self._emit("set_title", "")
            self._emit("hide_progress")

        threading.Thread(target=_w, daemon=True).start()
        return True

    # ── Process ───────────────────────────────────────────────────────────────

    def start_process(self, p):
        self._stop_event.clear()

        def _w():
            process_files_thread(
                _SV(p["output_folder"]),
                _SV(p["category"]),
                FILTER_OPTIONS,
                self._log,
                self._mb,
                self._stop_event,
                refresh_power_query_files,
                _SV(p["pq_file1"]),
                _SV(p["pq_file2"]),
                _SV(p["macro1"]),
                _SV(p["macro2"]),
                progress_callback=self._progress,
                set_title=self._set_title,
            )
            self._emit("set_title", "")
            self._emit("hide_progress")

        threading.Thread(target=_w, daemon=True).start()
        return True

    # ── Stages ────────────────────────────────────────────────────────────────

    def run_stage_q1(self, p):
        self._stop_event.clear()
        threading.Thread(
            target=lambda: (
                run_stage_query1(
                    _SV(p["pq_file1"]), self._log, self._stop_event, self._mb
                ),
                self._emit("set_title", ""),
            ),
            daemon=True,
        ).start()
        return True

    def run_stage_q2(self, p):
        self._stop_event.clear()
        threading.Thread(
            target=lambda: (
                run_stage_query2(
                    _SV(p["pq_file2"]), self._log, self._stop_event, self._mb
                ),
                self._emit("set_title", ""),
            ),
            daemon=True,
        ).start()
        return True

    def run_stage_macros(self, p):
        self._stop_event.clear()
        threading.Thread(
            target=lambda: (
                run_stage_macros(
                    _SV(p["pq_file2"]),
                    _SV(p["macro1"]),
                    _SV(p["macro2"]),
                    self._log,
                    self._stop_event,
                    self._mb,
                ),
                self._emit("set_title", ""),
            ),
            daemon=True,
        ).start()
        return True

    # ── Competitors ───────────────────────────────────────────────────────────

    def run_competitors(self, p):
        self._stop_event.clear()

        def _w():
            def _upd(path):
                self._last_competitors_file = path

            refresh_competitors_pipeline(
                _SV(p["olap_file"]),
                _SV(p["competitors_file"]),
                self._log,
                self._mb,
                self._stop_event,
                on_file_updated=_upd,
            )
            self._emit("set_title", "")

        threading.Thread(target=_w, daemon=True).start()
        return True

    # ── Nielsen ───────────────────────────────────────────────────────────────

    def run_nielsen(self, p):
        self._stop_event.clear()
        threading.Thread(
            target=lambda: (
                process_nielsen(
                    p["input_file"],
                    p["output_dir"],
                    p["format"],
                    self._log,
                    self._mb,
                    self._stop_event,
                    p["category"],
                ),
                self._emit("set_title", ""),
            ),
            daemon=True,
        ).start()
        return True

    # ── Query Refresh ─────────────────────────────────────────────────────────

    def run_query_refresh(self, p):
        self._stop_event.clear()

        def _w():
            from competitors_functions import refresh_file

            ok = refresh_file(
                p["file"], self._log, self._stop_event, timeout_minutes=90
            )
            if ok:
                self._emit(
                    "toast",
                    {
                        "type": "success",
                        "message": f"Обновлено: {os.path.basename(p['file'])}",
                    },
                )
            self._emit("set_title", "")

        threading.Thread(target=_w, daemon=True).start()
        return True

    # ── Production ────────────────────────────────────────────────────────────

    def run_production(self, p):
        self._stop_event.clear()
        threading.Thread(
            target=lambda: (
                run_production(
                    p["svod_folder"],
                    p["npk_file"],
                    p["tolyatti_folder"],
                    p["target_file"],
                    p["mapping_file"],
                    p["month_str"],
                    p["year"],
                    self._log,
                    self._mb,
                    self._stop_event,
                ),
                self._emit("set_title", ""),
            ),
            daemon=True,
        ).start()
        return True

    # ── SKU Matcher ───────────────────────────────────────────────────────────

    def run_sku_matching(self, p):
        def _prog(msg):
            self._emit("sku_log", msg)

        def _done(results, error=None):
            if error:
                self._emit("sku_error", str(error))
            else:
                self._emit("sku_results", results)

        threading.Thread(
            target=run_matching,
            args=(p["ref_path"], p["csv_folder"], float(p["threshold"]), _prog, _done),
            daemon=True,
        ).start()
        return True

    def save_sku_results(self, p):
        try:
            count = save_to_reference(p["results"], p["ref_path"])
            return {"success": True, "count": count}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── Сравнение цен ─────────────────────────────────────────────────────────

    def run_price_comparison(self, p):
        """
        p: {kuper_file, promo_file, sprav_file, output_file, threshold}
        """
        self._stop_event.clear()

        def _w():
            self._emit("set_title", "⏳ Сравнение цен…")
            self._emit("pc_started", None)
            try:
                n = run_price_comparison(
                    path_kuper=p["kuper_file"],
                    path_promodata=p["promo_file"],
                    path_sprav=p["sprav_file"],
                    output_file=p["output_file"],
                    threshold=float(p.get("threshold", 0.5)),
                    log=self._pc_log,
                    stop_event=self._stop_event,
                )
                self._emit("pc_done", {"rows": n, "output": p["output_file"]})
                self._emit(
                    "toast",
                    {
                        "type": "success",
                        "message": f"Готово: {n} строк → {os.path.basename(p['output_file'])}",
                    },
                )
            except Exception as e:
                logging.error(f"price_comparison error: {e}")
                self._emit("pc_error", str(e))
                self._emit("toast", {"type": "error", "message": str(e)})
            finally:
                self._emit("set_title", "")
                self._emit("hide_progress")

        threading.Thread(target=_w, daemon=True).start()
        return True

    def _pc_log(self, msg: str):
        logging.info(msg)
        self._emit("log", str(msg))
        self._emit("pc_log", str(msg))

    def open_pc_result(self, path):
        self.open_file(path)
        return True


    # ── Планировщик промодаты ─────────────────────────────────────────────────

    def _run_scheduled_pipeline(self, cfg, steps, month_from, year_from, month_to, year_to, date_from=None, date_to=None):
        """Выполняется в фоновом потоке планировщика."""
        from promodate_functions import (
            FILTER_OPTIONS, download_files_thread, process_files_thread,
            run_stage_query1, run_stage_query2, run_stage_macros,
        )

        stop_event = threading.Event()
        mb = self._mb

        category      = cfg.get("scheduler_category") or cfg.get("category", "Масло")
        output_folder = cfg.get("output_folder", "")
        pq_file1      = cfg.get("pq_file1", "")
        pq_file2      = cfg.get("pq_file2", "")
        macro1        = cfg.get("macro1", "")
        macro2        = cfg.get("macro2", "")

        self._log(
            f"🕐 Планировщик: промодата {month_from}/{year_from}–{month_to}/{year_to} | {steps}"
        )

        if "download" in steps:
            self._log("📥 [Планировщик] Скачивание файлов FTP...")
            try:
                download_files_thread(
                    _SV(month_from), _SV(year_from),
                    _SV(month_to),   _SV(year_to),
                    self._log, mb,
                    date_from_str=date_from,
                    date_to_str=date_to,
                )
            except Exception as e:
                self._log(f"⚠️ Ошибка скачивания: {e}")

        if "process" in steps:
            self._log("⚙️ [Планировщик] Обработка файлов → CSV...")
            try:
                def _noop(*a, **kw): pass
                process_files_thread(
                    _SV(output_folder), _SV(category), FILTER_OPTIONS,
                    self._log, mb, stop_event,
                    _noop, _SV(pq_file1), _SV(pq_file2), _SV(macro1), _SV(macro2),
                )
            except Exception as e:
                self._log(f"⚠️ Ошибка обработки: {e}")

        if "query1" in steps:
            self._log("🔄 [Планировщик] Query 1...")
            try:
                run_stage_query1(_SV(pq_file1), self._log, stop_event, mb)
            except Exception as e:
                self._log(f"⚠️ Ошибка Query 1: {e}")

        if "query2" in steps:
            self._log("🔄 [Планировщик] Query 2...")
            try:
                run_stage_query2(_SV(pq_file2), self._log, stop_event, mb)
            except Exception as e:
                self._log(f"⚠️ Ошибка Query 2: {e}")

        if "macros" in steps:
            self._log("▶ [Планировщик] Макросы...")
            try:
                run_stage_macros(
                    _SV(pq_file2), _SV(macro1), _SV(macro2),
                    self._log, stop_event, mb,
                )
            except Exception as e:
                self._log(f"⚠️ Ошибка макросов: {e}")

        self._log("✅ Планировщик: пайплайн завершён")

    def get_scheduler_config(self):
        cfg = load_config()
        return {k: cfg.get(k, v) for k, v in SCHEDULER_DEFAULTS.items()}

    def save_scheduler_config(self, data: dict):
        cfg = load_config()
        for k in SCHEDULER_DEFAULTS:
            if k in data:
                cfg[k] = data[k]
        save_config_data(cfg)
        self._scheduler.stop()
        self._scheduler.start()
        return True

    def scheduler_run_now(self, data: dict):
        cfg = load_config()
        steps = data.get("steps") or cfg.get("scheduler_steps", list(SCHEDULER_DEFAULTS["scheduler_steps"]))
        now   = __import__('datetime').datetime.now()
        auto  = data.get("auto_month", True)
        if auto:
            mf = mt = now.month
            yf = yt = now.year
        else:
            mf = int(data.get("month_from") or now.month)
            yf = int(data.get("year_from")  or now.year)
            mt = int(data.get("month_to")   or mf)
            yt = int(data.get("year_to")    or yf)
        # Override category if passed from UI
        cat = data.get("category")
        if cat:
            cfg["scheduler_category"] = cat
        df = data.get("date_from") or None
        dt = data.get("date_to")   or None
        self._scheduler.run_now(cfg, steps=steps, mf=mf, yf=yf, mt=mt, yt=yt, date_from=df, date_to=dt)
        return True

    # ── Windows Task Scheduler интеграция ────────────────────────────────────

    TASK_NAME = "EFKO PromoData Auto"

    def _get_python_exe(self) -> str:
        """Возвращает путь к pythonw.exe рядом с текущим python."""
        import sys, os
        base = os.path.dirname(sys.executable)
        pythonw = os.path.join(base, "pythonw.exe")
        return pythonw if os.path.exists(pythonw) else sys.executable

    def _get_script_path(self) -> str:
        base = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base, "promodate_headless.py")

    def create_windows_task(self, data: dict):
        """
        Создаёт задачу в Windows Task Scheduler через COM API (win32com).
        Не требует прав администратора — работает от имени текущего пользователя.
        """
        try:
            import pythoncom
            import win32com.client as win32
        except ImportError:
            return {"ok": False, "msg": "Требуется pywin32: pip install pywin32"}

        cfg      = load_config()
        time_str = data.get("time", cfg.get("scheduler_time", "08:00"))
        days_raw = data.get("days", cfg.get("scheduler_days", ["mon","tue","wed","thu","fri"]))

        # Карта дней: win32com использует числа 1=Вс,2=Пн,...,7=Сб
        day_num = {"sun":1,"mon":2,"tue":3,"wed":4,"thu":5,"fri":6,"sat":7}
        days_bits = 0
        for d in days_raw:
            if d in day_num:
                days_bits |= (1 << (day_num[d] - 1))  # bitmask
        if days_bits == 0:
            days_bits = 0b0111110  # Пн-Пт по умолчанию

        python_exe  = self._get_python_exe()
        script_path = self._get_script_path()

        hh, mm = map(int, time_str.split(":"))

        try:
            pythoncom.CoInitialize()
            svc = win32.Dispatch("Schedule.Service")
            svc.Connect()

            folder = svc.GetFolder("\\")

            # Удаляем старую задачу если существует
            try:
                folder.DeleteTask(self.TASK_NAME, 0)
            except Exception:
                pass

            # Создаём определение задачи
            td = svc.NewTask(0)
            td.RegistrationInfo.Description = "EFKO FlowManager — автозапуск промодаты"
            td.Settings.Enabled             = True
            td.Settings.StopIfGoingOnBatteries = False
            td.Settings.DisallowStartIfOnBatteries = False
            td.Settings.ExecutionTimeLimit  = "PT4H"  # макс 4 часа
            td.Settings.StartWhenAvailable  = True    # запустить если пропущен

            # Триггер: еженедельный
            trigger = td.Triggers.Create(3)   # TASK_TRIGGER_WEEKLY = 3
            # Время старта: сегодня в нужный час
            now = datetime.now()
            start_str = now.strftime(f"%Y-%m-%dT{hh:02d}:{mm:02d}:00")
            trigger.StartBoundary    = start_str
            trigger.Enabled          = True
            trigger.DaysOfWeek       = days_bits
            trigger.WeeksInterval    = 1

            # Действие: запуск python-скрипта
            action = td.Actions.Create(0)     # TASK_ACTION_EXEC = 0
            action.Path              = python_exe
            action.Arguments         = f'"{script_path}"'
            action.WorkingDirectory  = os.path.dirname(script_path)

            # Регистрируем задачу (TASK_CREATE_OR_UPDATE = 6, TASK_LOGON_INTERACTIVE_TOKEN = 3)
            folder.RegisterTaskDefinition(
                self.TASK_NAME,
                td,
                6,    # TASK_CREATE_OR_UPDATE
                "",   # пользователь — текущий
                "",   # пароль — не нужен
                3,    # TASK_LOGON_INTERACTIVE_TOKEN (только когда залогинен)
                ""
            )

            cfg["scheduler_win_task"] = True
            cfg["scheduler_time"]     = time_str
            cfg["scheduler_days"]     = days_raw
            save_config_data(cfg)
            logging.info(f"Windows Task создана через COM: {self.TASK_NAME}")
            self._emit("toast", {"type": "success", "message": "Задача создана в Планировщике Windows ✅"})
            return {"ok": True, "msg": ""}

        except Exception as e:
            msg = str(e)
            logging.error(f"create_windows_task COM error: {msg}")
            # Fallback: попробуем через schtasks без /rl HIGHEST
            return self._create_task_schtasks_fallback(data, cfg, time_str, days_raw)
        finally:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass

    def _create_task_schtasks_fallback(self, data, cfg, time_str, days_raw):
        """Запасной вариант через schtasks (без /rl HIGHEST)."""
        import subprocess
        days_map = {"mon":"MON","tue":"TUE","wed":"WED","thu":"THU","fri":"FRI","sat":"SAT","sun":"SUN"}
        days_str = ",".join(days_map[d] for d in days_raw if d in days_map) or "MON"
        python_exe  = self._get_python_exe()
        script_path = self._get_script_path()

        subprocess.run(["schtasks","/delete","/tn",self.TASK_NAME,"/f"], capture_output=True)

        cmd = [
            "schtasks", "/create",
            "/tn", self.TASK_NAME,
            "/tr", f'"{python_exe}" "{script_path}"',
            "/sc", "WEEKLY",
            "/d", days_str,
            "/st", time_str,
            "/f",
            # Без /rl HIGHEST — не требует прав администратора
        ]
        result = subprocess.run(cmd, capture_output=True)
        stdout = (result.stdout or b"").decode("cp866", errors="replace")
        stderr = (result.stderr or b"").decode("cp866", errors="replace")
        ok  = result.returncode == 0
        msg = stdout.strip() or stderr.strip()

        if ok:
            cfg["scheduler_win_task"] = True
            save_config_data(cfg)
            self._emit("toast", {"type": "success", "message": "Задача создана в Планировщике Windows ✅"})
        else:
            self._emit("toast", {"type": "error", "message": f"Ошибка: {msg}"})
            logging.error(f"schtasks fallback error: {msg}")
        return {"ok": ok, "msg": msg}

    def delete_windows_task(self):
        """Удаляет задачу из Windows Task Scheduler (COM API + schtasks fallback)."""
        ok = False
        try:
            import pythoncom, win32com.client as win32
            pythoncom.CoInitialize()
            svc = win32.Dispatch("Schedule.Service")
            svc.Connect()
            svc.GetFolder("\\").DeleteTask(self.TASK_NAME, 0)
            ok = True
        except Exception:
            # Fallback через schtasks
            import subprocess
            r = subprocess.run(["schtasks","/delete","/tn",self.TASK_NAME,"/f"], capture_output=True)
            ok = r.returncode == 0
        finally:
            try: pythoncom.CoUninitialize()
            except Exception: pass

        cfg = load_config()
        cfg["scheduler_win_task"] = False
        save_config_data(cfg)
        if ok:
            self._emit("toast", {"type": "success", "message": "Задача удалена из Планировщика Windows"})
        return {"ok": ok}

    def get_windows_task_status(self):
        """Проверяет статус задачи в Windows Task Scheduler."""
        import subprocess
        result = subprocess.run(
            ["schtasks", "/query", "/tn", self.TASK_NAME, "/fo", "LIST"],
            capture_output=True
        )
        if result.returncode != 0:
            return {"exists": False}

        out   = (result.stdout or b"").decode("cp866", errors="replace")
        lines = {
            line.split(":")[0].strip(): ":".join(line.split(":")[1:]).strip()
            for line in out.splitlines() if ":" in line
        }
        # Ключи могут быть на русском (русский Windows) или английском
        status_key  = next((k for k in lines if "Стат" in k or "Status" in k), None)
        next_key    = next((k for k in lines if "Следующ" in k or "Next Run" in k), None)
        last_key    = next((k for k in lines if "Последн" in k or "Last Run" in k), None)

        return {
            "exists":   True,
            "status":   lines.get(status_key, ""),
            "next_run": lines.get(next_key, ""),
            "last_run": lines.get(last_key, ""),
            "raw":      out[:400],
        }

    def run_windows_task_now(self):
        """Запускает задачу немедленно через schtasks /run."""
        import subprocess
        result = subprocess.run(
            ["schtasks", "/run", "/tn", self.TASK_NAME],
            capture_output=True
        )
        ok = result.returncode == 0
        if ok:
            self._emit("toast", {"type": "success", "message": "Задача запущена через Планировщик Windows"})
        return {"ok": ok}

    def export_ics(self, data: dict):
        """Создаёт .ics файл для импорта в Календарь Windows."""
        import uuid
        from datetime import timedelta

        cfg      = load_config()
        time_str = data.get("time", cfg.get("scheduler_time", "08:00"))
        days_raw = data.get("days", cfg.get("scheduler_days", ["mon","tue","wed","thu","fri"]))
        hh, mm   = map(int, time_str.split(":"))

        # BYDAY для RRULE
        day_ical = {
            "mon": "MO", "tue": "TU", "wed": "WE",
            "thu": "TH", "fri": "FR", "sat": "SA", "sun": "SU",
        }
        byday = ",".join(day_ical[d] for d in days_raw if d in day_ical) or "MO"

        now = datetime.now()
        dtstart = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        dtend   = dtstart + timedelta(hours=2)

        uid  = str(uuid.uuid4())
        fmt  = "%Y%m%dT%H%M%S"

        ics = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//EFKO FlowManager//PromoData Scheduler//RU
BEGIN:VEVENT
UID:{uid}
SUMMARY:EFKO PromoData — Автообновление
DESCRIPTION:Автоматический запуск промодаты через FlowManager
DTSTART:{dtstart.strftime(fmt)}
DTEND:{dtend.strftime(fmt)}
RRULE:FREQ=WEEKLY;BYDAY={byday}
STATUS:CONFIRMED
END:VEVENT
END:VCALENDAR"""

        save_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "promodata_schedule.ics")
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(ics)

        try:
            os.startfile(save_path)  # Откроет в Календаре Windows
        except Exception as e:
            logging.error(f"Ошибка открытия ics: {e}")

        return {"ok": True, "path": save_path}


# ── Entry point ───────────────────────────────────────────────────────────────

setup_logger()
_splash_set(96, "Запуск интерфейса…")
api = Api()

html_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "web", "index.html"
)

window = webview.create_window(
    "EFKO FlowManager",
    html_path,
    js_api=api,
    width=1480,
    height=960,
    min_size=(1000, 700),
    background_color="#F5F5F7",
    easy_drag=False,
)
api._window = window


def _bring_to_front():
    import ctypes

    try:
        hwnd = ctypes.windll.user32.FindWindowW(None, "EFKO FlowManager")
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 9)
            ctypes.windll.user32.SetForegroundWindow(hwnd)
    except Exception:
        pass


threading.Thread(target=_bring_to_front, daemon=True).start()

_splash_set(100, "Готово!")
_splash_close()

webview.start(debug=False)