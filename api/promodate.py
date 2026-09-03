"""
api/promodate.py — миксин: вкладка «Промодата».

Здесь и режимы (ЦО / Мониторинг цен / Дополнительно), и сами операции:
скачивание с FTP, обработка xlsx → CSV, отдельные стадии Power Query и
макросы. Раньше операции жили в api/scheduler.py — в файле про планировщик
и Windows Task Scheduler, где их никто не искал.

Каждый режим — своя папка скачивания xlsx (services.promodate.download_folder_for_mode)
и свой набор «Папка сохранения CSV» + «Power Query / Макросы», чтобы данные и
настройки разных режимов не путались. Папка скачивания подбирается
автоматически, остальные поля — обычные поля формы, которые при
переключении режима подменяются на запомненные для этого режима значения.
"""

from core.config import _SV, load_config, save_config_data
from services.promodate import (
    PROMO_MODES,
    DEFAULT_PROMO_MODE,
    FILTER_OPTIONS,
    download_files_thread,
    process_files_thread,
    refresh_power_query_files,
    run_stage_query1,
    run_stage_query2,
    # алиас: метод миксина ниже называется так же. Сейчас вызов внутри него
    # разрешается в эту функцию только потому, что атрибуты класса не входят
    # в область видимости — ловушка на ровном месте.
    run_stage_macros as run_stage_macros_svc,
    download_folder_for_mode,
)

# Поля, которые запоминаются отдельно на каждый режим промодаты.
MODE_FIELDS = ["output_folder", "pq_file1", "pq_file2", "macro1", "macro2"]


class ApiPromodateMixin:

    def get_promodata_modes(self):
        return [{"key": k, "label": v} for k, v in PROMO_MODES.items()]

    def set_promodata_mode(self, mode: str):
        """
        Переключает режим промодаты.

        Текущие значения MODE_FIELDS запоминаются за старым режимом, для
        нового режима подставляются его сохранённые значения (или дефолты,
        если режим ещё не использовался). Возвращает обновлённый конфиг,
        чтобы фронт мог сразу обновить поля формы.
        """
        cfg = load_config()
        if mode not in PROMO_MODES:
            mode = DEFAULT_PROMO_MODE

        settings = cfg.get("promodata_mode_settings")
        if not isinstance(settings, dict):
            settings = {}

        old_mode = cfg.get("promodata_mode", DEFAULT_PROMO_MODE)
        settings[old_mode] = {f: cfg.get(f, "") for f in MODE_FIELDS}

        cfg["promodata_mode_settings"] = settings
        cfg["promodata_mode"] = mode

        new_values = settings.get(mode) or {}
        for f in MODE_FIELDS:
            cfg[f] = new_values.get(f, "")

        save_config_data(cfg)
        return cfg

    # ── Запуск: скачивание и поэтапная обработка ─────────────────────────

    def start_download(self, p):
        """Только скачивание файлов с FTP. Вызывается кнопкой «⬇ Скачать»."""
        mode = p.get("promodata_mode") or load_config().get("promodata_mode", "co")

        def _w():
            download_files_thread(
                _SV(p.get("month_from")),
                _SV(p.get("year_from")),
                _SV(p.get("month_to")),
                _SV(p.get("year_to")),
                self._log,
                self._mb,
                progress_callback=self._progress,
                set_title=self._set_title,
                date_from_str=p.get("date_from"),
                date_to_str=p.get("date_to"),
                dates_list=p.get("dates_list"),
                download_folder=download_folder_for_mode(mode),
            )

        self._run_bg("", _w, name="Скачивание промодаты")
        return True

    def start_process(self, p):
        """Полный пайплайн: скачивание → обработка → query1 → query2 → макросы."""
        mode = p.get("promodata_mode") or load_config().get("promodata_mode", "co")
        dl_folder = download_folder_for_mode(mode)

        def _w():
            download_files_thread(
                _SV(p.get("month_from")),
                _SV(p.get("year_from")),
                _SV(p.get("month_to")),
                _SV(p.get("year_to")),
                self._log,
                self._mb,
                progress_callback=self._progress,
                set_title=self._set_title,
                date_from_str=p.get("date_from"),
                date_to_str=p.get("date_to"),
                dates_list=p.get("dates_list"),
                download_folder=dl_folder,
            )
            if self._stop_event.is_set():
                return
            process_files_thread(
                _SV(p.get("output_folder")),
                _SV(p.get("category")),
                FILTER_OPTIONS,
                self._log,
                self._mb,
                self._stop_event,
                refresh_power_query_files,          # ← сама функция, не True
                _SV(p.get("pq_file1", "")),
                _SV(p.get("pq_file2", "")),
                p.get("macro1", ""),
                p.get("macro2", ""),
                progress_callback=self._progress,
                set_title=self._set_title,
                networks=p.get("networks") or None,
                download_folder=dl_folder,
            )

        self._run_bg("", _w, name="Промодата (полный пайплайн)")
        return True

    def start_process_csv(self, p):
        """
        Только обработка: xlsx из «Скаченное» → CSV в папку сохранения.
        Без скачивания с FTP, без Power Query и без макросов.
        Вызывается кнопкой «⚙️ Сделать CSV» на главном экране.
        """
        mode = p.get("promodata_mode") or load_config().get("promodata_mode", "co")

        def _w():
            process_files_thread(
                _SV(p.get("output_folder")),
                _SV(p.get("category")),
                FILTER_OPTIONS,
                self._log,
                self._mb,
                self._stop_event,
                lambda *a, **kw: None,   # Power Query намеренно не трогаем
                _SV(""),
                _SV(""),
                "",
                "",
                progress_callback=self._progress,
                set_title=self._set_title,
                networks=p.get("networks") or None,
                download_folder=download_folder_for_mode(mode),
            )

        self._run_bg("", _w, name="Сделать CSV")
        return True

    def run_stage_q1(self, p):
        """Обновить Power Query 1."""
        def _w():
            run_stage_query1(_SV(p.get("pq_file1")), self._log, self._stop_event, self._mb)

        self._run_bg("⏳ Power Query 1…", _w, name="Power Query 1")
        return True

    def run_stage_q2(self, p):
        """Обновить Power Query 2."""
        def _w():
            run_stage_query2(_SV(p.get("pq_file2")), self._log, self._stop_event, self._mb)

        self._run_bg("⏳ Power Query 2…", _w, name="Power Query 2")
        return True

    def run_stage_macros(self, p):
        """Запустить макросы xlsm."""
        def _w():
            run_stage_macros_svc(
                _SV(p.get("pq_file2")),
                p.get("macro1", ""),
                p.get("macro2", ""),
                self._log,
                self._stop_event,
                self._mb,
            )

        self._run_bg("⏳ Макросы…", _w, name="Макросы xlsm")
