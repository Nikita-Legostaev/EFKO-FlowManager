"""
app_config.py — конфиг, логирование и вспомогательные классы.
Импортируется всеми api_*.py и app.py.
"""
import os
import json
import logging
import sys as _sys
from datetime import datetime
from production_functions import MONTH_LABELS
from scheduler_functions import SCHEDULER_DEFAULTS


# ── Пути ─────────────────────────────────────────────────────────────────────

def _resource(rel_path: str) -> str:
    """Абсолютный путь к ресурсу — корректно и в EXE, и из исходников."""
    if getattr(_sys, "frozen", False):
        base = os.path.dirname(_sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, rel_path)


CONFIG_FILE = _resource("config.json")


# ── Логирование ───────────────────────────────────────────────────────────────

def setup_logger():
    if getattr(_sys, "frozen", False):
        base = os.path.dirname(_sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    log_path = os.path.join(base, "flowmanager.log")

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)
    logging.info(f"Лог: {log_path}")


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
        "dark_theme": False,
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
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
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
