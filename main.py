# ruff: noqa: E402
"""
main.py — EFKO FlowManager, точка входа.

Порядок best-effort: очистка зависших процессов -> сплэш -> тяжёлые
импорты -> сборка Api() -> окно -> проверка обновлений.
"""

import os
import sys

from app.orphans import cleanup_orphans_bg

cleanup_orphans_bg()

# ═══════════════════════════════════════════════════════════════════════════
# СПЛЭШ — до любых тяжёлых импортов
# ═══════════════════════════════════════════════════════════════════════════
from app.splash import make_splash

_splash_set, _splash_close = make_splash()
_splash_set(8, "Загрузка модулей…")


# ── Тяжёлые импорты ───────────────────────────────────────────────────────
_splash_set(18, "Базовые модули…")

from core.logging import setup_logger

_splash_set(30, "Конфиг…")

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

_splash_set(90, "Сборка API…")

setup_logger()
_step("setup_logger OK")
_splash_set(96, "Запуск интерфейса…")
_step("webview.create_window ...")

api = Api()
_step("✓ Api() init OK")

from app.window import create_main_window, bring_to_front_bg, preload_heavy_modules_bg

window = create_main_window(api)
preload_heavy_modules_bg()

_splash_set(100, "Готово!")

# webview.create_window() только регистрирует окно — реально оно появляется
# позже, внутри webview.start(). Раньше сплэш закрывался и окно поднималось
# на передний план сразу здесь, ДО того как окно физически создано — отсюда
# видимый разрыв (сплэш уже погас, а приложения ещё нет) и то, что
# bring_to_front_bg() часто не находил окно (гонка). Обе операции теперь
# висят на events.shown — реальном моменте показа окна. pywebview сам
# исполняет обработчики events.* в отдельном потоке, так что блокирующий
# time.sleep() внутри _splash_close() не подвесит показ окна.
def _on_window_shown():
    bring_to_front_bg()
    _splash_close()


window.events.shown += _on_window_shown

from updater import check_for_updates

check_for_updates(
    on_exit=lambda: window.destroy(),
    notify=lambda info: api._emit("update_available", info),
)

import webview

webview.start(debug=False)
