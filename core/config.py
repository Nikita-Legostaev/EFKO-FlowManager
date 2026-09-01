"""
core/config.py — конфиг и вспомогательные классы.
Импортируется всеми api/*.py и app/*.py.
"""

import os
import json
import logging
from datetime import datetime

from services.production import MONTH_LABELS
from services.scheduler import SCHEDULER_DEFAULTS
from core.paths import _resource

CONFIG_FILE = _resource("config.json")


# ── Конфиг ────────────────────────────────────────────────────────────────────


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
        "nielsen_input2": "",
        "nielsen_output2": "",
        "nielsen_sprav_path": "",
        "nielsen_pq_file": "",
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
        "pc_kuper_file": "",
        "pc_promo_file": "",
        "pc_sprav_file": "",
        "pc_output_file": "",
        "pc_threshold": 0.5,
        # ── Отчёт без OOS ──
        "oos_category": "Майонез",
        "oos_kub_file": "",
        "oos_elt_file": "",
        "oos_report_sloboda": "",
        "oos_report_provansale": "",
        "oos_report_olive": "",
        "oos_ketchup_folder": "",
        "oos_ketchup_report_2026": "",
        "oos_ketchup_report_2024_2026": "",
        "oos_ketchup_need_2026": "1",
        # ── Дистрибуция конкурентов / Доли рынка ──
        "dist_competitors_file": "",
        "market_share_territory_file": "",
        "msb_file1": "",
        "msb_file2": "",
        "msb_file3": "",
        "dark_theme": False,
        "sku_ref_path": "",
        "sku_csv_folder": "",
        "dl_mode": "range",
        # ── Режимы промодаты ──
        # На каждый режим — своя папка сохранения CSV и свои файлы/макросы
        # Power Query, чтобы «Мониторинг цен» не путался с «ЦО» и т.п.
        "promodata_mode": "co",
        "promodata_mode_settings": {
            "co": {
                "output_folder": "", "pq_file1": "", "pq_file2": "",
                "macro1": "ExtendDatesAndFormulas", "macro2": "ExtendDatesAndFormulas_MNZ",
            },
            "monitoring": {
                "output_folder": "", "pq_file1": "", "pq_file2": "",
                "macro1": "ExtendDatesAndFormulas", "macro2": "ExtendDatesAndFormulas_MNZ",
            },
            "extra": {
                "output_folder": "", "pq_file1": "", "pq_file2": "",
                "macro1": "ExtendDatesAndFormulas", "macro2": "ExtendDatesAndFormulas_MNZ",
            },
        },
        # ── Парсинг ЖДСК ──
        "parsing_output": "",   # папка для Excel по сетям
        "parsing_keys": {},     # {ИМЯ_ПЕРЕМЕННОЙ: API-ключ}
        "dates_list": "",
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
    """
    Сохраняет настройки, дополняя уже записанные, а не заменяя их целиком.

    Раньше сюда приходил словарь с главного экрана и затирал разделы,
    которых в нём не было, — например, настройки вкладки парсинга.
    """
    try:
        current = {}
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    current = json.load(f)
                if not isinstance(current, dict):
                    current = {}
            except Exception as e:
                logging.warning(f"Config read before save: {e}")

        current.update(data or {})

        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Config save error: {e}")


# ── Вспомогательные классы ────────────────────────────────────────────────────


class _SV:
    """Обёртка строкового значения с методом .get() — для совместимости."""

    def __init__(self, v):
        self._v = v

    def get(self):
        return str(self._v) if self._v is not None else ""


class _MB:
    """Заглушка messagebox — транслирует в JS-тосты."""

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
            import json as _json

            return bool(
                self._api._window.evaluate_js(f"confirm({_json.dumps(str(msg))})")
            )
        except Exception:
            return False

    def askokcancel(self, title, msg):
        return self.askyesno(title, msg)
