"""app/window.py — создание webview-окна и фоновый прогрев тяжёлых модулей."""

import os
import ctypes
import threading

import webview

from core.paths import _resource


def create_main_window(api):
    html_path = _resource(os.path.join("web", "index.html"))

    try:
        ctypes.windll.user32.SetProcessDPIAware()
        sw = ctypes.windll.user32.GetSystemMetrics(0)
        sh = ctypes.windll.user32.GetSystemMetrics(1)
    except Exception:
        sw, sh = 1280, 800

    window = webview.create_window(
        "EFKO FlowManager",
        html_path,
        js_api=api,
        width=sw,
        height=sh,
        min_size=(1000, 700),
        background_color="#F5F5F7",
        easy_drag=False,
        maximized=True,
    )
    api._window = window
    return window


def bring_to_front_bg():
    def _run():
        try:
            hwnd = ctypes.windll.user32.FindWindowW(None, "EFKO FlowManager")
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 3)
                ctypes.windll.user32.SetForegroundWindow(hwnd)
        except Exception:
            pass

    threading.Thread(target=_run, daemon=True).start()


def preload_heavy_modules_bg():
    def _run():
        import time
        time.sleep(1.5)
        # прогрев тяжёлых модулей: подгружаем в фоне, чтобы первое нажатие
        # «Сравнение цен» / «Отчёт без OOS» не ждало импорта
        for lib in ["pandas", "polars", "openpyxl", "openpyxl.styles",
                    "rapidfuzz", "rapidfuzz.fuzz",
                    "services.price_comparison", "services.oos"]:
            try:
                __import__(lib)
            except Exception:
                pass

    threading.Thread(target=_run, daemon=True).start()
