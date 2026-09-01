"""
core/paths.py — где искать ресурсы приложения.

Корень приложения — это папка рядом с exe (собранная версия) или корень
репозитория (запуск из исходников, на уровень выше core/).
"""

import os
import sys


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def app_root() -> str:
    if is_frozen():
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _resource(rel_path: str) -> str:
    """Абсолютный путь к ресурсу — корректно и в EXE, и из исходников."""
    return os.path.join(app_root(), rel_path)
