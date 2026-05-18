# competitors_functions.py
import os
import time
import gc

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


# Тяжёлые COM-библиотеки — ленивый импорт, чтобы не тормозить запуск exe




def _set_sync_refresh(wb, log):
    """Отключает BackgroundQuery для всех OLEDB/PQ соединений → RefreshAll() синхронный."""
    saved = []
    for conn in wb.Connections:
        try:
            if conn.Type == 1:  # xlConnectionTypeOLEDB
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
        try:
            oledb.BackgroundQuery = original
        except Exception:
            pass


def refresh_file(file_path, log, stop_event, timeout_minutes: int = 15):
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
        _excel_optimize(excel)
        wb = excel.Workbooks.Open(file_path)

        saved = _set_sync_refresh(wb, log)

        if stop_event.is_set():
            log(f"{filename} — остановлено до обновления")
            return False

        log(f"{filename} — RefreshAll() запущен (синхронно)...")
        wb.RefreshAll()  # блокирует до завершения всех PQ
        log(f"{filename} — обновление завершено ✅")

        if stop_event.is_set():
            log(f"{filename} — остановлено до сохранения")
            return False

        _restore_bg_refresh(saved)
        _excel_restore(excel)
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
    olap_file,
    competitors_file,
    log,
    messagebox,
    stop_event,
    on_file_updated=None,  # callback(path) → app.py обновит свой last_updated_competitors_file
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