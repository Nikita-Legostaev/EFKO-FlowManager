"""
api_core.py — базовый миксин API:
  __init__, push-события, конфиг, файловые диалоги, утилиты, стоп/очистка.
"""

import os
import json
import logging
import threading
import webview  # pyright: ignore[reportMissingImports]
from pathlib import Path

from app_config import load_config, save_config_data, _SV, _MB
from promodate_functions import FILTER_OPTIONS
from production_functions import MONTH_LABELS
from scheduler_functions import PromodateScheduler
from promodate_functions import clear_download_folder, clear_output_folder


class ApiCoreMixin:

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
