"""
api/core.py — базовый миксин API:
  __init__, push-события, конфиг, файловые диалоги, утилиты, стоп/очистка.
"""

import os
import json
import logging
import threading
import webview  # pyright: ignore[reportMissingImports]
from pathlib import Path

from core.config import load_config, save_config_data, _SV, _MB
from services.promodate import FILTER_OPTIONS
from services.production import MONTH_LABELS
from services.scheduler import PromodateScheduler
from services.promodate import clear_download_folder, clear_output_folder


class ApiCoreMixin:

    def __init__(self):
        self._window = None
        self._stop_event = threading.Event()
        self._mb = _MB(self)
        self._last_competitors_file = None
        # Одна операция за раз: почти все они гоняют Excel через COM, а
        # _stop_event один на всех — параллельный запуск ломал и то, и
        # другое (см. _run_bg).
        self._busy_lock = threading.Lock()
        self._busy_name = ""
        self._scheduler = PromodateScheduler(
            get_config_fn=load_config,
            save_config_fn=save_config_data,
            run_pipeline_fn=self._run_scheduled_pipeline,
            emit_fn=self._emit,
        )
        self._scheduler.start()

    # ── Фоновые операции ─────────────────────────────────────────────────────

    def _run_bg(self, title, work, *, name="", on_error=None):
        """
        Запускает work() в фоновом потоке — единообразно для всех вкладок.

        Раньше каждый run_*-метод писал это руками, и у девяти из них не
        было try/except вокруг работы. Любое исключение (недоступная
        сетевая папка, занятый Excel, обрыв FTP) убивало поток молча:
        событий «done»/«hide_progress» не приходило, заголовок оставался
        «⏳ …», прогресс-бар крутился вечно — со стороны выглядело как
        зависшее приложение, хотя ошибка просто некуда было показать.

        Здесь это закрыто раз и навсегда:
          • ошибка → запись в лог с трассировкой, тост и строка в логе
            интерфейса, а не тишина;
          • finally → заголовок и прогресс сбрасываются всегда, чем бы
            операция ни закончилась;
          • блокировка занятости → вторая операция не стартует поверх
            первой. Это не только про COM: _stop_event общий, и старый
            код в начале каждого запуска делал _stop_event.clear() —
            то есть запуск второй операции незаметно отменял «Стоп»,
            нажатый для первой.

        title — текст в шапке на время работы ("" — не трогать).
        work  — функция без аргументов, сама операция.
        name  — имя для сообщения «уже выполняется».
        """
        if not self._busy_lock.acquire(blocking=False):
            self._emit("toast", {
                "type": "warning",
                "message": f"Уже выполняется: {self._busy_name} — дождитесь завершения",
            })
            return False

        self._busy_name = name or title or "операция"
        self._stop_event.clear()
        if title:
            self._emit("set_title", title)

        def _worker():
            try:
                work()
            except InterruptedError:
                self._emit("toast", {"type": "warning", "message": "Остановлено"})
            except Exception as e:
                logging.exception(f"[{self._busy_name}] ошибка")
                self._log(f"❌ Ошибка: {e}")
                if on_error is not None:
                    try:
                        on_error(e)
                    except Exception:
                        logging.exception("on_error")
                self._emit("toast", {"type": "error", "message": f"Ошибка: {e}"})
            finally:
                self._emit("set_title", "")
                self._emit("hide_progress")
                self._emit("done")
                self._busy_name = ""
                self._busy_lock.release()

        threading.Thread(target=_worker, daemon=True).start()
        return True

    # ── Push events ──────────────────────────────────────────────────────────

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

    # ── Конфиг ───────────────────────────────────────────────────────────────

    def js_error(self, msg: str):
        """Логирует JS ошибки из браузера."""
        import logging
        logging.getLogger("flowmanager").error(f"[JS] {msg}")
        return True

    def get_config(self):
        return load_config()

    def save_config(self, data):
        save_config_data(data)
        return True

    def get_filter_options(self):
        return list(FILTER_OPTIONS.keys())

    def get_month_labels(self):
        return MONTH_LABELS

    # ── Файловые диалоги ─────────────────────────────────────────────────────

    def browse_file(self, initial_dir: str = ""):
        start = initial_dir if initial_dir and os.path.isdir(initial_dir) else os.path.expanduser("~")
        result = self._window.create_file_dialog(
            webview.FileDialog.OPEN,
            directory=start,
            file_types=("Excel Files (*.xlsx;*.xlsm)", "All Files (*.*)"),
        )
        return result[0] if result else None

    def browse_any_file(self, initial_dir: str = ""):
        """Диалог без фильтра — показывает все файлы."""
        start = initial_dir if initial_dir and os.path.isdir(initial_dir) else os.path.expanduser("~")
        result = self._window.create_file_dialog(
            webview.FileDialog.OPEN,
            directory=start,
            file_types=("All Files (*.*)", "Excel Files (*.xlsx;*.xlsm)"),
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

    # ── Утилиты ──────────────────────────────────────────────────────────────

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
        from services.promodate import download_folder_for_mode
        mode = load_config().get("promodata_mode", "co")
        threading.Thread(
            target=clear_download_folder,
            args=(self._log, self._mb, download_folder_for_mode(mode)),
            daemon=True,
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
    
    def get_networks(self):
        """Возвращает список уникальных сетей из файлов в папке скачивания текущего режима."""
        from services.promodate import get_available_networks, download_folder_for_mode
        try:
            mode = load_config().get("promodata_mode", "co")
            return get_available_networks(download_folder_for_mode(mode))
        except Exception as e:
            self._log(f"⚠ get_networks: {e}")
            return []