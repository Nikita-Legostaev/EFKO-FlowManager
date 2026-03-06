"""
promodate_headless.py — Автономный запуск промодаты без GUI
============================================================
Используется Windows Task Scheduler или ручным запуском.

Запуск:
    pythonw.exe promodate_headless.py
    pythonw.exe promodate_headless.py --steps download,process,query1,query2,macros

Аргументы (все необязательны):
    --steps     Через запятую: download, process, query1, query2, macros
                По умолчанию: берёт из config.json → scheduler_steps
    --config    Путь к config.json (по умолчанию рядом со скриптом)
    --month     Переопределить месяц (1-12)
    --year      Переопределить год (напр. 2026)
"""

import argparse
import json
import logging
import os
import sys
import threading
from datetime import datetime
from pathlib import Path

# ── Пути ─────────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent.resolve()
DEFAULT_CONFIG = BASE_DIR / "config.json"
LOG_FILE = BASE_DIR / "flowmanager_scheduler.log"

# ── Логгер ────────────────────────────────────────────────────────────────────

logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    encoding="utf-8",
)

console = logging.StreamHandler(sys.stdout)
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter("%(asctime)s %(message)s", "%H:%M:%S"))
logging.getLogger().addHandler(console)


def log(msg: str):
    logging.info(msg)


# ── Загрузка конфига ─────────────────────────────────────────────────────────


def load_config(path: Path) -> dict:
    if not path.exists():
        log(f"⚠️  Конфиг не найден: {path}")
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ── Mock-объекты (заменяют tkinter-переменные) ────────────────────────────────


class _SV:
    def __init__(self, v):
        self._v = v

    def get(self):
        return str(self._v) if self._v is not None else ""


class _MB:
    """Тихий messagebox: только в лог."""

    def showinfo(self, title, msg):
        log(f"[INFO] {title}: {msg}")

    def showwarning(self, title, msg):
        log(f"[WARN] {title}: {msg}")

    def showerror(self, title, msg):
        log(f"[ERROR] {title}: {msg}")

    def askyesno(self, title, msg):
        return True  # в автоматическом режиме всегда «да»

    def askokcancel(self, title, msg):
        return True


# ── Основной пайплайн ─────────────────────────────────────────────────────────


def run_pipeline(cfg: dict, steps: list[str], month: int, year: int):
    """Запускает выбранные шаги промодаты."""
    from promodate_functions import (
        FILTER_OPTIONS,
        download_files_thread,
        process_files_thread,
        run_stage_query1,
        run_stage_query2,
        run_stage_macros,
    )

    stop_event = threading.Event()
    mb = _MB()

    category = cfg.get("category", "Масло")
    output_folder = cfg.get("output_folder", "")
    pq_file1 = cfg.get("pq_file1", "")
    pq_file2 = cfg.get("pq_file2", "")
    macro1 = cfg.get("macro1", "")
    macro2 = cfg.get("macro2", "")

    log(f"▶ Запуск промодаты | шаги: {steps} | {month}/{year} | категория: {category}")

    # ── Шаг 1: Скачивание ────────────────────────────────────────────────────
    if "download" in steps:
        log("── Шаг: Скачивание файлов FTP")
        download_files_thread(
            _SV(month),
            _SV(year),
            _SV(month),
            _SV(year),
            log,
            mb,
        )

    # ── Шаг 2: Обработка (фильтрация → CSV) ─────────────────────────────────
    if "process" in steps:
        log("── Шаг: Обработка файлов → CSV")

        def _noop_refresh(*args, **kwargs):
            pass  # PQ запустим отдельно ниже

        process_files_thread(
            _SV(output_folder),
            _SV(category),
            FILTER_OPTIONS,
            log,
            mb,
            stop_event,
            _noop_refresh,  # отключаем встроенный refresh
            _SV(pq_file1),
            _SV(pq_file2),
            _SV(macro1),
            _SV(macro2),
        )

    # ── Шаг 3: Query 1 ──────────────────────────────────────────────────────
    if "query1" in steps:
        log("── Шаг: Обновление Power Query 1")
        run_stage_query1(_SV(pq_file1), log, stop_event, mb)

    # ── Шаг 4: Query 2 ──────────────────────────────────────────────────────
    if "query2" in steps:
        log("── Шаг: Обновление Power Query 2 (xlsm)")
        run_stage_query2(_SV(pq_file2), log, stop_event, mb)

    # ── Шаг 5: Макросы ──────────────────────────────────────────────────────
    if "macros" in steps:
        log("── Шаг: Запуск макросов")
        run_stage_macros(_SV(pq_file2), _SV(macro1), _SV(macro2), log, stop_event, mb)

    log("✅ Пайплайн промодаты завершён")


# ── CLI ───────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Headless PromoData runner")
    parser.add_argument(
        "--steps", default=None, help="download,process,query1,query2,macros"
    )
    parser.add_argument(
        "--config", default=str(DEFAULT_CONFIG), help="Путь к config.json"
    )
    parser.add_argument("--month", type=int, default=None)
    parser.add_argument("--year", type=int, default=None)
    args = parser.parse_args()

    cfg = load_config(Path(args.config))

    # Определяем шаги: CLI > config > всё
    if args.steps:
        steps = [s.strip() for s in args.steps.split(",") if s.strip()]
    else:
        steps = cfg.get(
            "scheduler_steps", ["download", "process", "query1", "query2", "macros"]
        )

    # Месяц/год: CLI > текущий
    now = datetime.now()
    month = args.month or now.month
    year = args.year or now.year

    os.chdir(BASE_DIR)  # чтобы папка «Скаченное» создалась рядом со скриптом

    run_pipeline(cfg, steps, month, year)


if __name__ == "__main__":
    main()
