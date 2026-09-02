# ruff: noqa: E402
"""
main.py — EFKO FlowManager, точка входа.

Порядок best-effort: очистка зависших процессов -> тяжёлые импорты ->
сборка Api() -> окно -> проверка обновлений.
"""

import os
import sys

if sys.platform == "win32":
    import asyncio
    import subprocess
    # Парсеры (Fix Price, Доброцен) используют Playwright, который на
    # старте спавнит свой Node-драйвер через asyncio-подпроцесс — на
    # Windows это работает только с ProactorEventLoop. Она и так дефолтная
    # с Python 3.8+, но фиксируем явно: иначе, если что-то в стеке
    # pywebview/его зависимостей успеет выставить SelectorEventLoop раньше
    # нас, запуск браузера у парсера тихо зависает навсегда без единой
    # ошибки в логе.
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    # Приложение оконное (console=False, без своей консоли). Любой
    # консольный подпроцесс, запущенный из такого процесса без явного
    # CREATE_NO_WINDOW, заставляет Windows на лету открыть для него новое
    # консольное окно — оно мелькает и закрывается вместе с подпроцессом.
    # Playwright именно так спавнит свой Node-драйвер (и процесс
    # `playwright install`) — мы не можем поправить точечно внутри самого
    # Playwright, поэтому подмешиваем флаг глобально на уровне
    # subprocess.Popen: asyncio на Windows тоже создаёт подпроцессы через
    # него, так что фикс закрывает сразу оба случая. На GUI-процессы
    # (сам Chrome/Edge) флаг не влияет — у них и так нет консоли.
    _orig_popen_init = subprocess.Popen.__init__

    def _popen_init_no_window(self, *args, **kwargs):
        kwargs["creationflags"] = kwargs.get("creationflags", 0) | subprocess.CREATE_NO_WINDOW
        _orig_popen_init(self, *args, **kwargs)

    subprocess.Popen.__init__ = _popen_init_no_window

from app.orphans import cleanup_orphans_bg

cleanup_orphans_bg()

# ── Тяжёлые импорты ───────────────────────────────────────────────────────
from core.logging import setup_logger

# ── Пошаговый лог запуска — помогает найти где зависает ──────────────────
_start_log = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "startup.log")


def _step(name):
    """Пишет шаг в файл немедленно (flush) — видно даже если зависнет."""
    import datetime
    line = f"{datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3]}  {name}\n"
    try:
        with open(_start_log, "a", encoding="utf-8") as f:
            f.write(line)
            f.flush()
    except Exception:
        pass


# Очищаем лог предыдущего запуска
try:
    with open(_start_log, "w", encoding="utf-8") as f:
        f.write(f"=== Запуск {__import__('datetime').datetime.now()} ===\n")
except Exception:
    pass

_step("core OK")
_step("import api ...")
from api import Api

_step("✓ api")

setup_logger()
_step("setup_logger OK")
_step("webview.create_window ...")

api = Api()
_step("✓ Api() init OK")

from app.window import create_main_window, bring_to_front_bg, preload_heavy_modules_bg

window = create_main_window(api)
preload_heavy_modules_bg()

# webview.create_window() только регистрирует окно — реально оно появляется
# позже, внутри webview.start(). Приведение окна на передний план подвешено
# на events.shown — реальном моменте показа окна, иначе FindWindowW часто
# ничего не находит (гонка).
window.events.shown += bring_to_front_bg

from updater import check_for_updates

check_for_updates(
    on_exit=lambda: window.destroy(),
    notify=lambda info: api._emit("update_available", info),
)

import webview

webview.start(debug=False)
