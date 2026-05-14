# nielsen_functions.py
"""
Обработчик выгрузок Nielsen.
Полностью открыт для расширения: никаких хардкодов имён листов,
id-колонок или маппингов. Всё определяется автоматически из данных,
маппинги задаются в CATEGORY_MAPPINGS.
"""

import os
import re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── Паттерн даты в заголовках Nielsen ("MAR 21", "APR 22" и т.п.) ─────────────
_DATE_COL_RE = re.compile(r"^[A-Z]{3}\s+\d{2}$", re.IGNORECASE)

# ── Допустимые значения FACT ───────────────────────────────────────────────────
valid_FACT = [
    "Units (in 1000 PACKS)",
    "Volume (in 1000 LTR)",
    "Volume (in 1000 KG)",
    "Value (in 1000 RUR)",
    "Price (Unit)",
    "Price (Volume)",
    "Weighted Distribution (C)",
    "Numeric Distribution (C)",
    "Volume (in 1000 )",
]

# ── Маппинги по категории ──────────────────────────────────────────────────────
# Добавить новую категорию — добавить ключ в этот словарь.
# Каждый словарь верхнего уровня — это набор колонок с маппингами значений.
# Если для категории маппинг не нужен — просто не включай ключ.
CATEGORY_MAPPINGS: dict[str, dict[str, dict[str, str]]] = {
    "Масло": {
        "IF REFINED": {
            "NOT APPLICABLE":                          "рафинированное",
            "NOT REFINED":                             "нерафинированное",
            "REFINED":                                 "рафинированное",
            "REFINED & NOT REFINED (MIXED PACK)":      "рафинированное",
        },
        "PRODUCT BASE": {
            "ALMOND":                                  "прочие",
            "ALMOND & SUNFLOWER":                      "микс",
            "AMARANTH":                                "прочие",
            "AMARANTH & LINSEED":                      "прочие",
            "APRICOT KERNEL":                          "прочие",
            "ARGAN":                                   "прочие",
            "AVOCADO":                                 "прочие",
            "AVOCADO & COCONUT":                       "прочие",
            "AVOCADO & OLIVE":                         "прочие",
            "AVOCADO & SUNFLOWER":                     "микс",
            "BLACK CUMIN SEED":                        "прочие",
            "BLACK SESAME":                            "прочие",
            "CAMELINA (RYZHIK)":                       "прочие",
            "CANOLA SEED":                             "прочие",
            "CEDAR NUT":                               "прочие",
            "CEDAR NUT & LINSEED":                     "прочие",
            "CEDAR NUT & LINSEED & SESAME & SUNFLOWER":"прочие",
            "CEDAR NUT & PEANUT & WALNUT":             "прочие",
            "CEDAR NUT & SUNFLOWER":                   "микс",
            "CEREAL & FRUIT":                          "прочие",
            "CHIA SEED":                               "прочие",
            "CHIA SEED & SUNFLOWER":                   "прочие",
            "COCOA":                                   "прочие",
            "COCONUT":                                 "прочие",
            "COCONUT & PALM":                          "прочие",
            "COLESEED":                                "прочие",
            "CORN":                                    "кукурузное",
            "CORN & SUNFLOWER":                        "микс",
            "CORN GERM":                               "кукурузное",
            "CORN SEEDS & GRAPE SEEDS & RAPE SEEDS & RICE BRAN & SESAME": "прочие",
            "COTTON":                                  "прочие",
            "CUMIN SEED":                              "прочие",
            "GRAPE SEEDS":                             "прочие",
            "GRAPE SEEDS & SUNFLOWER":                 "микс",
            "HAZELNUT":                                "прочие",
            "HEMP":                                    "прочие",
            "HEMP & LINSEED":                          "прочие",
            "HEMP & SUNFLOWER":                        "прочие",
            "LINSEED":                                 "прочие",
            "LINSEED & MUSTARD & SUNFLOWER":           "прочие",
            "LINSEED & OLIVE":                         "прочие",
            "LINSEED & PUMPKIN SEEDS":                 "прочие",
            "LINSEED & SESAME":                        "прочие",
            "LINSEED & SUNFLOWER":                     "микс",
            "LINSEED & WALNUT":                        "прочие",
            "MACADAMIA NUT":                           "прочие",
            "MIX OIL":                                 "прочие",
            "MUSTARD":                                 "прочие",
            "MUSTARD & SUNFLOWER":                     "прочие",
            "MUSTARD & SUNFLOWER & WALNUT":            "прочие",
            "NUT":                                     "прочие",
            "OLIVE":                                   "оливковое",
            "OLIVE & PUMPKIN":                         "прочие",
            "OLIVE & RAPE SEED":                       "прочие",
            "OLIVE & SESAME":                          "прочие",
            "OLIVE OIL & SUNFLOWER":                   "микс",
            "PALM":                                    "прочие",
            "PEANUT":                                  "прочие",
            "PISTACHIO":                               "прочие",
            "POPPY SEED":                              "прочие",
            "PUMPKIN SEEDS":                           "прочие",
            "RAPE SEED & SUNFLOWER":                   "микс",
            "RAPE SEEDS":                              "прочие",
            "RAPE SEEDS & SAFFLOWER & SUNFLOWER":      "прочие",
            "RICE":                                    "прочие",
            "ROSEHIP":                                 "прочие",
            "RUCCOLA SEED":                            "прочие",
            "SAFFLOWER":                               "прочие",
            "SEA BUCKTHORN & SUNFLOWER":               "микс",
            "SEABERRY / SEA BUCKTHORN":                "прочие",
            "SESAME":                                  "прочие",
            "SOYA":                                    "прочие",
            "SUNFLOWER":                               "подсолнечное",
            "SUNFLOWER & SESAME":                      "микс",
            "SUNFLOWER & SOYA":                        "микс",
            "SUNFLOWER & WALNUT":                      "микс",
            "THISTLE SEEDS (RASTOROPSHA)":             "прочие",
            "TRIGONELLA":                              "прочие",
            "WALNUT (GRETSKIY OREKH)":                 "прочие",
            "WATERMELON SEEDS":                        "прочие",
            "WHEAT GERM":                              "прочие",
            "WHITE SESAME":                            "прочие",
        },
    },
    # ── Кетчуп ────────────────────────────────────────────────────────────────
    # Пока маппинги не нужны — значения передаются как есть.
    # Чтобы добавить маппинг, просто добавь ключ с именем колонки:
    # "Кетчуп": {
    #     "PRODUCT BASE": {"TOMATO": "томат", ...},
    # },
    "Кетчуп": {},
}


# ── Вспомогательные функции ────────────────────────────────────────────────────

def _max_workers() -> int:
    return min(4, os.cpu_count() or 2)


def _is_date_col(name: str) -> bool:
    """True если колонка — период Nielsen («MAR 21», «APR 22»)."""
    return bool(_DATE_COL_RE.match(str(name).strip()))


def _detect_sheets(wb_sheet_names: list[str]) -> dict[str, list[str]]:
    """
    Автоматически раскладывает листы книги по ролям:
      sku      — листы с данными SKU (все листы, начинающиеся с «SKU»)
      brand    — листы с данными BRAND
      man      — листы с данными MANUFACTURER / MAN
    Регистронезависимо.
    """
    result: dict[str, list[str]] = {"sku": [], "brand": [], "man": []}
    for name in wb_sheet_names:
        nl = name.strip().upper()
        if nl.startswith("SKU"):
            result["sku"].append(name)
        elif nl.startswith("BRAND"):
            result["brand"].append(name)
        elif nl.startswith("MAN"):
            result["man"].append(name)
    return result


def _cache_dir_for(input_file: str, base_cache_dir: Path) -> Path:
    """
    Возвращает уникальную подпапку кэша для конкретного файла.
    Ключ = хэш от абсолютного пути + времени изменения файла.
    При изменении файла или смене категории кэш не смешивается.
    """
    import hashlib
    mtime = os.path.getmtime(input_file)
    key = f"{os.path.abspath(input_file)}|{mtime}"
    digest = hashlib.md5(key.encode()).hexdigest()[:12]
    cache_path = base_cache_dir / digest
    cache_path.mkdir(parents=True, exist_ok=True)
    return cache_path


def _cleanup_old_caches(base_cache_dir: Path, keep: str, log):
    """
    Удаляет все кэш-папки кроме текущей (keep).
    Вызывается после успешного запуска.
    """
    if not base_cache_dir.exists():
        return
    for entry in base_cache_dir.iterdir():
        if entry.is_dir() and entry.name != keep:
            import shutil
            try:
                shutil.rmtree(entry)
                log(f"🗑 Старый кэш удалён: {entry.name}")
            except Exception as e:
                log(f"⚠ Не удалось удалить кэш {entry.name}: {e}")


def make_unique_columns(columns):
    seen = {}
    new_cols = []
    for col in columns:
        col = col or "Unnamed"
        if col in seen:
            seen[col] += 1
            new_cols.append(f"{col}_{seen[col]}")
        else:
            seen[col] = 0
            new_cols.append(col)
    return new_cols


def load_sheet(sheet_name: str, input_file: str, cache_dir: Path, log):
    import polars as pl

    cache_file = cache_dir / f"{sheet_name}.parquet"
    if cache_file.exists():
        log(f"Из кэша → {sheet_name}")
        return sheet_name, pl.read_parquet(cache_file)

    log(f"Читаем Excel → {sheet_name}")
    df = pl.read_excel(
        source=input_file,
        sheet_name=sheet_name,
        engine="calamine",
        infer_schema_length=100_000,
    )
    df = df.rename(dict(zip(df.columns, make_unique_columns(df.columns))))
    df = df.drop([c for c in df.columns if str(c).startswith("Unnamed")])
    df = df.filter(~pl.all_horizontal(pl.all().is_null()))
    df.write_parquet(cache_file, compression="zstd")
    return sheet_name, df


def _split_id_date(df) -> tuple[list[str], list[str]]:
    """
    Делит колонки датафрейма на id-колонки (измерения) и date-колонки (периоды).
    Date-колонки определяются по паттерну «MMM YY».
    """
    id_cols  = [c for c in df.columns if not _is_date_col(c)]
    date_cols = [c for c in df.columns if _is_date_col(c)]
    return id_cols, date_cols


def melt_polars(df, id_cols: list[str]):
    import polars as pl

    date_cols = [c for c in df.columns if c not in id_cols]
    date_mapping = {}
    for col in date_cols:
        cleaned = col.strip().upper()
        parts = cleaned.split()
        if (
            len(parts) == 2
            and len(parts[0]) == 3
            and parts[1].isdigit()
            and len(parts[1]) == 2
        ):
            date_str = f"{parts[0]} {parts[1]} 1"
            parsed = pl.Series([date_str]).str.to_date("%b %y %d", strict=False)[0]
            date_mapping[col] = (
                parsed.strftime("%d.%m.%Y") if parsed is not None else None
            )
        else:
            date_mapping[col] = None

    return (
        df.unpivot(
            index=id_cols, on=date_cols, variable_name="ATTRIBUTE", value_name="VALUE"
        )
        .with_columns(
            pl.col("ATTRIBUTE")
            .replace_strict(date_mapping, default=None)
            .alias("ATTRIBUTE")
        )
        .filter(pl.col("VALUE").is_not_null())
    )


def optimize_for_size(df):
    """
    Оптимизирует датафрейм для сжатия: все строковые колонки → Categorical,
    VALUE → Float32. Работает для любого набора колонок, не зависит от категории.
    """
    import polars as pl

    for col in df.columns:
        if df[col].dtype == pl.Utf8 or df[col].dtype == pl.String:
            df = df.with_columns(pl.col(col).cast(pl.Categorical("lexical")))
    if "VALUE" in df.columns:
        df = df.with_columns(pl.col("VALUE").round(4).cast(pl.Float32))
    return df


def save_optimized(df, name: str, output_dir: Path, fmt: str, log, stop_event):
    import polars as pl

    if stop_event.is_set():
        return
    log(f"Сохранение {name}...")
    df = df.with_columns([pl.col(pl.Utf8).str.strip_chars()])

    if fmt == "csv":
        path = output_dir / f"{name}.csv"
        df = df.with_columns(
            pl.col("VALUE")
            .cast(pl.Utf8)
            .str.replace(".", ",", literal=True)
            .alias("VALUE")
        )
        df.write_csv(
            path,
            separator=";",
            include_bom=True,
            quote_style="necessary",
            null_value="",
        )
        size_mb = path.stat().st_size / (1024**2)
        log(f"✓ {name}.csv — {size_mb:.1f} МБ")

    elif fmt == "excel":
        max_rows = 1_048_575
        num_parts = (len(df) + max_rows - 1) // max_rows
        if num_parts > 1:
            for i in range(num_parts):
                if stop_event.is_set():
                    return
                chunk = df.slice(i * max_rows, max_rows)
                chunk.write_excel(
                    output_dir / f"{name}_part{i + 1}.xlsx", worksheet="Data"
                )
            log(f"✓ {name} разбит на {num_parts} файлов .xlsx ({len(df)} строк)")
        else:
            df.write_excel(output_dir / f"{name}.xlsx", worksheet="Data")
            log(f"✓ {name}.xlsx сохранён ({len(df)} строк)")


def _apply_mappings(df, category: str, log):
    """
    Применяет маппинги из CATEGORY_MAPPINGS для заданной категории.
    Колонки, которых нет в датафрейме — пропускаются без ошибок.
    Категории без маппинга — возвращают df без изменений.
    """
    import polars as pl

    mappings = CATEGORY_MAPPINGS.get(category, {})
    if not mappings:
        return df

    transforms = []
    for col, mapping in mappings.items():
        if col not in df.columns:
            log(f"  ⚠ Колонка «{col}» не найдена в данных — маппинг пропущен")
            continue
        default = mapping.get("__default__", None)
        clean_map = {k: v for k, v in mapping.items() if k != "__default__"}
        transforms.append(
            pl.col(col)
            .cast(pl.Utf8)
            .str.strip_chars()
            .str.to_uppercase()
            .replace_strict(clean_map, default=default)
            .alias(col)
        )

    if transforms:
        df = df.with_columns(transforms)
    return df


# ── Основная функция ───────────────────────────────────────────────────────────

def process_nielsen(
    input_file: str,
    output_dir_str: str,
    fmt: str,
    log,
    messagebox,
    stop_event,
    category: str,
):
    import polars as pl
    import openpyxl

    if not input_file or not os.path.isfile(input_file):
        log("Входной файл Nielsen не выбран!")
        messagebox.showwarning("Ошибка", "Выберите входной файл Nielsen")
        return
    if not output_dir_str or not os.path.isdir(output_dir_str):
        log("Папка сохранения не выбрана!")
        messagebox.showwarning("Ошибка", "Выберите папку сохранения")
        return

    output_dir = Path(output_dir_str)
    base_cache_dir = output_dir / "cache"
    base_cache_dir.mkdir(exist_ok=True)

    # Кэш привязан к конкретному файлу (путь + mtime) — смена файла = новый кэш
    cache_dir = _cache_dir_for(input_file, base_cache_dir)
    log(f"Кэш: {cache_dir.name}")

    # ── Автоопределение листов ─────────────────────────────────────────────────
    wb_meta = openpyxl.load_workbook(input_file, read_only=True, data_only=True)
    sheet_roles = _detect_sheets(wb_meta.sheetnames)
    wb_meta.close()

    if not sheet_roles["sku"]:
        log("❌ Не найдено ни одного листа SKU в файле")
        messagebox.showwarning("Ошибка", "В файле не найдено листов SKU*")
        return

    log(f"Листы SKU: {sheet_roles['sku']}")
    log(f"Листы BRAND: {sheet_roles['brand']}")
    log(f"Листы MAN: {sheet_roles['man']}")
    log(f"Категория: {category}")
    if category not in CATEGORY_MAPPINGS:
        log(f"  ℹ Категория «{category}» не в CATEGORY_MAPPINGS — значения передаются без маппинга")

    data = {}

    # ── Загружаем ВСЕ листы параллельно (SKU + BRAND + MAN) ──────────────────
    all_sheets = sheet_roles["sku"] + sheet_roles["brand"] + sheet_roles["man"]
    log(f"Загрузка {len(all_sheets)} листов параллельно...")
    with ThreadPoolExecutor(max_workers=_max_workers()) as executor:
        futures = {
            executor.submit(load_sheet, sheet, input_file, cache_dir, log): sheet
            for sheet in all_sheets
        }
        for future in as_completed(futures):
            if stop_event.is_set():
                log("Обработка Nielsen остановлена")
                return
            name, df = future.result()
            data[name] = df

    if stop_event.is_set():
        return

    # ── Объединение SKU-листов ─────────────────────────────────────────────────
    sku_frames = [data[s] for s in sheet_roles["sku"] if s in data]
    df_sku = pl.concat(sku_frames, how="diagonal") if len(sku_frames) > 1 else sku_frames[0]

    # Собираем задачи на melt: (output_key, dataframe, role_label)
    melt_tasks: list[tuple[str, object, str]] = []

    for role, label in [("man", "MAN"), ("brand", "BRAND")]:
        sheets = sheet_roles[role]
        if not sheets:
            log(f"⚠ Листов {label} не найдено — пропуск")
            continue
        frames = [data[s] for s in sheets if s in data]
        df_role = pl.concat(frames, how="diagonal") if len(frames) > 1 else frames[0]
        melt_tasks.append((f"{label}_long", df_role, label))

    id_cols_sku, _ = _split_id_date(df_sku)
    log(f"SKU id-колонок: {len(id_cols_sku)}: {id_cols_sku}")
    melt_tasks.append(("SKU_long", df_sku, "SKU"))

    # ── Melt всех ролей параллельно ────────────────────────────────────────────
    def _melt_task(key: str, df, label: str):
        id_cols, _ = _split_id_date(df)
        log(f"Обработка {label} (melt {len(df)} строк × {len(id_cols)} id-колонок)...")
        melted = melt_polars(df, id_cols)
        log(f"  ✓ {label}: {len(melted)} строк после melt")
        return key, melted, id_cols

    results = {}
    with ThreadPoolExecutor(max_workers=_max_workers()) as executor:
        futures = {
            executor.submit(_melt_task, key, df, label): key
            for key, df, label in melt_tasks
        }
        for future in as_completed(futures):
            if stop_event.is_set():
                log("⛔ Остановлено во время melt")
                return
            key, melted, id_cols = future.result()
            results[key] = (melted, id_cols)

    if stop_event.is_set():
        return

    # ── Фильтр по FACT + маппинги + unique — только для SKU ──────────────────
    df_sku_long, id_cols_sku = results.pop("SKU_long")
    df_sku_filtered = df_sku_long.filter(pl.col("FACT").is_in(valid_FACT))
    df_sku_filtered = _apply_mappings(df_sku_filtered, category, log)
    df_sku_unique   = df_sku_filtered.unique(subset=id_cols_sku + ["ATTRIBUTE"])

    # ── Оптимизация и сохранение ───────────────────────────────────────────────
    to_save = {"SKU_long_unique": optimize_for_size(df_sku_unique)}
    for key, (df_role, _) in results.items():
        label = key.replace("_long", "")
        to_save[f"{label}_long"] = optimize_for_size(df_role)

    for name, df in to_save.items():
        if stop_event.is_set():
            log("⛔ Сохранение остановлено пользователем")
            return
        save_optimized(df, name, output_dir, fmt, log, stop_event)

    log(f"Готово! Файлы сохранены в формате {fmt.upper()}")
    _cleanup_old_caches(base_cache_dir, keep=cache_dir.name, log=log)
    messagebox.showinfo("Готово", "Обработка Nielsen завершена!")