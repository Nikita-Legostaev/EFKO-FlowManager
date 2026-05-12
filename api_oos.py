"""
api_oos.py — миксин: отчёт без OOS (Слобода / Провансаль / Оливковый).
"""

import logging
import threading
from pathlib import Path
from oos_functions import run_oos_report as _run_oos_report


class ApiOosMixin:

    def run_oos_all(self, p):
        """
        p: {kub_file, elt_file, tasks: [{report_type, report_file}, ...]}
        Запускает все задачи последовательно в одном потоке.
        """
        self._stop_event.clear()

        def _w():
            self._emit("set_title", "⏳ Отчёт без OOS…")
            tasks = p.get("tasks", [])
            last_file = ""
            for i, task in enumerate(tasks, 1):
                if self._stop_event.is_set():
                    self._emit("toast", {"type": "warning", "message": "Остановлено"})
                    break
                rt = task["report_type"]
                rf = task["report_file"]
                self._log(f"📋 [{i}/{len(tasks)}] {rt} → {rf}")
                try:
                    _run_oos_report(
                        report_type=rt,
                        kub_file=p["kub_file"],
                        elt_file=p["elt_file"],
                        report_file=rf,
                        log=self._log,
                        stop_event=self._stop_event,
                    )
                    last_file = rf
                    self._emit(
                        "toast", {"type": "success", "message": f"✅ {rt} готов"}
                    )
                except Exception as e:
                    logging.error(f"OOS [{rt}] error: {e}")
                    self._emit("toast", {"type": "error", "message": f"❌ {rt}: {e}"})
            if last_file:
                self._emit("oos_done", {"report_file": last_file})
            self._emit("set_title", "")
            self._emit("hide_progress")

        threading.Thread(target=_w, daemon=True).start()
        return True

    def open_oos_folder(self, path):
        folder = str(Path(path).parent) if path else ""
        return self.open_folder(folder)
