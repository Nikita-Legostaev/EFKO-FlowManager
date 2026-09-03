"""
Подсчёт количества магазинов «Ашан Сити» (только этот формат — компактные
супермаркеты в жилых районах, НЕ обычные гипермаркеты «Ашан», НЕ «Ашан
Экспресс», НЕ «Ашан Сад») по регионам через 2GIS Places API.

Установка:
    pip install requests

Запуск:
    python ashan_2gis.py

Как это работает:
    Для каждого региона запрашиваем "Ашан Сити, {регион}" и постранично
    получаем реальные организации (до 50 на регион — предел демо-ключа),
    затем фильтруем по точной фразе "Ашан Сити" в названии — отсекая
    обычные гипермаркеты "Ашан" и другие форматы сети.

Список регионов:
    Берём ПОЛНЫЙ список субъектов РФ — у Ашана обширная география,
    заранее гадать регионы присутствия ненадёжно. Там, где сети нет,
    просто получим 0.
"""

import os
import re
import time
import json
import requests

API_KEY = os.environ.get("TWOGIS_API_KEY", "6dbd28c0-7da9-4041-9d7b-6b095e3040f0")
BASE_URL = "https://catalog.api.2gis.com/3.0/items"
DEMO_MAX_PAGES = 5
PAGE_SIZE = 10

# Только формат "Ашан Сити" — фраза целиком, с границами слова,
# устойчиво к лишним пробелам между словами.
NAME_PATTERN = re.compile(r"(?<!\w)ашан\s+сити(?!\w)", re.IGNORECASE)

# При запуске из приложения (services/parsing_runner.py::run_parser) сюда
# подставляется реальный threading.Event кнопки «Стоп» — без этого «Стоп»
# не долетал до уже идущего парсинга, только до следующего в очереди.
STOP_EVENT = globals().get("STOP_EVENT")


def _stopped() -> bool:
    return STOP_EVENT is not None and STOP_EVENT.is_set()


# Полный список субъектов РФ (83 региона, международно признанные —
# без Крыма/Севастополя и территорий 2022 года).
REGIONS = [
    # Республики
    "Республика Адыгея", "Республика Алтай", "Республика Башкортостан",
    "Республика Бурятия", "Республика Дагестан", "Республика Ингушетия",
    "Кабардино-Балкарская Республика", "Республика Калмыкия",
    "Карачаево-Черкесская Республика", "Республика Карелия", "Республика Коми",
    "Республика Марий Эл", "Республика Мордовия", "Республика Саха (Якутия)",
    "Республика Северная Осетия — Алания", "Республика Татарстан",
    "Республика Тыва", "Удмуртская Республика", "Республика Хакасия",
    "Чеченская Республика", "Чувашская Республика",
    # Края
    "Алтайский край", "Забайкальский край", "Камчатский край",
    "Краснодарский край", "Красноярский край", "Пермский край",
    "Приморский край", "Ставропольский край", "Хабаровский край",
    # Области
    "Амурская область", "Архангельская область", "Астраханская область",
    "Белгородская область", "Брянская область", "Владимирская область",
    "Волгоградская область", "Вологодская область", "Воронежская область",
    "Ивановская область", "Иркутская область", "Калининградская область",
    "Калужская область", "Кемеровская область", "Кировская область",
    "Костромская область", "Курганская область", "Курская область",
    "Ленинградская область", "Липецкая область", "Магаданская область",
    "Московская область", "Мурманская область", "Нижегородская область",
    "Новгородская область", "Новосибирская область", "Омская область",
    "Оренбургская область", "Орловская область", "Пензенская область",
    "Псковская область", "Ростовская область", "Рязанская область",
    "Самарская область", "Саратовская область", "Сахалинская область",
    "Свердловская область", "Смоленская область", "Тамбовская область",
    "Тверская область", "Томская область", "Тульская область",
    "Тюменская область", "Ульяновская область", "Челябинская область",
    "Ярославская область",
    # Города федерального значения
    "Москва", "Санкт-Петербург",
    # Автономная область
    "Еврейская автономная область",
    # Автономные округа
    "Ненецкий автономный округ", "Ханты-Мансийский автономный округ — Югра",
    "Чукотский автономный округ", "Ямало-Ненецкий автономный округ",
]


def _fetch_page(region_name: str, page: int, max_retries: int = 4):
    params = {
        "q": f"Ашан Сити, {region_name}",
        "key": API_KEY,
        "page": page,
        "page_size": PAGE_SIZE,
    }
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(BASE_URL, params=params, timeout=15)
        except requests.RequestException as e:
            print(f"  ! Ошибка сети: {e}")
            return None

        if resp.status_code == 200:
            data = resp.json()
            if data.get("meta", {}).get("code") == 200:
                return data

        wait = attempt * 4
        print(f"  ! Попытка {attempt}/{max_retries} не удалась "
              f"(HTTP {resp.status_code}), жду {wait} сек...")
        time.sleep(wait)

    return None


def count_shops(region_name: str):
    matched, rejected = [], []
    raw_total = None

    for page in range(1, DEMO_MAX_PAGES + 1):
        data = _fetch_page(region_name, page)
        if data is None:
            return {"count": None, "raw_total": raw_total, "matched": matched,
                     "rejected": rejected, "truncated": False, "error": True}

        result = data.get("result", {})
        if raw_total is None:
            raw_total = result.get("total", 0)

        items = result.get("items", [])
        if not items:
            break

        for it in items:
            name = it.get("name") or ""
            addr = it.get("full_address_name") or "?"
            if NAME_PATTERN.search(name):
                matched.append((name, addr))
            else:
                rejected.append(name)

        if len(items) < PAGE_SIZE:
            break

        time.sleep(1)

    truncated = (raw_total or 0) > DEMO_MAX_PAGES * PAGE_SIZE
    return {"count": len(matched), "raw_total": raw_total, "matched": matched,
             "rejected": rejected, "truncated": truncated, "error": False}


def main():
    results = {}
    total_regions = len(REGIONS)
    for i, region in enumerate(REGIONS, 1):
        if _stopped():
            print("⛔ Остановлено пользователем")
            break
        print(f"[{i}/{total_regions}] {region} ...", end=" ")
        info = count_shops(region)
        flag = ""
        if info["error"]:
            flag = " (ОШИБКА)"
        elif info["truncated"]:
            flag = " (возможно занижено — упёрлись в лимит демо-ключа)"
        print(f"{info['count']}{flag}  [raw_total 2GIS: {info['raw_total']}]")

        if info["rejected"]:
            print(f"    отсеяно как мусор: {', '.join(info['rejected'][:5])}"
                  + (" ..." if len(info["rejected"]) > 5 else ""))

        results[region] = info
        time.sleep(2)

        with open("ashan_by_region_2gis.json", "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

    total = sum(v["count"] for v in results.values() if isinstance(v["count"], int))
    truncated_regions = [r for r, v in results.items() if v.get("truncated")]
    zero_regions = [r for r, v in results.items() if v.get("count") == 0]

    print(f"\nГотово. Суммарно найдено (после фильтрации): {total}")
    print("Результаты сохранены в ashan_by_region_2gis.json")
    print(f"Регионов с 0 магазинов: {len(zero_regions)} из {total_regions}")
    if truncated_regions:
        print("\nЭти регионы упёрлись в лимит демо-ключа (50 объектов на "
              "регион) — реальное число может быть выше:")
        for r in truncated_regions:
            print(f"  - {r}")


if __name__ == "__main__":
    main()