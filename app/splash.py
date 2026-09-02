"""app/splash.py — мгновенный сплэш на tkinter, до тяжёлых импортов."""

import os
import time
import tkinter as tk

from core.paths import _resource

_MIN_SHOW_SECONDS = 5.0
_TRANSPARENT_KEY = "#FE01FE"  # маловероятный цвет — им ничего в логотипе не покрашено


def make_splash():
    W, H = 300, 120
    root = tk.Tk()
    root.overrideredirect(True)
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")
    root.configure(bg=_TRANSPARENT_KEY)
    try:
        # Windows-only: делает фон окна прозрачным, остаётся только сам
        # логотип, без прямоугольной подложки вокруг него.
        root.attributes("-transparentcolor", _TRANSPARENT_KEY)
    except tk.TclError:
        pass  # не Windows / не поддерживается — останется сплошной фон ключевого цвета

    c = tk.Canvas(root, width=W, height=H, bg=_TRANSPARENT_KEY, highlightthickness=0)
    c.pack(fill="both", expand=True)

    try:
        logo_img = tk.PhotoImage(file=_resource(os.path.join("icon", "logo_blue.png")))
        # PhotoImage не умеет плавно даунскейлить — .png уже 440×80 (2x под 220×40)
        logo_img = logo_img.subsample(2, 2)
        c.create_image(W // 2, H // 2, image=logo_img)
        c._logo_img_ref = logo_img  # без этого tkinter соберёт картинку и она пропадёт с канваса
    except Exception:
        c.create_text(W // 2, H // 2, text="FlowManager", font=("Segoe UI", 22, "bold"), fill="#002BE5")

    # ── Гарантируем показ поверх всех окон, а не «в фоне» ──────────────────
    # overrideredirect-окно на Windows иногда не забирает фокус с первого
    # раза (особенно если запуск идёт из IDE/консоли, которая держит фокус
    # на себе) — топмост переустанавливаем ещё раз через мгновение после
    # первой отрисовки.
    root.attributes("-topmost", True)
    root.lift()
    root.focus_force()
    root.update()
    root.after(60, lambda: (root.attributes("-topmost", True), root.lift()))
    root.update()

    started_at = time.time()

    def set_progress(pct, text=""):
        # Бар убран — просто держим tk-цикл живым, чтобы окно не «зависало»
        # и оставалось поверх остальных на всё время инициализации.
        try:
            root.attributes("-topmost", True)
            root.update()
        except Exception:
            pass

    def close():
        # Не закрываем раньше _MIN_SHOW_SECONDS с момента показа — даже если
        # инициализация прошла мгновенно, заставку должно быть видно.
        remaining = _MIN_SHOW_SECONDS - (time.time() - started_at)
        if remaining > 0:
            time.sleep(remaining)
        try:
            root.destroy()
        except Exception:
            pass

    return set_progress, close
