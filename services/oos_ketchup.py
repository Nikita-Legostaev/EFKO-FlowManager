"""
services/oos_ketchup.py — модуль «Отчёт без OOS» для категории «Кетчуп».

Источник — папка с файлами кубов (КУБ, ELT, конкуренты и т.п. — сколько бы
их ни было). Берутся ВСЕ xlsx-файлы, которые лежат в этой папке (кроме
файлов самих отчётов). Обновление — как и везде в проекте (см.
services/competitors.py::refresh_file): файл открывается в Excel через
COM и обновляется RefreshAll() (синхронный пересчёт Power Query), затем
сохраняется.

Последовательность: сначала все кубы из папки, затем отчёт «2026»
(если нужен), затем отчёт «2024-2026» — каждый файл уже содержит
Power Query, подтягивающий данные из кубов, поэтому его RefreshAll()
и есть «вставка новых данных из кубов».
"""

from pathlib import Path

from services.competitors import refresh_file


def find_ketchup_files(folder, exclude=None) -> list:
    """
    Возвращает список всех xlsx-файлов кубов в папке (сортировка по имени),
    кроме временных ~$-файлов и файлов из `exclude` (пути к уже выбранным
    файлам отчётов — сравнение по имени файла, а не по маске в названии,
    т.к. сами кубы часто содержат слово «отчёт(а)» в имени).
    """
    folder = Path(folder)
    if not folder.is_dir():
        return []
    exclude_names = {Path(p).name for p in (exclude or ()) if p}
    return [
        f
        for f in sorted(folder.glob("*.xlsx"))
        if not f.name.startswith("~$") and f.name not in exclude_names
    ]


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
      1) все файлы кубов, найденные в папке
      2) отчёт 2026 (если нужен)
      3) отчёт 2024-2026
    """

    def chk():
        if stop_event.is_set():
            raise InterruptedError("Остановлено пользователем")

    cube_paths = find_ketchup_files(
        kub_folder, exclude=(report_2026_file, report_2024_2026_file)
    )
    if not cube_paths:
        raise ValueError("В указанной папке не найдено ни одного файла куба")

    log(f"🗂 Шаг 1/3: обновляем кубы через query ({len(cube_paths)} файл(ов))...")
    for path in cube_paths:
        chk()
        log(f"  → {path.name}")
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
