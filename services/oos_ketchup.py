"""
services/oos_ketchup.py — модуль «Отчёт без OOS» для категории «Кетчуп».

Источник — папка с несколькими файлами кубов (основной куб, конкуренты,
конкуренты 300, ELT). Обновление — как и везде в проекте (см.
services/competitors.py::refresh_file): файл открывается в Excel через
COM и обновляется RefreshAll() (синхронный пересчёт Power Query), затем
сохраняется.

Последовательность: сначала все кубы из папки, затем отчёт «2026»
(если нужен), затем отчёт «2024-2026» — каждый файл уже содержит
Power Query, подтягивающий данные из кубов, поэтому его RefreshAll()
и есть «вставка новых данных из кубов».
"""

import re
from pathlib import Path

from services.competitors import refresh_file

# ─── Поиск файлов кубов в папке ────────────────────────────────────────────
_RE_ELT = re.compile(r"elt", re.IGNORECASE)
_RE_COMP_300 = re.compile(r"конкурент\w*.*300|300.*конкурент", re.IGNORECASE)
_RE_COMP = re.compile(r"конкурент", re.IGNORECASE)
_RE_MAIN = re.compile(r"куб", re.IGNORECASE)
_RE_REPORT = re.compile(r"отч[её]т|report", re.IGNORECASE)

_ROLE_LABELS = {
    "main": "КУБ",
    "competitors": "Конкуренты",
    "competitors_300": "Конкуренты 300",
    "elt": "ELT",
}
# Порядок обновления кубов: сначала основной, потом ELT, потом конкуренты
_ROLE_ORDER = ["main", "elt", "competitors", "competitors_300"]


def find_ketchup_files(folder) -> dict:
    """
    Ищет в папке файлы кубов кетчупа по маскам имени. Файлы самих отчётов
    («Отчет по кетчупу...») из поиска исключаются.
    Возвращает {role: Path|None} для ролей main/competitors/competitors_300/elt.
    """
    folder = Path(folder)
    found = {"main": None, "competitors": None, "competitors_300": None, "elt": None}
    if not folder.is_dir():
        return found
    for f in sorted(folder.glob("*.xlsx")):
        if f.name.startswith("~$"):
            continue
        name = f.name
        if _RE_REPORT.search(name):
            continue
        if _RE_ELT.search(name):
            found["elt"] = f
        elif _RE_COMP_300.search(name):
            found["competitors_300"] = f
        elif _RE_COMP.search(name):
            found["competitors"] = f
        elif _RE_MAIN.search(name):
            found["main"] = f
    return found


# ─── Главная функция ────────────────────────────────────────────────────────
def run_ketchup_report(
    kub_folder: str,
    report_2026_file: str,
    report_2024_2026_file: str,
    need_2026: bool,
    log,
    stop_event,
):
    """
    Последовательное обновление через query (RefreshAll), как везде в проекте:
      1) все кубы, найденные в папке
      2) отчёт 2026 (если нужен)
      3) отчёт 2024-2026
    """

    def chk():
        if stop_event.is_set():
            raise InterruptedError("Остановлено пользователем")

    folder = Path(kub_folder)
    found = find_ketchup_files(folder)
    missing = [r for r, p in found.items() if p is None]
    if missing:
        log(f"  [WARN] Не найдены файлы: {', '.join(_ROLE_LABELS[m] for m in missing)}")

    cube_paths = [found[role] for role in _ROLE_ORDER if found[role] is not None]
    if not cube_paths:
        raise ValueError("В указанной папке не найдено ни одного файла куба кетчупа")

    log(f"🗂 Шаг 1/3: обновляем кубы через query ({len(cube_paths)} файл(ов))...")
    for path in cube_paths:
        chk()
        if not refresh_file(str(path), log, stop_event):
            if stop_event.is_set():
                raise InterruptedError("Остановлено пользователем")
            raise RuntimeError(f"Не удалось обновить куб: {path.name}")

    chk()
    if need_2026:
        if not report_2026_file:
            log("⚠️ Шаг 2/3: файл отчёта 2026 не указан — пропускаем")
        else:
            log("📋 Шаг 2/3: обновляем отчёт 2026 через query...")
            if not refresh_file(report_2026_file, log, stop_event):
                if stop_event.is_set():
                    raise InterruptedError("Остановлено пользователем")
                raise RuntimeError("Не удалось обновить отчёт 2026")
    else:
        log("⏭ Шаг 2/3: файл 2026 не требуется — пропускаем")

    chk()
    if not report_2024_2026_file:
        log("⚠️ Шаг 3/3: файл отчёта 2024-2026 не указан — пропускаем")
    else:
        log("📋 Шаг 3/3: обновляем отчёт 2024-2026 через query...")
        if not refresh_file(report_2024_2026_file, log, stop_event):
            if stop_event.is_set():
                raise InterruptedError("Остановлено пользователем")
            raise RuntimeError("Не удалось обновить отчёт 2024-2026")

    log("✅ Готово!")
