"""app/splash.py — мгновенный сплэш на tkinter, до тяжёлых импортов."""

import os
import time
import tkinter as tk

from core.paths import _resource

_MIN_SHOW_SECONDS = 5.0


def make_splash():
    W, H = 420, 240
    root = tk.Tk()
    root.overrideredirect(True)
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")
    root.configure(bg="#8B34EA")

    c = tk.Canvas(root, width=W, height=H, bg="#8B34EA", highlightthickness=0)
    c.pack(fill="both", expand=True)

    # Фиолетовый градиент (светлый → тёмный), в тон остальному интерфейсу
    for i in range(48):
        t = i / 48
        r = int(0xA8 + (0x6D - 0xA8) * t)
        g = int(0x55 + (0x28 - 0x55) * t)
        b = int(0xF7 + (0xD9 - 0xF7) * t)
        y0, y1 = int(H * i / 48), int(H * (i + 1) / 48) + 1
        c.create_rectangle(0, y0, W, y1, fill=f"#{r:02x}{g:02x}{b:02x}", outline="")

    try:
        logo_img = tk.PhotoImage(file=_resource(os.path.join("icon", "logo_white.png")))
        # PhotoImage не умеет плавно даунскейлить — .png уже 440×80 (2x под 220×40)
        logo_img = logo_img.subsample(2, 2)
        c.create_image(W // 2, H // 2, image=logo_img)
        c._logo_img_ref = logo_img  # без этого tkinter соберёт картинку и она пропадёт с канваса
    except Exception:
        c.create_text(W // 2, H // 2, text="FlowManager", font=("Segoe UI", 24, "bold"), fill="#ffffff")

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
