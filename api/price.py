"""
api/price.py — миксин: сравнение цен Купер vs PromoData.
"""

import logging
import os
# services.price_comparison импортируется лениво, внутри рабочего потока:
# его загрузка занимает ~19 секунд и раньше происходила при каждом старте


class ApiPriceMixin:

    def run_price_comparison(self, p):
        def _w():
            from services.price_comparison import run_comparison as run_price_comparison
            self._emit("pc_started", None)
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
            self._emit("toast", {
                "type": "success",
                "message": f"Готово: {n} строк → {os.path.basename(p['output_file'])}",
            })

        # pc_error нужен фронту, чтобы разблокировать вкладку сравнения цен
        self._run_bg(
            "⏳ Сравнение цен…", _w,
            name="Сравнение цен",
            on_error=lambda e: self._emit("pc_error", str(e)),
        )
        return True

    def _pc_log(self, msg: str):
        logging.info(msg)
        self._emit("log", str(msg))
        self._emit("pc_log", str(msg))

    def open_pc_result(self, path):
        self.open_file(path)
        return True
