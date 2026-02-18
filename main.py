import os
import shutil
import customtkinter as ctk
from tkinter import messagebox, filedialog
from datetime import datetime
import threading
from concurrent.futures import ThreadPoolExecutor
import polars as pl
import pandas as pd
import win32com.client as win32
import time
import gc
import pythoncom

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("green")

CONFIG_FILE = "last_folder.txt"

# ====================== ПАПКИ ======================
FTP_FOLDER = r"M:\FTP"
DOWNLOAD_FOLDER = os.path.join(os.getcwd(), "Скаченное")
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# ====================== СЕТИ ======================
network_map = {
    "Globus", "Metro", "Ашан", "Дикси",
    "Лента Гипер", "Лента Супер", "Лента Эконом",
    "Магнит (у дома)", "Магнит Мини",
    "Магнит Семейный", "Магнит Экстра",
    "Монетка", "О'кей",
    "Перекрёсток*", "Пятёрочка", "Чижик"
}

needed_columns = ['group', 'category', 'brand', 'pd_sku', 'retailer', 'region', 'date', 'promo', 'regular']

# ====================== ФИЛЬТРЫ ======================
FILTER_OPTIONS = {
    "Масло": {"group": "Соусы и масла", "category": "Масло растительное"},
    "Маргарин": {"group": "Майонез, масло сливочное, яйцо", "category": "Маргарин, спред, жир"},
    "Майонез": {"group": "Майонез, масло сливочное, яйцо", "category": "Майонез"},
    "Кетчуп": {"group": "Соусы и масла", "category": "Кетчупы"},
    "Продукты растительного происхождения": {"group": "Диетическое и здоровое питание", "category": "Продукты растительного происхождения"}
}

# ====================== POWER QUERY ======================
STATUS_SHEET = "Проверка_обновления"
STATUS_CELL = "A2"

# ====================== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ======================
stop_event = threading.Event()
last_updated_competitors_file = None

# ====================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ======================
def extract_date(filename):
    for part in filename.split('_'):
        try:
            return datetime.strptime(part, "%Y-%m-%d")
        except:
            continue
    return None

def log(message):
    log_text.configure(state='normal')
    log_text.insert(ctk.END, f"[{datetime.now().strftime('%H:%M:%S')}] {message}\n")
    log_text.see(ctk.END)
    log_text.update_idletasks()
    log_text.configure(state='disabled')

# ====================== КОНФИГУРАЦИЯ ======================
def save_config():
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            f.write(output_folder_var.get().strip() + "\n")
            f.write(pq_file1.get().strip() + "\n")
            f.write(pq_file2.get().strip() + "\n")
            f.write(olap_file.get().strip() + "\n")
            f.write(competitors_file.get().strip() + "\n")
    except Exception as e:
        log(f"Ошибка сохранения конфига: {e}")

def load_config():
    output_folder = ""
    file1 = ""
    file2 = ""
    olap = ""
    competitors = ""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f.readlines()]
                if len(lines) >= 1 and os.path.isdir(lines[0]):
                    output_folder = lines[0]
                if len(lines) >= 2 and os.path.isfile(lines[1]):
                    file1 = lines[1]
                if len(lines) >= 3 and os.path.isfile(lines[2]):
                    file2 = lines[2]
                if len(lines) >= 4 and os.path.isfile(lines[3]):
                    olap = lines[3]
                if len(lines) >= 5 and os.path.isfile(lines[4]):
                    competitors = lines[4]
        except Exception as e:
            log(f"Ошибка загрузки конфига: {e}")
    return output_folder, file1, file2, olap, competitors

# ====================== ЗАГРУЗКА ФАЙЛОВ ======================
def download_file(src, dst):
    try:
        filename = os.path.basename(src)
        log(f"Начата загрузка: {filename}")
        shutil.copy2(src, dst)
        log(f"Загрузка завершена: {filename}")
    except Exception as e:
        log(f"Ошибка загрузки {filename}: {e}")

def download_files_thread():
    month = int(month_var.get())
    year = int(year_var.get())
    files = [f for f in os.listdir(FTP_FOLDER) if f.endswith(".xlsx")]
    files_to_download = [f for f in files if extract_date(f) and extract_date(f).month == month and extract_date(f).year == year]

    if not files_to_download:
        log("Нет файлов за выбранный месяц/год")
        messagebox.showwarning("Инфо", "Нет файлов для загрузки")
        return

    with ThreadPoolExecutor(max_workers=6) as executor:
        for file in files_to_download:
            src = os.path.join(FTP_FOLDER, file)
            dst = os.path.join(DOWNLOAD_FOLDER, file)
            executor.submit(download_file, src, dst)

    messagebox.showinfo("Готово", f"Загрузка завершена!\nПапка: {DOWNLOAD_FOLDER}")
    log("Загрузка всех файлов завершена 🎉")

def start_download_thread():
    threading.Thread(target=download_files_thread, daemon=True).start()

# ====================== ОЧИСТКА ======================
def clear_download_folder():
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

def start_clear_download_thread():
    threading.Thread(target=clear_download_folder, daemon=True).start()

# ====================== ВЫБОР ПАПОК ======================
def browse_output_folder():
    folder = filedialog.askdirectory()
    if folder:
        output_folder_var.set(folder)
        save_config()

def browse_power_query_file(var):
    file = filedialog.askopenfilename(title="Выберите Excel файл", filetypes=[("Excel", "*.xlsx *.xlsm")])
    if file:
        var.set(file)
        log(f"Выбран файл: {file}")
        save_config()

# ====================== EXCEL ======================
def get_first_sheet_name(file_path):
    import openpyxl
    wb = openpyxl.load_workbook(file_path, read_only=True)
    return wb.sheetnames[0]

# ====================== ОБРАБОТКА ПРОМОДАТЫ ======================
def process_file(file_path, output_folder, selected_filter, chunk_size=100_000):
    try:
        filename = os.path.basename(file_path)
        log(f"Обработка: {filename}")

        sheet_name = get_first_sheet_name(file_path)
        df = pl.read_excel(file_path, sheet_name=sheet_name).select(needed_columns)
        df = df.with_columns([pl.col(c).cast(pl.Utf8).str.strip_chars() for c in df.columns])

        mask = (
            (df['group'] == selected_filter["group"]) &
            (df['category'] == selected_filter["category"]) &
            (df['retailer'].is_in(network_map))
        )
        df_filtered = df.filter(mask)

        os.makedirs(output_folder, exist_ok=True)
        output_file = os.path.join(output_folder, os.path.splitext(filename)[0] + ".csv")

        for start in range(0, df_filtered.height, chunk_size):
            chunk = df_filtered[start:start + chunk_size].to_pandas()
            mode = "w" if start == 0 else "a"
            header = start == 0
            chunk.to_csv(output_file, index=False, encoding="utf-8-sig", mode=mode, header=header)

        log(f"Готово: {filename} | {df.height} → {df_filtered.height} строк")
    except Exception as e:
        log(f"Ошибка обработки {filename}: {e}")

# ====================== POWER QUERY (Promodate) ======================
def read_refresh_value(wb):
    try:
        return wb.Worksheets[STATUS_SHEET].Range(STATUS_CELL).Value
    except:
        return None

def refresh_file(file_path):
    filename = os.path.basename(file_path)
    excel = None
    wb = None
    try:
        pythoncom.CoInitialize()  # Инициализация COM для этого потока
        excel = win32.DispatchEx("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        wb = excel.Workbooks.Open(file_path)

        before = read_refresh_value(wb)
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
            after = read_refresh_value(wb)
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

def refresh_power_query_files():
    file1 = pq_file1.get()
    file2 = pq_file2.get()
    if not file1 or not os.path.isfile(file1):
        log("Power Query файл 1 не выбран!")
        return
    if not file2 or not os.path.isfile(file2):
        log("Power Query файл 2 не выбран!")
        return
    log("Обновляем Promodate...")
    success1 = refresh_file(file1)
    if success1 and not stop_event.is_set():
        success2 = refresh_file(file2)
        if success2:
            log("Promodate обновлён 🎉")
            messagebox.showinfo("Готово", "Promodate обновлён!")

# ====================== ОСНОВНАЯ ОБРАБОТКА ПРОМОДАТЫ ======================
def process_files_thread():
    output_folder = output_folder_var.get().strip()
    if not output_folder:
        messagebox.showwarning("Ошибка", "Укажите папку сохранения!")
        return

    save_config()
    selected_filter = FILTER_OPTIONS[filter_var.get()]

    files = [os.path.join(DOWNLOAD_FOLDER, f) for f in os.listdir(DOWNLOAD_FOLDER) if f.endswith(".xlsx")]
    if not files:
        messagebox.showwarning("Ошибка", "Нет Excel-файлов в папке Скаченное!")
        return

    with ThreadPoolExecutor(max_workers=6) as executor:
        for file in files:
            executor.submit(process_file, file, output_folder, selected_filter)

    log("Обработка промодаты завершена 🎉")
    messagebox.showinfo("Готово", f"CSV-файлы сохранены в:\n{output_folder}")
    refresh_power_query_files()

def start_processing_thread():
    threading.Thread(target=process_files_thread, daemon=True).start()

# ====================== ПАЙПЛАЙН КОНКУРЕНТОВ ======================
def refresh_competitors_pipeline():
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

    if not refresh_file(olap_path):
        log("❌ OLAP не обновлён — прерываем")
        return
    if stop_event.is_set():
        return

    log("\nOLAP готов → запускаем основной файл...")
    success = refresh_file(competitors_path)

    if success and not stop_event.is_set():
        global last_updated_competitors_file
        last_updated_competitors_file = competitors_path
        log("✅ Положение конкурентов успешно обновлено!")
        messagebox.showinfo("Готово", "Положение конкурентов обновлено!")
    else:
        log("Пайплайн прерван или завершился с ошибкой")

# ====================== ЕДИНЫЙ ЗАПУСК ======================
def start_main_action():
    stop_event.clear()
    if action_var.get() == "promodate":
        log("Запущен режим: Фильтрация промодаты + Promodate")
        start_processing_thread()
    elif action_var.get() == "competitors":
        log("Запущен режим: Положение конкурентов")
        threading.Thread(target=refresh_competitors_pipeline, daemon=True).start()
    else:
        messagebox.showwarning("Ошибка", "Выберите режим работы")

def open_last_file():
    global last_updated_competitors_file
    if last_updated_competitors_file and os.path.exists(last_updated_competitors_file):
        try:
            os.startfile(last_updated_competitors_file)
            log(f"Открыт: {os.path.basename(last_updated_competitors_file)}")
        except Exception as e:
            log(f"Не удалось открыть файл: {e}")
    else:
        messagebox.showinfo("Инфо", "Последний файл не найден (запустите обновление конкурентов)")

# ====================== ОБНОВЛЕНИЕ GUI ======================
def update_gui(*args):
    mode = action_var.get()
    if mode == "promodate":
        # Показать элементы для promodate
        label_month.grid()
        menu_month.grid()
        label_year.grid()
        menu_year.grid()
        label_category.grid()
        menu_category.grid()
        label_output.grid()
        entry_output.grid()
        btn_output.grid()
        label_pq1.grid()
        entry_pq1.grid()
        btn_pq1.grid()
        label_pq2.grid()
        entry_pq2.grid()
        btn_pq2.grid()

        # Скрыть элементы для competitors
        label_olap.grid_remove()
        entry_olap.grid_remove()
        btn_olap.grid_remove()
        label_competitors.grid_remove()
        entry_competitors.grid_remove()
        btn_competitors.grid_remove()

        # Кнопки
        btn_download.grid_remove()
        btn_clear.grid_remove()
        start_btn.grid_remove()
        stop_btn.grid_remove()
        btn_open_last.grid_remove()

        btn_download.grid(row=0, column=0, padx=10, pady=5)
        btn_clear.grid(row=0, column=1, padx=10, pady=5)
        start_btn.grid(row=0, column=2, padx=10, pady=5)
        stop_btn.grid(row=0, column=3, padx=10, pady=5)

    elif mode == "competitors":
        # Скрыть элементы для promodate
        label_month.grid_remove()
        menu_month.grid_remove()
        label_year.grid_remove()
        menu_year.grid_remove()
        label_category.grid_remove()
        menu_category.grid_remove()
        label_output.grid_remove()
        entry_output.grid_remove()
        btn_output.grid_remove()
        label_pq1.grid_remove()
        entry_pq1.grid_remove()
        btn_pq1.grid_remove()
        label_pq2.grid_remove()
        entry_pq2.grid_remove()
        btn_pq2.grid_remove()

        # Показать элементы для competitors
        label_olap.grid()
        entry_olap.grid()
        btn_olap.grid()
        label_competitors.grid()
        entry_competitors.grid()
        btn_competitors.grid()

        # Кнопки
        btn_download.grid_remove()
        btn_clear.grid_remove()
        start_btn.grid_remove()
        stop_btn.grid_remove()
        btn_open_last.grid_remove()

        start_btn.grid(row=0, column=0, padx=10, pady=5)
        stop_btn.grid(row=0, column=1, padx=10, pady=5)
        btn_open_last.grid(row=0, column=2, padx=10, pady=5)

    root.update_idletasks()

# ====================== GUI ======================
root = ctk.CTk()
root.title("Промодата + Положение конкурентов")
root.geometry("1150x750")

# Tkinter переменные
last_output, last_pq1, last_pq2, last_olap, last_competitors = load_config()
month_var = ctk.StringVar(value=str(datetime.now().month))
year_var = ctk.StringVar(value=str(datetime.now().year))
output_folder_var = ctk.StringVar(value=last_output)
filter_var = ctk.StringVar(value="Масло")
pq_file1 = ctk.StringVar(value=last_pq1)
pq_file2 = ctk.StringVar(value=last_pq2)
olap_file = ctk.StringVar(value=last_olap)
competitors_file = ctk.StringVar(value=last_competitors)
action_var = ctk.StringVar(value="promodate")

# Верхняя панель
top_frame = ctk.CTkFrame(root)
top_frame.pack(fill="x", padx=20, pady=10)

# Элементы для promodate (row 0-4)
label_month = ctk.CTkLabel(top_frame, text="Месяц:")
label_month.grid(row=0, column=0, sticky="e", padx=5, pady=5)
menu_month = ctk.CTkOptionMenu(top_frame, variable=month_var, values=[str(i) for i in range(1, 13)])
menu_month.grid(row=0, column=1, padx=5, pady=5)

label_year = ctk.CTkLabel(top_frame, text="Год:")
label_year.grid(row=0, column=2, sticky="e", padx=5, pady=5)
menu_year = ctk.CTkOptionMenu(top_frame, variable=year_var, values=[str(y) for y in range(2020, 2031)])
menu_year.grid(row=0, column=3, padx=5, pady=5)

label_category = ctk.CTkLabel(top_frame, text="Категория:")
label_category.grid(row=1, column=0, sticky="e", padx=5, pady=5)
menu_category = ctk.CTkOptionMenu(top_frame, variable=filter_var, values=list(FILTER_OPTIONS.keys()))
menu_category.grid(row=1, column=1, columnspan=3, sticky="w", padx=5, pady=5)

label_output = ctk.CTkLabel(top_frame, text="Папка сохранения:")
label_output.grid(row=2, column=0, sticky="e", padx=5, pady=5)
entry_output = ctk.CTkEntry(top_frame, textvariable=output_folder_var, width=700)
entry_output.grid(row=2, column=1, columnspan=3, padx=5, pady=5)
btn_output = ctk.CTkButton(top_frame, text="Обзор", command=browse_output_folder)
btn_output.grid(row=2, column=4, padx=5, pady=5)

label_pq1 = ctk.CTkLabel(top_frame, text="Power Query (Promodate 1):")
label_pq1.grid(row=3, column=0, sticky="e", padx=5, pady=5)
entry_pq1 = ctk.CTkEntry(top_frame, textvariable=pq_file1, width=700)
entry_pq1.grid(row=3, column=1, columnspan=3, padx=5, pady=5)
btn_pq1 = ctk.CTkButton(top_frame, text="Выбрать", command=lambda: browse_power_query_file(pq_file1))
btn_pq1.grid(row=3, column=4, padx=5, pady=5)

label_pq2 = ctk.CTkLabel(top_frame, text="Power Query (Promodate 2):")
label_pq2.grid(row=4, column=0, sticky="e", padx=5, pady=5)
entry_pq2 = ctk.CTkEntry(top_frame, textvariable=pq_file2, width=700)
entry_pq2.grid(row=4, column=1, columnspan=3, padx=5, pady=5)
btn_pq2 = ctk.CTkButton(top_frame, text="Выбрать", command=lambda: browse_power_query_file(pq_file2))
btn_pq2.grid(row=4, column=4, padx=5, pady=5)

# Элементы для competitors (row 5-6)
label_olap = ctk.CTkLabel(top_frame, text="OLAP файл:")
label_olap.grid(row=5, column=0, sticky="e", padx=5, pady=5)
entry_olap = ctk.CTkEntry(top_frame, textvariable=olap_file, width=700)
entry_olap.grid(row=5, column=1, columnspan=3, padx=5, pady=5)
btn_olap = ctk.CTkButton(top_frame, text="Выбрать", command=lambda: browse_power_query_file(olap_file))
btn_olap.grid(row=5, column=4, padx=5, pady=5)

label_competitors = ctk.CTkLabel(top_frame, text="Положение конкурентов:")
label_competitors.grid(row=6, column=0, sticky="e", padx=5, pady=5)
entry_competitors = ctk.CTkEntry(top_frame, textvariable=competitors_file, width=700)
entry_competitors.grid(row=6, column=1, columnspan=3, padx=5, pady=5)
btn_competitors = ctk.CTkButton(top_frame, text="Выбрать", command=lambda: browse_power_query_file(competitors_file))
btn_competitors.grid(row=6, column=4, padx=5, pady=5)

# Выбор режима
mode_frame = ctk.CTkFrame(root, fg_color="transparent")
mode_frame.pack(fill="x", padx=20, pady=10)

ctk.CTkLabel(mode_frame, text="Выберите действие", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", pady=5)

radio_promodate = ctk.CTkRadioButton(mode_frame, text="Фильтрация промодаты + обновление Promodate", 
                                     variable=action_var, value="promodate")
radio_promodate.pack(anchor="w", pady=5)

radio_competitors = ctk.CTkRadioButton(mode_frame, text="Обновление «Положение конкурентов на рынке кетчупа»", 
                                       variable=action_var, value="competitors")
radio_competitors.pack(anchor="w", pady=5)

# Кнопки
btn_frame = ctk.CTkFrame(root)
btn_frame.pack(fill="x", padx=20, pady=10)

btn_download = ctk.CTkButton(btn_frame, text="Скачать файлы", command=start_download_thread, width=200)
btn_clear = ctk.CTkButton(btn_frame, text="Очистить Скаченное", command=start_clear_download_thread, width=200)
start_btn = ctk.CTkButton(btn_frame, text="▶ ЗАПУСТИТЬ", command=start_main_action,
                          width=200, height=40, font=ctk.CTkFont(size=14, weight="bold"))
stop_btn = ctk.CTkButton(btn_frame, text="■ Остановить", command=lambda: stop_event.set(),
                         width=200, height=40)
btn_open_last = ctk.CTkButton(btn_frame, text="Открыть последний файл", command=open_last_file,
                              width=200, height=40)

# Лог
log_frame = ctk.CTkFrame(root)
log_frame.pack(fill="both", expand=True, padx=20, pady=10)
ctk.CTkLabel(log_frame, text="Лог работы:", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="nw", pady=5)
log_text = ctk.CTkTextbox(log_frame, state='disabled', height=200)
log_text.pack(fill="both", expand=True)

# Привязка обновления GUI к изменению action_var
action_var.trace("w", update_gui)

# Инициализация GUI в зависимости от начального режима
update_gui()

# Выход
def on_closing():
    if messagebox.askokcancel("Выход", "Закрыть приложение?"):
        save_config()
        root.destroy()

root.protocol("WM_DELETE_WINDOW", on_closing)
log("Приложение запущено. Выберите режим и нажмите ЗАПУСТИТЬ")
root.mainloop()