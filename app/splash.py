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
    root.attributes("-topmost", True)
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
        c.create_image(W // 2, 82, image=logo_img)
        c._logo_img_ref = logo_img  # без этого tkinter соберёт картинку и она пропадёт с канваса
    except Exception:
        c.create_text(W // 2, 82, text="FlowManager", font=("Segoe UI", 24, "bold"), fill="#ffffff")

    c.create_text(W // 2, 118, text="EFKO  ·  v3.0", font=("Segoe UI", 9), fill="#E6D6FA")

    bx1, by1, bx2, by2 = 60, 168, W - 60, 173
    # tkinter не понимает 8-значный hex с альфой — берём сплошной тёмный оттенок трека
    c.create_rectangle(bx1, by1, bx2, by2, fill="#5C2499", outline="")
    bar = c.create_rectangle(bx1, by1, bx1, by2, fill="white", outline="")
    hint = c.create_text(W // 2, 192, text="Запуск…", font=("Segoe UI", 9), fill="#E6D6FA")

    root.lift()
    root.focus_force()
    root.update()

    started_at = time.time()

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
