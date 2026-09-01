"""
api/oos.py — миксин: отчёт без OOS (Слобода / Провансаль / Оливковый).
"""

import logging
import threading
from pathlib import Path
# services.oos импортируется лениво, внутри рабочего потока:
# его загрузка занимает ~5 секунд и раньше происходила при каждом старте


class ApiOosMixin:

    def run_oos_all(self, p):
        """
        p: {kub_file, elt_file, tasks: [{report_type, report_file}, ...]}
        Запускает все задачи последовательно в одном потоке.
        """
        self._stop_event.clear()

        def _w():
            from services.oos import run_oos_report as _run_oos_report
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

    def scan_ketchup_folder(self, folder):
        """Возвращает {роль: имя_файла|None} для предпросмотра на фронте."""
        from services.oos_ketchup import find_ketchup_files, _ROLE_LABELS
        if not folder:
            return {}
        found = find_ketchup_files(folder)
        return {_ROLE_LABELS[role]: (p.name if p else None) for role, p in found.items()}

    def run_oos_ketchup(self, p):
        """
        p: {kub_folder, report_2026, report_2024_2026, need_2026}
        Обновляет отчёты кетчупа последовательно через query: кубы → 2026 → 2024-2026.
        """
        self._stop_event.clear()

        def _w():
            from services.oos_ketchup import run_ketchup_report
            self._emit("set_title", "⏳ Отчёт без OOS (Кетчуп)…")
            try:
                run_ketchup_report(
                    kub_folder=p["kub_folder"],
                    report_2026_file=p.get("report_2026", ""),
                    report_2024_2026_file=p.get("report_2024_2026", ""),
                    need_2026=bool(p.get("need_2026", True)),
                    log=self._log,
                    stop_event=self._stop_event,
                )
                last_file = p.get("report_2024_2026") or p.get("report_2026") or ""
                self._emit("toast", {"type": "success", "message": "✅ Кетчуп: отчёты обновлены"})
                if last_file:
                    self._emit("oos_done", {"report_file": last_file})
            except InterruptedError:
                self._emit("toast", {"type": "warning", "message": "Остановлено"})
            except Exception as e:
                logging.error(f"OOS ketchup error: {e}")
                self._emit("toast", {"type": "error", "message": f"❌ Кетчуп: {e}"})
            self._emit("set_title", "")
            self._emit("hide_progress")

        threading.Thread(target=_w, daemon=True).start()
        return True
