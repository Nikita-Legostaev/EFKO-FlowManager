# -*- coding: utf-8 -*-
"""
updater.py — автообновление EFKO FlowManager через сетевую папку.

Что изменилось против старой версии:
  • version.txt ищется рядом с exe (frozen) ИЛИ рядом с исходником (dev),
    а не в папке интерпретатора;
  • номер версии пишется .bat-файлом ПОСЛЕ успешного move, а не до —
    если обновление не применилось, приложение не считает себя обновлённым;
  • обновляются не только exe, но и любые файлы/папки из списка "files"
    в version.json (web, config-шаблоны, парсеры и т.д.);
  • появился check_updates_manual() для кнопки «Проверить обновления» в UI —
    без tkinter из фонового потока;
  • если сетевой диск недоступен, всё тихо логируется и приложение работает.

Формат version.json в сетевой папке:
{
  "version": "3.1.0",
  "exe": "EFKO-FlowManager_3.1.0.exe",
  "notes": "Что нового в этой версии",
  "files": ["web", "parsers.json"],
  "mandatory": false
}
"exe"   — имя файла в сетевой папке (можно версионировать, чтобы заливка
          новой сборки не ломала уже запущенные копии).
"files" — необязательный список доп. файлов/папок, которые копируются
          рядом с exe (перезаписью).
"""

import os
import sys
import json
import shutil
import logging
import subprocess
import threading

UPDATE_FOLDER = (
    r"V:/ОАР/Внутренняя/старый Коммон/33_КОМИТЕТ ПО ЦЕНООБРАЗОВАНИЮ БП"
    r"/Полочные цены Promodata/EFKO-FlowManager"
)
VERSION_FILE = "version.json"

# ── Пути ─────────────────────────────────────────────────────────────────────

IS_FROZEN = getattr(sys, "frozen", False)


def _base_dir() -> str:
    """Папка, где живёт приложение: рядом с exe или рядом с исходниками."""
    if IS_FROZEN:
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _is_onefile() -> bool:
    """
    True — сборка одним файлом, False — папкой (COLLECT).

    У onefile распакованные ресурсы лежат во временной папке, не связанной
    с exe; у onedir — внутри папки приложения.
    """
    if not IS_FROZEN:
        return False
    meipass = getattr(sys, "_MEIPASS", "")
    if not meipass:
        return False
    try:
        return os.path.normcase(os.path.commonpath([meipass, _base_dir()])) \
            != os.path.normcase(_base_dir())
    except Exception:
        return True


IS_ONEFILE = _is_onefile()
CURRENT_VERSION_FILE = os.path.join(_base_dir(), "version.txt")


def _version_file_candidates():
    """
    Где искать version.txt.

    Первым — рядом с exe: туда его пишет обновление. Дальше — упакованные
    ресурсы: при onedir-сборке version.txt из datas попадает в _internal,
    а не в корень папки приложения, и без этого запаса приложение считало бы
    себя версией 0.0.0 и предлагало обновиться на пустом месте.
    """
    paths = [CURRENT_VERSION_FILE]
    meipass = getattr(sys, "_MEIPASS", "")
    if meipass:
        paths.append(os.path.join(meipass, "version.txt"))
    paths.append(os.path.join(_base_dir(), "_internal", "version.txt"))
    return paths


def _read_current_version() -> str:
    for path in _version_file_candidates():
        try:
            if os.path.isfile(path):
                with open(path, encoding="utf-8") as f:
                    v = f.read().strip()
                    if v:
                        return v
        except Exception as e:
            logging.debug(f"[updater] {path} не прочитан: {e}")
    return "0.0.0"


def _read_remote_version():
    path = os.path.join(UPDATE_FOLDER, VERSION_FILE)
    try:
        if not os.path.exists(path):
            logging.debug(f"[updater] нет {path}")
            return None
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception as e:
        logging.debug(f"[updater] Не удалось прочитать version.json: {e}")
        return None


def _version_tuple(v):
    try:
        parts = [int(x) for x in str(v).strip().split(".")]
        while len(parts) < 3:
            parts.append(0)
        return tuple(parts[:3])
    except Exception:
        return (0, 0, 0)


def is_newer(remote_ver, current_ver) -> bool:
    return _version_tuple(remote_ver) > _version_tuple(current_ver)


# ── Публичное API для UI ─────────────────────────────────────────────────────

def get_update_info() -> dict:
    """
    Синхронно возвращает состояние обновлений — для кнопки в интерфейсе.
    {"ok":bool,"available":bool,"current":str,"remote":str,"notes":str,"msg":str}
    """
    current = _read_current_version()
    remote = _read_remote_version()
    if not remote:
        return {
            "ok": False,
            "available": False,
            "current": current,
            "remote": "",
            "notes": "",
            "msg": "Папка обновлений недоступна (проверьте подключение диска V:)",
        }
    remote_ver = str(remote.get("version", "0.0.0"))
    return {
        "ok": True,
        "available": is_newer(remote_ver, current),
        "current": current,
        "remote": remote_ver,
        "notes": remote.get("notes", ""),
        "msg": "",
    }


# ── Установка ────────────────────────────────────────────────────────────────

def _copy_extra_files(remote: dict, log=logging.info):
    """Копирует доп. файлы/папки из version.json['files'] рядом с приложением."""
    extras = remote.get("files") or []
    base = _base_dir()
    for rel in extras:
        src = os.path.join(UPDATE_FOLDER, rel)
        dst = os.path.join(base, rel)
        try:
            if os.path.isdir(src):
                shutil.copytree(src, dst, dirs_exist_ok=True)
            elif os.path.isfile(src):
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
            else:
                log(f"[updater] пропущен (нет в источнике): {rel}")
                continue
            log(f"[updater] обновлён ресурс: {rel}")
        except Exception as e:
            log(f"[updater] не удалось скопировать {rel}: {e}")


def _prepare_onefile(remote: dict) -> dict:
    """Сборка одним файлом: подменяем exe через .bat после выхода."""
    exe_name = remote.get("exe", "EFKO-FlowManager.exe")
    version = str(remote.get("version", "0.0.0"))
    src = os.path.join(UPDATE_FOLDER, exe_name)
    dst = sys.executable
    dst_new = dst + ".new"
    bat_path = os.path.join(os.path.dirname(dst), "_update.bat")

    if not os.path.isfile(src):
        return {"ok": False, "bat": "", "msg": f"Нет файла обновления: {src}"}

    try:
        shutil.copy2(src, dst_new)
        _copy_extra_files(remote)

        bat = (
            "@echo off\r\n"
            "chcp 65001 > nul\r\n"
            "timeout /t 2 /nobreak > nul\r\n"
            "set TRIES=0\r\n"
            ":retry\r\n"
            f'move /y "{dst_new}" "{dst}" > nul 2>&1\r\n'
            "if errorlevel 1 (\r\n"
            "  set /a TRIES+=1\r\n"
            "  if %TRIES% LSS 10 (\r\n"
            "    timeout /t 2 /nobreak > nul\r\n"
            "    goto retry\r\n"
            "  )\r\n"
            "  echo Не удалось применить обновление. Закройте приложение и повторите.\r\n"
            "  pause\r\n"
            "  exit /b 1\r\n"
            ")\r\n"
            f'> "{CURRENT_VERSION_FILE}" echo {version}\r\n'
            f'start "" "{dst}"\r\n'
            'del "%~f0"\r\n'
        )
        with open(bat_path, "w", encoding="utf-8") as f:
            f.write(bat)
        return {"ok": True, "bat": bat_path, "msg": ""}
    except Exception as e:
        logging.error(f"[updater] onefile: {e}")
        try:
            if os.path.exists(dst_new):
                os.remove(dst_new)
        except Exception:
            pass
        return {"ok": False, "bat": "", "msg": str(e)}


def _prepare_onedir(remote: dict) -> dict:
    """
    Сборка папкой (COLLECT): подменять один exe нельзя — рядом лежат
    _internal с библиотеками, web и parsing. Копируем папку целиком
    через robocopy после выхода из приложения.

    В version.json для такой сборки указывается "dir" — имя папки
    в сетевом каталоге обновлений:
        "dir": "EFKO-FlowManager_3.1.0"
    """
    version = str(remote.get("version", "0.0.0"))
    dir_name = remote.get("dir") or remote.get("folder")
    if not dir_name:
        return {"ok": False, "bat": "",
                "msg": "В version.json не указано поле \"dir\" с именем папки сборки"}

    src = os.path.join(UPDATE_FOLDER, dir_name)
    dst = _base_dir()
    exe_path = sys.executable
    bat_path = os.path.join(dst, "_update.bat")
    log_path = os.path.join(dst, "_update.log")

    if not os.path.isdir(src):
        return {"ok": False, "bat": "", "msg": f"Нет папки обновления: {src}"}
    if not os.path.isfile(os.path.join(src, os.path.basename(exe_path))):
        return {"ok": False, "bat": "",
                "msg": f"В папке обновления нет {os.path.basename(exe_path)}"}

    try:
        bat = (
            "@echo off\r\n"
            "chcp 65001 > nul\r\n"
            "timeout /t 3 /nobreak > nul\r\n"
            "set TRIES=0\r\n"
            ":retry\r\n"
            f'robocopy "{src}" "{dst}" /E /R:2 /W:2 /NFL /NDL /NJH /NJS '
            f'/XF _update.bat _update.log config.json version.txt '
            f'>> "{log_path}" 2>&1\r\n'
            "if %ERRORLEVEL% GEQ 8 (\r\n"
            "  set /a TRIES+=1\r\n"
            "  if %TRIES% LSS 5 (\r\n"
            "    timeout /t 3 /nobreak > nul\r\n"
            "    goto retry\r\n"
            "  )\r\n"
            "  echo Не удалось применить обновление, подробности в _update.log\r\n"
            "  pause\r\n"
            "  exit /b 1\r\n"
            ")\r\n"
            f'> "{CURRENT_VERSION_FILE}" echo {version}\r\n'
            f'start "" "{exe_path}"\r\n'
            'del "%~f0"\r\n'
        )
        with open(bat_path, "w", encoding="utf-8") as f:
            f.write(bat)
        logging.info(f"[updater] onedir-обновление подготовлено: {version}")
        return {"ok": True, "bat": bat_path, "msg": ""}
    except Exception as e:
        logging.error(f"[updater] onedir: {e}")
        return {"ok": False, "bat": "", "msg": str(e)}


def prepare_update(remote: dict) -> dict:
    """
    Готовит обновление и .bat, который применит его после выхода.
    Возвращает {"ok":bool,"bat":str,"msg":str}.
    """
    if not IS_FROZEN:
        return {"ok": False, "bat": "",
                "msg": "Обновление доступно только для собранного приложения"}
    return _prepare_onefile(remote) if IS_ONEFILE else _prepare_onedir(remote)


def apply_update(bat_path: str, on_exit=None):
    """Запускает .bat и закрывает приложение."""
    try:
        subprocess.Popen(
            bat_path, shell=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
    except Exception as e:
        logging.error(f"[updater] Не удалось запустить {bat_path}: {e}")
        return False
    if on_exit:
        on_exit()
    else:
        sys.exit(0)
    return True


def install_now(on_exit=None) -> dict:
    """Проверить + подготовить + применить одним вызовом (для кнопки в UI)."""
    remote = _read_remote_version()
    if not remote:
        return {"ok": False, "msg": "Папка обновлений недоступна"}
    if not is_newer(remote.get("version", "0.0.0"), _read_current_version()):
        return {"ok": False, "msg": "У вас уже последняя версия"}
    res = prepare_update(remote)
    if not res["ok"]:
        return {"ok": False, "msg": res["msg"]}
    apply_update(res["bat"], on_exit=on_exit)
    return {"ok": True, "msg": "Приложение перезапустится"}


# ── Автопроверка при старте ──────────────────────────────────────────────────

def check_for_updates(splash_set=None, on_exit=None, notify=None):
    """
    Фоновая проверка при запуске.

    notify(info) — необязательный колбэк в UI (обычно self._emit('update_available', info)).
    Если notify задан — окно tkinter НЕ показывается, решение принимает интерфейс.
    Если notify не задан — показывается системный диалог (как раньше).
    """

    def _worker():
        try:
            if splash_set:
                splash_set(5, "Проверка обновлений…")
            info = get_update_info()
            if not info["ok"] or not info["available"]:
                logging.debug(f"[updater] {info.get('msg') or 'версия актуальна'}")
                return

            if notify:
                try:
                    notify(info)
                except Exception as e:
                    logging.error(f"[updater] notify: {e}")
                return

            # Fallback: собственный диалог
            import tkinter as tk
            from tkinter import messagebox

            msg = (
                "Доступна новая версия EFKO FlowManager!\n\n"
                f"Текущая: {info['current']}\n"
                f"Новая: {info['remote']}\n"
            )
            if info["notes"]:
                msg += f"\nЧто нового:\n{info['notes']}\n"
            msg += "\nОбновить сейчас?"

            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            answer = messagebox.askyesno("Обновление", msg, parent=root)
            root.destroy()
            if not answer:
                return

            remote = _read_remote_version()
            res = prepare_update(remote)
            if res["ok"]:
                apply_update(res["bat"], on_exit=on_exit)
            else:
                logging.error(f"[updater] {res['msg']}")
        except Exception as e:
            logging.error(f"[updater] check_for_updates: {e}")

    threading.Thread(target=_worker, daemon=True).start()