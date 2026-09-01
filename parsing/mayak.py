"""Диагностика Яндекс Places API. Запустите и пришлите вывод."""
import sys, requests

api_key = sys.argv[1] if len(sys.argv) > 1 else "ВАШ_КЛЮЧ"

# Пробуем разные endpoints
tests = [
    ("search-maps", "https://search-maps.yandex.ru/v1/", {
        "apikey": api_key, "text": "гипермаркет МАЯК Москва",
        "lang": "ru_RU", "type": "biz", "results": 5,
    }),
    ("geocode", "https://geocode-maps.yandex.ru/1.x/", {
        "apikey": api_key, "geocode": "гипермаркет МАЯК Москва",
        "format": "json", "results": 5,
    }),
]

for name, url, params in tests:
    r = requests.get(url, params=params, timeout=10)
    print(f"\n=== {name} ===")
    print(f"Status: {r.status_code}")
    print(f"Ответ: {r.text[:300]}")