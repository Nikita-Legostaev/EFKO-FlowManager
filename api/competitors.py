"""
api/competitors.py — миксин: конкуренты, Nielsen, обновление квери.
"""

import os

from core.config import _SV
from services.competitors import refresh_competitors_pipeline
from services.nielsen import process_nielsen


class ApiCompetitorsMixin:

    def run_competitors(self, p):
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

        self._run_bg("⏳ Конкуренты…", _w, name="Конкуренты")
        return True

    def run_nielsen(self, p):
        def _w():
            process_nielsen(
                p["input_file"],
                p["output_dir"],
                p["format"],
                self._log,
                self._mb,
                self._stop_event,
                p["category"],
                sprav_path=p.get("sprav_path") or None,
                input_file2=p.get("input_file2") or None,
                output_dir2=p.get("output_dir2") or None,
                pq_file=p.get("pq_file") or None,
                pq_file_nu=p.get("pq_file_nu") or None,
                arch_input=p.get("arch_input") or None,
                arch_input2=p.get("arch_input2") or None,
                arch_enabled=p.get("arch_enabled", False),
            )

        self._run_bg("⏳ Nielsen…", _w, name="Nielsen")
        return True

    def run_query_refresh(self, p):
        """
        p: {file, page?} — page (необязательно) пробрасывается обратно в
        событие query_refresh_done, чтобы фронт знал, для какой вкладки
        показывать кнопку «Открыть файл».
        """
        def _w():
            from services.competitors import refresh_file

            ok = refresh_file(
                p["file"], self._log, self._stop_event, timeout_minutes=90
            )
            if ok:
                self._emit("toast", {
                    "type": "success",
                    "message": f"Обновлено: {os.path.basename(p['file'])}",
                })
                self._emit(
                    "query_refresh_done", {"file": p["file"], "page": p.get("page", "")}
                )
            elif not self._stop_event.is_set():
                self._emit("toast", {
                    "type": "error",
                    "message": f"Не удалось обновить: {os.path.basename(p['file'])}",
                })

        self._run_bg("⏳ Обновление квери…", _w, name="Обновить квери")
        return True

    def run_market_share_brands(self, p):
        """
        p: {file1, file2, file3}
        Отчёт по динамике долей рынка брендов Компании: сначала обновляются
        через query файл1 и файл2, затем (после них) — файл3.
        """
        def _w():
            from services.competitors import refresh_files_sequential

            files = [p["file1"], p["file2"], p["file3"]]

            self._log("📋 Шаг 1/2: обновляем исходные файлы (1, 2)...")
            ok = refresh_files_sequential(files[:2], self._log, self._stop_event)

            if ok:
                self._log("📋 Шаг 2/2: обновляем итоговый файл (3)...")
                ok = refresh_files_sequential(files[2:], self._log, self._stop_event)

            if ok:
                self._emit("toast", {
                    "type": "success", "message": "✅ Доли рынка брендов обновлены",
                })
                self._emit("market_share_brands_done", {"file": files[2]})
            elif self._stop_event.is_set():
                self._emit("toast", {"type": "warning", "message": "Остановлено"})
            else:
                self._emit("toast", {
                    "type": "error", "message": "❌ Не удалось обновить все файлы",
                })

        self._run_bg("⏳ Доли рынка брендов…", _w, name="Доли рынка брендов")
        return True
