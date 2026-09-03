"""
api/oos.py — миксин: отчёт без OOS (Слобода / Провансаль / Оливковый).
"""

import logging
from pathlib import Path
# services.oos импортируется лениво, внутри рабочего потока:
# его загрузка занимает ~5 секунд и раньше происходила при каждом старте


class ApiOosMixin:

    def run_oos_all(self, p):
        """
        p: {kub_file, elt_file, tasks: [{report_type, report_file}, ...]}
        Запускает все задачи последовательно в одном потоке.
        """
        def _w():
            from services.oos import run_oos_report as _run_oos_report
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

        self._run_bg("⏳ Отчёт без OOS…", _w, name="Отчёт без OOS")
        return True

    def open_oos_folder(self, path):
        folder = str(Path(path).parent) if path else ""
        return self.open_folder(folder)

    def scan_ketchup_folder(self, folder, report_2026=None, report_2024_2026=None):
        """Возвращает список имён xlsx-файлов кубов в папке — для предпросмотра на фронте.
        Файлы, уже выбранные как отчёты (report_2026/report_2024_2026), в список кубов не входят.
        """
        from services.oos_ketchup import find_ketchup_files
        if not folder:
            return []
        return [
            p.name
            for p in find_ketchup_files(folder, exclude=(report_2026, report_2024_2026))
        ]

    def run_oos_ketchup(self, p):
        """
        p: {kub_folder, report_2026, report_2024_2026, need_2026}
        Обновляет отчёты кетчупа последовательно через query: кубы → 2026 → 2024-2026.
        """
        def _w():
            from services.oos_ketchup import run_ketchup_report

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

        self._run_bg("⏳ Отчёт без OOS (Кетчуп)…", _w, name="Отчёт без OOS (Кетчуп)")
        return True
