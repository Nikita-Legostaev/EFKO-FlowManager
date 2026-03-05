# nielsen_functions.py
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# Тяжёлые библиотеки — ленивый импорт (polars грузится только при вызове process_nielsen)

small_sheets = ["MAN", "BRAND"]
large_sheets = ["SKU1", "SKU2"]

valid_FACT = [
    "Units (in 1000 PACKS)",
    "Volume (in 1000 LTR)",
    "Value (in 1000 RUR)",
    "Price (Unit)",
    "Price (Volume)",
    "Weighted Distribution (C)",
    "Numeric Distribution (C)",
    "Volume (in 1000 )",
]


def _max_workers() -> int:
    return min(4, os.cpu_count() or 2)


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
    import polars as pl  # ленивый импорт

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
    import polars as pl

    cat_cols = [
        "MARKET",
        "FACT",
        "Long Description",
        "MANUFACTURER",
        "BRAND",
        "PRODUCT BASE",
        "QUALITY",
        "IF REFINED",
        "PACKAGE TYPE",
        "PACKAGING MATERIAL",
        "WEIGHT",
        "ITEM",
    ]
    for col in cat_cols:
        if col in df.columns:
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

    if not input_file or not os.path.isfile(input_file):
        log("Входной файл Nielsen не выбран!")
        messagebox.showwarning("Ошибка", "Выберите входной файл Nielsen")
        return
    if not output_dir_str or not os.path.isdir(output_dir_str):
        log("Папка сохранения не выбрана!")
        messagebox.showwarning("Ошибка", "Выберите папку сохранения")
        return

    output_dir = Path(output_dir_str)
    cache_dir = output_dir / "cache"
    cache_dir.mkdir(exist_ok=True)

    data = {}

    # Загрузка малых листов последовательно
    for sheet in small_sheets:
        if stop_event.is_set():
            log("Обработка Nielsen остановлена")
            return
        name, df = load_sheet(sheet, input_file, cache_dir, log)
        data[name] = df

    # Загрузка больших листов параллельно
    with ThreadPoolExecutor(max_workers=_max_workers()) as executor:
        futures = {
            executor.submit(load_sheet, sheet, input_file, cache_dir, log): sheet
            for sheet in large_sheets
        }
        for future in as_completed(futures):
            if stop_event.is_set():
                log("Обработка Nielsen остановлена")
                return
            name, df = future.result()
            data[name] = df

    if stop_event.is_set():
        return

    df_sku = pl.concat([data["SKU1"], data["SKU2"]], how="vertical")

    log("Обработка MAN...")
    id_cols_man = ["MARKET", "FACT", "Long Description", "MANUFACTURER"]
    data["MAN_long"] = melt_polars(data["MAN"], id_cols_man)

    if stop_event.is_set():
        return

    log("Обработка BRAND...")
    id_cols_brand = ["MARKET", "FACT", "Long Description", "MANUFACTURER", "BRAND"]
    data["BRAND_long"] = melt_polars(data["BRAND"], id_cols_brand)

    if stop_event.is_set():
        return

    log("Обработка SKU...")
    id_cols_sku = [
        "MARKET",
        "FACT",
        "Long Description",
        "MANUFACTURER",
        "BRAND",
        "PRODUCT BASE",
        "QUALITY",
        "IF REFINED",
        "PACKAGE TYPE",
        "PACKAGING MATERIAL",
        "WEIGHT",
        "ITEM",
    ]
    data["SKU_long"] = melt_polars(df_sku, id_cols_sku)

    if stop_event.is_set():
        return

    # Маппинги по категории
    if category == "Масло":
        refine_map = {
            "NOT APPLICABLE": "рафинированное",
            "NOT REFINED": "нерафинированное",
            "REFINED": "рафинированное",
            "REFINED & NOT REFINED (MIXED PACK)": "рафинированное",
        }
        product_base_map = {
            "ALMOND": "прочие",
            "ALMOND & SUNFLOWER": "микс",
            "AMARANTH": "прочие",
            "AMARANTH & LINSEED": "прочие",
            "APRICOT KERNEL": "прочие",
            "ARGAN": "прочие",
            "AVOCADO": "прочие",
            "AVOCADO & COCONUT": "прочие",
            "AVOCADO & OLIVE": "прочие",
            "AVOCADO & SUNFLOWER": "микс",
            "BLACK CUMIN SEED": "прочие",
            "BLACK SESAME": "прочие",
            "CAMELINA (RYZHIK)": "прочие",
            "CANOLA SEED": "прочие",
            "CEDAR NUT": "прочие",
            "CEDAR NUT & LINSEED": "прочие",
            "CEDAR NUT & LINSEED & SESAME & SUNFLOWER": "прочие",
            "CEDAR NUT & PEANUT & WALNUT": "прочие",
            "CEDAR NUT & SUNFLOWER": "микс",
            "CEREAL & FRUIT": "прочие",
            "CHIA SEED": "прочие",
            "CHIA SEED & SUNFLOWER": "прочие",
            "COCOA": "прочие",
            "COCONUT": "прочие",
            "COCONUT & PALM": "прочие",
            "COLESEED": "прочие",
            "CORN": "кукурузное",
            "CORN & SUNFLOWER": "микс",
            "CORN GERM": "кукурузное",
            "CORN SEEDS & GRAPE SEEDS & RAPE SEEDS & RICE BRAN & SESAME": "прочие",
            "COTTON": "прочие",
            "CUMIN SEED": "прочие",
            "GRAPE SEEDS": "прочие",
            "GRAPE SEEDS & SUNFLOWER": "микс",
            "HAZELNUT": "прочие",
            "HEMP": "прочие",
            "HEMP & LINSEED": "прочие",
            "HEMP & SUNFLOWER": "прочие",
            "LINSEED": "прочие",
            "LINSEED & MUSTARD & SUNFLOWER": "прочие",
            "LINSEED & OLIVE": "прочие",
            "LINSEED & PUMPKIN SEEDS": "прочие",
            "LINSEED & SESAME": "прочие",
            "LINSEED & SUNFLOWER": "микс",
            "LINSEED & WALNUT": "прочие",
            "MACADAMIA NUT": "прочие",
            "MIX OIL": "прочие",
            "MUSTARD": "прочие",
            "MUSTARD & SUNFLOWER": "прочие",
            "MUSTARD & SUNFLOWER & WALNUT": "прочие",
            "NUT": "прочие",
            "OLIVE": "оливковое",
            "OLIVE & PUMPKIN": "прочие",
            "OLIVE & RAPE SEED": "прочие",
            "OLIVE & SESAME": "прочие",
            "OLIVE OIL & SUNFLOWER": "микс",
            "PALM": "прочие",
            "PEANUT": "прочие",
            "PISTACHIO": "прочие",
            "POPPY SEED": "прочие",
            "PUMPKIN SEEDS": "прочие",
            "RAPE SEED & SUNFLOWER": "микс",
            "RAPE SEEDS": "прочие",
            "RAPE SEEDS & SAFFLOWER & SUNFLOWER": "прочие",
            "RICE": "прочие",
            "ROSEHIP": "прочие",
            "RUCCOLA SEED": "прочие",
            "SAFFLOWER": "прочие",
            "SEA BUCKTHORN & SUNFLOWER": "микс",
            "SEABERRY / SEA BUCKTHORN": "прочие",
            "SESAME": "прочие",
            "SOYA": "прочие",
            "SUNFLOWER": "подсолнечное",
            "SUNFLOWER & SESAME": "микс",
            "SUNFLOWER & SOYA": "микс",
            "SUNFLOWER & WALNUT": "микс",
            "THISTLE SEEDS (RASTOROPSHA)": "прочие",
            "TRIGONELLA": "прочие",
            "WALNUT (GRETSKIY OREKH)": "прочие",
            "WATERMELON SEEDS": "прочие",
            "WHEAT GERM": "прочие",
            "WHITE SESAME": "прочие",
        }
    else:
        refine_map = {}
        product_base_map = {}
        log(
            f"Для категории '{category}' маппинги не заданы — используются значения по умолчанию."
        )

    data["SKU_long_filtered"] = (
        data["SKU_long"]
        .filter(pl.col("FACT").is_in(valid_FACT))
        .with_columns(
            [
                pl.col("IF REFINED")
                .cast(pl.Utf8)
                .str.strip_chars()
                .str.to_uppercase()
                .replace_strict(refine_map, default=None)
                .alias("IF REFINED"),
                pl.col("PRODUCT BASE")
                .cast(pl.Utf8)
                .str.strip_chars()
                .str.to_uppercase()
                .replace_strict(product_base_map, default="прочие")
                .alias("PRODUCT BASE"),
            ]
        )
    )

    if stop_event.is_set():
        return

    data["SKU_long_unique"] = data["SKU_long_filtered"].unique(
        subset=id_cols_sku + ["ATTRIBUTE"]
    )

    # Оптимизация
    data["MAN_long"] = optimize_for_size(data["MAN_long"])
    data["BRAND_long"] = optimize_for_size(data["BRAND_long"])
    data["SKU_long_unique"] = optimize_for_size(data["SKU_long_unique"])

    # Сохранение — с проверкой stop_event между файлами
    for name, key in [
        ("SKU_long_unique", "SKU_long_unique"),
        ("MAN_long", "MAN_long"),
        ("BRAND_long", "BRAND_long"),
    ]:
        if stop_event.is_set():
            log("⛔ Сохранение остановлено пользователем")
            return
        save_optimized(data[key], name, output_dir, fmt, log, stop_event)

    log(f"Готово! Файлы сохранены в формате {fmt.upper()}")
    messagebox.showinfo("Готово", "Обработка Nielsen завершена!")
