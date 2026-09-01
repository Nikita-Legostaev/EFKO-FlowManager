# -*- coding: utf-8 -*-
"""
apply_speedup.py — ускорение запуска EFKO FlowManager.

Из чего складывались 25 секунд (по вашему startup.log от 19.08):

    price_comparison_functions   19.0 с
    oos_functions                 5.1 с
    всё остальное                 0.9 с

Оба модуля грузятся при каждом старте, хотя нужны только когда человек
нажимает «Сравнение цен» или «Отчёт без OOS». Причина тяжести — импорты
уровня модуля внутри них (pandas/numpy/rapidfuzz и, судя по TF-IDF, sklearn).

Что делает скрипт:
  1. api_price.py и api_oos.py — импорт тяжёлого модуля переносится внутрь
     рабочего потока, то есть выполняется в момент нажатия кнопки;
  2. app.py — убирает диагностические предзагрузки тех же модулей
     (без этого пункта пункт 1 бесполезен: app.py импортирует их сам);
  3. app.py — переносит очистку зависших процессов (psutil обходит весь
     список процессов) в фоновый поток;
  4. app.py — расширяет фоновый прогрев: через пару секунд после появления
     окна тяжёлые модули подгружаются в фоне, поэтому первое нажатие кнопки
     тоже не будет ждать 19 секунд.

Запуск из корня проекта:
    python apply_speedup.py --dry-run
    python apply_speedup.py

Резервные копии — *.bak_speedup_YYYYMMDD_HHMMSS.
"""

import os
import re
import sys
import shutil
import datetime

DRY = "--dry-run" in sys.argv
ROOT = os.path.dirname(os.path.abspath(__file__))
STAMP = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

OK, SKIP, FAIL = [], [], []

# Метки «правка уже применена». Ищутся отдельно от самой строки импорта:
# после правки такая же строка появляется внутри _w(), и без метки скрипт
# принимал бы её за неправленый импорт уровня модуля.
MARKER = "# price_comparison_functions импортируется лениво, внутри рабочего потока:"
MARKER_OOS = "# oos_functions импортируется лениво, внутри рабочего потока:"


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def write(path, text):
    if DRY:
        return
    bak = f"{path}.bak_speedup_{STAMP}"
    if not os.path.exists(bak):
        shutil.copy2(path, bak)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def step(name, ok, msg=""):
    (OK if ok is True else SKIP if ok is None else FAIL).append((name, msg))
    mark = "✔" if ok is True else ("•" if ok is None else "✘")
    print(f"  {mark} {name}" + (f" — {msg}" if msg else ""))


# ═════════════════════════════════════════════════════════════════════════════
# 1. api_price.py — ленивый импорт price_comparison_functions
# ═════════════════════════════════════════════════════════════════════════════

def patch_api_price():
    path = os.path.join(ROOT, "api_price.py")
    print("\napi_price.py")
    if not os.path.isfile(path):
        step("файл", False, "не найден")
        return
    s = read(path)

    if MARKER in s:
        step("ленивый импорт", None, "уже сделано")
        return

    # Импорт уровня модуля — только в начале строки, без отступа.
    # Такая же строка с отступом внутри _w() — это уже результат правки,
    # трогать её нельзя.
    top_re = re.compile(
        r"^from price_comparison_functions import "
        r"run_comparison as run_price_comparison[ \t]*\n", re.M)
    if not top_re.search(s):
        step("ленивый импорт", None, "импорта верхнего уровня нет — уже сделано")
        return

    s = top_re.sub(
        MARKER + "\n"
        "# его загрузка занимает ~19 секунд и раньше происходила при каждом старте\n",
        s, count=1)

    # добавляем импорт внутрь _w()
    m = re.search(r"^([ \t]*)def _w\(\):\s*\n", s, re.M)
    if not m:
        step("ленивый импорт", False, "не найдена функция _w() внутри run_price_comparison")
        return
    body_indent = m.group(1) + "    "
    ins = (f"{body_indent}from price_comparison_functions import "
           f"run_comparison as run_price_comparison\n")
    s = s[:m.end()] + ins + s[m.end():]

    write(path, s)
    step("ленивый импорт", True, "минус ~19 с при старте")


# ═════════════════════════════════════════════════════════════════════════════
# 2. api_oos.py — ленивый импорт oos_functions
# ═════════════════════════════════════════════════════════════════════════════

def patch_api_oos():
    path = os.path.join(ROOT, "api_oos.py")
    print("\napi_oos.py")
    if not os.path.isfile(path):
        step("файл", False, "не найден")
        return
    s = read(path)

    if MARKER_OOS in s:
        step("ленивый импорт", None, "уже сделано")
        return

    top_re = re.compile(
        r"^from oos_functions import run_oos_report as _run_oos_report[ \t]*\n", re.M)
    if not top_re.search(s):
        step("ленивый импорт", None, "импорта верхнего уровня нет — уже сделано")
        return

    s = top_re.sub(
        MARKER_OOS + "\n"
        "# его загрузка занимает ~5 секунд и раньше происходила при каждом старте\n",
        s, count=1)

    m = re.search(r"^([ \t]*)def _w\(\):\s*\n", s, re.M)
    if not m:
        step("ленивый импорт", False, "не найдена функция _w() внутри run_oos_all")
        return
    body_indent = m.group(1) + "    "
    ins = f"{body_indent}from oos_functions import run_oos_report as _run_oos_report\n"
    s = s[:m.end()] + ins + s[m.end():]

    write(path, s)
    step("ленивый импорт", True, "минус ~5 с при старте")


# ═════════════════════════════════════════════════════════════════════════════
# 3. app.py — убрать диагностические предзагрузки
# ═════════════════════════════════════════════════════════════════════════════

HEAVY_MODULES = [
    "production_functions",
    "price_comparison_functions",
    "scheduler_functions",
    "promodate_functions",
    "oos_functions",
    "sku_matcher_functions",
]


def patch_app_preimports():
    path = os.path.join(ROOT, "app.py")
    print("\napp.py — диагностические предзагрузки")
    if not os.path.isfile(path):
        step("файл", False, "не найден")
        return
    s = read(path)
    orig = s
    removed = []

    # Блок чтения исходника sku_matcher_functions (полтора десятка строк в лог)
    m = re.search(
        r"^# Покажем что реально лежит в файле\n"
        r"try:\n(?:.*\n)*?"
        r"except Exception as _e:\n"
        r"[ \t]*_step\(f\"[^\"]*\"\)\n",
        s, re.M)
    if m:
        s = s[:m.start()] + s[m.end():]
        removed.append("дамп sku_matcher_functions в лог")

    # Блоки вида:
    #   _step("   → mod...")
    #   try:
    #       import mod as _x        (или from mod import ...)
    #       _step("   ✓ mod")
    #   except Exception as e:
    #       _step(f"   ✗ mod: {e}")
    for mod in HEAVY_MODULES:
        pat = re.compile(
            r"^[ \t]*_step\(\"[^\"]*" + re.escape(mod) + r"[^\"]*\"\)\n"
            r"try:\n"
            r"[ \t]*(?:import|from)[ \t]+" + re.escape(mod) + r"[^\n]*\n"
            r"[ \t]*_step\(\"[^\"]*\"\)\n"
            r"except Exception as e:\n"
            r"[ \t]*_step\(f\"[^\"]*\"\)\n",
            re.M)
        s, n = pat.subn("", s)
        if n:
            removed.append(mod)

    if not removed:
        step("предзагрузки", None, "не найдены — вероятно, уже убраны")
    else:
        write(path, s)
        step("предзагрузки", True, "убрано: " + ", ".join(removed))

    return s if s != orig else None


# ═════════════════════════════════════════════════════════════════════════════
# 4. app.py — очистка процессов в фоне
# ═════════════════════════════════════════════════════════════════════════════

def patch_app_cleanup():
    path = os.path.join(ROOT, "app.py")
    print("\napp.py — очистка процессов в фоне")
    s = read(path)

    if "_cleanup_orphans_bg" in s:
        step("фоновая очистка", None, "уже есть")
        return

    old = re.search(
        r"^try:\n[ \t]*_cleanup_orphans\(\)\nexcept Exception:\n[ \t]*pass\n",
        s, re.M)
    if not old:
        step("фоновая очистка", None, "вызов _cleanup_orphans() не найден, пропущено")
        return

    new = (
        "def _cleanup_orphans_bg():\n"
        "    \"\"\"Обход списка процессов через psutil — не держим им старт окна.\"\"\"\n"
        "    try:\n"
        "        _cleanup_orphans()\n"
        "    except Exception:\n"
        "        pass\n"
        "\n"
        "\n"
        "import threading as _th\n"
        "_th.Thread(target=_cleanup_orphans_bg, daemon=True).start()\n"
    )
    s = s[:old.start()] + new + s[old.end():]
    write(path, s)
    step("фоновая очистка", True)


# ═════════════════════════════════════════════════════════════════════════════
# 5. app.py — прогрев тяжёлых модулей после показа окна
# ═════════════════════════════════════════════════════════════════════════════

def patch_app_preload():
    path = os.path.join(ROOT, "app.py")
    print("\napp.py — фоновый прогрев")
    s = read(path)

    if "price_comparison_functions" in s and "_preload_heavy_modules" in s \
            and "# прогрев тяжёлых модулей" in s:
        step("прогрев", None, "уже есть")
        return

    m = re.search(
        r"^([ \t]*)for lib in \[[^\]]*\]:\s*$",
        s, re.M)
    if not m:
        step("прогрев", None, "функция _preload_heavy_modules не найдена, пропущено")
        return

    ind = m.group(1)
    new_line = (
        f"{ind}# прогрев тяжёлых модулей: подгружаем в фоне, чтобы первое нажатие\n"
        f"{ind}# «Сравнение цен» / «Отчёт без OOS» не ждало импорта\n"
        f"{ind}for lib in [\"pandas\", \"polars\", \"openpyxl\", \"openpyxl.styles\",\n"
        f"{ind}            \"rapidfuzz\", \"rapidfuzz.fuzz\",\n"
        f"{ind}            \"price_comparison_functions\", \"oos_functions\"]:"
    )
    s = s[:m.start()] + new_line + s[m.end():]
    write(path, s)
    step("прогрев", True, "тяжёлые модули греются после показа окна")


# ═════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 62)
    print("EFKO FlowManager — ускорение запуска" + ("  [ТЕСТОВЫЙ ПРОГОН]" if DRY else ""))
    print(f"Папка проекта: {ROOT}")
    print("=" * 62)

    patch_api_price()
    patch_api_oos()
    patch_app_preimports()
    patch_app_cleanup()
    patch_app_preload()

    print("\n" + "=" * 62)
    print(f"Применено: {len(OK)}   Пропущено: {len(SKIP)}   Ошибок: {len(FAIL)}")
    if FAIL:
        print("\nТребует ручной правки:")
        for name, msg in FAIL:
            print(f"  ✘ {name} — {msg}")
    if DRY:
        print("\nТестовый прогон, файлы не изменены.")
    else:
        print(f"\nРезервные копии: *.bak_speedup_{STAMP}")
        print("\nПроверьте startup.log после запуска — должно стать около секунды.")
    print("=" * 62)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())