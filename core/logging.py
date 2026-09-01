"""core/logging.py — настройка логирования приложения."""

import os
import logging as _logging

from core.paths import app_root


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
    ch = _logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)
    _logging.info(f"Лог: {log_path}")
