"""
api_production.py — миксин: производство и SKU-матчер.
"""

import threading
from production_functions import run_production
from sku_matcher_functions import run_matching, save_to_reference


class ApiProductionMixin:

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

    def run_sku_matching(self, p):
        def _prog(msg):
            self._emit("sku_log", msg)

        def _done(results, error=None, all_new_skus=None):
            if error:
                self._emit("sku_error", str(error))
            else:
                self._emit("sku_results", results)
                if all_new_skus is not None:
                    self._emit("sku_all_new", all_new_skus)

        threading.Thread(
            target=run_matching,
            args=(p["ref_path"], p["csv_folder"], float(p["threshold"]), _prog, _done),
            kwargs={"mode": p.get("mode", "ml")},
            daemon=True,
        ).start()
        return True

    def save_sku_results(self, p):
        try:
            count = save_to_reference(p["results"], p["ref_path"])
            return {"success": True, "count": count}
        except Exception as e:
            return {"success": False, "error": str(e)}