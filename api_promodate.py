"""
api_promodate.py — миксин промодаты: скачивание, обработка, стадии.
"""

import threading
from app_config import _SV
from promodate_functions import (
    FILTER_OPTIONS,
    download_files_thread,
    process_files_thread,
    refresh_power_query_files,
    run_stage_query1,
    run_stage_query2,
    run_stage_macros,
)


class ApiPromodateMixin:

    def start_download(self, p):
        self._stop_event.clear()

        def _w():
            download_files_thread(
                _SV(p.get("month_from", "")),
                _SV(p.get("year_from", "")),
                _SV(p.get("month_to", "")),
                _SV(p.get("year_to", "")),
                self._log,
                self._mb,
                progress_callback=self._progress,
                set_title=self._set_title,
                date_from_str=p.get("date_from") or None,
                date_to_str=p.get("date_to") or None,
            )
            self._emit("set_title", "")
            self._emit("hide_progress")

        threading.Thread(target=_w, daemon=True).start()
        return True

    def start_process(self, p):
        self._stop_event.clear()

        def _noop(*args, **kwargs):
            pass

        def _w():
            process_files_thread(
                _SV(p["output_folder"]),
                _SV(p["category"]),
                FILTER_OPTIONS,
                self._log,
                self._mb,
                self._stop_event,
                _noop,
                _SV(p["pq_file1"]),
                _SV(p["pq_file2"]),
                _SV(p["macro1"]),
                _SV(p["macro2"]),
                progress_callback=self._progress,
                set_title=self._set_title,
            )
            if self._stop_event.is_set():
                self._emit("set_title", "")
                self._emit("hide_progress")
                return

            refresh_power_query_files(
                _SV(p["pq_file1"]),
                _SV(p["pq_file2"]),
                _SV(p["macro1"]),
                _SV(p["macro2"]),
                self._log,
                self._stop_event,
            )
            self._emit("set_title", "")
            self._emit("hide_progress")

        threading.Thread(target=_w, daemon=True).start()
        return True

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
