import os
import shutil
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import gc

FTP_FOLDER = r"M:\FTP"
DOWNLOAD_FOLDER = os.path.join(os.getcwd(), "Скаченное")
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# ── Режимы промодаты ──────────────────────────────────────────────────────────
# Каждый режим — свой источник скачанных xlsx, чтобы файлы разных режимов
# не путались между собой. «ЦО» — это и есть исторический DOWNLOAD_FOLDER,
# оставлен как есть ради обратной совместимости с уже скачанными файлами.
PROMO_MODES = {"co": "ЦО", "monitoring": "Мониторинг цен", "extra": "Дополнительно"}
DEFAULT_PROMO_MODE = "co"


def download_folder_for_mode(mode: str) -> str:
    """Папка скачивания xlsx для выбранного режима промодаты."""
    if mode not in PROMO_MODES or mode == DEFAULT_PROMO_MODE:
        return DOWNLOAD_FOLDER
    path = os.path.join(DOWNLOAD_FOLDER, PROMO_MODES[mode])
    os.makedirs(path, exist_ok=True)
    return path

network_map = {
    "Globus", "Metro", "Ашан", "Дикси",
    "Лента Гипер", "Лента Супер", "Лента Эконом",
    "Магнит (у дома)", "Магнит Мини", "Магнит Семейный", "Магнит Экстра",
    "Монетка", "О'кей", "Перекрёсток*", "Пятёрочка", "Чижик",
}

needed_columns = [
    "group", "category", "brand", "pd_sku",
    "retailer", "region", "date", "promo", "regular",
]

FILTER_OPTIONS = {
    "Масло": {"group": "Соусы и масла", "category": "Масло растительное"},
    "Маргарин": {"group": "Майонез, масло сливочное, яйцо", "category": "Маргарин, спред, жир"},
    "Майонез": {"group": "Майонез, масло сливочное, яйцо", "category": "Майонез"},
    "Кетчуп": {"group": "Соусы и масла", "category": "Кетчупы"},
    "Кетчуп+Майонез": [
        {"group": "Соусы и масла", "category": "Кетчупы"},
        {"group": "Майонез, масло сливочное, яйцо", "category": "Майонез"},
    ],
    "Продукты растительного происхождения": {
        "group": "Диетическое и здоровое питание",
        "category": "Продукты растительного происхождения",
    },
}


# ── Чтение доступных сетей из файлов ─────────────────────────────────────────

def get_available_networks(folder: str = None) -> list:
    """
    Читает уникальные сети (retailer) из первого xlsx в папке.
    Если файлов нет или ошибка — возвращает дефолтный network_map.
    """
    folder = folder or DOWNLOAD_FOLDER
    if not os.path.isdir(folder):
        return sorted(network_map)
    files = [f for f in os.listdir(folder) if f.endswith(".xlsx")]
    if not files:
        return sorted(network_map)
    try:
        import polars as pl
        file_path = os.path.join(folder, files[0])
        df = pl.read_excel(file_path, sheet_id=1).select(["retailer"])
        networks = df["retailer"].drop_nulls().unique().to_list()
        result   = sorted(str(n).strip() for n in networks if str(n).strip())
        return result if result else sorted(network_map)
    except Exception:
        return sorted(network_map)


# ── Логирование ───────────────────────────────────────────────────────────────

def setup_file_logger():
    log_path = os.path.join(os.getcwd(), "flowmanager.log")
    logging.basicConfig(
        filename=log_path, level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S", encoding="utf-8",
    )

def file_log(message: str):
    logging.info(message)


# ── Вспомогательные функции ───────────────────────────────────────────────────

def extract_date(filename: str):
    name = os.path.splitext(filename)[0]
    for part in name.split("_"):
        try:
            return datetime.strptime(part, "%Y-%m-%d")
        except ValueError:
            continue
    return None

def _iter_months(month_from, year_from, month_to, year_to):
    m, y = month_from, year_from
    while (y, m) <= (year_to, month_to):
        yield m, y
        m += 1
        if m > 12:
            m, y = 1, y + 1

def _max_workers() -> int:
    return min(6, os.cpu_count() or 4)

def _excel_optimize(excel):
    try: excel.ScreenUpdating = False
    except Exception: pass
    try: excel.EnableEvents = False
    except Exception: pass
    try: excel.Calculation = -4135
    except Exception: pass

def _excel_restore(excel):
    try: excel.Calculation = -4105
    except Exception: pass
    try: excel.ScreenUpdating = True
    except Exception: pass
    try: excel.EnableEvents = True
    except Exception: pass


# ── Скачивание ────────────────────────────────────────────────────────────────

def _download_one(src, dst, log):
    filename = os.path.basename(src)
    try:
        if os.path.exists(dst):
            src_stat = os.stat(src)
            dst_stat = os.stat(dst)
            if src_stat.st_size == dst_stat.st_size and src_stat.st_mtime <= dst_stat.st_mtime:
                log(f"Пропущен (уже скачан): {filename}")
                return True
        log(f"Начата загрузка: {filename}")
        shutil.copy2(src, dst)
        log(f"Загрузка завершена: {filename}")
        return True
    except Exception as e:
        log(f"Ошибка загрузки {filename}: {e}")
        return False


def download_files_thread(
    month_from_var, year_from_var, month_to_var, year_to_var,
    log, messagebox, progress_callback=None, set_title=None,
    date_from_str=None, date_to_str=None, dates_list=None,
    download_folder=None,
):
    dst_folder = download_folder or DOWNLOAD_FOLDER
    os.makedirs(dst_folder, exist_ok=True)
    if dates_list:
        try:
            exact_dates = {datetime.strptime(ds, "%Y-%m-%d").date() for ds in dates_list}
        except ValueError:
            exact_dates = None
        if exact_dates:
            files_to_download = [
                f for f in os.listdir(FTP_FOLDER)
                if f.endswith(".xlsx") and (d := extract_date(f)) and d.date() in exact_dates
            ]
    elif date_from_str and date_to_str:
        try:
            d_from = datetime.strptime(date_from_str, "%Y-%m-%d")
            d_to   = datetime.strptime(date_to_str,   "%Y-%m-%d")
        except ValueError:
            date_from_str = date_to_str = None

    if not dates_list and date_from_str and date_to_str:
        if d_from > d_to:
            messagebox.showwarning("Ошибка", "Начало диапазона не может быть позже конца!")
            return
        files_to_download = [
            f for f in os.listdir(FTP_FOLDER)
            if f.endswith(".xlsx") and (d := extract_date(f)) and d_from <= d <= d_to
        ]
    elif not dates_list:
        month_from = int(month_from_var.get()) if month_from_var else 1
        year_from  = int(year_from_var.get())  if year_from_var  else datetime.now().year
        month_to   = int(month_to_var.get())   if month_to_var   else month_from
        year_to    = int(year_to_var.get())    if year_to_var    else year_from
        if (year_from, month_from) > (year_to, month_to):
            messagebox.showwarning("Ошибка", "Начало диапазона не может быть позже конца!")
            return
        valid_pairs = set(_iter_months(month_from, year_from, month_to, year_to))
        files_to_download = [
            f for f in os.listdir(FTP_FOLDER)
            if f.endswith(".xlsx") and (d := extract_date(f)) and (d.month, d.year) in valid_pairs
        ]

    if not files_to_download:
        log("Нет файлов за выбранный период")
        messagebox.showwarning("Инфо", "Нет файлов для загрузки")
        return

    total = len(files_to_download)
    log(f"Найдено файлов для загрузки: {total}")
    if set_title: set_title(f"⏳ Загрузка 0 / {total}...")

    completed = 0
    with ThreadPoolExecutor(max_workers=_max_workers()) as executor:
        futures = {
            executor.submit(_download_one, os.path.join(FTP_FOLDER, f), os.path.join(dst_folder, f), log): f
            for f in files_to_download
        }
        for future in as_completed(futures):
            completed += 1
            if progress_callback: progress_callback(completed, total)
            if set_title: set_title(f"⏳ Загрузка {completed} / {total}...")

    if set_title: set_title("✅ Готово")
    messagebox.showinfo("Готово", f"Загрузка завершена!\nПапка: {dst_folder}")
    log("Загрузка всех файлов завершена 🎉")


# ── Очистка ───────────────────────────────────────────────────────────────────

def clear_download_folder(log, messagebox, download_folder=None):
    folder = download_folder or DOWNLOAD_FOLDER
    files = [os.path.join(folder, f) for f in os.listdir(folder)]
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

def clear_output_folder(output_folder_var, log, messagebox):
    folder = output_folder_var.get().strip()
    if not folder or not os.path.isdir(folder):
        messagebox.showwarning("Очистка", "Папка сохранения не задана или не существует")
        return
    files = [os.path.join(folder, f) for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))]
    if not files:
        messagebox.showinfo("Очистка", "Папка уже пуста")
        return
    for file in files:
        try:
            os.remove(file)
            log(f"Удалён: {os.path.basename(file)}")
        except Exception as e:
            log(f"Ошибка удаления: {e}")
    messagebox.showinfo("Очистка", f"Папка очищена! Удалено файлов: {len(files)}")
    log("Очистка папки сохранения завершена 🎉")


# ── Обработка файлов ──────────────────────────────────────────────────────────

def get_first_sheet_name(file_path):
    import openpyxl
    wb   = openpyxl.load_workbook(file_path, read_only=True)
    name = wb.sheetnames[0]
    wb.close()
    return name


CATEGORY_MARKER = "_last_category.txt"


def _read_last_category(output_folder: str) -> str:
    path = os.path.join(output_folder, CATEGORY_MARKER)
    try:
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                return f.read().strip()
    except Exception:
        pass
    return ""


def _write_last_category(output_folder: str, cat_name: str):
    try:
        os.makedirs(output_folder, exist_ok=True)
        with open(os.path.join(output_folder, CATEGORY_MARKER), "w", encoding="utf-8") as f:
            f.write(cat_name)
    except Exception as e:
        logging.error(f"[promodate] не удалось записать {CATEGORY_MARKER}: {e}")


def _reset_output_if_category_changed(output_folder: str, cat_name: str, log) -> bool:
    """
    Если прошлый прогон был по другой категории — удаляет старые CSV.

    Имя CSV собирается только из имени исходного xlsx и категорию не содержит,
    поэтому без этой чистки process_file() посчитает лежащие файлы «уже
    обработанными» и в папке останутся данные предыдущей категории.
    """
    os.makedirs(output_folder, exist_ok=True)
    prev = _read_last_category(output_folder)

    if prev and prev != cat_name:
        removed = 0
        for f in os.listdir(output_folder):
            if not f.lower().endswith(".csv"):
                continue
            try:
                os.remove(os.path.join(output_folder, f))
                removed += 1
            except Exception as e:
                log(f"⚠ Не удалось удалить {f}: {e}")
        log(f"🔄 Категория сменилась: «{prev}» → «{cat_name}». Удалено старых CSV: {removed}")
    elif not prev:
        log(f"ℹ Категория обработки: «{cat_name}» (первый прогон в этой папке)")
    else:
        log(f"ℹ Категория обработки: «{cat_name}» — та же, готовые CSV пропускаются")

    _write_last_category(output_folder, cat_name)
    return bool(prev and prev != cat_name)


def process_file(file_path, output_folder, selected_filter, log, networks=None):
    """
    Фильтрует один Excel-файл и сохраняет CSV.

    networks — список сетей для фильтрации.
               None или пустой список = использовать дефолтный network_map.
    """
    import polars as pl

    filename    = os.path.basename(file_path)
    output_file = os.path.join(output_folder, os.path.splitext(filename)[0] + ".csv")

    if os.path.exists(output_file):
        if os.path.getmtime(output_file) >= os.path.getmtime(file_path):
            log(f"Пропущен (уже обработан): {filename}")
            return True

    try:
        log(f"Обработка: {filename}")

        active_networks = set(networks) if networks else network_map

        # sheet_id=1 читает первый лист по позиции — не нужен отдельный
        # проход через openpyxl только ради имени листа.
        df = pl.read_excel(file_path, sheet_id=1).select(needed_columns)
        df = df.with_columns([pl.col(c).cast(pl.Utf8).str.strip_chars() for c in df.columns])

        if isinstance(selected_filter, dict):
            group_mask = (df["group"] == selected_filter["group"]) & (df["category"] == selected_filter["category"])
        else:
            group_mask = pl.lit(False)
            for filt in selected_filter:
                group_mask = group_mask | ((df["group"] == filt["group"]) & (df["category"] == filt["category"]))

        df_filtered = df.filter(group_mask & df["retailer"].is_in(active_networks))

        os.makedirs(output_folder, exist_ok=True)
        df_filtered.write_csv(output_file, separator=",")

        cat_label = (selected_filter.get("category") if isinstance(selected_filter, dict)
                     else "+".join(f["category"] for f in selected_filter))
        log(f"Готово: {filename} | {df.height} → {df_filtered.height} строк "
            f"| категория: {cat_label} | сетей: {len(active_networks)}")
        return True
    except Exception as e:
        log(f"Ошибка обработки {filename}: {e}")
        return False


def process_files_thread(
    output_folder_var, filter_var, FILTER_OPTIONS,
    log, messagebox, stop_event, refresh_power_query_files,
    pq_file1, pq_file2, macro1_name, macro2_name,
    progress_callback=None, set_title=None,
    networks=None,   # список выбранных сетей, None = все по умолчанию
    download_folder=None,
):
    src_folder = download_folder or DOWNLOAD_FOLDER
    output_folder = output_folder_var.get().strip()
    if not output_folder:
        messagebox.showwarning("Ошибка", "Укажите папку сохранения!")
        return

    cat_name = filter_var.get()
    if cat_name not in FILTER_OPTIONS:
        messagebox.showwarning("Ошибка", f"Неизвестная категория: {cat_name}")
        return
    selected_filter = FILTER_OPTIONS[cat_name]

    # Смена категории обязана обнулить папку — иначе останутся CSV прошлой категории
    _reset_output_if_category_changed(output_folder, cat_name, log)
    files = [os.path.join(src_folder, f) for f in os.listdir(src_folder) if f.endswith(".xlsx")]
    if not files:
        messagebox.showwarning("Ошибка", f"Нет Excel-файлов в папке {src_folder}!")
        return

    # Лог какие сети используются
    if networks:
        log(f"Фильтр по сетям: {', '.join(networks)}")
    else:
        log(f"Фильтр по сетям: дефолтный ({len(network_map)} сетей)")

    total = len(files)
    log(f"Начинаем обработку {total} файлов...")
    if set_title: set_title(f"⏳ Обработка 0 / {total}...")

    completed = 0
    with ThreadPoolExecutor(max_workers=_max_workers()) as executor:
        futures = {
            executor.submit(process_file, f, output_folder, selected_filter, log, networks): f
            for f in files
        }
        for future in as_completed(futures):
            if stop_event.is_set():
                log("⛔ Остановлено пользователем")
                break
            completed += 1
            if progress_callback: progress_callback(completed, total)
            if set_title: set_title(f"⏳ Обработка {completed} / {total}...")

    if stop_event.is_set():
        if set_title: set_title("⛔ Остановлено")
        return

    if set_title: set_title("✅ Готово")
    log("Обработка промодаты завершена 🎉")
    messagebox.showinfo("Готово", f"CSV-файлы сохранены в:\n{output_folder}")

    refresh_power_query_files(pq_file1, pq_file2, macro1_name, macro2_name, log, stop_event)


# ── Power Query / Excel refresh ───────────────────────────────────────────────

def _set_sync_refresh(wb, log):
    saved = []
    for conn in wb.Connections:
        try:
            if conn.Type == 1:
                oledb = conn.OLEDBConnection
                saved.append((oledb, oledb.BackgroundQuery))
                oledb.BackgroundQuery = False
        except Exception:
            pass
    if saved:
        log(f"  Синхронный режим: {len(saved)} PQ-соединений")
    else:
        log("  ⚠ PQ-соединений не найдено — RefreshAll() может быть асинхронным")
    return saved

def _restore_bg_refresh(saved):
    for oledb, original in saved:
        try: oledb.BackgroundQuery = original
        except Exception: pass

def refresh_file(file_path, log, stop_event):
    import pythoncom
    import win32com.client as win32
    filename = os.path.basename(file_path)
    excel = wb = None
    try:
        pythoncom.CoInitialize()
        excel = win32.DispatchEx("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        _excel_optimize(excel)
        wb = excel.Workbooks.Open(file_path)
        saved = _set_sync_refresh(wb, log)
        if stop_event.is_set(): return False
        log(f"{filename} — RefreshAll() запущен (синхронно)...")
        wb.RefreshAll()
        log(f"{filename} — обновление завершено ✅")
        if stop_event.is_set(): return False
        _restore_bg_refresh(saved)
        _excel_restore(excel)
        wb.Save()
        log(f"{filename} — сохранён ✅")
        return True
    except Exception as e:
        log(f"Ошибка {filename}: {e}")
        return False
    finally:
        try:
            if wb: wb.Close(SaveChanges=False)
        except Exception: pass
        finally: del wb
        try:
            if excel: excel.Quit()
        except Exception: pass
        finally: del excel
        try: pythoncom.CoUninitialize()
        except Exception: pass
        gc.collect()

def _excel_session(log, func):
    import pythoncom
    import win32com.client as win32
    excel = pid = None
    pythoncom.CoInitialize()
    try:
        excel = win32.DispatchEx("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        excel.AutomationSecurity = 1
        _excel_optimize(excel)
        pid = _get_excel_pid(excel)
        return func(excel)
    except Exception: raise
    finally:
        try:
            if excel: excel.Quit()
        except Exception: pass
        try: del excel
        except Exception: pass
        try: pythoncom.CoUninitialize()
        except Exception: pass
        gc.collect()
        if pid: kill_excel_pid(pid, log)

def _refresh_xlsm_query(file_path, log, stop_event):
    filename = os.path.basename(file_path)
    def _run(excel):
        wb = None
        try:
            wb = excel.Workbooks.Open(file_path, UpdateLinks=0, ReadOnly=False)
            saved = _set_sync_refresh(wb, log)
            if stop_event.is_set(): return False
            try: wb.RefreshAll()
            except Exception as e: log(f"{filename} — RefreshAll ошибка (продолжаем): {e}")
            log(f"{filename} — Power Query обновлён ✅")
            if stop_event.is_set(): return False
            _restore_bg_refresh(saved)
            time.sleep(3)
            try:
                _excel_restore(excel)
                wb.Save()
            except Exception as e:
                log(f"{filename} — ошибка сохранения: {e}")
                return False
            log(f"{filename} — сохранён после обновления ✅")
            return True
        finally:
            try:
                if wb: wb.Close(SaveChanges=False)
            except Exception: pass
            try: del wb
            except Exception: pass
    try: return _excel_session(log, _run)
    except Exception as e:
        log(f"Ошибка обновления квери {filename}: {e}")
        return False

def _run_xlsm_macros(file_path, macro_names, log, stop_event):
    filename = os.path.basename(file_path)
    macros = [m.strip() for m in macro_names if m.strip()]
    if not macros:
        log(f"{filename} — имена макросов не заданы, шаг пропущен")
        return True
    def _run(excel):
        wb = None
        try:
            wb = excel.Workbooks.Open(file_path, UpdateLinks=0, ReadOnly=False)
            log(f"{filename} — запускаем макросы ({len(macros)} шт.)...")
            for macro_name in macros:
                if stop_event.is_set(): return False
                log(f"  ▷ Макрос: {macro_name}")
                try:
                    excel.Application.Run(macro_name)
                    log(f"  ✅ {macro_name} — выполнен")
                except Exception as e:
                    log(f"  ❌ Ошибка макроса «{macro_name}»: {e}")
            if stop_event.is_set(): return False
            _excel_restore(excel)
            wb.Save()
            log(f"{filename} — сохранён после макросов ✅")
            return True
        finally:
            try:
                if wb: wb.Close(SaveChanges=False)
            except Exception: pass
            try: del wb
            except Exception: pass
    try: return _excel_session(log, _run)
    except Exception as e:
        log(f"Ошибка запуска макросов {filename}: {e}")
        return False

def refresh_file_with_macros(file_path, macro_names, log, stop_event):
    filename = os.path.basename(file_path)
    log(f"▶ {filename}: сеанс 1 — обновление Power Query")
    ok = _refresh_xlsm_query(file_path, log, stop_event)
    if not ok or stop_event.is_set(): return False
    time.sleep(3)
    log(f"▶ {filename}: сеанс 2 — запуск макросов")
    return _run_xlsm_macros(file_path, macro_names, log, stop_event)

def _get_excel_pid(excel):
    try:
        import win32process
        hwnd = excel.Hwnd
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        return pid
    except Exception: return None

def kill_excel_pid(pid, log):
    if pid is None: return
    try:
        import subprocess
        result = subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True, text=True)
        if result.returncode == 0:
            log(f"🧹 Процесс Excel (PID {pid}) завершён")
        else:
            log(f"🧹 Процесс Excel (PID {pid}) уже не активен")
    except Exception as e:
        log(f"Ошибка при завершении процесса Excel PID {pid}: {e}")

def refresh_power_query_files(pq_file1, pq_file2, macro1_name, macro2_name, log, stop_event):
    file1 = pq_file1.get()
    file2 = pq_file2.get()
    if not file1 or not os.path.isfile(file1):
        log("⚠️ Power Query файл 1 не выбран — шаг пропущен")
    else:
        log("▶ Обновляем Promodate (файл 1)...")
        if not refresh_file(file1, log, stop_event):
            log("⚠️ Файл 1 не обновлён, продолжаем...")
        if stop_event.is_set(): return
    if not file2 or not os.path.isfile(file2):
        log("⚠️ Power Query файл 2 не выбран — шаг пропущен")
        return
    m1 = macro1_name.get().strip() if hasattr(macro1_name, "get") else str(macro1_name).strip()
    m2 = macro2_name.get().strip() if hasattr(macro2_name, "get") else str(macro2_name).strip()
    macro_names = [m for m in [m1, m2] if m]
    log("▶ Обновляем Promodate (файл 2 — xlsm + макросы)...")
    if refresh_file_with_macros(file2, macro_names, log, stop_event):
        log("Promodate полностью обновлён 🎉")


# ── Поэтапный запуск ─────────────────────────────────────────────────────────

def run_stage_query1(pq_file1_var, log, stop_event, messagebox=None):
    file1 = pq_file1_var.get() if hasattr(pq_file1_var, "get") else str(pq_file1_var)
    if not file1 or not os.path.isfile(file1):
        log("⏭ Power Query файл 1 не указан — шаг пропущен")
        return True
    log("▶ Стадия: Обновление Query 1...")
    ok = refresh_file(file1, log, stop_event)
    if ok: log("✅ Query 1 обновлён!")
    return ok

def run_stage_query2(pq_file2_var, log, stop_event, messagebox=None):
    file2 = pq_file2_var.get() if hasattr(pq_file2_var, "get") else str(pq_file2_var)
    if not file2 or not os.path.isfile(file2):
        log("⏭ Power Query файл 2 не указан — шаг пропущен")
        return True
    log("▶ Стадия: Обновление Query 2 (xlsm)...")
    ok = _refresh_xlsm_query(file2, log, stop_event)
    if ok: log("✅ Query 2 обновлён!")
    return ok

def run_stage_macros(pq_file2_var, macro1_name, macro2_name, log, stop_event, messagebox=None):
    file2 = pq_file2_var.get() if hasattr(pq_file2_var, "get") else str(pq_file2_var)
    if not file2 or not os.path.isfile(file2):
        log("⏭ Файл макросов (xlsm) не указан — шаг пропущен")
        return True
    m1 = macro1_name.get().strip() if hasattr(macro1_name, "get") else str(macro1_name).strip()
    m2 = macro2_name.get().strip() if hasattr(macro2_name, "get") else str(macro2_name).strip()
    macro_names = [m for m in [m1, m2] if m]
    if not macro_names:
        log("⏭ Имена макросов не заданы — шаг пропущен")
        return True
    log(f"▶ Стадия: Запуск макросов ({', '.join(macro_names)})...")
    ok = _run_xlsm_macros(file2, macro_names, log, stop_event)
    if ok: log("✅ Макросы выполнены!")
    return ok