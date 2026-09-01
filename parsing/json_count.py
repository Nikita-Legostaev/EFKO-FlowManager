"""
Геокодинг координат Bristol.
Сохраняет прогресс — если упадёт, продолжит с того места.

Установка:
    pip install geopy pandas openpyxl requests

Запуск:
    python geocode_bristol.py               # геокодинг координат
    python geocode_bristol.py fix           # дополнить через справочник
    python geocode_bristol.py fix2          # дополнить через Nominatim по адресу
    python geocode_bristol.py yandex КЛЮЧ  # дополнить через Яндекс геокодер
    python geocode_bristol.py dadata КЛЮЧ  # дополнить через DaData

Ключи бесплатно:
    Яндекс: https://developer.tech.yandex.ru/
    DaData:  https://dadata.ru/
"""

import json, time, os, re, sys
import pandas as pd
import requests as req
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

INPUT_FILE    = "bristol_jsib_cord.json"
PROGRESS_FILE = "progress.json"
DICT_FILE     = "city_and_regions_Russia.xlsx"
OUTPUT_FILE   = "bristol_shops.xlsx"

geolocator  = Nominatim(user_agent="bristol_geocoder_v1")
geocode_rev = RateLimiter(geolocator.reverse, min_delay_seconds=1.1)
geocode_fwd = RateLimiter(geolocator.geocode, min_delay_seconds=1.1)


# ═══════════════════════════════════════════════════════════════════════════════
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ═══════════════════════════════════════════════════════════════════════════════

def load_city_dict(path=DICT_FILE):
    try:
        df = pd.read_excel(path, usecols=["city", "region_name"]).dropna()
        d  = dict(zip(df["city"].str.strip(), df["region_name"].str.strip()))
        print(f"  Справочник: {len(d)} городов")
        return d
    except FileNotFoundError:
        print(f"  Справочник не найден: {path}")
        return {}


def parse_region(address: str) -> str:
    """Вытаскивает регион из строки Nominatim."""
    if not address:
        return ""
    parts = [p.strip() for p in address.split(",")]
    for part in parts:
        pl = part.lower()
        if any(ex in pl for ex in ["федеральный", "муниципальный", "россия"]):
            continue
        if part.isdigit():
            continue
        if any(kw in pl for kw in ["область", "край", "республика",
                                    "автономный округ", "автономная область"]):
            return part
        if part in ("Москва", "Санкт-Петербург", "Севастополь"):
            return part
    return ""


def region_from_dict(address: str, city_dict: dict) -> str:
    """Ищет город из строки адреса в справочнике."""
    if not address or not city_dict:
        return ""
    parts = [p.strip() for p in address.split(",")]
    for part in parts:
        if any(kw in part.lower() for kw in [
            "федеральный", "поселение", "район", "округ", "россия",
            "улица", "проспект", "переулок", "шоссе", "бульвар",
            "набережная", "площадь", "тракт", "бристоль"
        ]):
            continue
        if part.isdigit() or len(part) < 3 or re.match(r'^\d', part):
            continue
        if part in city_dict:
            return city_dict[part]
        no_yo = part.replace("ё", "е")
        if no_yo in city_dict:
            return city_dict[no_yo]
    return ""


def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_progress(done: dict):
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(done, f, ensure_ascii=False)


def load_excel() -> pd.DataFrame:
    if not os.path.exists(OUTPUT_FILE):
        print(f"ОШИБКА: файл {OUTPUT_FILE} не найден!")
        sys.exit(1)
    df = pd.read_excel(OUTPUT_FILE)
    print(f"Загружено строк: {len(df)}")
    return df


def save_excel(df: pd.DataFrame):
    df = df.sort_values("region")
    df.to_excel(OUTPUT_FILE, index=False)
    print(f"✓ Сохранено → {OUTPUT_FILE}")


def empty_mask(df: pd.DataFrame):
    return df["region"].isna() | df["region"].astype(str).str.strip().isin(["", "???"])


# ═══════════════════════════════════════════════════════════════════════════════
# РЕЖИМ 1: Основной геокодинг координат (Nominatim)
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    with open(INPUT_FILE, encoding="utf-8") as f:
        data = json.load(f)

    city_dict = load_city_dict()
    opened    = [s for s in data if s.get("store_status") == "opened"]
    total     = len(opened)
    print(f"Открытых магазинов: {total}")

    done = load_progress()
    print(f"Уже обработано:     {len(done)}\n")

    errors = 0

    for i, item in enumerate(opened, 1):
        sid = str(item["id"])
        lat = item.get("lat")
        lon = item.get("lon")

        if sid in done:
            continue

        print(f"[{i:4}/{total}] {lat}, {lon}", end=" → ", flush=True)

        try:
            location = geocode_rev((lat, lon), language="ru")
            address  = location.address if location else ""

            region = parse_region(address)
            if not region:
                region = region_from_dict(address, city_dict)

            done[sid] = {
                "id": item["id"], "lat": lat, "lon": lon,
                "address": address, "region": region,
            }
            print(f"{region or '???'} | {address[:55]}")
            errors = 0

        except Exception as e:
            print(f"ОШИБКА: {e}")
            errors += 1
            if errors >= 5:
                print("Слишком много ошибок — сохраняем и выходим")
                save_progress(done)
                break
            time.sleep(5)
            continue

        if len(done) % 50 == 0:
            save_progress(done)
            rem = total - len(done)
            print(f"  💾 {len(done)}/{total} | осталось ~{rem//60}м {rem%60}с")

    save_progress(done)
    rows = list(done.values())
    df   = pd.DataFrame(rows, columns=["id", "region", "address", "lat", "lon"])
    save_excel(df)
    print(f"Итого: {len(done)}/{total}")

    if len(done) >= total and os.path.exists(PROGRESS_FILE):
        os.remove(PROGRESS_FILE)
        print("✓ Прогресс удалён — всё готово!")


# ═══════════════════════════════════════════════════════════════════════════════
# РЕЖИМ 2: fix — справочник городов (без интернета, мгновенно)
# ═══════════════════════════════════════════════════════════════════════════════

def fix_with_dict():
    print("\n=== Режим: справочник ===")
    city_dict = load_city_dict()
    if not city_dict:
        return

    df    = load_excel()
    mask  = empty_mask(df)
    empty = df[mask]
    print(f"Строк без региона: {len(empty)}\n")

    if len(empty) == 0:
        print("Все регионы уже заполнены!")
        return

    fixed = 0
    for idx, row in empty.iterrows():
        address = str(row.get("address", ""))
        region  = parse_region(address) or region_from_dict(address, city_dict)
        if region:
            df.at[idx, "region"] = region
            fixed += 1
            print(f"  ✓ {region} ← {address[:65]}")
        else:
            print(f"  ? {address[:65]}")

    print(f"\nИсправлено: {fixed}/{len(empty)}")
    save_excel(df)


# ═══════════════════════════════════════════════════════════════════════════════
# РЕЖИМ 3: fix2 — Nominatim по адресной строке
# ═══════════════════════════════════════════════════════════════════════════════

def fix_by_address():
    print("\n=== Режим: Nominatim по адресу ===")
    city_dict = load_city_dict()

    df    = load_excel()
    mask  = empty_mask(df)
    empty = df[mask]
    total = len(empty)
    print(f"Строк без региона: {total}\n")

    if total == 0:
        print("Все регионы уже заполнены!")
        return

    fixed = 0
    for i, (idx, row) in enumerate(empty.iterrows(), 1):
        address = str(row.get("address", ""))
        if not address or address == "nan":
            continue

        # Вытаскиваем город из строки адреса
        city = ""
        for part in [p.strip() for p in address.split(",")]:
            pl = part.lower()
            if any(kw in pl for kw in [
                "улица", "проспект", "переулок", "шоссе", "бульвар",
                "набережная", "площадь", "тупик", "федеральный",
                "поселение", "россия", "бристоль", "район"
            ]):
                continue
            if part.isdigit() or len(part) < 3 or re.match(r'^\d', part):
                continue
            city = part
            break

        print(f"  [{i:4}/{total}] '{city}'", end=" → ", flush=True)

        # Сначала справочник
        region = city_dict.get(city) or city_dict.get(city.replace("ё", "е"), "")

        if region:
            print(f"[справочник] {region}")
        else:
            try:
                loc = geocode_fwd(f"{city}, Россия", language="ru", country_codes="ru")
                if loc:
                    rev    = loc.raw.get("display_name", "")
                    region = parse_region(rev) or region_from_dict(rev, city_dict)
                    print(f"[nominatim] {region or '???'}")
                else:
                    print("не найдено")
            except Exception as e:
                print(f"ошибка: {e}")
                time.sleep(3)
                continue

        if region:
            df.at[idx, "region"] = region
            fixed += 1

    print(f"\nИсправлено: {fixed}/{total}")
    save_excel(df)


# ═══════════════════════════════════════════════════════════════════════════════
# РЕЖИМ 4: yandex — Яндекс геокодер
# ═══════════════════════════════════════════════════════════════════════════════

def fix_with_yandex(api_key: str):
    print("\n=== Режим: Яндекс геокодер ===")

    df    = load_excel()
    mask  = empty_mask(df)
    empty = df[mask]
    total = len(empty)
    print(f"Строк без региона: {total}\n")

    if total == 0:
        print("Все регионы уже заполнены!")
        return

    fixed  = 0
    errors = 0

    for i, (idx, row) in enumerate(empty.iterrows(), 1):
        lat = row.get("lat", "")
        lon = row.get("lon", "")

        # Яндекс: координаты в формате "lon,lat"
        query = f"{lon},{lat}" if lat and lon else str(row.get("address", ""))
        print(f"  [{i:4}/{total}] {query[:60]}", end=" → ", flush=True)

        try:
            r = req.get(
                "https://geocode-maps.yandex.ru/1.x/",
                params={
                    "apikey":  api_key,
                    "geocode": query,
                    "format":  "json",
                    "results": 1,
                    "lang":    "ru_RU",
                },
                timeout=10
            )
            members = (r.json()["response"]["GeoObjectCollection"]["featureMember"])

            region = ""
            if members:
                comps = (members[0]["GeoObject"]["metaDataProperty"]
                         ["GeocoderMetaData"]["Address"]["Components"])
                for comp in comps:
                    if comp.get("kind") == "province":
                        region = comp.get("name", "")
                        break

            if region:
                df.at[idx, "region"] = region
                fixed += 1
                errors = 0
                print(f"✓ {region}")
            else:
                print("не найдено")

        except Exception as e:
            print(f"ОШИБКА: {e}")
            errors += 1
            if errors >= 10:
                print("Слишком много ошибок — останавливаемся")
                break
            time.sleep(2)
            continue

        time.sleep(0.2)  # Яндекс: до 5 req/сек

    print(f"\nИсправлено: {fixed}/{total}")
    save_excel(df)


# ═══════════════════════════════════════════════════════════════════════════════
# РЕЖИМ 5: dadata — DaData (10 000 запросов/день бесплатно)
# ═══════════════════════════════════════════════════════════════════════════════

def fix_with_dadata(token: str, secret: str):
    """
    Использует библиотеку dadata-py.
    Установка: pip install dadata
    Токен и секрет берём из личного кабинета dadata.ru
    """
    print("\n=== Режим: DaData ===")

    try:
        from dadata import Dadata
    except ImportError:
        print("ОШИБКА: установите библиотеку: pip install dadata")
        return

    df    = load_excel()
    mask  = empty_mask(df)
    empty = df[mask]
    total = len(empty)
    print(f"Строк без региона: {total}\n")

    if total == 0:
        print("Все регионы уже заполнены!")
        return

    fixed  = 0
    errors = 0

    with Dadata(token, secret) as dadata:
        for i, (idx, row) in enumerate(empty.iterrows(), 1):
            address = str(row.get("address", ""))
            if not address or address == "nan":
                continue

            print(f"  [{i:4}/{total}] {address[:60]}", end=" → ", flush=True)

            try:
                result = dadata.clean("address", address)

                if not result:
                    print("пустой ответ")
                    continue

                region = (result.get("region_with_type", "")
                          or result.get("region", ""))
                qc     = result.get("qc", -1)  # 0=точно, 1=с допущением, 2=не найдено

                if region and qc in (0, 1):
                    df.at[idx, "region"] = region
                    fixed += 1
                    errors = 0
                    print(f"✓ {region}")
                else:
                    print(f"? не найдено (qc={qc})")

            except Exception as e:
                print(f"ОШИБКА: {e}")
                errors += 1
                if errors >= 10:
                    print("Слишком много ошибок — останавливаемся")
                    break
                time.sleep(2)
                continue

            time.sleep(0.11)  # DaData: до 10 req/сек

    print(f"\nИсправлено через DaData: {fixed}/{total}")
    save_excel(df)


# ═══════════════════════════════════════════════════════════════════════════════
# ТОЧКА ВХОДА
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    args = sys.argv[1:]

    if not args:
        main()
    elif args[0] == "fix":
        fix_with_dict()
    elif args[0] == "fix2":
        fix_by_address()
    elif args[0] == "yandex" and len(args) > 1:
        fix_with_yandex(args[1])
    elif args[0] == "dadata" and len(args) > 2:
        fix_with_dadata(args[1], args[2])
    elif args[0] == "dadata":
        print("Укажите токен и секрет:")
        print("  python geocode_bristol.py dadata ТОКЕН СЕКРЕТ")
    else:
        print("Использование:")
        print("  python geocode_bristol.py               # геокодинг координат")
        print("  python geocode_bristol.py fix           # справочник городов")
        print("  python geocode_bristol.py fix2          # Nominatim по адресу")
        print("  python geocode_bristol.py yandex КЛЮЧ  # Яндекс геокодер")
        print("  python geocode_bristol.py dadata ТОКЕН СЕКРЕТ  # DaData")