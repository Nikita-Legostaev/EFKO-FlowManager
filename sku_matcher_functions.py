"""
sku_matcher_functions.py
Логика матчинга SKU — без GUI, импортируется из main.py
"""

import re
from pathlib import Path
import pandas as pd
import openpyxl

# ─── Соусные бренды (автодобавление при наличии слова «соус») ─────────────────

SAUCE_BRANDS = {
    # Хайнц
    "хайнц":             "Хайнц",
    "heinz":             "Хайнц",
    # Кальве
    "кальве":            "Кальве",
    "calve":             "Кальве",
    # Астория
    "астория":           "Астория",
    "astoria":           "Астория",
    # Махеев
    "махеев":            "Махеев",
    "makheev":           "Махеев",
    "maheev":            "Махеев",
    # Слобода
    "слобода":           "Слобода",
    "sloboda":           "Слобода",
    # Я люблю готовить
    "я люблю готовить":  "Я люблю готовить",
    # Рикко
    "рикко":             "Рикко",
    "mr ricco":          "Рикко",
    "ricco":             "Рикко",
    # Пикадор
    "пикадор":           "Пикадор",
    "pikador":           "Пикадор",
}


def _match_sauce_brand(csv_brand: str) -> str | None:
    """
    Возвращает нормализованное название бренда из SAUCE_BRANDS,
    если csv_brand содержит хотя бы один ключ словаря. Иначе None.
    """
    bl = csv_brand.lower()
    for key, canonical in SAUCE_BRANDS.items():
        if key in bl:
            return canonical
    return None


# ─── Дескрипторы ──────────────────────────────────────────────────────────────

DESCRIPTORS = [
    "острый",
    "острая",
    "острое",
    "томатный",
    "томатная",
    "томатное",
    "оливковый",
    "оливковая",
    "классический",
    "классическая",
    "шашлычный",
    "шашлычная",
    "сладкий",
    "сладкая",
    "чесночный",
    "чесночная",
    "горчичный",
    "горчичная",
    "базилик",
    "укроп",
    "зелень",
    "копченый",
    "копченая",
    "барбекю",
    "bbq",
    "провансаль",
    "уральский",
    "уральская",
    "сметанный",
    "сметанная",
    "перепелиный",
    "перепелином",
    "новосибирский",
    "саратовский",
    "московский",
]


# ─── Алгоритм сходства ────────────────────────────────────────────────────────


def extract_weight(s: str):
    matches = re.findall(
        r"(\d+(?:[.,]\d+)?)\s*(мл|мг|кг|л(?=[^а-яёa-z]|$)|г(?=[^а-яёa-z]|$)|kg|ml|mg|lb)",
        s,
        re.IGNORECASE,
    )
    if not matches:
        return None
    vals = []
    for num_str, unit in matches:
        num = float(num_str.replace(",", "."))
        u = unit.lower()
        if u == "л":
            num *= 1000
        if u in ("кг", "kg"):
            num *= 1000
        vals.append(num)
    return max(vals)


def weight_penalty(a: str, b: str) -> float:
    wa, wb = extract_weight(a), extract_weight(b)
    if wa is None or wb is None:
        return 1.0
    return (min(wa, wb) / max(wa, wb)) ** 2


def descriptor_penalty(a: str, b: str) -> float:
    al, bl = a.lower(), b.lower()
    da = {d for d in DESCRIPTORS if d in al}
    db = {d for d in DESCRIPTORS if d in bl}
    if not da and not db:
        return 1.0
    conflicts = len(da - db) + len(db - da)
    return max(0.3, 1 - conflicts * 0.15)


def levenshtein_ratio(a: str, b: str) -> float:
    a, b = a.lower(), b.lower()
    if a == b:
        return 1.0
    la, lb = len(a), len(b)
    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        curr = [i] + [0] * lb
        for j in range(1, lb + 1):
            curr[j] = (
                prev[j - 1]
                if a[i - 1] == b[j - 1]
                else 1 + min(prev[j], curr[j - 1], prev[j - 1])
            )
        prev = curr
    return 1 - prev[lb] / max(la, lb)


def similarity(a: str, b: str) -> float:
    return levenshtein_ratio(a, b) * weight_penalty(a, b) * descriptor_penalty(a, b)


# ─── Основной пайплайн ────────────────────────────────────────────────────────


def run_matching(
    ref_path: str, csv_folder: str, threshold: float, on_progress, on_done
):
    """
    Запускается в отдельном потоке.
    on_progress(msg: str)
    on_done(results: list[dict], error: str | None)
    """
    try:
        wb = openpyxl.load_workbook(ref_path)
        ws = wb["SKU"] if "SKU" in wb.sheetnames else wb.active
        ref_rows = [list(row) for row in ws.iter_rows(min_row=2, values_only=True)]

        indicative = [r for r in ref_rows if r[4] == "индикативное"]
        existing = {r[2] for r in ref_rows if r[2]}
        on_progress(
            f"Справочник: {len(ref_rows)} строк, индикативных: {len(indicative)}"
        )

        csv_files = list(Path(csv_folder).glob("*.csv"))
        if not csv_files:
            on_done([], error="В папке нет CSV файлов")
            return

        frames = []
        for f in csv_files:
            try:
                df = pd.read_csv(f)
                if "pd_sku" not in df.columns:
                    on_progress(f"⚠ Пропущен {f.name} — нет pd_sku")
                    continue
                cols = [c for c in ["pd_sku", "brand", "category"] if c in df.columns]
                frames.append(df[cols].drop_duplicates("pd_sku"))
                on_progress(f"→ {f.name}: {len(df)} строк")
            except Exception as e:
                on_progress(f"⚠ Ошибка {f.name}: {e}")

        if not frames:
            on_done([], error="Ни один CSV не подошёл")
            return

        all_skus = pd.concat(frames).drop_duplicates("pd_sku")
        new_skus = all_skus[~all_skus["pd_sku"].isin(existing)]
        on_progress(f"Новых SKU для матчинга: {len(new_skus)}")

        results = []
        sauce_auto = 0
        total = len(new_skus)

        for idx, (_, row) in enumerate(new_skus.iterrows()):
            csv_sku = row["pd_sku"]
            csv_brand = str(row.get("brand", "")).lower()

            # ── Авто-добавление соусов ────────────────────────────────────────
            # Условие: слово «соус» есть в названии SKU И бренд входит в список
            if "соус" in csv_sku.lower():
                canonical_brand = _match_sauce_brand(csv_brand)
                if canonical_brand:
                    results.append(
                        {
                            "Категория":        "Соус",
                            "Бренд":            canonical_brand,
                            "Наименование SKU": csv_sku,
                            "Совпало с":        "",        # пропускаем
                            "SKU скорр":        "",        # пропускаем
                            "Статус SKU":       "индикативное",
                            "Уверенность":      1.0,
                        }
                    )
                    sauce_auto += 1
                    if idx % 20 == 0:
                        on_progress(f"Обработано: {idx + 1}/{total}...")
                    continue  # не гоним через similarity-матчинг

            # ── Обычный матчинг по similarity ─────────────────────────────────
            best_score, best_ind = 0.0, None
            for ind in indicative:
                if csv_brand and csv_brand != "nan":
                    ind_brand = str(ind[1] or "").lower()
                    if ind_brand not in csv_brand and csv_brand not in ind_brand:
                        continue
                score = similarity(csv_sku, str(ind[2] or ""))
                if score > best_score:
                    best_score, best_ind = score, ind

            if best_score >= threshold and best_ind:
                results.append(
                    {
                        "Категория":        best_ind[0],
                        "Бренд":            best_ind[1],
                        "Наименование SKU": csv_sku,
                        "Совпало с":        best_ind[2],
                        "SKU скорр":        best_ind[3],
                        "Статус SKU":       "индикативное",
                        "Уверенность":      round(best_score, 2),
                    }
                )

            if idx % 20 == 0:
                on_progress(f"Обработано: {idx + 1}/{total}...")

        on_progress(f"Соусов добавлено автоматически: {sauce_auto}")
        results.sort(key=lambda x: -x["Уверенность"])
        on_done(results)

    except Exception as e:
        on_done([], error=str(e))


# ─── Сохранение ───────────────────────────────────────────────────────────────


def save_to_reference(selected_results: list, ref_path: str) -> int:
    """Дописывает выбранные строки в лист SKU справочника."""
    wb = openpyxl.load_workbook(ref_path)
    ws = wb["SKU"] if "SKU" in wb.sheetnames else wb.active

    if ws.cell(row=1, column=6).value != "Уверенность совпадения":
        ws.cell(row=1, column=6).value = "Уверенность совпадения"

    next_row = ws.max_row + 1
    for r in selected_results:
        ws.cell(row=next_row, column=1).value = r["Категория"]
        ws.cell(row=next_row, column=2).value = r["Бренд"]
        ws.cell(row=next_row, column=3).value = r["Наименование SKU"]
        ws.cell(row=next_row, column=4).value = r["SKU скорр"]
        ws.cell(row=next_row, column=5).value = r["Статус SKU"]
        ws.cell(row=next_row, column=6).value = r["Уверенность"]
        next_row += 1

    wb.save(ref_path)
    return len(selected_results)