# competitors_functions.py
import os
import time
import gc
import pythoncom
import win32com.client as win32

# ====================== POWER QUERY ======================
STATUS_SHEET = "Проверка_обновления"
STATUS_CELL = "A2"


def refresh_file(file_path, log, stop_event):
    filename = os.path.basename(file_path)
    excel = None
    wb = None
    try:
        pythoncom.CoInitialize()  # Инициализация COM для этого потока
        excel = win32.DispatchEx("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        wb = excel.Workbooks.Open(file_path)

        before = wb.Worksheets[STATUS_SHEET].Range(STATUS_CELL).Value
        log(f"{filename} — до: {before}")
        wb.RefreshAll()
        log(f"{filename} — RefreshAll запущен...")

        timeout = 0
        while timeout < 450:  # ~15 минут
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
        pythoncom.CoUninitialize()  # Очистка COM
        gc.collect()


def refresh_competitors_pipeline(
    olap_file, competitors_file, log, messagebox, stop_event
):
    olap_path = olap_file.get()
    competitors_path = competitors_file.get()

    if not olap_path or not os.path.isfile(olap_path):
        log("OLAP файл не выбран!")
        messagebox.showwarning("Ошибка", "Выберите OLAP файл")
        return
    if not competitors_path or not os.path.isfile(competitors_path):
        log("Файл Положение конкурентов не выбран!")
        messagebox.showwarning("Ошибка", "Выберите файл Положение конкурентов")
        return

    log("=== ЗАПУСК ПАЙПЛАЙНА «ПОЛОЖЕНИЕ КОНКУРЕНТОВ» ===")
    stop_event.clear()

    if not refresh_file(olap_path, log, stop_event):
        log("❌ OLAP не обновлён — прерываем")
        return
    if stop_event.is_set():
        return

    log("\nOLAP готов → запускаем основной файл...")
    success = refresh_file(competitors_path, log, stop_event)

    if success and not stop_event.is_set():
        global last_updated_competitors_file
        last_updated_competitors_file = competitors_path
        log("✅ Положение конкурентов успешно обновлено!")
        messagebox.showinfo("Готово", "Положение конкурентов обновлено!")
    else:
        log("Пайплайн прерван или завершился с ошибкой")
