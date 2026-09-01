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


def _resource(rel_path: str, writable: bool = False) -> str:
    """
    Абсолютный путь к ресурсу — корректно и в EXE, и из исходников.

    При onedir-сборке (PyInstaller 6+) все datas (web/, parsers/,
    config.json и т.д.) физически лежат в _internal/ рядом с exe, а не
    прямо в папке приложения — sys._MEIPASS указывает именно туда (для
    onefile-сборки — на временную папку распаковки). Без этой проверки
    _resource() всегда мимо для собранного onedir-приложения.

    Порядок поиска (для write=False, обычное чтение ресурсов сборки):
      1. рядом с exe — сюда автообновление докладывает файлы поверх
         сборки, у них приоритет;
      2. sys._MEIPASS (_internal/ для onedir, temp-папка для onefile);
      3. если нигде не нашли — путь рядом с exe как раньше (для случаев,
         когда ресурс ещё будет создан, а не только прочитан).

    writable=True — для файлов, которые приложение само перезаписывает
    (config.json): _internal/ никогда не возвращается, даже если файла
    рядом с exe ещё нет, — иначе настройки будут жить в папке, которую
    следующее onedir-обновление целиком затирает копией с сетевого диска.
    """
    beside_exe = os.path.join(app_root(), rel_path)
    if writable or os.path.exists(beside_exe):
        return beside_exe
    meipass = getattr(sys, "_MEIPASS", "")
    if meipass:
        bundled = os.path.join(meipass, rel_path)
        if os.path.exists(bundled):
            return bundled
    return beside_exe
