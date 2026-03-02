# competitors_functions.py
import os
import time
import gc

# Тяжёлые COM-библиотеки — ленивый импорт, чтобы не тормозить запуск exe

STATUS_SHEET = "Проверка_обновления"
STATUS_CELL = "A2"


def refresh_file(file_path, log, stop_event, timeout_minutes: int = 15):
    import pythoncom              # ленивый импорт
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
        max_iter = timeout_minutes * 30  # итераций (sleep 2 сек → 30 итер/мин)
        while timeout < max_iter:
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

        # Исправлено: проверяем stop_event перед сохранением
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
        if wb:
            wb.Close(SaveChanges=False)
            del wb
        if excel:
            excel.Quit()
            del excel
        pythoncom.CoUninitialize()
        gc.collect()


def refresh_competitors_pipeline(
    olap_file, competitors_file, log, messagebox, stop_event,
    on_file_updated=None,   # callback(path) → app.py обновит свой last_updated_competitors_file
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
    # Исправлено: убран stop_event.clear() — app.py делает это сам перед запуском

    if not refresh_file(olap_path, log, stop_event):
        if not stop_event.is_set():
            log("❌ OLAP не обновлён — прерываем")
        return

    if stop_event.is_set():
        return

    log("\nOLAP готов → запускаем основной файл...")
    success = refresh_file(competitors_path, log, stop_event)

    if success and not stop_event.is_set():
        # Исправлено: сообщаем app.py через callback вместо своего глобала
        if on_file_updated:
            on_file_updated(competitors_path)
        log("✅ Положение конкурентов успешно обновлено!")
        messagebox.showinfo("Готово", "Положение конкурентов обновлено!")
    else:
        log("Пайплайн прерван или завершился с ошибкой")