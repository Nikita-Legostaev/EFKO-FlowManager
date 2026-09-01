"""
api/promodate.py — миксин: режимы промодаты (ЦО / Мониторинг цен / Дополнительно).

Каждый режим — свои папка скачивания xlsx и папка сохранения CSV, чтобы
данные разных режимов не путались. Папка скачивания подбирается
автоматически (services.promodate.download_folder_for_mode), папка
сохранения — обычное поле output_folder, которое при переключении режима
подменяется на запомненное для этого режима значение.
"""

from core.config import load_config, save_config_data
from services.promodate import PROMO_MODES, DEFAULT_PROMO_MODE


class ApiPromodateMixin:

    def get_promodata_modes(self):
        return [{"key": k, "label": v} for k, v in PROMO_MODES.items()]

    def set_promodata_mode(self, mode: str):
        """
        Переключает режим промодаты.

        Текущее значение output_folder запоминается за старым режимом,
        для нового режима подставляется его сохранённое значение (или
        пусто, если режим ещё не использовался). Возвращает обновлённый
        конфиг, чтобы фронт мог сразу обновить поле папки сохранения.
        """
        cfg = load_config()
        if mode not in PROMO_MODES:
            mode = DEFAULT_PROMO_MODE

        folders = cfg.get("promodata_output_folders")
        if not isinstance(folders, dict):
            folders = {}

        old_mode = cfg.get("promodata_mode", DEFAULT_PROMO_MODE)
        folders[old_mode] = cfg.get("output_folder", "")

        cfg["promodata_output_folders"] = folders
        cfg["promodata_mode"] = mode
        cfg["output_folder"] = folders.get(mode, "")
        save_config_data(cfg)
        return cfg
