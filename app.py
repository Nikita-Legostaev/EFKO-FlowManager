# ruff: noqa: E402
"""
EFKO FlowManager — pywebview backend
pip install pywebview
"""

# ═══════════════════════════════════════════════════════════════════════════
# СПЛЭШ — САМЫЕ ПЕРВЫЕ СТРОКИ, до любых импортов
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

    for i in range(48):
        t = i / 48
        r = int(0x18 + (0x30 - 0x18) * t)
        g = int(0x8C + (0xC7 - 0x8C) * t)
        b = int(0x3A + (0x55 - 0x3A) * t)
        y0, y1 = int(H * i / 48), int(H * (i + 1) / 48) + 1
        c.create_rectangle(0, y0, W, y1, fill=f"#{r:02x}{g:02x}{b:02x}", outline="")

    cx, cy = W // 2, 72
    c.create_oval(
        cx - 28, cy - 28, cx + 28, cy + 28, fill="#2aaa52", outline="#aaffbb", width=1
    )
    c.create_line(
        cx - 13,
        cy + 2,
        cx - 3,
        cy + 12,
        cx + 14,
        cy - 9,
        fill="white",
        width=3,
        capstyle="round",
        joinstyle="round",
    )

    c.create_text(
        W // 2 - 1,
        124,
        text="Flow",
        font=("Segoe UI", 26, "bold"),
        fill="#ffffff",
        anchor="e",
    )
    c.create_text(
        W // 2 - 1,
        124,
        text="Manager",
        font=("Segoe UI", 26),
        fill="#aaeebb",
        anchor="w",
    )
    c.create_text(
        W // 2, 150, text="EFKO  ·  v3.0", font=("Segoe UI", 9), fill="#88ccaa"
    )

    bx1, by1, bx2, by2 = 50, 178, W - 50, 183
    c.create_rectangle(bx1, by1, bx2, by2, fill="#2aaa52", outline="")
    bar = c.create_rectangle(bx1, by1, bx1, by2, fill="white", outline="")
    hint = c.create_text(
        W // 2, 200, text="Запуск…", font=("Segoe UI", 9), fill="#88ccaa"
    )

    root.lift()
    root.focus_force()
    root.update()

    def set_progress(pct, text=""):
        try:
            w = (bx2 - bx1) * min(pct, 100) / 100
            c.coords(bar, bx1, by1, bx1 + w, by2)
            if text:
                c.itemconfigure(hint, text=text)
            root.update()
        except Exception:
            pass

    def close():
        try:
            root.destroy()
        except Exception:
            pass

    return set_progress, close


_splash_set, _splash_close = _make_splash()
_splash_set(8, "Загрузка модулей…")


# ── Тяжёлые импорты ───────────────────────────────────────────────────────
import webview
import threading
import os

_splash_set(18, "Базовые модули…")

from app_config import setup_logger, _resource

_splash_set(30, "Конфиг…")

from api_core import ApiCoreMixin
from api_promodate import ApiPromodateMixin
from api_competitors import ApiCompetitorsMixin
from api_production import ApiProductionMixin
from api_price import ApiPriceMixin
from api_scheduler import ApiSchedulerMixin
from api_oos import ApiOosMixin

_splash_set(90, "Сборка API…")


# ═══════════════════════════════════════════════════════════════════════════
# API — собирается из миксинов
# ═══════════════════════════════════════════════════════════════════════════


class Api(
    ApiCoreMixin,
    ApiPromodateMixin,
    ApiCompetitorsMixin,
    ApiProductionMixin,
    ApiPriceMixin,
    ApiSchedulerMixin,
    ApiOosMixin,
):
    """Единая точка входа для JS. Логика разнесена по api_*.py."""

    pass


# ── Entry point ───────────────────────────────────────────────────────────────

setup_logger()
_splash_set(96, "Запуск интерфейса…")
api = Api()

html_path = _resource(os.path.join("web", "index.html"))

window = webview.create_window(
    "EFKO FlowManager",
    html_path,
    js_api=api,
    width=1700,
    height=1200,
    min_size=(1000, 700),
    background_color="#F5F5F7",
    easy_drag=False,
    maximized=True,
)
api._window = window


def _bring_to_front():
    import ctypes

    try:
        hwnd = ctypes.windll.user32.FindWindowW(None, "EFKO FlowManager")
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 9)
            ctypes.windll.user32.SetForegroundWindow(hwnd)
    except Exception:
        pass


threading.Thread(target=_bring_to_front, daemon=True).start()

_splash_set(100, "Готово!")
_splash_close()

webview.start(debug=False)
