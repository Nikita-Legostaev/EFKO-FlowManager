# nielsen_functions.py
import os
import polars as pl
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from tkinter import messagebox

small_sheets = ["MAN", "BRAND"]
large_sheets = ["SKU1", "SKU2"]

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

def load_sheet(sheet_name: str, input_file: str, cache_dir: Path, log) -> tuple[str, pl.DataFrame]:
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

# ====================== MELT ======================
def melt_polars(df: pl.DataFrame, id_cols: list[str]) -> pl.DataFrame:
    date_cols = [c for c in df.columns if c not in id_cols]
    
    date_mapping = {}
    for col in date_cols:
        cleaned = col.strip().upper()
        parts = cleaned.split()
        if len(parts) == 2 and len(parts[0]) == 3 and parts[1].isdigit() and len(parts[1]) == 2:
            date_str = f"{parts[0]} {parts[1]} 1"
            parsed = pl.Series([date_str]).str.to_date("%b %y %d", strict=False)[0]
            date_mapping[col] = parsed.strftime("%d.%m.%Y") if parsed is not None else None
        else:
            date_mapping[col] = None
    
    df_long = (
        df.unpivot(
            index=id_cols,
            on=date_cols,
            variable_name="ATTRIBUTE",
            value_name="VALUE"
        )
        .with_columns(
            pl.col("ATTRIBUTE").replace_strict(date_mapping, default=None).alias("ATTRIBUTE")
        )
    )
    
    # Удаляем строки, где VALUE is null (чтобы уменьшить размер и убрать неинтересные строки)
    df_long = df_long.filter(pl.col("VALUE").is_not_null())
    
    return df_long

def optimize_for_size(df: pl.DataFrame) -> pl.DataFrame:
    cat_cols = ['MARKET', 'FACT', 'Long Description', 'MANUFACTURER', 'BRAND',
                'PRODUCT BASE', 'QUALITY', 'IF REFINED', 'PACKAGE TYPE',
                'PACKAGING MATERIAL', 'WEIGHT', 'ITEM']
    for col in cat_cols:
        if col in df.columns:
            df = df.with_columns(pl.col(col).cast(pl.Categorical("lexical")))
    
    if "VALUE" in df.columns:
        df = df.with_columns(pl.col("VALUE").round(4).cast(pl.Float32))
    
    return df

# ====================== ФИЛЬТРАЦИЯ И МАППИНГИ ======================
valid_FACT = [
    "Units (in 1000 PACKS)", "Volume (in 1000 LTR)", "Value (in 1000 RUR)",
    "Price (Unit)", "Price (Volume)", "Weighted Distribution (C)",
    "Numeric Distribution (C)", "Volume (in 1000 )"
]

refine_map = {
    "NOT APPLICABLE": "рафинированное",
    "NOT REFINED": "нерафинированное",
    "REFINED": "рафинированное",
    "REFINED & NOT REFINED (MIXED PACK)": "рафинированное"
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

def save_optimized(df: pl.DataFrame, name: str, output_dir: Path, format: str, log):
    log(f"Сохранение {name}...")
    
    # Очистка строк
    df = df.with_columns([
        pl.col(pl.Utf8).str.strip_chars()
    ])
    
    if format == "csv":
        path = output_dir / f"{name}.csv"
        df = df.with_columns(
            pl.col("VALUE").cast(pl.Utf8).str.replace(".", ",", literal=True).alias("VALUE")
        )
        df.write_csv(
            path,
            separator=";",
            include_bom=True,
            quote_style="necessary",
            null_value=""
        )
        size_mb = path.stat().st_size / (1024**2)
        log(f"✓ {name}.csv — {size_mb:.1f} МБ")
    
    elif format == "excel":
        max_rows = 1_048_575
        num_parts = (len(df) + max_rows - 1) // max_rows
        if num_parts > 1:
            for i in range(num_parts):
                start = i * max_rows
                end = min((i + 1) * max_rows, len(df))
                df_part = df.slice(start, end - start)
                df_part.write_excel(output_dir / f"{name}_part{i+1}.xlsx", worksheet="Data")
            log(f"✓ {name} разбит на {num_parts} файлов .xlsx ({len(df)} строк)")
        else:
            df.write_excel(output_dir / f"{name}.xlsx", worksheet="Data")
            log(f"✓ {name}.xlsx сохранён ({len(df)} строк)")

def process_nielsen(input_file: str, output_dir_str: str, format: str, log, messagebox, stop_event):
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

    for sheet in small_sheets:
        if stop_event.is_set():
            log("Обработка Nielsen остановлена пользователем")
            return
        name, df = load_sheet(sheet, input_file, cache_dir, log)
        data[name] = df

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_to_sheet = {executor.submit(load_sheet, sheet, input_file, cache_dir, log): sheet for sheet in large_sheets}
        for future in as_completed(future_to_sheet):
            if stop_event.is_set():
                log("Обработка Nielsen остановлена пользователем")
                return
            name, df = future.result()
            data[name] = df

    df_sku = pl.concat([data["SKU1"], data["SKU2"]], how="vertical")

    log("Обработка MAN...")
    id_cols_man = ['MARKET', 'FACT', 'Long Description', 'MANUFACTURER']
    data["MAN_long"] = melt_polars(data["MAN"], id_cols_man)

    log("Обработка BRAND...")
    id_cols_brand = ['MARKET', 'FACT', 'Long Description', 'MANUFACTURER', 'BRAND']
    data["BRAND_long"] = melt_polars(data["BRAND"], id_cols_brand)

    log("Обработка SKU...")
    id_cols_sku = ['MARKET', 'FACT', 'Long Description', 'MANUFACTURER', 'BRAND',
                   'PRODUCT BASE', 'QUALITY', 'IF REFINED', 'PACKAGE TYPE',
                   'PACKAGING MATERIAL', 'WEIGHT', 'ITEM']
    data["SKU_long"] = melt_polars(df_sku, id_cols_sku)

    data["SKU_long_filtered"] = (
        data["SKU_long"]
        .filter(pl.col("FACT").is_in(valid_FACT))
        .with_columns([
            pl.col("IF REFINED").cast(pl.Utf8).str.strip_chars().str.to_uppercase()
              .replace_strict(refine_map, default=None).alias("IF REFINED"),
            pl.col("PRODUCT BASE").cast(pl.Utf8).str.strip_chars().str.to_uppercase()
              .replace_strict(product_base_map, default="прочие").alias("PRODUCT BASE")
        ])
    )

    data["SKU_long_unique"] = data["SKU_long_filtered"].unique(subset=id_cols_sku + ["ATTRIBUTE"])

    # Оптимизация
    data["MAN_long"] = optimize_for_size(data["MAN_long"])
    data["BRAND_long"] = optimize_for_size(data["BRAND_long"])
    data["SKU_long_unique"] = optimize_for_size(data["SKU_long_unique"])

    # Сохранение
    save_optimized(data["SKU_long_unique"], "SKU_long_unique", output_dir, format, log)
    save_optimized(data["MAN_long"], "MAN_long", output_dir, format, log)
    save_optimized(data["BRAND_long"], "BRAND_long", output_dir, format, log)

    log(f"Готово! Файлы сохранены в формате {format.upper()}")
    messagebox.showinfo("Готово", "Обработка Nielsen завершена!")