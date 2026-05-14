import os
import shutil
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import gc
from tkinter import filedialog

# Тяжёлые библиотеки импортируются лениво (внутри функций) — ускоряет запуск exe

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
    "Кетчуп+Майонез": [
        {"group": "Соусы и масла", "category": "Кетчупы"},
        {"group": "Майонез, масло сливочное, яйцо", "category": "Майонез"},
    ],
    "Продукты растительного происхождения": {
        "group": "Диетическое и здоровое питание",
        "category": "Продукты растительного происхождения",
    },
}

STATUS_SHEET = "Проверка_обновления"
STATUS_CELL = "A2"


# ── Логирование в файл ────────────────────────────────────────────────────────


def setup_file_logger():
    """Инициализирует запись лога в файл рядом с exe."""
    log_path = os.path.join(os.getcwd(), "flowmanager.log")
    logging.basicConfig(
        filename=log_path,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        encoding="utf-8",
    )


def file_log(message: str):
    """Дублирует сообщение в файл лога."""
    logging.info(message)


# ── Вспомогательные функции ───────────────────────────────────────────────────


def extract_date(filename: str) -> datetime | None:
    name = os.path.splitext(filename)[0]
    for part in name.split("_"):
        try:
            return datetime.strptime(part, "%Y-%m-%d")
        except ValueError:
            continue
    return None


def _iter_months(month_from, year_from, month_to, year_to):
    """Генерирует пары (month, year) включительно."""
    m, y = month_from, year_from
    while (y, m) <= (year_to, month_to):
        yield m, y
        m += 1
        if m > 12:
            m, y = 1, y + 1


def _max_workers() -> int:
    """Оптимальное число потоков под текущую машину."""
    return min(6, os.cpu_count() or 4)


# ── Скачивание ────────────────────────────────────────────────────────────────


def _download_one(src, dst, log):
    filename = os.path.basename(src)
    try:
        log(f"Начата загрузка: {filename}")
        shutil.copy2(src, dst)
        log(f"Загрузка завершена: {filename}")
        return True
    except Exception as e:
        log(f"Ошибка загрузки {filename}: {e}")
        return False


def download_files_thread(
    month_from_var,
    year_from_var,
    month_to_var,
    year_to_var,
    log,
    messagebox,
    progress_callback=None,
    set_title=None,
    date_from_str=None,  # "YYYY-MM-DD" — если задан, фильтр по дню
    date_to_str=None,  # "YYYY-MM-DD" — если задан, фильтр по дню
    dates_list=None,  # список "YYYY-MM-DD" — точечный выбор дат
):
    # Если переданы точечные даты — используем их напрямую
    if dates_list:
        try:
            exact_dates = set()
            for ds in dates_list:
                exact_dates.add(datetime.strptime(ds, "%Y-%m-%d").date())
        except ValueError:
            exact_dates = None

        if exact_dates:
            files_to_download = []
            for f in os.listdir(FTP_FOLDER):
                if not f.endswith(".xlsx"):
                    continue
                d = extract_date(f)
                if d and d.date() in exact_dates:
                    files_to_download.append(f)
    # Если переданы конкретные даты — используем day-level фильтр
    elif date_from_str and date_to_str:
        try:
            d_from = datetime.strptime(date_from_str, "%Y-%m-%d")
            d_to = datetime.strptime(date_to_str, "%Y-%m-%d")
        except ValueError:
            date_from_str = date_to_str = None

    if not dates_list and date_from_str and date_to_str:
        if d_from > d_to:
            messagebox.showwarning(
                "Ошибка", "Начало диапазона не может быть позже конца!"
            )
            return
        files_to_download = []
        for f in os.listdir(FTP_FOLDER):
            if not f.endswith(".xlsx"):
                continue
            d = extract_date(f)
            if d and d_from <= d <= d_to:
                files_to_download.append(f)
    else:
        # Fallback: month-level (legacy)
        month_from = int(month_from_var.get()) if month_from_var else 1
        year_from = int(year_from_var.get()) if year_from_var else datetime.now().year
        month_to = int(month_to_var.get()) if month_to_var else month_from
        year_to = int(year_to_var.get()) if year_to_var else year_from

        if (year_from, month_from) > (year_to, month_to):
            messagebox.showwarning(
                "Ошибка", "Начало диапазона не может быть позже конца!"
            )
            return

        valid_pairs = set(_iter_months(month_from, year_from, month_to, year_to))
        files_to_download = []
        for f in os.listdir(FTP_FOLDER):
            if not f.endswith(".xlsx"):
                continue
            d = extract_date(f)
            if d and (d.month, d.year) in valid_pairs:
                files_to_download.append(f)

    if not files_to_download:
        log("Нет файлов за выбранный период")
        messagebox.showwarning("Инфо", "Нет файлов для загрузки")
        return

    total = len(files_to_download)
    log(f"Найдено файлов для загрузки: {total}")
    if set_title:
        set_title(f"⏳ Загрузка 0 / {total}...")

    completed = 0
    with ThreadPoolExecutor(max_workers=_max_workers()) as executor:
        futures = {
            executor.submit(
                _download_one,
                os.path.join(FTP_FOLDER, f),
                os.path.join(DOWNLOAD_FOLDER, f),
                log,
            ): f
            for f in files_to_download
        }
        for future in as_completed(futures):
            completed += 1
            if progress_callback:
                progress_callback(completed, total)
            if set_title:
                set_title(f"⏳ Загрузка {completed} / {total}...")

    if set_title:
        set_title("✅ Готово")
    messagebox.showinfo("Готово", f"Загрузка завершена!\nПапка: {DOWNLOAD_FOLDER}")
    log("Загрузка всех файлов завершена 🎉")


# ── Очистка папки ─────────────────────────────────────────────────────────────


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


def clear_output_folder(output_folder_var, log, messagebox):
    """Удаляет все файлы из папки сохранения CSV."""
    folder = output_folder_var.get().strip()
    if not folder or not os.path.isdir(folder):
        messagebox.showwarning(
            "Очистка", "Папка сохранения не задана или не существует"
        )
        return
    files = [
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if os.path.isfile(os.path.join(folder, f))
    ]
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
    import openpyxl  # ленивый импорт

    wb = openpyxl.load_workbook(file_path, read_only=True)
    name = wb.sheetnames[0]
    wb.close()
    return name


def process_file(file_path, output_folder, selected_filter, log):
    """Фильтрует один Excel-файл и сохраняет CSV."""
    import polars as pl  # ленивый импорт

    filename = os.path.basename(file_path)
    try:
        log(f"Обработка: {filename}")

        sheet_name = get_first_sheet_name(file_path)
        df = pl.read_excel(file_path, sheet_name=sheet_name).select(needed_columns)
        df = df.with_columns(
            [pl.col(c).cast(pl.Utf8).str.strip_chars() for c in df.columns]
        )

        if isinstance(selected_filter, dict):
            group_mask = (df["group"] == selected_filter["group"]) & (
                df["category"] == selected_filter["category"]
            )
        else:
            group_mask = pl.lit(False)
            for filt in selected_filter:
                group_mask = group_mask | (
                    (df["group"] == filt["group"])
                    & (df["category"] == filt["category"])
                )

        df_filtered = df.filter(group_mask & df["retailer"].is_in(network_map))

        os.makedirs(output_folder, exist_ok=True)
        output_file = os.path.join(
            output_folder, os.path.splitext(filename)[0] + ".csv"
        )
        df_filtered.write_csv(output_file, separator=",")

        log(f"Готово: {filename} | {df.height} → {df_filtered.height} строк")
        return True
    except Exception as e:
        log(f"Ошибка обработки {filename}: {e}")
        return False


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
    macro1_name,
    macro2_name,
    progress_callback=None,
    set_title=None,
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

    total = len(files)
    log(f"Начинаем обработку {total} файлов...")
    if set_title:
        set_title(f"⏳ Обработка 0 / {total}...")

    completed = 0
    with ThreadPoolExecutor(max_workers=_max_workers()) as executor:
        futures = {
            executor.submit(process_file, f, output_folder, selected_filter, log): f
            for f in files
        }
        for future in as_completed(futures):
            if stop_event.is_set():
                log("⛔ Остановлено пользователем")
                break
            completed += 1
            if progress_callback:
                progress_callback(completed, total)
            if set_title:
                set_title(f"⏳ Обработка {completed} / {total}...")

    if stop_event.is_set():
        if set_title:
            set_title("⛔ Остановлено")
        return

    if set_title:
        set_title("✅ Готово")
    log("Обработка промодаты завершена 🎉")
    messagebox.showinfo("Готово", f"CSV-файлы сохранены в:\n{output_folder}")

    refresh_power_query_files(
        pq_file1,
        pq_file2,
        macro1_name,
        macro2_name,
        log,
        stop_event,
    )


# ── Power Query / Excel refresh ───────────────────────────────────────────────


def refresh_file(file_path, log, stop_event):
    """Обновляет Power Query в обычном .xlsx файле."""
    import pythoncom
    import win32com.client as win32

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

        if stop_event.is_set():
            log(f"{filename} — остановлено до сохранения")
            return False

        wb.Save()
        log(f"{filename} — сохранён ✅")
        return True
    except Exception as e:
        log(f"Ошибка {filename}: {e}")
        return False
    finally:
        try:
            if wb:
                wb.Close(SaveChanges=False)
        except Exception:
            pass
        finally:
            del wb
        try:
            if excel:
                excel.Quit()
        except Exception:
            pass
        finally:
            del excel
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass
        gc.collect()


def _excel_session(log, func):
    """Открывает изолированный COM-сеанс Excel, выполняет func(excel) и корректно закрывает."""
    import pythoncom
    import win32com.client as win32

    excel = None
    pid = None
    pythoncom.CoInitialize()
    try:
        excel = win32.DispatchEx("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        excel.AutomationSecurity = 1
        pid = _get_excel_pid(excel)
        return func(excel)
    except Exception:
        raise
    finally:
        try:
            if excel:
                excel.Quit()
        except Exception:
            pass
        try:
            del excel
        except Exception:
            pass
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass
        gc.collect()
        if pid:
            kill_excel_pid(pid, log)


def _refresh_xlsm_query(file_path, log, stop_event):
    """Сеанс 1: открыть .xlsm, обновить Power Query, сохранить, закрыть."""
    filename = os.path.basename(file_path)

    def _run(excel):
        wb = None
        try:
            wb = excel.Workbooks.Open(file_path, UpdateLinks=0, ReadOnly=False)

            before = None
            try:
                before = wb.Worksheets[STATUS_SHEET].Range(STATUS_CELL).Value
                log(f"{filename} — до обновления: {before}")
            except Exception:
                log(f"{filename} — лист «{STATUS_SHEET}» не найден, ждём по таймауту")

            try:
                wb.RefreshAll()
            except Exception as e:
                log(f"{filename} — RefreshAll ошибка (продолжаем): {e}")
            log(f"{filename} — RefreshAll запущен...")

            time.sleep(5)

            timeout = 0
            while timeout < 450:
                if stop_event.is_set():
                    log(f"{filename} — остановлено пользователем")
                    return False
                time.sleep(2)
                try:
                    excel.Calculate()
                except Exception:
                    timeout += 1
                    continue
                if before is not None:
                    try:
                        after = wb.Worksheets[STATUS_SHEET].Range(STATUS_CELL).Value
                        if after is not None and after != before:
                            log(f"{filename} — Power Query обновлён: {after}")
                            break
                    except Exception:
                        pass
                timeout += 1
            else:
                log(f"{filename} — тайм-аут ожидания Power Query")

            if stop_event.is_set():
                log(f"{filename} — остановлено до сохранения")
                return False

            time.sleep(3)
            try:
                wb.Save()
            except Exception as e:
                log(f"{filename} — ошибка сохранения: {e}")
                return False
            log(f"{filename} — сохранён после обновления ✅")
            return True
        finally:
            try:
                if wb:
                    wb.Close(SaveChanges=False)
            except Exception:
                pass
            try:
                del wb
            except Exception:
                pass

    try:
        return _excel_session(log, _run)
    except Exception as e:
        log(f"Ошибка обновления квери {filename}: {e}")
        return False


def _run_xlsm_macros(file_path, macro_names, log, stop_event):
    """Сеанс 2: открыть .xlsm, запустить макросы, сохранить, закрыть."""
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
                if stop_event.is_set():
                    log("⛔ Остановлено пользователем")
                    return False
                log(f"  ▷ Макрос: {macro_name}")
                try:
                    excel.Application.Run(macro_name)
                    log(f"  ✅ {macro_name} — выполнен")
                except Exception as e:
                    log(f"  ❌ Ошибка макроса «{macro_name}»: {e}")

            if stop_event.is_set():
                log(f"{filename} — остановлено до сохранения")
                return False

            wb.Save()
            log(f"{filename} — сохранён после макросов ✅")
            return True
        finally:
            try:
                if wb:
                    wb.Close(SaveChanges=False)
            except Exception:
                pass
            try:
                del wb
            except Exception:
                pass

    try:
        return _excel_session(log, _run)
    except Exception as e:
        log(f"Ошибка запуска макросов {filename}: {e}")
        return False


def refresh_file_with_macros(file_path, macro_names, log, stop_event):
    """RefreshAll → макросы — два отдельных COM-сеанса."""
    filename = os.path.basename(file_path)

    log(f"▶ {filename}: сеанс 1 — обновление Power Query")
    ok = _refresh_xlsm_query(file_path, log, stop_event)
    if not ok or stop_event.is_set():
        return False

    time.sleep(3)

    log(f"▶ {filename}: сеанс 2 — запуск макросов")
    return _run_xlsm_macros(file_path, macro_names, log, stop_event)


def _get_excel_pid(excel) -> int | None:
    try:
        import win32process

        hwnd = excel.Hwnd
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        return pid
    except Exception:
        return None


def kill_excel_pid(pid: int | None, log):
    if pid is None:
        return
    try:
        import subprocess

        result = subprocess.run(
            ["taskkill", "/F", "/PID", str(pid)], capture_output=True, text=True
        )
        if result.returncode == 0:
            log(f"🧹 Процесс Excel (PID {pid}) завершён")
        else:
            log(f"🧹 Процесс Excel (PID {pid}) уже не активен")
    except Exception as e:
        log(f"Ошибка при завершении процесса Excel PID {pid}: {e}")


def refresh_power_query_files(
    pq_file1, pq_file2, macro1_name, macro2_name, log, stop_event
):
    """Обновляет оба файла Promodate полностью."""
    file1 = pq_file1.get()
    file2 = pq_file2.get()

    if not file1 or not os.path.isfile(file1):
        log("⚠️ Power Query файл 1 не выбран — шаг пропущен")
    else:
        log("▶ Обновляем Promodate (файл 1)...")
        success1 = refresh_file(file1, log, stop_event)
        if not success1:
            log("⚠️ Файл 1 не обновлён, продолжаем...")
        if stop_event.is_set():
            return

    if not file2 or not os.path.isfile(file2):
        log("⚠️ Power Query файл 2 не выбран — шаг пропущен")
        return

    m1 = (
        macro1_name.get().strip()
        if hasattr(macro1_name, "get")
        else str(macro1_name).strip()
    )
    m2 = (
        macro2_name.get().strip()
        if hasattr(macro2_name, "get")
        else str(macro2_name).strip()
    )
    macro_names = [m for m in [m1, m2] if m]

    log("▶ Обновляем Promodate (файл 2 — xlsm + макросы)...")
    success2 = refresh_file_with_macros(file2, macro_names, log, stop_event)
    if success2:
        log("Promodate полностью обновлён 🎉")


# ── Поэтапный запуск ─────────────────────────────────────────────────────────


def run_stage_query1(pq_file1_var, log, stop_event, messagebox=None):
    """Только обновление файла 1 (xlsx)."""
    file1 = pq_file1_var.get() if hasattr(pq_file1_var, "get") else str(pq_file1_var)
    if not file1 or not os.path.isfile(file1):
        msg = "⚠️ Power Query файл 1 не выбран или не существует"
        log(msg)
        if messagebox:
            messagebox.showwarning("Ошибка", msg)
        return False
    log("▶ Стадия: Обновление Query 1...")
    ok = refresh_file(file1, log, stop_event)
    if ok:
        log("✅ Query 1 обновлён!")
    return ok


def run_stage_query2(pq_file2_var, log, stop_event, messagebox=None):
    """Только обновление Power Query файла 2 (xlsm), без макросов."""
    file2 = pq_file2_var.get() if hasattr(pq_file2_var, "get") else str(pq_file2_var)
    if not file2 or not os.path.isfile(file2):
        msg = "⚠️ Power Query файл 2 не выбран или не существует"
        log(msg)
        if messagebox:
            messagebox.showwarning("Ошибка", msg)
        return False
    log("▶ Стадия: Обновление Query 2 (xlsm)...")
    ok = _refresh_xlsm_query(file2, log, stop_event)
    if ok:
        log("✅ Query 2 обновлён!")
    return ok


def run_stage_macros(
    pq_file2_var, macro1_name, macro2_name, log, stop_event, messagebox=None
):
    """Только запуск макросов файла 2 (xlsm), без обновления PQ."""
    file2 = pq_file2_var.get() if hasattr(pq_file2_var, "get") else str(pq_file2_var)
    if not file2 or not os.path.isfile(file2):
        msg = "⚠️ Power Query файл 2 не выбран или не существует"
        log(msg)
        if messagebox:
            messagebox.showwarning("Ошибка", msg)
        return False

    m1 = (
        macro1_name.get().strip()
        if hasattr(macro1_name, "get")
        else str(macro1_name).strip()
    )
    m2 = (
        macro2_name.get().strip()
        if hasattr(macro2_name, "get")
        else str(macro2_name).strip()
    )
    macro_names = [m for m in [m1, m2] if m]

    if not macro_names:
        log("⚠️ Имена макросов не заданы — нечего запускать")
        if messagebox:
            messagebox.showwarning("Ошибка", "Укажите имена макросов в полях выше")
        return False

    log(f"▶ Стадия: Запуск макросов ({', '.join(macro_names)})...")
    ok = _run_xlsm_macros(file2, macro_names, log, stop_event)
    if ok:
        log("✅ Макросы выполнены!")
    return ok