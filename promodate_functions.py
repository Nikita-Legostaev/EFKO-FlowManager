import os
import shutil
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import polars as pl
import time
import gc
from tkinter import filedialog
import pythoncom
import win32com.client as win32

FTP_FOLDER = r"M:\FTP"
DOWNLOAD_FOLDER = os.path.join(os.getcwd(), "Скаченное")
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

network_map = {
    "Globus",
    "Metro",
    "Ашан",
    "Дикси",
    "Лента Гипер",
    "Лента Супер",
    "Лента Эконом",
    "Магнит (у дома)",
    "Магнит Мини",
    "Магнит Семейный",
    "Магнит Экстра",
    "Монетка",
    "О'кей",
    "Перекрёсток*",
    "Пятёрочка",
    "Чижик",
}

needed_columns = [
    "group",
    "category",
    "brand",
    "pd_sku",
    "retailer",
    "region",
    "date",
    "promo",
    "regular",
]

FILTER_OPTIONS = {
    "Масло": {"group": "Соусы и масла", "category": "Масло растительное"},
    "Маргарин": {
        "group": "Майонез, масло сливочное, яйцо",
        "category": "Маргарин, спред, жир",
    },
    "Майонез": {"group": "Майонез, масло сливочное, яйцо", "category": "Майонез"},
    "Кетчуп": {"group": "Соусы и масла", "category": "Кетчупы"},
    "Продукты растительного происхождения": {
        "group": "Диетическое и здоровое питание",
        "category": "Продукты растительного происхождения",
    },
}

STATUS_SHEET = "Проверка_обновления"
STATUS_CELL = "A2"


def extract_date(filename):
    for part in filename.split("_"):
        try:
            return datetime.strptime(part, "%Y-%m-%d")
        except ValueError:
            continue
    return None


def download_file(src, dst, log):
    try:
        filename = os.path.basename(src)
        log(f"Начата загрузка: {filename}")
        shutil.copy2(src, dst)
        log(f"Загрузка завершена: {filename}")
    except Exception as e:
        log(f"Ошибка загрузки {filename}: {e}")


def download_files_thread(month_var, year_var, log, messagebox):
    month = int(month_var.get())
    year = int(year_var.get())
    files = [f for f in os.listdir(FTP_FOLDER) if f.endswith(".xlsx")]
    files_to_download = [
        f
        for f in files
        if extract_date(f)
        and extract_date(f).month == month
        and extract_date(f).year == year
    ]

    if not files_to_download:
        log("Нет файлов за выбранный месяц/год")
        messagebox.showwarning("Инфо", "Нет файлов для загрузки")
        return

    with ThreadPoolExecutor(max_workers=6) as executor:
        for file in files_to_download:
            src = os.path.join(FTP_FOLDER, file)
            dst = os.path.join(DOWNLOAD_FOLDER, file)
            executor.submit(download_file, src, dst, log)

    messagebox.showinfo("Готово", f"Загрузка завершена!\nПапка: {DOWNLOAD_FOLDER}")
    log("Загрузка всех файлов завершена 🎉")


def clear_download_folder(log, messagebox):
    files = [os.path.join(DOWNLOAD_FOLDER, f) for f in os.listdir(DOWNLOAD_FOLDER)]
    if not files:
        messagebox.showinfo("Очистка", "Папка уже пуста")
        return
    for file in files:
        try:
            os.remove(file)
            log(f"Удалён: {os.path.basename(file)}")
        except Exception as e:
            log(f"Ошибка удаления: {e}")
    messagebox.showinfo("Очистка", "Папка очищена!")
    log("Очистка завершена 🎉")


def browse_output_folder(output_folder_var):
    folder = filedialog.askdirectory()
    if folder:
        output_folder_var.set(folder)


def get_first_sheet_name(file_path):
    import openpyxl

    wb = openpyxl.load_workbook(file_path, read_only=True)
    return wb.sheetnames[0]


def process_file(file_path, output_folder, selected_filter, log, chunk_size=100_000):
    try:
        filename = os.path.basename(file_path)
        log(f"Обработка: {filename}")

        sheet_name = get_first_sheet_name(file_path)
        df = pl.read_excel(file_path, sheet_name=sheet_name).select(needed_columns)
        df = df.with_columns(
            [pl.col(c).cast(pl.Utf8).str.strip_chars() for c in df.columns]
        )

        mask = (
            (df["group"] == selected_filter["group"])
            & (df["category"] == selected_filter["category"])
            & (df["retailer"].is_in(network_map))
        )
        df_filtered = df.filter(mask)

        os.makedirs(output_folder, exist_ok=True)
        output_file = os.path.join(
            output_folder, os.path.splitext(filename)[0] + ".csv"
        )

        for start in range(0, df_filtered.height, chunk_size):
            chunk = df_filtered[start : start + chunk_size].to_pandas()
            mode = "w" if start == 0 else "a"
            header = start == 0
            chunk.to_csv(
                output_file, index=False, encoding="utf-8-sig", mode=mode, header=header
            )

        log(f"Готово: {filename} | {df.height} → {df_filtered.height} строк")
    except Exception as e:
        log(f"Ошибка обработки {filename}: {e}")


def refresh_file(file_path, log, stop_event):
    filename = os.path.basename(file_path)
    excel = None
    wb = None
    try:
        pythoncom.CoInitialize()
        excel = win32.DispatchEx("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        wb = excel.Workbooks.Open(file_path)

        before = wb.Worksheets[STATUS_SHEET].Range(STATUS_CELL).Value
        log(f"{filename} — до: {before}")
        wb.RefreshAll()
        log(f"{filename} — RefreshAll запущен...")

        timeout = 0
        while timeout < 450:
            if stop_event.is_set():
                log(f"{filename} — остановлено пользователем")
                return False
            time.sleep(2)
            excel.Calculate()
            after = wb.Worksheets[STATUS_SHEET].Range(STATUS_CELL).Value
            if after is not None and after != before:
                log(f"{filename} — обновлено: {after}")
                break
            timeout += 1
        else:
            log(f"{filename} — тайм-аут ожидания")

        wb.Save()
        log(f"{filename} — сохранён ✅")
        return True
    except Exception as e:
        log(f"Ошибка {filename}: {e}")
        return False
    finally:
        if wb:
            wb.Close(SaveChanges=False)
            del wb
        if excel:
            excel.Quit()
            del excel
        pythoncom.CoUninitialize()
        gc.collect()


def refresh_power_query_files(pq_file1, pq_file2, log, stop_event):
    file1 = pq_file1.get()
    file2 = pq_file2.get()
    if not file1 or not os.path.isfile(file1):
        log("Power Query файл 1 не выбран!")
        return
    if not file2 or not os.path.isfile(file2):
        log("Power Query файл 2 не выбран!")
        return
    log("Обновляем Promodate...")
    success1 = refresh_file(file1, log, stop_event)
    if success1 and not stop_event.is_set():
        success2 = refresh_file(file2, log, stop_event)
        if success2:
            log("Promodate обновлён 🎉")


def process_files_thread(
    output_folder_var,
    filter_var,
    FILTER_OPTIONS,
    log,
    messagebox,
    stop_event,
    refresh_power_query_files,
    pq_file1,
    pq_file2,
):
    output_folder = output_folder_var.get().strip()
    if not output_folder:
        messagebox.showwarning("Ошибка", "Укажите папку сохранения!")
        return

    selected_filter = FILTER_OPTIONS[filter_var.get()]

    files = [
        os.path.join(DOWNLOAD_FOLDER, f)
        for f in os.listdir(DOWNLOAD_FOLDER)
        if f.endswith(".xlsx")
    ]
    if not files:
        messagebox.showwarning("Ошибка", "Нет Excel-файлов в папке Скаченное!")
        return

    with ThreadPoolExecutor(max_workers=6) as executor:
        for file in files:
            executor.submit(process_file, file, output_folder, selected_filter, log)

    log("Обработка промодаты завершена 🎉")
    messagebox.showinfo("Готово", f"CSV-файлы сохранены в:\n{output_folder}")
    refresh_power_query_files(pq_file1, pq_file2, log, stop_event)
