"""
EFKO FlowManager — pywebview backend
pip install pywebview
"""

# ═══════════════════════════════════════════════════════════════════════════
# СПЛЭШ — САМЫЕ ПЕРВЫЕ СТРОКИ, до любых импортов
# tkinter встроен в Python, поэтому грузится мгновенно
# ═══════════════════════════════════════════════════════════════════════════
import tkinter as tk

def _make_splash():
    W, H = 400, 240
    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")
    root.configure(bg="#1e8c42")

    c = tk.Canvas(root, width=W, height=H, bg="#1e8c42", highlightthickness=0)
    c.pack(fill="both", expand=True)

    # Градиент
    for i in range(48):
        t = i / 48
        r = int(0x18 + (0x30 - 0x18) * t)
        g = int(0x8c + (0xc7 - 0x8c) * t)
        b = int(0x3a + (0x55 - 0x3a) * t)
        y0, y1 = int(H * i / 48), int(H * (i+1) / 48) + 1
        c.create_rectangle(0, y0, W, y1, fill=f"#{r:02x}{g:02x}{b:02x}", outline="")

    # Иконка
    cx, cy = W // 2, 72
    c.create_oval(cx-28, cy-28, cx+28, cy+28, fill="#2aaa52", outline="#aaffbb", width=1)
    c.create_line(cx-13, cy+2, cx-3, cy+12, cx+14, cy-9,
                  fill="white", width=3, capstyle="round", joinstyle="round")

    # Название
    c.create_text(W//2 - 1, 124, text="Flow",    font=("Segoe UI", 26, "bold"), fill="#ffffff",  anchor="e")
    c.create_text(W//2 - 1, 124, text="Manager", font=("Segoe UI", 26),         fill="#aaeebb", anchor="w")
    c.create_text(W//2,     150, text="EFKO  ·  v3.0", font=("Segoe UI", 9),    fill="#88ccaa")

    # Прогресс
    bx1, by1, bx2, by2 = 50, 178, W - 50, 183
    c.create_rectangle(bx1, by1, bx2, by2, fill="#2aaa52", outline="")
    bar  = c.create_rectangle(bx1, by1, bx1, by2, fill="white", outline="")
    hint = c.create_text(W//2, 200, text="Запуск…", font=("Segoe UI", 9), fill="#88ccaa")

    root.lift()
    root.focus_force()
    root.update()

    def set_progress(pct, text=""):
        try:
            w = (bx2 - bx1) * min(pct, 100) / 100
            c.coords(bar, bx1, by1, bx1 + w, by2)
            if text: c.itemconfigure(hint, text=text)
            root.update()
        except Exception:
            pass

    def close():
        try: root.destroy()
        except Exception: pass

    return set_progress, close

_splash_set, _splash_close = _make_splash()
_splash_set(8, "Загрузка модулей…")

# ── Теперь грузим всё тяжёлое ─────────────────────────────────────────────
import webview
import threading
import json
import os
import logging
from pathlib import Path
from datetime import datetime
_splash_set(18, "Базовые модули…")


from promodate_functions import (
    FILTER_OPTIONS,
    download_files_thread,
    clear_download_folder,
    clear_output_folder,
    process_files_thread,
    refresh_power_query_files,
    run_stage_query1,
    run_stage_query2,
    run_stage_macros,
)
_splash_set(35, "Загрузка функций промодаты…")

from sku_matcher_functions import run_matching, save_to_reference
_splash_set(50, "SKU Matcher…")

from competitors_functions import refresh_competitors_pipeline
_splash_set(62, "Модуль конкурентов…")

from nielsen_functions import process_nielsen
_splash_set(74, "Nielsen…")

from production_functions import run_production, MONTH_LABELS
_splash_set(85, "Модуль производства…")

CONFIG_FILE = "config.json"


# ── Logger ────────────────────────────────────────────────────────────────────

def setup_logger():
    log_path = os.path.join(os.getcwd(), "flowmanager.log")
    logging.basicConfig(
        filename=log_path, level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S", encoding="utf-8",
    )


# ── Config ────────────────────────────────────────────────────────────────────

def load_config() -> dict:
    defaults = {
        "output_folder": "", "pq_file1": "", "pq_file2": "",
        "macro1": "ExtendDatesAndFormulas",
        "macro2": "ExtendDatesAndFormulas_MNZ",
        "olap_file": "", "competitors_file": "",
        "nielsen_input": "", "nielsen_output": "",
        "nielsen_format": "csv", "nielsen_category": "Масло",
        "query_refresh_file": "",
        "prod_svod_folder": "", "prod_npk_file": "",
        "prod_tolyatti": "", "prod_target": "",
        "prod_mapping": "", "prod_year": str(datetime.now().year),
        "prod_month": MONTH_LABELS[datetime.now().month - 1],
        "dark_theme": False,
    }
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


# ── Mock helpers ──────────────────────────────────────────────────────────────

class _SV:
    """Mock StringVar for legacy function compatibility."""
    def __init__(self, v): self._v = v
    def get(self): return str(self._v) if self._v is not None else ""


class _MB:
    """Mock tkinter.messagebox → push JS toasts."""
    def __init__(self, api): self._api = api

    def showinfo(self, title, msg):
        self._api._emit("toast", {"type": "success", "message": str(msg)})

    def showwarning(self, title, msg):
        self._api._emit("toast", {"type": "warning", "message": str(msg)})

    def showerror(self, title, msg):
        self._api._emit("toast", {"type": "error", "message": str(msg)})

    def askyesno(self, title, msg):
        try:
            return bool(self._api._window.evaluate_js(f'confirm({json.dumps(str(msg))})'))
        except Exception:
            return False

    def askokcancel(self, title, msg):
        return self.askyesno(title, msg)


# ═════════════════════════════════════════════════════════════════════════════
# API exposed to JS
# ═════════════════════════════════════════════════════════════════════════════

class Api:
    def __init__(self):
        self._window = None
        self._stop_event = threading.Event()
        self._mb = _MB(self)
        self._last_competitors_file = None

    # ── Push events to JS ─────────────────────────────────────────────────────

    def _emit(self, event_type, data=None):
        if self._window:
            try:
                payload = json.dumps({"type": event_type, "data": data})
                self._window.evaluate_js(f'window.__pyEvent({payload})')
            except Exception as e:
                logging.error(f"emit error [{event_type}]: {e}")

    def _log(self, msg):
        logging.info(msg)
        self._emit("log", str(msg))

    def _progress(self, done, total):
        self._emit("progress", {"done": done, "total": total})

    def _set_title(self, text):
        self._emit("set_title", str(text))

    # ── Config ────────────────────────────────────────────────────────────────

    def get_config(self):
        return load_config()

    def save_config(self, data):
        save_config_data(data)
        return True

    def get_filter_options(self):
        return list(FILTER_OPTIONS.keys())

    def get_month_labels(self):
        return MONTH_LABELS

    # ── File dialogs ──────────────────────────────────────────────────────────

    def browse_file(self):
        result = self._window.create_file_dialog(
            webview.OPEN_DIALOG,
            file_types=('Excel Files (*.xlsx;*.xlsm)', 'All Files (*.*)')
        )
        return result[0] if result else None

    def browse_folder(self):
        result = self._window.create_file_dialog(webview.FOLDER_DIALOG)
        return result[0] if result else None

    # ── Utilities ─────────────────────────────────────────────────────────────

    def open_folder(self, path):
        if path and os.path.isdir(path):
            try: os.startfile(path)
            except Exception as e:
                self._emit("toast", {"type": "error", "message": str(e)})
        return True

    def open_file(self, path):
        if path and os.path.isfile(path):
            try: os.startfile(path)
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
            target=clear_download_folder,
            args=(self._log, self._mb), daemon=True
        ).start()
        return True

    def clear_output(self, path):
        threading.Thread(
            target=clear_output_folder,
            args=(_SV(path), self._log, self._mb), daemon=True
        ).start()
        return True

    def open_last_competitors_file(self):
        if self._last_competitors_file:
            self.open_file(self._last_competitors_file)
        else:
            self._emit("toast", {"type": "warning", "message": "Последний файл не найден"})
        return True

    def get_csv_count(self, folder):
        if folder and os.path.isdir(folder):
            return len(list(Path(folder).glob('*.csv')))
        return 0

    # ── Download ──────────────────────────────────────────────────────────────

    def start_download(self, p):
        self._stop_event.clear()
        def _w():
            download_files_thread(
                _SV(p['month_from']), _SV(p['year_from']),
                _SV(p['month_to']),   _SV(p['year_to']),
                self._log, self._mb,
                progress_callback=self._progress,
                set_title=self._set_title,
            )
            self._emit("set_title", "")
            self._emit("hide_progress")
        threading.Thread(target=_w, daemon=True).start()
        return True

    # ── Process (full pipeline) ───────────────────────────────────────────────

    def start_process(self, p):
        self._stop_event.clear()
        def _w():
            process_files_thread(
                _SV(p['output_folder']), _SV(p['category']),
                FILTER_OPTIONS,
                self._log, self._mb, self._stop_event,
                refresh_power_query_files,
                _SV(p['pq_file1']), _SV(p['pq_file2']),
                _SV(p['macro1']),   _SV(p['macro2']),
                progress_callback=self._progress,
                set_title=self._set_title,
            )
            self._emit("set_title", "")
            self._emit("hide_progress")
        threading.Thread(target=_w, daemon=True).start()
        return True

    # ── Stages ────────────────────────────────────────────────────────────────

    def run_stage_q1(self, p):
        self._stop_event.clear()
        threading.Thread(
            target=lambda: (
                run_stage_query1(_SV(p['pq_file1']), self._log, self._stop_event, self._mb),
                self._emit("set_title", ""),
            ), daemon=True
        ).start()
        return True

    def run_stage_q2(self, p):
        self._stop_event.clear()
        threading.Thread(
            target=lambda: (
                run_stage_query2(_SV(p['pq_file2']), self._log, self._stop_event, self._mb),
                self._emit("set_title", ""),
            ), daemon=True
        ).start()
        return True

    def run_stage_macros(self, p):
        self._stop_event.clear()
        threading.Thread(
            target=lambda: (
                run_stage_macros(
                    _SV(p['pq_file2']), _SV(p['macro1']), _SV(p['macro2']),
                    self._log, self._stop_event, self._mb),
                self._emit("set_title", ""),
            ), daemon=True
        ).start()
        return True

    # ── Competitors ───────────────────────────────────────────────────────────

    def run_competitors(self, p):
        self._stop_event.clear()
        def _w():
            def _upd(path): self._last_competitors_file = path
            refresh_competitors_pipeline(
                _SV(p['olap_file']), _SV(p['competitors_file']),
                self._log, self._mb, self._stop_event,
                on_file_updated=_upd)
            self._emit("set_title", "")
        threading.Thread(target=_w, daemon=True).start()
        return True

    # ── Nielsen ───────────────────────────────────────────────────────────────

    def run_nielsen(self, p):
        self._stop_event.clear()
        threading.Thread(
            target=lambda: (
                process_nielsen(
                    p['input_file'], p['output_dir'],
                    p['format'], self._log, self._mb,
                    self._stop_event, p['category']),
                self._emit("set_title", ""),
            ), daemon=True
        ).start()
        return True

    # ── Query Refresh ─────────────────────────────────────────────────────────

    def run_query_refresh(self, p):
        self._stop_event.clear()
        def _w():
            from competitors_functions import refresh_file
            ok = refresh_file(p['file'], self._log, self._stop_event, timeout_minutes=90)
            if ok:
                self._emit("toast", {
                    "type": "success",
                    "message": f"Обновлено: {os.path.basename(p['file'])}"
                })
            self._emit("set_title", "")
        threading.Thread(target=_w, daemon=True).start()
        return True

    # ── Production ────────────────────────────────────────────────────────────

    def run_production(self, p):
        self._stop_event.clear()
        threading.Thread(
            target=lambda: (
                run_production(
                    p['svod_folder'], p['npk_file'],
                    p['tolyatti_folder'], p['target_file'],
                    p['mapping_file'], p['month_str'],
                    p['year'], self._log, self._mb, self._stop_event),
                self._emit("set_title", ""),
            ), daemon=True
        ).start()
        return True

    # ── SKU Matcher ───────────────────────────────────────────────────────────

    def run_sku_matching(self, p):
        def _prog(msg): self._emit("sku_log", msg)
        def _done(results, error=None):
            if error:
                self._emit("sku_error", str(error))
            else:
                self._emit("sku_results", results)
        threading.Thread(
            target=run_matching,
            args=(p['ref_path'], p['csv_folder'], float(p['threshold']), _prog, _done),
            daemon=True
        ).start()
        return True

    def save_sku_results(self, p):
        try:
            count = save_to_reference(p['results'], p['ref_path'])
            return {"success": True, "count": count}
        except Exception as e:
            return {"success": False, "error": str(e)}


# ── Entry point ───────────────────────────────────────────────────────────────

setup_logger()
_splash_set(92, "Запуск интерфейса…")
api = Api()

html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web', 'index.html')

window = webview.create_window(
    'EFKO FlowManager',
    html_path,
    js_api=api,
    width=1480,
    height=960,
    min_size=(1000, 700),
    background_color='#F5F5F7',
    easy_drag=False,
)
api._window = window

# Выносим окно на передний план через 1 сек после старта (из фонового потока)
def _bring_to_front():
    import time, ctypes
    try:
        # Находим окно по заголовку и выносим вперёд
        hwnd = ctypes.windll.user32.FindWindowW(None, "EFKO FlowManager")
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 9)       # SW_RESTORE
            ctypes.windll.user32.SetForegroundWindow(hwnd)
    except Exception:
        pass

threading.Thread(target=_bring_to_front, daemon=True).start()

# Закрываем сплэш ДО webview.start() — иначе конфликт главного потока
_splash_set(100, "Готово!")
_splash_close()

webview.start(debug=False)