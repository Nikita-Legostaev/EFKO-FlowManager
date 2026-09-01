"""
api/promodate.py — миксин: режимы промодаты (ЦО / Мониторинг цен / Дополнительно).

Каждый режим — своя папка скачивания xlsx (services.promodate.download_folder_for_mode)
и свой набор «Папка сохранения CSV» + «Power Query / Макросы», чтобы данные и
настройки разных режимов не путались. Папка скачивания подбирается
автоматически, остальные поля — обычные поля формы, которые при
переключении режима подменяются на запомненные для этого режима значения.
"""

from core.config import load_config, save_config_data
from services.promodate import PROMO_MODES, DEFAULT_PROMO_MODE

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
