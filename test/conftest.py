import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# ── Заглушки Windows-библиотек ────────────────────────────────────────────
# services/*.py работают с Excel через COM: `import pythoncom` и
# `import win32com.client as win32` — оба лежат ВНУТРИ функций (так задумано:
# при старте приложения их грузить незачем). Из-за этого мокать их как
# services.promodate.pythoncom нельзя — модульных атрибутов с такими именами
# нет, patch падает с AttributeError ещё до вызова кода.
#
# Ставим заглушки прямо в sys.modules: функция при вызове сделает `import
# pythoncom` и получит отсюда MagicMock. Заодно весь Windows-зависимый слой
# становится тестируемым на любой ОС — раньше эти тесты не проходили нигде,
# кроме машины с установленным pywin32.
for _name in ("pythoncom", "win32com", "win32com.client", "win32api", "win32con"):
    if _name not in sys.modules:
        try:
            __import__(_name)
        except ImportError:
            sys.modules[_name] = MagicMock(name=_name)

# win32com.client должен быть доступен и как атрибут win32com — иначе
# `import win32com.client as win32` не отдаст заглушку.
if isinstance(sys.modules.get("win32com"), MagicMock):
    sys.modules["win32com"].client = sys.modules["win32com.client"]
