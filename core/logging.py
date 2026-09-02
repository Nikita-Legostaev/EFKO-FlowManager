"""core/logging.py — настройка логирования приложения."""

import os
import logging as _logging

from core.paths import app_root, is_frozen


def setup_logger():
    log_path = os.path.join(app_root(), "flowmanager.log")

    logger = _logging.getLogger()
    logger.setLevel(_logging.INFO)
    fmt = _logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    fh = _logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    # Консольный handler — только при запуске из исходников (там реально
    # есть куда его выводить и его удобно смотреть). Собранное приложение
    # оконное (console=False), консоли нет, а сам StreamHandler привязан
    # к системной кодировке (на русской Windows часто cp1251) и падает с
    # UnicodeEncodeError на любых символах вне неё — например, на рамках
    # ASCII-арта из сообщений Playwright (╔ ║ ╚). Раз смотреть всё равно
    # некому — не создаём этот риск в собранной версии.
    if not is_frozen():
        ch = _logging.StreamHandler()
        ch.setFormatter(fmt)
        logger.addHandler(ch)

    _logging.info(f"Лог: {log_path}")
