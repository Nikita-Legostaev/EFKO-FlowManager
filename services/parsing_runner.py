# -*- coding: utf-8 -*-
"""
services/parsing_runner.py — движок вкладки «Парсинг ЖДСК».

Схема работы:
  • сами скрипты (fixprice.py, bristol.py …) и реестр registry.json лежат
    ВНУТРИ сборки приложения, в папке parsers/ — вместе с приложением
    обновляются и вместе с ним раздаются;
  • результаты (Excel по каждой сети) пишутся в папку, которую пользователь
    выбирает во вкладке. На сетевой диск парсинг ничего не пишет;
  • скрипты не переписываются: запускаются через runpy как обычные скрипты,
    но рабочей папкой им подставляется папка результатов, поэтому все их
    xlsx/json оказываются именно там.

Вспомогательные данные (towns.csv, city_and_regions_Russia.xlsx и т.п.)
при первом запуске копируются из сборки в папку результатов — иначе скрипт
их не найдёт, ведь он читает файлы из текущей папки.
"""

import io
import os
import re
import sys
import json
import runpy
import shutil
import socket
import tempfile
import subprocess
import logging
import threading
import contextlib

REGISTRY_NAME = "registry.json"
SCRIPTS_DIRNAME = "parsers"

# Утилиты, которые не показываем как парсеры сетей
_HIDDEN_BY_DEFAULT = {"json_count.py", "mayak.py"}

# Расширения вспомогательных файлов, которые копируются в папку результатов
_DATA_EXT = {".csv", ".xlsx", ".xls", ".txt", ".html", ".json"}


# ── Где лежат скрипты ────────────────────────────────────────────────────────

def scripts_dir() -> str:
    """
    Папка со скриптами внутри приложения.

    В собранном exe это распакованный ресурс (только чтение),
    при запуске из исходников — ./parsers рядом с main.py.
    """
    from core.paths import _resource, app_root
    try:
        path = _resource(SCRIPTS_DIRNAME)
        if os.path.isdir(path):
            return path
    except Exception:
        pass

    return os.path.join(app_root(), SCRIPTS_DIRNAME)


# ── Реестр ───────────────────────────────────────────────────────────────────

def registry_path() -> str:
    return os.path.join(scripts_dir(), REGISTRY_NAME)


def load_registry() -> dict:
    path = registry_path()
    if not os.path.isfile(path):
        logging.error(f"[parsing] Нет {path}")
        return {"parsers": []}
    try:
        with open(path, encoding="utf-8-sig") as f:
            data = json.load(f)
        if isinstance(data, list):
            data = {"parsers": data}
        data.setdefault("parsers", [])
        return data
    except Exception as e:
        logging.error(f"[parsing] Битый {REGISTRY_NAME}: {e}")
        return {"parsers": []}


def list_parsers() -> list:
    """
    Список сетей: реестр + реально лежащие в сборке .py файлы.
    Скрипт без записи в реестре тоже показывается — с пометкой.
    """
    folder = scripts_dir()
    if not os.path.isdir(folder):
        return []

    reg = load_registry()
    known, result = {}, []

    for item in reg.get("parsers", []):
        script = item.get("script", "")
        entry = {
            "key": item.get("key") or _slug(script),
            "name": item.get("name") or script,
            "script": script,
            "icon": item.get("icon", "🏬"),
            "help": item.get("help", ""),
            "outputs": item.get("outputs", []),
            "needs_key": bool(item.get("needs_key")),
            "env_key": item.get("env_key", ""),
            "key_title": item.get("key_title", "API-ключ"),
            "key_url": item.get("key_url", ""),
            "key_help": item.get("key_help", ""),
            "args": item.get("args", []),
            "needs_chrome_cdp": bool(item.get("needs_chrome_cdp")),
            "cdp_port": item.get("cdp_port", CDP_PORT),
            "needs_browser": bool(item.get("needs_browser")),
            "hidden": bool(item.get("hidden")),
            "exists": bool(script) and os.path.isfile(os.path.join(folder, script)),
            "known": True,
        }
        known[script.lower()] = entry
        if not entry["hidden"]:
            result.append(entry)

    try:
        for fn in sorted(os.listdir(folder)):
            if not fn.lower().endswith(".py"):
                continue
            if fn.lower() in known or fn in _HIDDEN_BY_DEFAULT:
                continue
            result.append({
                "key": _slug(fn), "name": os.path.splitext(fn)[0], "script": fn,
                "icon": "❔",
                "help": ("Скрипт есть в сборке, но не описан в registry.json.\n"
                         "Добавьте его в реестр, чтобы задать название, "
                         "имя файла результата и инструкцию."),
                "outputs": [], "needs_key": False, "env_key": "",
                "key_title": "API-ключ", "key_url": "", "key_help": "",
                "args": [], "hidden": False, "exists": True, "known": False,
            })
    except Exception as e:
        logging.error(f"[parsing] Не удалось прочитать {folder}: {e}")

    return result


def find_parser(key: str):
    for p in list_parsers():
        if p["key"] == key:
            return p
    return None


def _slug(name: str) -> str:
    base = os.path.splitext(os.path.basename(name or ""))[0]
    return re.sub(r"[^0-9a-zA-Zа-яА-ЯёЁ]+", "_", base).strip("_").lower()


# ── Подготовка папки результатов ─────────────────────────────────────────────

def prepare_workdir(output_folder: str, log=None) -> int:
    """
    Копирует вспомогательные данные из сборки в папку результатов.

    Скрипты читают исходники (towns.csv, справочники городов) из текущей
    папки, а писать результаты они должны туда же. Уже существующие файлы
    не трогаем — иначе затрём накопленные кэши и чекпоинты.
    """
    src = scripts_dir()
    copied = 0
    os.makedirs(output_folder, exist_ok=True)

    try:
        for fn in os.listdir(src):
            ext = os.path.splitext(fn)[1].lower()
            if ext not in _DATA_EXT or fn == REGISTRY_NAME:
                continue
            dst = os.path.join(output_folder, fn)
            if os.path.exists(dst):
                continue
            try:
                shutil.copy2(os.path.join(src, fn), dst)
                copied += 1
            except Exception as e:
                if log:
                    log(f"   ⚠ Не удалось скопировать {fn}: {e}")
    except Exception as e:
        logging.error(f"[parsing] prepare_workdir: {e}")

    if copied and log:
        log(f"   📄 В папку результатов скопировано исходных файлов: {copied}")
    return copied


# ── Chrome с отладочным портом ───────────────────────────────────────────────

CDP_PORT = 9222

_CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
]


def _port_alive(port: int, timeout: float = 0.4) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout):
            return True
    except OSError:
        return False


def _find_chrome() -> str:
    for p in _CHROME_PATHS:
        if p and os.path.isfile(p):
            return p
    return ""


def ensure_chrome_cdp(log, port: int = CDP_PORT, wait: float = 20.0) -> bool:
    """
    Поднимает Chrome с --remote-debugging-port, если он ещё не слушает порт.

    Часть парсеров (например, Бристоль) не запускают браузер сами, а
    подключаются к уже работающему через CDP. Раньше человеку пришлось бы
    руками стартовать Chrome с нужным флагом.

    Профиль берётся отдельный, во временной папке: подключиться к обычному
    Chrome, запущенному без флага, всё равно нельзя, а перезапускать
    пользователю рабочие вкладки — недопустимо.
    """
    if _port_alive(port):
        log(f"   🌐 Chrome уже слушает порт {port}")
        return True

    exe = _find_chrome()
    if not exe:
        log("   ❌ Не найден Chrome или Edge. Установите Chrome либо запустите "
            f"его вручную с флагом --remote-debugging-port={port}")
        return False

    profile = os.path.join(tempfile.gettempdir(), f"efko_cdp_profile_{port}")
    os.makedirs(profile, exist_ok=True)

    log(f"   🌐 Запускаю {os.path.basename(exe)} с отладочным портом {port}…")
    try:
        subprocess.Popen(
            [exe,
             f"--remote-debugging-port={port}",
             f"--user-data-dir={profile}",
             "--no-first-run",
             "--no-default-browser-check",
             "--disable-popup-blocking",
             "about:blank"],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception as e:
        log(f"   ❌ Не удалось запустить браузер: {e}")
        return False

    import time
    deadline = time.time() + wait
    while time.time() < deadline:
        if _port_alive(port):
            log("   ✅ Браузер готов")
            return True
        time.sleep(0.5)

    log(f"   ❌ Браузер не открыл порт {port} за {int(wait)} с")
    return False


# ── Перехват вывода ──────────────────────────────────────────────────────────

class _LogStream(io.TextIOBase):
    """Превращает print() скрипта в построчные вызовы log()."""

    def __init__(self, log, prefix=""):
        self._log, self._prefix, self._buf = log, prefix, ""

    def write(self, s):
        if not s:
            return 0
        self._buf += s
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            line = line.rstrip("\r")
            if line.strip():
                try:
                    self._log(f"{self._prefix}{line}")
                except Exception:
                    pass
        return len(s)

    def flush(self):
        if self._buf.strip():
            try:
                self._log(f"{self._prefix}{self._buf.strip()}")
            except Exception:
                pass
        self._buf = ""

    def isatty(self):
        return False


class _LogHandler(logging.Handler):
    """
    Пробрасывает logging.info()/warning() скрипта в log() интерфейса.

    Часть парсеров (fixprice.py, kb.py) пишут прогресс через logging, а не
    print(). contextlib.redirect_stdout/stderr их не ловит — а собственный
    logging.basicConfig() скрипта не срабатывает, потому что к моменту
    запуска парсера у root-логгера уже есть обработчики от setup_logger()
    приложения (basicConfig — no-op, если у root уже есть handlers). Без
    этого перехвата пользователь не видит вообще никакого прогресса на
    время долгого парсинга и решает, что приложение зависло.

    ВАЖНО: log_fn (Api._log) сам вызывает logging.info() — без защиты от
    реентерабельности это создаёт бесконечную рекурсию (emit -> log_fn ->
    logging.info -> тот же root-логгер -> тот же handler -> emit -> ...),
    которая забивает лог тысячами дублей с нарастающим отступом и в итоге
    падает по превышению глубины рекурсии.
    """

    def __init__(self, log_fn, prefix=""):
        super().__init__()
        self._log_fn, self._prefix = log_fn, prefix
        self._in_emit = False

    def emit(self, record):
        if self._in_emit:
            return
        self._in_emit = True
        try:
            self._log_fn(f"{self._prefix}{self.format(record)}")
        except Exception:
            pass
        finally:
            self._in_emit = False


# ── Запуск ───────────────────────────────────────────────────────────────────

_run_lock = threading.Lock()
_running_key = None


def is_running() -> bool:
    return _running_key is not None


def current_parser() -> str:
    return _running_key or ""


def run_parser(output_folder: str, key: str, log, stop_event=None,
               extra_args=None, api_keys=None) -> dict:
    """
    Синхронно выполняет один парсер. Вызывать из фонового потока.

    output_folder — куда лягут Excel и промежуточные файлы.
    api_keys — {ИМЯ_ПЕРЕМЕННОЙ: значение}; подставляются в окружение только
    на время работы скрипта.

    Возвращает {"ok":bool,"msg":str,"outputs":[пути созданных файлов]}
    """
    global _running_key

    if not output_folder:
        return {"ok": False, "msg": "Не выбрана папка сохранения результатов",
                "outputs": []}

    parser = find_parser(key)
    if not parser:
        return {"ok": False, "msg": f"Парсер «{key}» не найден", "outputs": []}

    script_path = os.path.join(scripts_dir(), parser["script"])
    if not os.path.isfile(script_path):
        return {"ok": False, "msg": f"Нет файла в сборке: {parser['script']}",
                "outputs": []}

    if not _run_lock.acquire(blocking=False):
        return {"ok": False,
                "msg": f"Уже выполняется «{_running_key}» — дождитесь завершения",
                "outputs": []}

    _running_key = parser["name"]
    old_cwd, old_argv = os.getcwd(), list(sys.argv)
    stream = _LogStream(log, prefix="   ")

    env_name = parser.get("env_key") or ""
    env_value = (api_keys or {}).get(env_name, "") if env_name else ""
    env_backup = None

    log(f"▶ Парсинг: {parser['name']} ({parser['script']})")
    log(f"   📁 Результаты: {output_folder}")
    if parser.get("needs_key"):
        if env_value:
            log(f"   🔑 Ключ {env_name} подставлен из настроек")
        else:
            log(f"   ⚠ Ключ {env_name or 'API'} не задан — нажмите 🔑 на карточке "
                f"сети, иначе будет ошибка авторизации или неполные данные")

    try:
        prepare_workdir(output_folder, log)

        if parser.get("needs_chrome_cdp"):
            if not ensure_chrome_cdp(log, int(parser.get("cdp_port") or CDP_PORT)):
                return {"ok": False,
                        "msg": "Не удалось подготовить браузер с отладочным портом",
                        "outputs": []}
        elif parser.get("needs_browser"):
            # Fix Price/Доброцен запускают playwright.chromium.launch с
            # channel="msedge" — используют уже установленный в системе
            # Edge, а не отдельно скачиваемый Playwright-Chromium (в сетях
            # с закрытым доступом к серверам загрузки Microsoft/Google его
            # не докачать даже вручную — сам Node-драйвер Playwright при
            # этом работает нормально, это отдельная сеть/CDN).
            if not _find_chrome():
                log("   ❌ Не найден Chrome или Edge — установите один из них")
                return {"ok": False,
                        "msg": "Нет системного браузера (Chrome/Edge)",
                        "outputs": []}

        if env_name and env_value:
            env_backup = os.environ.get(env_name)
            os.environ[env_name] = env_value

        # Рабочая папка = папка результатов: скрипт пишет свои xlsx сюда
        os.chdir(output_folder)
        args = list(parser.get("args") or [])
        if extra_args:
            args += [str(a) for a in extra_args]
        sys.argv = [script_path] + args

        log_handler = _LogHandler(log, prefix="   ")
        root_logger = logging.getLogger()
        root_logger.addHandler(log_handler)
        try:
            with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
                runpy.run_path(script_path, run_name="__main__")
        finally:
            root_logger.removeHandler(log_handler)
        stream.flush()

        outputs = []
        for rel in parser.get("outputs") or []:
            full = os.path.join(output_folder, rel)
            if os.path.isfile(full):
                outputs.append(full)
                log(f"   ✅ Файл сети готов: {rel}")
            else:
                log(f"   ⚠ Ожидался файл {rel}, но его нет — "
                    f"скорее всего сеть отдала пустой результат")

        log(f"✅ {parser['name']} — завершено")
        return {"ok": True, "msg": "", "outputs": outputs}

    except SystemExit as e:
        stream.flush()
        code = getattr(e, "code", 0) or 0
        ok = code == 0
        log(f"{'✅' if ok else '❌'} {parser['name']} — завершено (код {code})")
        return {"ok": ok, "msg": "" if ok else f"код выхода {code}", "outputs": []}

    except KeyboardInterrupt:
        stream.flush()
        log(f"⛔ {parser['name']} — прервано")
        return {"ok": False, "msg": "Прервано пользователем", "outputs": []}

    except ModuleNotFoundError as e:
        stream.flush()
        mod = getattr(e, "name", "") or str(e)
        log(f"❌ {parser['name']} — не хватает библиотеки «{mod}»")
        if mod == "playwright":
            log("   Установите: pip install playwright "
                "и затем python -m playwright install chromium")
        else:
            log(f"   Установите: pip install {mod}")
        return {"ok": False, "msg": f"нет библиотеки {mod}", "outputs": []}

    except FileNotFoundError as e:
        stream.flush()
        missing = getattr(e, "filename", "") or str(e)
        log(f"❌ {parser['name']} — нет исходного файла «{missing}»")
        log("   Он должен лежать в папке parsers/ внутри приложения и "
            "копироваться в папку результатов при запуске")
        return {"ok": False, "msg": f"нет файла {missing}", "outputs": []}

    except Exception as e:
        stream.flush()
        logging.exception(f"[parsing] {parser['script']}")
        log(f"❌ {parser['name']} — ошибка: {e}")
        return {"ok": False, "msg": str(e), "outputs": []}

    finally:
        try:
            os.chdir(old_cwd)
        except Exception:
            pass
        if env_name and env_value:
            if env_backup is None:
                os.environ.pop(env_name, None)
            else:
                os.environ[env_name] = env_backup
        sys.argv = old_argv
        _running_key = None
        _run_lock.release()


def run_many(output_folder: str, keys: list, log, stop_event=None,
             api_keys=None) -> dict:
    """Последовательный прогон нескольких сетей. Стоп проверяется между ними."""
    done, failed, outputs = [], [], []
    for k in keys:
        if stop_event is not None and stop_event.is_set():
            log("⛔ Остановлено пользователем")
            break
        res = run_parser(output_folder, k, log, stop_event, api_keys=api_keys)
        outputs += res.get("outputs") or []
        (done if res["ok"] else failed).append(k)
    log(f"Итог: успешно {len(done)}, с ошибкой {len(failed)}")
    return {"ok": not failed, "done": done, "failed": failed, "outputs": outputs}