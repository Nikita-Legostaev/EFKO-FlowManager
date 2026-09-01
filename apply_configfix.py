# -*- coding: utf-8 -*-
"""
apply_configfix.py — чинит сохранение настроек вкладки «Парсинг ЖДСК».

Симптом: во вкладке выбираешь папку результатов, а поле остаётся пустым.

Причина в app_config.py. load_config() собирает словарь defaults и
переносит из файла только те ключи, которые в нём перечислены:

    for k in defaults:
        if k in data:
            defaults[k] = data[k]

parsing_output и parsing_keys в defaults не значатся, поэтому путь
записывался в config.json и тут же терялся при следующем чтении.

Вторая проблема: save_config_data() пишет переданный словарь целиком,
затирая всё, чего в нём нет. Сохранение с главного экрана вычищало бы
настройки парсинга из файла.

Что делает скрипт:
  1. добавляет parsing_output и parsing_keys в defaults;
  2. переводит save_config_data() на слияние с уже записанным файлом,
     чтобы новые разделы приложения не приходилось каждый раз
     регистрировать в белом списке.

Запуск из корня проекта:
    python apply_configfix.py --dry-run
    python apply_configfix.py
"""

import os
import re
import sys
import shutil
import datetime

DRY = "--dry-run" in sys.argv
ROOT = os.path.dirname(os.path.abspath(__file__))
STAMP = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
PATH = os.path.join(ROOT, "app_config.py")

OK, SKIP, FAIL = [], [], []


def step(name, ok, msg=""):
    (OK if ok is True else SKIP if ok is None else FAIL).append((name, msg))
    print(f"  {'✔' if ok is True else '•' if ok is None else '✘'} {name}"
          + (f" — {msg}" if msg else ""))


NEW_SAVE = '''def save_config_data(data: dict):
    """
    Сохраняет настройки, дополняя уже записанные, а не заменяя их целиком.

    Раньше сюда приходил словарь с главного экрана и затирал разделы,
    которых в нём не было, — например, настройки вкладки парсинга.
    """
    try:
        current = {}
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    current = json.load(f)
                if not isinstance(current, dict):
                    current = {}
            except Exception as e:
                logging.warning(f"Config read before save: {e}")

        current.update(data or {})

        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Config save error: {e}")
'''


def main():
    print("=" * 62)
    print("EFKO FlowManager — настройки парсинга" + ("  [ТЕСТОВЫЙ ПРОГОН]" if DRY else ""))
    print(f"Файл: {PATH}")
    print("=" * 62)

    if not os.path.isfile(PATH):
        step("app_config.py", False, "не найден")
        return 1

    with open(PATH, encoding="utf-8") as f:
        s = f.read()
    orig = s

    # ── 1. Ключи в defaults ──────────────────────────────────────────────
    if '"parsing_output"' in s:
        step("ключи parsing_* в defaults", None, "уже есть")
    else:
        m = re.search(r'^([ \t]*)"dl_mode":\s*"range",\s*$', s, re.M)
        if not m:
            m = re.search(r'^([ \t]*)"dark_theme":\s*False,\s*$', s, re.M)
        if not m:
            step("ключи parsing_* в defaults", False,
                 "не найдено место в словаре defaults — добавьте вручную")
        else:
            ind = m.group(1)
            ins = (f'\n{ind}# ── Парсинг ЖДСК ──\n'
                   f'{ind}"parsing_output": "",   # папка для Excel по сетям\n'
                   f'{ind}"parsing_keys": {{}},     # {{ИМЯ_ПЕРЕМЕННОЙ: API-ключ}}')
            s = s[:m.end()] + ins + s[m.end():]
            step("ключи parsing_* в defaults", True)

    # ── 2. Слияние при сохранении ────────────────────────────────────────
    if "Config read before save" in s:
        step("слияние в save_config_data", None, "уже есть")
    else:
        m = re.search(
            r"^def save_config_data\(data: dict\):\n"
            r"(?:[ \t]+.*\n|\n)*?"
            r"[ \t]+logging\.error\(f\"Config save error: \{e\}\"\)\n",
            s, re.M)
        if not m:
            step("слияние в save_config_data", False,
                 "функция не найдена — правьте вручную")
        else:
            s = s[:m.start()] + NEW_SAVE + s[m.end():]
            step("слияние в save_config_data", True)

    if s != orig and not DRY:
        bak = f"{PATH}.bak_cfg_{STAMP}"
        if not os.path.exists(bak):
            shutil.copy2(PATH, bak)
        with open(PATH, "w", encoding="utf-8", newline="") as f:
            f.write(s)

    print("\n" + "=" * 62)
    print(f"Применено: {len(OK)}   Пропущено: {len(SKIP)}   Ошибок: {len(FAIL)}")
    if DRY:
        print("\nТестовый прогон, файл не изменён.")
    elif s != orig:
        print(f"\nРезервная копия: {PATH}.bak_cfg_{STAMP}")
    print("=" * 62)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
