import os
import json
import threading
import customtkinter as ctk
from tkinter import messagebox, filedialog
from datetime import datetime

from promodate_functions import (
    FILTER_OPTIONS,
    download_files_thread,
    clear_download_folder,
    browse_output_folder,
    process_files_thread,
    refresh_power_query_files,
    setup_file_logger,
    file_log,
    DOWNLOAD_FOLDER,
)
from competitors_functions import refresh_competitors_pipeline
from nielsen_functions import process_nielsen
from production_functions import run_production, MONTH_LABELS

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("green")

CONFIG_FILE = "config.json"
LOG_MAX_LINES = 500       # максимум строк в окне лога

stop_event = threading.Event()
last_updated_competitors_file = None

setup_file_logger()


# ── Конфиг (JSON) ──────────────────────────────────────────────────────────────

def save_config():
    data = {
        "output_folder":    output_folder_var.get().strip(),
        "pq_file1":         pq_file1.get().strip(),
        "pq_file2":         pq_file2.get().strip(),
        "olap_file":        olap_file.get().strip(),
        "competitors_file": competitors_file.get().strip(),
        "nielsen_input":    nielsen_input_file.get().strip(),
        "nielsen_output":   nielsen_output_dir.get().strip(),
        "nielsen_format":   nielsen_format.get(),
        "nielsen_category": nielsen_category_var.get(),
        "query_refresh_file": query_refresh_file.get().strip(),
        "prod_svod_folder":   prod_svod_folder.get().strip(),
        "prod_npk_file":      prod_npk_file.get().strip(),
        "prod_tolyatti":      prod_tolyatti_folder.get().strip(),
        "prod_target":        prod_target_file.get().strip(),
        "prod_mapping":       prod_mapping_file.get().strip(),
        "prod_year":          prod_year_var.get().strip(),
    }
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log(f"Ошибка сохранения конфига: {e}")


def load_config() -> dict:
    defaults = {
        "output_folder": "", "pq_file1": "", "pq_file2": "",
        "olap_file": "", "competitors_file": "",
        "nielsen_input": "", "nielsen_output": "",
        "nielsen_format": "csv", "nielsen_category": "Масло",
        "query_refresh_file": "",
        "prod_svod_folder":   "",
        "prod_npk_file":      "",
        "prod_tolyatti":      "",
        "prod_target":        "",
        "prod_mapping":       "",
        "prod_year":          str(datetime.now().year),
    }
    # Поддержка старого формата last_folder.txt при первом запуске
    if not os.path.exists(CONFIG_FILE) and os.path.exists("last_folder.txt"):
        try:
            with open("last_folder.txt", "r", encoding="utf-8") as f:
                lines = [l.strip() for l in f.readlines()]
            keys = ["output_folder","pq_file1","pq_file2","olap_file","competitors_file",
                    "nielsen_input","nielsen_output","nielsen_format","nielsen_category"]
            for i, key in enumerate(keys):
                if i < len(lines) and lines[i]:
                    defaults[key] = lines[i]
        except Exception:
            pass
        return defaults

    if not os.path.exists(CONFIG_FILE):
        return defaults
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k in defaults:
            if k in data:
                defaults[k] = data[k]
    except Exception as e:
        print(f"Ошибка загрузки конфига: {e}")
    return defaults


# ── Лог ───────────────────────────────────────────────────────────────────────

def log(message: str):
    """Пишет в окно лога, файл и ограничивает число строк."""
    file_log(message)
    timestamp = datetime.now().strftime("%H:%M:%S")
    line = f"[{timestamp}] {message}\n"

    log_text.configure(state="normal")
    log_text.insert(ctk.END, line)

    # Удаляем старые строки при превышении лимита
    content = log_text.get("1.0", ctk.END)
    lines = content.splitlines()
    if len(lines) > LOG_MAX_LINES:
        excess = len(lines) - LOG_MAX_LINES
        log_text.delete("1.0", f"{excess + 1}.0")

    log_text.see(ctk.END)
    log_text.update_idletasks()
    log_text.configure(state="disabled")


# ── Заголовок окна ─────────────────────────────────────────────────────────────

def set_title(text: str):
    root.title(f"EFKO FlowManager  —  {text}")


def reset_title():
    root.title("EFKO FlowManager")


# ── Прогресс-бар ──────────────────────────────────────────────────────────────

def set_progress(done: int, total: int):
    """Вызывается из рабочего потока — обновляет прогресс-бар и метку."""
    pct = done / total if total else 0
    progress_bar.set(pct)
    progress_label.configure(text=f"{done} / {total}")
    root.update_idletasks()


def show_progress():
    progress_frame.pack(fill="x", padx=15, pady=(0, 4))


def hide_progress():
    progress_bar.set(0)
    progress_label.configure(text="")
    progress_frame.pack_forget()


# ── Сохранение и открытие ─────────────────────────────────────────────────────

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


def open_last_file():
    global last_updated_competitors_file
    if last_updated_competitors_file and os.path.exists(last_updated_competitors_file):
        try:
            os.startfile(last_updated_competitors_file)
            log(f"Открыт: {os.path.basename(last_updated_competitors_file)}")
        except Exception as e:
            log(f"Не удалось открыть файл: {e}")
    else:
        messagebox.showinfo("Инфо", "Последний файл не найден")


def open_output_folder():
    """Открывает папку с результатами в проводнике."""
    folder = output_folder_var.get().strip()
    if folder and os.path.isdir(folder):
        try:
            os.startfile(folder)
        except Exception as e:
            log(f"Не удалось открыть папку: {e}")
    else:
        messagebox.showinfo("Инфо", "Папка сохранения не задана или не существует")


# ── Запуск потоков ─────────────────────────────────────────────────────────────

def start_download_thread():
    show_progress()
    set_title("⏳ Загрузка файлов...")
    threading.Thread(
        target=_download_worker, daemon=True
    ).start()


def _download_worker():
    download_files_thread(
        month_from_var, year_from_var, month_to_var, year_to_var,
        log, messagebox,
        progress_callback=set_progress,
        set_title=set_title,
    )
    root.after(2000, reset_title)
    root.after(2000, hide_progress)


def start_clear_download_thread():
    if not messagebox.askyesno(
        "Подтверждение", "Удалить все файлы из папки «Скаченное»?"
    ):
        return
    threading.Thread(
        target=clear_download_folder, args=(log, messagebox), daemon=True
    ).start()


def start_processing_thread():
    show_progress()
    set_title("⏳ Обработка файлов...")
    threading.Thread(target=_processing_worker, daemon=True).start()


def _processing_worker():
    process_files_thread(
        output_folder_var, filter_var, FILTER_OPTIONS,
        log, messagebox, stop_event,
        refresh_power_query_files, pq_file1, pq_file2,
        progress_callback=set_progress,
        set_title=set_title,
    )
    root.after(2000, reset_title)
    root.after(2000, hide_progress)


def start_main_action():
    stop_event.clear()
    mode = action_var.get()
    if mode == "promodate":
        log("▶ Режим: Фильтрация промодаты + Promodate")
        start_processing_thread()
    elif mode == "competitors":
        log("▶ Режим: Положение конкурентов")
        set_title("⏳ Обновление конкурентов...")
        threading.Thread(target=_competitors_worker, daemon=True).start()
    elif mode == "nielsen":
        log("▶ Режим: Обработка Nielsen")
        set_title("⏳ Nielsen...")
        threading.Thread(target=_nielsen_worker, daemon=True).start()
    elif mode == "query_refresh":
        log("▶ Режим: Обновление Power Query")
        set_title("⏳ Обновление квери...")
        threading.Thread(target=_query_refresh_worker, daemon=True).start()
    elif mode == "production":
        log("▶ Режим: Производство")
        set_title("⏳ Формирование отчёта...")
        threading.Thread(target=_production_worker, daemon=True).start()
    else:
        messagebox.showwarning("Ошибка", "Выберите режим работы")


def _competitors_worker():
    def on_file_updated(path):
        global last_updated_competitors_file
        last_updated_competitors_file = path

    refresh_competitors_pipeline(
        olap_file, competitors_file, log, messagebox, stop_event,
        on_file_updated=on_file_updated,
    )
    root.after(2000, reset_title)


def _nielsen_worker():
    process_nielsen(
        nielsen_input_file.get(), nielsen_output_dir.get(),
        nielsen_format.get(), log, messagebox, stop_event,
        nielsen_category_var.get(),
    )
    root.after(2000, reset_title)


def _query_refresh_worker():
    from competitors_functions import refresh_file
    path = query_refresh_file.get().strip()
    if not path or not os.path.isfile(path):
        messagebox.showwarning("Ошибка", "Выберите Excel-файл для обновления!")
        root.after(0, reset_title)
        return
    log(f"▶ Обновление Power Query: {os.path.basename(path)}")
    success = refresh_file(path, log, stop_event, timeout_minutes=90)
    if success:
        log("✅ Обновление завершено!")
        messagebox.showinfo("Готово", f"Файл обновлён:\n{os.path.basename(path)}")
    root.after(2000, reset_title)


def _production_worker():
    month_label = prod_month_var.get()
    month_str   = month_label.split(" - ")[0]
    run_production(
        svod_folder     = prod_svod_folder.get().strip(),
        npk_file        = prod_npk_file.get().strip(),
        tolyatti_folder = prod_tolyatti_folder.get().strip(),
        target_file     = prod_target_file.get().strip(),
        mapping_file    = prod_mapping_file.get().strip(),
        month_str       = month_str,
        year            = prod_year_var.get().strip(),
        log             = log,
        messagebox      = messagebox,
        stop_event      = stop_event,
    )
    root.after(2000, reset_title)


# ── Тема ──────────────────────────────────────────────────────────────────────

def toggle_theme():
    current = ctk.get_appearance_mode()
    new_mode = "dark" if current == "Light" else "light"
    ctk.set_appearance_mode(new_mode)
    theme_btn.configure(text="☀️  Светлая" if new_mode == "dark" else "🌙  Тёмная")


# ── update_gui ────────────────────────────────────────────────────────────────

def update_gui(*args):
    mode = action_var.get()

    # Базовый сброс — скрываем все специфичные виджеты
    date_row_frame.grid_remove()
    label_category.grid_remove();        menu_category.grid_remove()
    label_output.grid_remove();          entry_output.grid_remove();         btn_output.grid_remove()
    label_pq1.grid_remove();             entry_pq1.grid_remove();            btn_pq1.grid_remove()
    label_pq2.grid_remove();             entry_pq2.grid_remove();            btn_pq2.grid_remove()
    label_olap.grid_remove();            entry_olap.grid_remove();           btn_olap.grid_remove()
    label_competitors.grid_remove();     entry_competitors.grid_remove();    btn_competitors.grid_remove()
    label_nielsen_input.grid_remove();   entry_nielsen_input.grid_remove();  btn_nielsen_input.grid_remove()
    label_nielsen_output.grid_remove();  entry_nielsen_output.grid_remove(); btn_nielsen_output.grid_remove()
    label_nielsen_format.grid_remove();  menu_nielsen_format.grid_remove()
    label_nielsen_category.grid_remove(); menu_nielsen_category.grid_remove()
    label_qr_file.grid_remove();         entry_qr_file.grid_remove();        btn_qr_file.grid_remove()
    label_prod_svod.grid_remove();    entry_prod_svod.grid_remove();    btn_prod_svod.grid_remove()
    label_prod_npk.grid_remove();     entry_prod_npk.grid_remove();     btn_prod_npk.grid_remove()
    label_prod_tol.grid_remove();     entry_prod_tol.grid_remove();     btn_prod_tol.grid_remove()
    label_prod_target.grid_remove();  entry_prod_target.grid_remove();  btn_prod_target.grid_remove()
    label_prod_mapping.grid_remove(); entry_prod_mapping.grid_remove(); btn_prod_mapping.grid_remove()
    prod_date_frame.grid_remove()
    btn_download.grid_remove(); btn_clear.grid_remove()
    btn_open_output.grid_remove(); btn_open_last.grid_remove()

    if mode == "promodate":
        date_row_frame.grid()
        label_category.grid();  menu_category.grid()
        label_output.grid();    entry_output.grid();  btn_output.grid()
        label_pq1.grid();       entry_pq1.grid();     btn_pq1.grid()
        label_pq2.grid();       entry_pq2.grid();     btn_pq2.grid()
        btn_download.grid(row=0, column=0, padx=6, pady=5)
        btn_clear.grid(row=0, column=1, padx=6, pady=5)
        btn_open_output.grid(row=0, column=2, padx=6, pady=5)
        start_btn.grid(row=0, column=3, padx=6, pady=5)
        stop_btn.grid(row=0, column=4, padx=6, pady=5)

    elif mode == "competitors":
        label_olap.grid();        entry_olap.grid();        btn_olap.grid()
        label_competitors.grid(); entry_competitors.grid(); btn_competitors.grid()
        start_btn.grid(row=0, column=0, padx=6, pady=5)
        stop_btn.grid(row=0, column=1, padx=6, pady=5)
        btn_open_last.grid(row=0, column=2, padx=6, pady=5)

    elif mode == "nielsen":
        label_nielsen_input.grid();   entry_nielsen_input.grid();   btn_nielsen_input.grid()
        label_nielsen_output.grid();  entry_nielsen_output.grid();  btn_nielsen_output.grid()
        label_nielsen_format.grid();  menu_nielsen_format.grid()
        label_nielsen_category.grid(); menu_nielsen_category.grid()
        start_btn.grid(row=0, column=0, padx=6, pady=5)
        stop_btn.grid(row=0, column=1, padx=6, pady=5)

    elif mode == "query_refresh":
        label_qr_file.grid(); entry_qr_file.grid(); btn_qr_file.grid()
        start_btn.grid(row=0, column=0, padx=6, pady=5)
        stop_btn.grid(row=0, column=1, padx=6, pady=5)

    elif mode == "production":
        label_prod_svod.grid();    entry_prod_svod.grid();    btn_prod_svod.grid()
        label_prod_npk.grid();     entry_prod_npk.grid();     btn_prod_npk.grid()
        label_prod_tol.grid();     entry_prod_tol.grid();     btn_prod_tol.grid()
        label_prod_target.grid();  entry_prod_target.grid();  btn_prod_target.grid()
        label_prod_mapping.grid(); entry_prod_mapping.grid(); btn_prod_mapping.grid()
        prod_date_frame.grid()
        start_btn.grid(row=0, column=0, padx=6, pady=5)
        stop_btn.grid(row=0, column=1, padx=6, pady=5)

    root.update_idletasks()


# ═══════════════════════════════════════════════════════════════════════════════
# ОКНО
# ═══════════════════════════════════════════════════════════════════════════════

root = ctk.CTk()
root.title("EFKO FlowManager")
root.geometry("1200x780")
root.attributes("-alpha", 0)  # делаем прозрачным на время сборки виджетов

cfg = load_config()

month_from_var      = ctk.StringVar(value=str(datetime.now().month))
year_from_var       = ctk.StringVar(value=str(datetime.now().year))
month_to_var        = ctk.StringVar(value=str(datetime.now().month))
year_to_var         = ctk.StringVar(value=str(datetime.now().year))
output_folder_var   = ctk.StringVar(value=cfg["output_folder"])
filter_var          = ctk.StringVar(value="Масло")
pq_file1            = ctk.StringVar(value=cfg["pq_file1"])
pq_file2            = ctk.StringVar(value=cfg["pq_file2"])
olap_file           = ctk.StringVar(value=cfg["olap_file"])
competitors_file    = ctk.StringVar(value=cfg["competitors_file"])
nielsen_input_file  = ctk.StringVar(value=cfg["nielsen_input"])
nielsen_output_dir  = ctk.StringVar(value=cfg["nielsen_output"])
nielsen_format      = ctk.StringVar(value=cfg["nielsen_format"])
nielsen_category_var = ctk.StringVar(value=cfg["nielsen_category"])
query_refresh_file   = ctk.StringVar(value=cfg["query_refresh_file"])
prod_svod_folder     = ctk.StringVar(value=cfg["prod_svod_folder"])
prod_npk_file        = ctk.StringVar(value=cfg["prod_npk_file"])
prod_tolyatti_folder = ctk.StringVar(value=cfg["prod_tolyatti"])
prod_target_file     = ctk.StringVar(value=cfg["prod_target"])
prod_mapping_file    = ctk.StringVar(value=cfg["prod_mapping"])
prod_month_var       = ctk.StringVar(value=MONTH_LABELS[datetime.now().month - 1])
prod_year_var        = ctk.StringVar(value=cfg["prod_year"])
action_var           = ctk.StringVar(value="promodate")

# ── Корневой контейнер ─────────────────────────────────────────────────────────
root_pane = ctk.CTkFrame(root, fg_color="transparent")
root_pane.pack(fill="both", expand=True)

# ── Боковая панель ─────────────────────────────────────────────────────────────
sidebar = ctk.CTkFrame(root_pane, width=210, corner_radius=0)
sidebar.pack(side="left", fill="y")
sidebar.pack_propagate(False)

ctk.CTkLabel(
    sidebar, text="FlowManager",
    font=ctk.CTkFont(size=16, weight="bold"),
).pack(pady=(20, 6), padx=10)

ctk.CTkLabel(
    sidebar, text="v2.0",
    font=ctk.CTkFont(size=11),
    text_color="gray60",
).pack(pady=(0, 24), padx=10)

NAV_ITEMS = [
    ("promodate",      "📊  Промодата"),
    ("competitors",    "🏪  Конкуренты"),
    ("nielsen",        "📈  Nielsen"),
    ("query_refresh",  "🔄  Обновить квери"),
    ("production",     "🏭  Производство"),
]
nav_buttons: dict[str, ctk.CTkButton] = {}


def _nav_select(mode: str):
    action_var.set(mode)
    for key, btn in nav_buttons.items():
        if key == mode:
            btn.configure(fg_color=("#2CC985", "#2FA572"), text_color="white")
        else:
            btn.configure(fg_color="transparent", text_color=("gray10", "gray90"))


for mode_key, mode_label in NAV_ITEMS:
    btn = ctk.CTkButton(
        sidebar, text=mode_label, anchor="w",
        height=44, width=190, corner_radius=8,
        fg_color="transparent", text_color=("gray10", "gray90"),
        hover_color=("gray85", "gray25"),
        font=ctk.CTkFont(size=13),
        command=lambda k=mode_key: _nav_select(k),
    )
    btn.pack(pady=3, padx=10)
    nav_buttons[mode_key] = btn

# Разделитель и кнопка темы внизу сайдбара
ctk.CTkFrame(sidebar, height=1, fg_color="gray70").pack(
    fill="x", padx=15, pady=(20, 10)
)
theme_btn = ctk.CTkButton(
    sidebar, text="🌙  Тёмная", anchor="w",
    height=36, width=190, corner_radius=8,
    fg_color="transparent", text_color=("gray10", "gray90"),
    hover_color=("gray85", "gray25"),
    font=ctk.CTkFont(size=12),
    command=toggle_theme,
)
theme_btn.pack(pady=3, padx=10)

# ── Правая область ─────────────────────────────────────────────────────────────
content = ctk.CTkFrame(root_pane, fg_color="transparent")
content.pack(side="left", fill="both", expand=True)

# Форма настроек
top_frame = ctk.CTkFrame(content)
top_frame.pack(fill="x", padx=15, pady=10)

# Строка дат
date_row_frame = ctk.CTkFrame(top_frame, fg_color="transparent")
date_row_frame.grid(row=0, column=0, columnspan=6, sticky="w", padx=5, pady=5)

ctk.CTkLabel(date_row_frame, text="Месяц с:").pack(side="left", padx=(0, 4))
menu_month_from = ctk.CTkOptionMenu(
    date_row_frame, variable=month_from_var,
    values=[str(i) for i in range(1, 13)], width=80,
)
menu_month_from.pack(side="left", padx=(0, 4))
ctk.CTkLabel(date_row_frame, text="—").pack(side="left", padx=(0, 4))
menu_month_to = ctk.CTkOptionMenu(
    date_row_frame, variable=month_to_var,
    values=[str(i) for i in range(1, 13)], width=80,
)
menu_month_to.pack(side="left", padx=(0, 20))

ctk.CTkLabel(date_row_frame, text="Год с:").pack(side="left", padx=(0, 4))
menu_year_from = ctk.CTkOptionMenu(
    date_row_frame, variable=year_from_var,
    values=[str(y) for y in range(2020, 2031)], width=100,
)
menu_year_from.pack(side="left", padx=(0, 4))
ctk.CTkLabel(date_row_frame, text="—").pack(side="left", padx=(0, 4))
menu_year_to = ctk.CTkOptionMenu(
    date_row_frame, variable=year_to_var,
    values=[str(y) for y in range(2020, 2031)], width=100,
)
menu_year_to.pack(side="left")

# Поля
ENTRY_W = 620

label_category = ctk.CTkLabel(top_frame, text="Категория:")
label_category.grid(row=1, column=0, sticky="e", padx=5, pady=5)
menu_category = ctk.CTkOptionMenu(top_frame, variable=filter_var, values=list(FILTER_OPTIONS.keys()))
menu_category.grid(row=1, column=1, columnspan=3, sticky="w", padx=5, pady=5)

label_output = ctk.CTkLabel(top_frame, text="Папка сохранения:")
label_output.grid(row=2, column=0, sticky="e", padx=5, pady=5)
entry_output = ctk.CTkEntry(top_frame, textvariable=output_folder_var, width=ENTRY_W)
entry_output.grid(row=2, column=1, columnspan=3, padx=5, pady=5)
btn_output = ctk.CTkButton(top_frame, text="Обзор",
                            command=lambda: browse_output_folder(output_folder_var))
btn_output.grid(row=2, column=4, padx=5, pady=5)

label_pq1 = ctk.CTkLabel(top_frame, text="Power Query (Promodate 1):")
label_pq1.grid(row=3, column=0, sticky="e", padx=5, pady=5)
entry_pq1 = ctk.CTkEntry(top_frame, textvariable=pq_file1, width=ENTRY_W)
entry_pq1.grid(row=3, column=1, columnspan=3, padx=5, pady=5)
btn_pq1 = ctk.CTkButton(top_frame, text="Выбрать",
                         command=lambda: browse_power_query_file(pq_file1))
btn_pq1.grid(row=3, column=4, padx=5, pady=5)

label_pq2 = ctk.CTkLabel(top_frame, text="Power Query (Promodate 2):")
label_pq2.grid(row=4, column=0, sticky="e", padx=5, pady=5)
entry_pq2 = ctk.CTkEntry(top_frame, textvariable=pq_file2, width=ENTRY_W)
entry_pq2.grid(row=4, column=1, columnspan=3, padx=5, pady=5)
btn_pq2 = ctk.CTkButton(top_frame, text="Выбрать",
                         command=lambda: browse_power_query_file(pq_file2))
btn_pq2.grid(row=4, column=4, padx=5, pady=5)

label_olap = ctk.CTkLabel(top_frame, text="OLAP файл:")
label_olap.grid(row=5, column=0, sticky="e", padx=5, pady=5)
entry_olap = ctk.CTkEntry(top_frame, textvariable=olap_file, width=ENTRY_W)
entry_olap.grid(row=5, column=1, columnspan=3, padx=5, pady=5)
btn_olap = ctk.CTkButton(top_frame, text="Выбрать",
                          command=lambda: browse_power_query_file(olap_file))
btn_olap.grid(row=5, column=4, padx=5, pady=5)

label_competitors = ctk.CTkLabel(top_frame, text="Положение конкурентов:")
label_competitors.grid(row=6, column=0, sticky="e", padx=5, pady=5)
entry_competitors = ctk.CTkEntry(top_frame, textvariable=competitors_file, width=ENTRY_W)
entry_competitors.grid(row=6, column=1, columnspan=3, padx=5, pady=5)
btn_competitors = ctk.CTkButton(top_frame, text="Выбрать",
                                 command=lambda: browse_power_query_file(competitors_file))
btn_competitors.grid(row=6, column=4, padx=5, pady=5)

label_nielsen_input = ctk.CTkLabel(top_frame, text="Входной файл Nielsen:")
label_nielsen_input.grid(row=7, column=0, sticky="e", padx=5, pady=5)
entry_nielsen_input = ctk.CTkEntry(top_frame, textvariable=nielsen_input_file, width=ENTRY_W)
entry_nielsen_input.grid(row=7, column=1, columnspan=3, padx=5, pady=5)
btn_nielsen_input = ctk.CTkButton(top_frame, text="Выбрать", command=browse_nielsen_input)
btn_nielsen_input.grid(row=7, column=4, padx=5, pady=5)

label_nielsen_output = ctk.CTkLabel(top_frame, text="Папка сохранения:")
label_nielsen_output.grid(row=8, column=0, sticky="e", padx=5, pady=5)
entry_nielsen_output = ctk.CTkEntry(top_frame, textvariable=nielsen_output_dir, width=ENTRY_W)
entry_nielsen_output.grid(row=8, column=1, columnspan=3, padx=5, pady=5)
btn_nielsen_output = ctk.CTkButton(top_frame, text="Обзор", command=browse_nielsen_output)
btn_nielsen_output.grid(row=8, column=4, padx=5, pady=5)

label_nielsen_format = ctk.CTkLabel(top_frame, text="Формат сохранения:")
label_nielsen_format.grid(row=9, column=0, sticky="e", padx=5, pady=5)
menu_nielsen_format = ctk.CTkOptionMenu(top_frame, variable=nielsen_format, values=["csv", "excel"])
menu_nielsen_format.grid(row=9, column=1, columnspan=3, sticky="w", padx=5, pady=5)

label_nielsen_category = ctk.CTkLabel(top_frame, text="Категория:")
label_nielsen_category.grid(row=10, column=0, sticky="e", padx=5, pady=5)
menu_nielsen_category = ctk.CTkOptionMenu(
    top_frame, variable=nielsen_category_var,
    values=["Масло", "Кетчуп", "Майонез", "Маргарин"],
)
menu_nielsen_category.grid(row=10, column=1, columnspan=3, sticky="w", padx=5, pady=5)

label_qr_file = ctk.CTkLabel(top_frame, text="Excel-файл:")
label_qr_file.grid(row=11, column=0, sticky="e", padx=5, pady=5)
entry_qr_file = ctk.CTkEntry(top_frame, textvariable=query_refresh_file, width=ENTRY_W)
entry_qr_file.grid(row=11, column=1, columnspan=3, padx=5, pady=5)
btn_qr_file = ctk.CTkButton(
    top_frame, text="Выбрать",
    command=lambda: browse_power_query_file(query_refresh_file),
)
btn_qr_file.grid(row=11, column=4, padx=5, pady=5)

# ── Производство ──────────────────────────────────────────────
def _browse_dir(var):
    d = filedialog.askdirectory()
    if d:
        var.set(d)
        save_config()

label_prod_svod = ctk.CTkLabel(top_frame, text="Папка СВОД:")
label_prod_svod.grid(row=12, column=0, sticky="e", padx=5, pady=5)
entry_prod_svod = ctk.CTkEntry(top_frame, textvariable=prod_svod_folder, width=ENTRY_W)
entry_prod_svod.grid(row=12, column=1, columnspan=3, padx=5, pady=5)
btn_prod_svod = ctk.CTkButton(top_frame, text="Обзор",
    command=lambda: _browse_dir(prod_svod_folder))
btn_prod_svod.grid(row=12, column=4, padx=5, pady=5)

label_prod_npk = ctk.CTkLabel(top_frame, text="Файл НПК:")
label_prod_npk.grid(row=13, column=0, sticky="e", padx=5, pady=5)
entry_prod_npk = ctk.CTkEntry(top_frame, textvariable=prod_npk_file, width=ENTRY_W)
entry_prod_npk.grid(row=13, column=1, columnspan=3, padx=5, pady=5)
btn_prod_npk = ctk.CTkButton(top_frame, text="Выбрать",
    command=lambda: browse_power_query_file(prod_npk_file))
btn_prod_npk.grid(row=13, column=4, padx=5, pady=5)

label_prod_tol = ctk.CTkLabel(top_frame, text="Папка Тольяти:")
label_prod_tol.grid(row=14, column=0, sticky="e", padx=5, pady=5)
entry_prod_tol = ctk.CTkEntry(top_frame, textvariable=prod_tolyatti_folder, width=ENTRY_W)
entry_prod_tol.grid(row=14, column=1, columnspan=3, padx=5, pady=5)
btn_prod_tol = ctk.CTkButton(top_frame, text="Обзор",
    command=lambda: _browse_dir(prod_tolyatti_folder))
btn_prod_tol.grid(row=14, column=4, padx=5, pady=5)

label_prod_target = ctk.CTkLabel(top_frame, text="Файл тестовые_данные:")
label_prod_target.grid(row=15, column=0, sticky="e", padx=5, pady=5)
entry_prod_target = ctk.CTkEntry(top_frame, textvariable=prod_target_file, width=ENTRY_W)
entry_prod_target.grid(row=15, column=1, columnspan=3, padx=5, pady=5)
btn_prod_target = ctk.CTkButton(top_frame, text="Выбрать",
    command=lambda: browse_power_query_file(prod_target_file))
btn_prod_target.grid(row=15, column=4, padx=5, pady=5)

label_prod_mapping = ctk.CTkLabel(top_frame, text="Файл маппинга:")
label_prod_mapping.grid(row=16, column=0, sticky="e", padx=5, pady=5)
entry_prod_mapping = ctk.CTkEntry(top_frame, textvariable=prod_mapping_file, width=ENTRY_W)
entry_prod_mapping.grid(row=16, column=1, columnspan=3, padx=5, pady=5)
btn_prod_mapping = ctk.CTkButton(top_frame, text="Выбрать",
    command=lambda: browse_power_query_file(prod_mapping_file))
btn_prod_mapping.grid(row=16, column=4, padx=5, pady=5)

# Месяц + год в одной строке
prod_date_frame = ctk.CTkFrame(top_frame, fg_color="transparent")
prod_date_frame.grid(row=17, column=0, columnspan=5, sticky="w", padx=5, pady=5)
ctk.CTkLabel(prod_date_frame, text="Месяц:").pack(side="left", padx=(0, 6))
menu_prod_month = ctk.CTkOptionMenu(
    prod_date_frame, variable=prod_month_var, values=MONTH_LABELS, width=180)
menu_prod_month.pack(side="left", padx=(0, 20))
ctk.CTkLabel(prod_date_frame, text="Год:").pack(side="left", padx=(0, 6))
entry_prod_year = ctk.CTkEntry(prod_date_frame, textvariable=prod_year_var, width=80)
entry_prod_year.pack(side="left")

# ── Прогресс-бар (скрыт по умолчанию) ────────────────────────────────────────
progress_frame = ctk.CTkFrame(content, fg_color="transparent")
# pack вызывается динамически в show_progress()

_pf_inner = ctk.CTkFrame(progress_frame, fg_color="transparent")
_pf_inner.pack(fill="x", padx=5)
progress_bar = ctk.CTkProgressBar(_pf_inner)
progress_bar.set(0)
progress_bar.pack(side="left", fill="x", expand=True, pady=4)
progress_label = ctk.CTkLabel(_pf_inner, text="", width=80, anchor="e")
progress_label.pack(side="left", padx=(8, 0))

# ── Кнопки действий ───────────────────────────────────────────────────────────
btn_frame = ctk.CTkFrame(content)
btn_frame.pack(fill="x", padx=15, pady=(0, 8))

btn_download = ctk.CTkButton(
    btn_frame, text="⬇  Скачать", command=start_download_thread, width=150)
btn_clear = ctk.CTkButton(
    btn_frame, text="🗑  Очистить", command=start_clear_download_thread, width=150)
btn_open_output = ctk.CTkButton(
    btn_frame, text="📁  Открыть папку", command=open_output_folder, width=160)
start_btn = ctk.CTkButton(
    btn_frame, text="▶  ЗАПУСТИТЬ", command=start_main_action,
    width=165, height=40, font=ctk.CTkFont(size=13, weight="bold"))
stop_btn = ctk.CTkButton(
    btn_frame, text="■  Стоп", command=lambda: stop_event.set(),
    width=130, height=40, fg_color="gray50", hover_color="gray40")
btn_open_last = ctk.CTkButton(
    btn_frame, text="📂  Последний файл", command=open_last_file,
    width=180, height=40)

# ── Лог ───────────────────────────────────────────────────────────────────────
log_frame = ctk.CTkFrame(content)
log_frame.pack(fill="both", expand=True, padx=15, pady=(0, 10))

_log_header = ctk.CTkFrame(log_frame, fg_color="transparent")
_log_header.pack(fill="x", padx=8, pady=(6, 2))
ctk.CTkLabel(_log_header, text="Лог работы:", font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
ctk.CTkButton(
    _log_header, text="Очистить лог", width=110, height=24,
    fg_color="transparent", border_width=1,
    command=lambda: [
        log_text.configure(state="normal"),
        log_text.delete("1.0", ctk.END),
        log_text.configure(state="disabled"),
    ],
).pack(side="right")

log_text = ctk.CTkTextbox(log_frame, state="disabled")
log_text.pack(fill="both", expand=True, padx=6, pady=(0, 6))

# ── Запуск ────────────────────────────────────────────────────────────────────
action_var.trace("w", update_gui)
_nav_select("promodate")

root.update_idletasks()         # финальный layout
root.attributes("-alpha", 1)    # показываем окно готовым сразу целиком


def on_closing():
    if messagebox.askokcancel("Выход", "Закрыть приложение?"):
        save_config()
        root.destroy()


root.protocol("WM_DELETE_WINDOW", on_closing)
log("Приложение запущено. Выберите режим и нажмите ЗАПУСТИТЬ")
log(f"Лог сохраняется в: {os.path.join(os.getcwd(), 'flowmanager.log')}")
root.mainloop()