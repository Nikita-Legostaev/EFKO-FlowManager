"""
startup_splash.py — мгновенный сплэш без mainloop.
Tkinter не поддерживает rgba/8-digit hex — используем только обычные цвета.
"""

import tkinter as tk


class SplashScreen:
    def __init__(self):
        self.W = 400
        self.H = 240

        root = tk.Tk()
        self._root = root

        root.overrideredirect(True)
        root.attributes("-topmost", True)

        # Центрируем окно
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        x = (sw - self.W) // 2
        y = (sh - self.H) // 2
        root.geometry(f"{self.W}x{self.H}+{x}+{y}")

        BG = "#1e8c42"
        root.configure(bg=BG)

        c = tk.Canvas(root, width=self.W, height=self.H, bg=BG, highlightthickness=0)
        c.pack(fill="both", expand=True)
        self._canvas = c

        # Градиент (светлее снизу)
        steps = 48
        for i in range(steps):
            t = i / steps
            r = int(0x18 + (0x30 - 0x18) * t)
            g = int(0x8C + (0xC7 - 0x8C) * t)
            b = int(0x3A + (0x55 - 0x3A) * t)
            y0 = int(self.H * i / steps)
            y1 = int(self.H * (i + 1) / steps) + 1
            c.create_rectangle(
                0, y0, self.W, y1, fill=f"#{r:02x}{g:02x}{b:02x}", outline=""
            )

        # Иконка — просто круг с галочкой
        cx, cy = self.W // 2, 72
        c.create_oval(
            cx - 28,
            cy - 28,
            cx + 28,
            cy + 28,
            fill="#2aaa52",
            outline="#aaffbb",
            width=1,
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

        # Название  "Flow" + "Manager"
        c.create_text(
            self.W // 2 - 1,
            124,
            text="Flow",
            font=("Segoe UI", 26, "bold"),
            fill="#ffffff",
            anchor="e",
        )
        c.create_text(
            self.W // 2 - 1,
            124,
            text="Manager",
            font=("Segoe UI", 26),
            fill="#aaeebb",
            anchor="w",
        )

        # Подзаголовок
        c.create_text(
            self.W // 2, 150, text="EFKO  ·  v3.0", font=("Segoe UI", 9), fill="#88ccaa"
        )

        # Прогресс-бар
        self._bx1 = 50
        self._by1 = 178
        self._bx2 = self.W - 50
        self._by2 = 183
        c.create_rectangle(
            self._bx1, self._by1, self._bx2, self._by2, fill="#2aaa52", outline=""
        )
        self._bar = c.create_rectangle(
            self._bx1, self._by1, self._bx1, self._by2, fill="white", outline=""
        )

        # Текст подсказки
        self._hint = c.create_text(
            self.W // 2, 200, text="Запуск…", font=("Segoe UI", 9), fill="#88ccaa"
        )

        # Показываем окно
        root.lift()
        root.focus_force()
        root.update()

    def set_progress(self, pct: int, hint: str = ""):
        try:
            w = (self._bx2 - self._bx1) * min(pct, 100) / 100
            self._canvas.coords(
                self._bar, self._bx1, self._by1, self._bx1 + w, self._by2
            )
            if hint:
                self._canvas.itemconfigure(self._hint, text=hint)
            self._root.update()
        except Exception:
            pass

    def close(self):
        try:
            self._root.destroy()
        except Exception:
            pass


def show_splash() -> SplashScreen:
    return SplashScreen()
