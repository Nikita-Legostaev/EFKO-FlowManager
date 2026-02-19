import os
import customtkinter as ctk
from tkinter import messagebox, filedialog
from datetime import datetime
import threading


from promodate_functions import (
    FILTER_OPTIONS,
    download_files_thread,
    clear_download_folder,
    browse_output_folder,
    process_files_thread,
    refresh_power_query_files,
)
from competitors_functions import refresh_competitors_pipeline
from nielsen_functions import process_nielsen

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("green")

CONFIG_FILE = "last_folder.txt"

stop_event = threading.Event()
last_updated_competitors_file = None


def log(message):
    log_text.configure(state="normal")
    log_text.insert(ctk.END, f"[{datetime.now().strftime('%H:%M:%S')}] {message}\n")
    log_text.see(ctk.END)
    log_text.update_idletasks()
    log_text.configure(state="disabled")


def save_config():
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            f.write(output_folder_var.get().strip() + "\n")
            f.write(pq_file1.get().strip() + "\n")
            f.write(pq_file2.get().strip() + "\n")
            f.write(olap_file.get().strip() + "\n")
            f.write(competitors_file.get().strip() + "\n")
            f.write(nielsen_input_file.get().strip() + "\n")
            f.write(nielsen_output_dir.get().strip() + "\n")
            f.write(nielsen_format.get() + "\n")
            f.write(nielsen_category_var.get() + "\n")
    except Exception as e:
        log(f"Ошибка сохранения конфига: {e}")


def load_config():
    output_folder = ""
    file1 = ""
    file2 = ""
    olap = ""
    competitors = ""
    nielsen_input = ""
    nielsen_output = ""
    nielsen_fmt = "csv"
    nielsen_category = "Масло"
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
                if len(lines) >= 6 and os.path.isfile(lines[5]):
                    nielsen_input = lines[5]
                if len(lines) >= 7 and os.path.isdir(lines[6]):
                    nielsen_output = lines[6]
                if len(lines) >= 8:
                    nielsen_fmt = lines[7]
                if len(lines) >= 9:
                    nielsen_category = lines[8]
        except Exception as e:
            log(f"Ошибка загрузки конфига: {e}")
    return (
        output_folder,
        file1,
        file2,
        olap,
        competitors,
        nielsen_input,
        nielsen_output,
        nielsen_fmt,
        nielsen_category,
    )


def start_download_thread():
    threading.Thread(
        target=download_files_thread,
        args=(month_var, year_var, log, messagebox),
        daemon=True,
    ).start()


def start_clear_download_thread():
    threading.Thread(
        target=clear_download_folder, args=(log, messagebox), daemon=True
    ).start()


def browse_power_query_file(var):
    file = filedialog.askopenfilename(
        title="Выберите Excel файл", filetypes=[("Excel", "*.xlsx *.xlsm")]
    )
    if file:
        var.set(file)
        log(f"Выбран файл: {file}")
        save_config()


def browse_nielsen_input():
    file = filedialog.askopenfilename(
        title="Выберите файл Nielsen", filetypes=[("Excel", "*.xlsx")]
    )
    if file:
        nielsen_input_file.set(file)
        log(f"Выбран файл Nielsen: {file}")
        save_config()


def browse_nielsen_output():
    folder = filedialog.askdirectory(title="Выберите папку сохранения")
    if folder:
        nielsen_output_dir.set(folder)
        log(f"Выбрана папка сохранения Nielsen: {folder}")
        save_config()


def start_processing_thread():
    threading.Thread(
        target=process_files_thread,
        args=(
            output_folder_var,
            filter_var,
            FILTER_OPTIONS,
            log,
            messagebox,
            stop_event,
            refresh_power_query_files,
            pq_file1,
            pq_file2,
        ),
        daemon=True,
    ).start()


def start_main_action():
    stop_event.clear()
    mode = action_var.get()
    if mode == "promodate":
        log("Запущен режим: Фильтрация промодаты + Promodate")
        start_processing_thread()
    elif mode == "competitors":
        log("Запущен режим: Положение конкурентов")
        threading.Thread(
            target=refresh_competitors_pipeline,
            args=(olap_file, competitors_file, log, messagebox, stop_event),
            daemon=True,
        ).start()
    elif mode == "nielsen":
        log("Запущен режим: Обработка Nielsen")
        threading.Thread(
            target=process_nielsen,
            args=(
                nielsen_input_file.get(),
                nielsen_output_dir.get(),
                nielsen_format.get(),
                log,
                messagebox,
                stop_event,
                nielsen_category_var.get(),
            ),
            daemon=True,
        ).start()
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
        messagebox.showinfo(
            "Инфо", "Последний файл не найден (запустите обновление конкурентов)"
        )


def update_gui(*args):
    mode = action_var.get()
    if mode == "promodate":
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

        label_olap.grid_remove()
        entry_olap.grid_remove()
        btn_olap.grid_remove()
        label_competitors.grid_remove()
        entry_competitors.grid_remove()
        btn_competitors.grid_remove()

        label_nielsen_input.grid_remove()
        entry_nielsen_input.grid_remove()
        btn_nielsen_input.grid_remove()
        label_nielsen_output.grid_remove()
        entry_nielsen_output.grid_remove()
        btn_nielsen_output.grid_remove()
        label_nielsen_format.grid_remove()
        menu_nielsen_format.grid_remove()
        label_nielsen_category.grid_remove()
        menu_nielsen_category.grid_remove()

        btn_download.grid(row=0, column=0, padx=10, pady=5)
        btn_clear.grid(row=0, column=1, padx=10, pady=5)
        start_btn.grid(row=0, column=2, padx=10, pady=5)
        stop_btn.grid(row=0, column=3, padx=10, pady=5)
        btn_open_last.grid_remove()

    elif mode == "competitors":
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

        label_olap.grid()
        entry_olap.grid()
        btn_olap.grid()
        label_competitors.grid()
        entry_competitors.grid()
        btn_competitors.grid()

        label_nielsen_input.grid_remove()
        entry_nielsen_input.grid_remove()
        btn_nielsen_input.grid_remove()
        label_nielsen_output.grid_remove()
        entry_nielsen_output.grid_remove()
        btn_nielsen_output.grid_remove()
        label_nielsen_format.grid_remove()
        menu_nielsen_format.grid_remove()
        label_nielsen_category.grid_remove()
        menu_nielsen_category.grid_remove()

        btn_download.grid_remove()
        btn_clear.grid_remove()
        start_btn.grid(row=0, column=0, padx=10, pady=5)
        stop_btn.grid(row=0, column=1, padx=10, pady=5)
        btn_open_last.grid(row=0, column=2, padx=10, pady=5)

    elif mode == "nielsen":
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

        label_olap.grid_remove()
        entry_olap.grid_remove()
        btn_olap.grid_remove()
        label_competitors.grid_remove()
        entry_competitors.grid_remove()
        btn_competitors.grid_remove()

        label_nielsen_input.grid()
        entry_nielsen_input.grid()
        btn_nielsen_input.grid()
        label_nielsen_output.grid()
        entry_nielsen_output.grid()
        btn_nielsen_output.grid()
        label_nielsen_format.grid()
        menu_nielsen_format.grid()
        label_nielsen_category.grid()
        menu_nielsen_category.grid()

        btn_download.grid_remove()
        btn_clear.grid_remove()
        start_btn.grid(row=0, column=0, padx=10, pady=5)
        stop_btn.grid(row=0, column=1, padx=10, pady=5)
        btn_open_last.grid_remove()

    root.update_idletasks()


root = ctk.CTk()
root.title("Промодата + Положение конкурентов + Обработка Nielsen")
root.geometry("1150x750")

(
    last_output,
    last_pq1,
    last_pq2,
    last_olap,
    last_competitors,
    last_nielsen_input,
    last_nielsen_output,
    last_nielsen_fmt,
    last_nielsen_category,
) = load_config()
month_var = ctk.StringVar(value=str(datetime.now().month))
year_var = ctk.StringVar(value=str(datetime.now().year))
output_folder_var = ctk.StringVar(value=last_output)
filter_var = ctk.StringVar(value="Масло")
pq_file1 = ctk.StringVar(value=last_pq1)
pq_file2 = ctk.StringVar(value=last_pq2)
olap_file = ctk.StringVar(value=last_olap)
competitors_file = ctk.StringVar(value=last_competitors)
nielsen_input_file = ctk.StringVar(value=last_nielsen_input)
nielsen_output_dir = ctk.StringVar(value=last_nielsen_output)
nielsen_format = ctk.StringVar(value=last_nielsen_fmt)
nielsen_category_var = ctk.StringVar(value=last_nielsen_category)
action_var = ctk.StringVar(value="promodate")

top_frame = ctk.CTkFrame(root)
top_frame.pack(fill="x", padx=20, pady=10)

label_month = ctk.CTkLabel(top_frame, text="Месяц:")
label_month.grid(row=0, column=0, sticky="e", padx=5, pady=5)
menu_month = ctk.CTkOptionMenu(
    top_frame, variable=month_var, values=[str(i) for i in range(1, 13)]
)
menu_month.grid(row=0, column=1, padx=5, pady=5)

label_year = ctk.CTkLabel(top_frame, text="Год:")
label_year.grid(row=0, column=2, sticky="e", padx=5, pady=5)
menu_year = ctk.CTkOptionMenu(
    top_frame, variable=year_var, values=[str(y) for y in range(2020, 2031)]
)
menu_year.grid(row=0, column=3, padx=5, pady=5)

label_category = ctk.CTkLabel(top_frame, text="Категория:")
label_category.grid(row=1, column=0, sticky="e", padx=5, pady=5)
menu_category = ctk.CTkOptionMenu(
    top_frame, variable=filter_var, values=list(FILTER_OPTIONS.keys())
)
menu_category.grid(row=1, column=1, columnspan=3, sticky="w", padx=5, pady=5)

label_output = ctk.CTkLabel(top_frame, text="Папка сохранения:")
label_output.grid(row=2, column=0, sticky="e", padx=5, pady=5)
entry_output = ctk.CTkEntry(top_frame, textvariable=output_folder_var, width=700)
entry_output.grid(row=2, column=1, columnspan=3, padx=5, pady=5)
btn_output = ctk.CTkButton(
    top_frame, text="Обзор", command=lambda: browse_output_folder(output_folder_var)
)
btn_output.grid(row=2, column=4, padx=5, pady=5)

label_pq1 = ctk.CTkLabel(top_frame, text="Power Query (Promodate 1):")
label_pq1.grid(row=3, column=0, sticky="e", padx=5, pady=5)
entry_pq1 = ctk.CTkEntry(top_frame, textvariable=pq_file1, width=700)
entry_pq1.grid(row=3, column=1, columnspan=3, padx=5, pady=5)
btn_pq1 = ctk.CTkButton(
    top_frame, text="Выбрать", command=lambda: browse_power_query_file(pq_file1)
)
btn_pq1.grid(row=3, column=4, padx=5, pady=5)

label_pq2 = ctk.CTkLabel(top_frame, text="Power Query (Promodate 2):")
label_pq2.grid(row=4, column=0, sticky="e", padx=5, pady=5)
entry_pq2 = ctk.CTkEntry(top_frame, textvariable=pq_file2, width=700)
entry_pq2.grid(row=4, column=1, columnspan=3, padx=5, pady=5)
btn_pq2 = ctk.CTkButton(
    top_frame, text="Выбрать", command=lambda: browse_power_query_file(pq_file2)
)
btn_pq2.grid(row=4, column=4, padx=5, pady=5)

label_olap = ctk.CTkLabel(top_frame, text="OLAP файл:")
label_olap.grid(row=5, column=0, sticky="e", padx=5, pady=5)
entry_olap = ctk.CTkEntry(top_frame, textvariable=olap_file, width=700)
entry_olap.grid(row=5, column=1, columnspan=3, padx=5, pady=5)
btn_olap = ctk.CTkButton(
    top_frame, text="Выбрать", command=lambda: browse_power_query_file(olap_file)
)
btn_olap.grid(row=5, column=4, padx=5, pady=5)

label_competitors = ctk.CTkLabel(top_frame, text="Положение конкурентов:")
label_competitors.grid(row=6, column=0, sticky="e", padx=5, pady=5)
entry_competitors = ctk.CTkEntry(top_frame, textvariable=competitors_file, width=700)
entry_competitors.grid(row=6, column=1, columnspan=3, padx=5, pady=5)
btn_competitors = ctk.CTkButton(
    top_frame, text="Выбрать", command=lambda: browse_power_query_file(competitors_file)
)
btn_competitors.grid(row=6, column=4, padx=5, pady=5)

label_nielsen_input = ctk.CTkLabel(top_frame, text="Входной файл Nielsen:")
label_nielsen_input.grid(row=7, column=0, sticky="e", padx=5, pady=5)
entry_nielsen_input = ctk.CTkEntry(
    top_frame, textvariable=nielsen_input_file, width=700
)
entry_nielsen_input.grid(row=7, column=1, columnspan=3, padx=5, pady=5)
btn_nielsen_input = ctk.CTkButton(
    top_frame, text="Выбрать", command=browse_nielsen_input
)
btn_nielsen_input.grid(row=7, column=4, padx=5, pady=5)

label_nielsen_output = ctk.CTkLabel(top_frame, text="Папка сохранения:")
label_nielsen_output.grid(row=8, column=0, sticky="e", padx=5, pady=5)
entry_nielsen_output = ctk.CTkEntry(
    top_frame, textvariable=nielsen_output_dir, width=700
)
entry_nielsen_output.grid(row=8, column=1, columnspan=3, padx=5, pady=5)
btn_nielsen_output = ctk.CTkButton(
    top_frame, text="Обзор", command=browse_nielsen_output
)
btn_nielsen_output.grid(row=8, column=4, padx=5, pady=5)

label_nielsen_format = ctk.CTkLabel(top_frame, text="Формат сохранения:")
label_nielsen_format.grid(row=9, column=0, sticky="e", padx=5, pady=5)
menu_nielsen_format = ctk.CTkOptionMenu(
    top_frame, variable=nielsen_format, values=["csv", "excel"]
)
menu_nielsen_format.grid(row=9, column=1, columnspan=3, sticky="w", padx=5, pady=5)

label_nielsen_category = ctk.CTkLabel(top_frame, text="Категория:")
label_nielsen_category.grid(row=10, column=0, sticky="e", padx=5, pady=5)
menu_nielsen_category = ctk.CTkOptionMenu(
    top_frame,
    variable=nielsen_category_var,
    values=["Масло", "Кетчуп", "Майонез", "Маргарин"],
)
menu_nielsen_category.grid(row=10, column=1, columnspan=3, sticky="w", padx=5, pady=5)

mode_frame = ctk.CTkFrame(root, fg_color="transparent")
mode_frame.pack(fill="x", padx=20, pady=10)

ctk.CTkLabel(
    mode_frame, text="Выберите действие", font=ctk.CTkFont(size=14, weight="bold")
).pack(anchor="w", pady=5)

radio_promodate = ctk.CTkRadioButton(
    mode_frame,
    text="Фильтрация промодаты + обновление Promodate",
    variable=action_var,
    value="promodate",
)
radio_promodate.pack(anchor="w", pady=5)

radio_competitors = ctk.CTkRadioButton(
    mode_frame,
    text="Обновление «Положение конкурентов»",
    variable=action_var,
    value="competitors",
)
radio_competitors.pack(anchor="w", pady=5)

radio_nielsen = ctk.CTkRadioButton(
    mode_frame, text="Обработка Nielsen", variable=action_var, value="nielsen"
)
radio_nielsen.pack(anchor="w", pady=5)

btn_frame = ctk.CTkFrame(root)
btn_frame.pack(fill="x", padx=20, pady=10)

btn_download = ctk.CTkButton(
    btn_frame, text="Скачать файлы", command=start_download_thread, width=200
)
btn_clear = ctk.CTkButton(
    btn_frame, text="Очистить Скаченное", command=start_clear_download_thread, width=200
)
start_btn = ctk.CTkButton(
    btn_frame,
    text="▶ ЗАПУСТИТЬ",
    command=start_main_action,
    width=200,
    height=40,
    font=ctk.CTkFont(size=14, weight="bold"),
)
stop_btn = ctk.CTkButton(
    btn_frame,
    text="■ Остановить",
    command=lambda: stop_event.set(),
    width=200,
    height=40,
)
btn_open_last = ctk.CTkButton(
    btn_frame,
    text="Открыть последний файл",
    command=open_last_file,
    width=200,
    height=40,
)

log_frame = ctk.CTkFrame(root)
log_frame.pack(fill="both", expand=True, padx=20, pady=10)
ctk.CTkLabel(
    log_frame, text="Лог работы:", font=ctk.CTkFont(size=14, weight="bold")
).pack(anchor="nw", pady=5)
log_text = ctk.CTkTextbox(log_frame, state="disabled", height=200)
log_text.pack(fill="both", expand=True)

action_var.trace("w", update_gui)

update_gui()


def on_closing():
    if messagebox.askokcancel("Выход", "Закрыть приложение?"):
        save_config()
        root.destroy()


root.protocol("WM_DELETE_WINDOW", on_closing)
log("Приложение запущено. Выберите режим и нажмите ЗАПУСТИТЬ")
root.mainloop()
