# -*- coding: utf-8 -*-
"""
api/parsing.py — миксин: вкладка «Парсинг ЖДСК».

Скрипты парсинга живут внутри сборки приложения, результаты пишутся в папку,
которую пользователь выбирает во вкладке. Путь запоминается в config.json
(ключ parsing_output), API-ключи — там же в parsing_keys.
"""

import os
import logging
import threading

from core.config import load_config, save_config_data
from services.parsing_runner import (
    scripts_dir,
    list_parsers,
    find_parser,
    run_parser,
    run_many,
    is_running,
)


class ApiParsingMixin:

    # ── Конфиг ───────────────────────────────────────────────────────────

    def _parsing_output(self) -> str:
        return (load_config().get("parsing_output") or "").strip()

    def _api_keys(self) -> dict:
        keys = load_config().get("parsing_keys") or {}
        return keys if isinstance(keys, dict) else {}

    def get_parsing_config(self):
        out = self._parsing_output()
        keys = self._api_keys()
        parsers = list_parsers()
        for p in parsers:
            env = p.get("env_key") or ""
            p["key_set"] = bool(env and (keys.get(env) or "").strip())
        return {
            "output": out,
            "output_ok": bool(out) and os.path.isdir(out),
            "scripts_dir": scripts_dir(),
            "scripts_ok": os.path.isdir(scripts_dir()),
            "running": is_running(),
            "parsers": parsers,
        }

    def save_parsing_output(self, path: str):
        cfg = load_config()
        cfg["parsing_output"] = (path or "").strip()
        save_config_data(cfg)
        return self.get_parsing_config()

    def browse_parsing_output(self):
        """Диалог выбора папки для результатов парсинга."""
        path = self.browse_folder()
        if path:
            self.save_parsing_output(path)
        return self.get_parsing_config()

    # ── API-ключи ────────────────────────────────────────────────────────

    def get_parser_key(self, key: str):
        p = find_parser(key)
        if not p:
            return {"ok": False, "msg": "Парсер не найден"}
        env = p.get("env_key") or ""
        return {
            "ok": True,
            "name": p["name"],
            "env_key": env,
            "key_title": p.get("key_title") or "API-ключ",
            "key_url": p.get("key_url") or "",
            "key_help": p.get("key_help") or "",
            "value": (self._api_keys().get(env, "") if env else ""),
        }

    def save_parser_key(self, data: dict):
        env = ((data or {}).get("env_key") or "").strip()
        value = ((data or {}).get("value") or "").strip()
        if not env:
            return {"ok": False, "msg": "Не указано имя переменной ключа"}

        cfg = load_config()
        keys = cfg.get("parsing_keys")
        if not isinstance(keys, dict):
            keys = {}
        if value:
            keys[env] = value
        else:
            keys.pop(env, None)
        cfg["parsing_keys"] = keys
        save_config_data(cfg)

        self._emit("toast", {"type": "success",
                             "message": "Ключ сохранён" if value else "Ключ удалён"})
        return {"ok": True, "saved": bool(value)}

    def open_key_url(self, url: str):
        if not url:
            return {"ok": False}
        try:
            import webbrowser
            webbrowser.open(url)
            return {"ok": True}
        except Exception as e:
            logging.error(f"[api.parsing] open url: {e}")
            return {"ok": False}

    # ── Справка ──────────────────────────────────────────────────────────

    def get_parser_help(self, key: str):
        p = find_parser(key)
        if not p:
            return {"ok": False, "name": "", "help": "Парсер не найден"}
        return {
            "ok": True,
            "name": p["name"],
            "script": p["script"],
            "help": p["help"] or "Инструкция для этой сети пока не заполнена.",
            "outputs": p.get("outputs", []),
            "needs_key": p.get("needs_key", False),
        }

    # ── Запуск ───────────────────────────────────────────────────────────

    def _check_ready(self):
        out = self._parsing_output()
        if not out:
            self._emit("toast", {"type": "warning",
                                 "message": "Выберите папку сохранения результатов"})
            return None
        try:
            os.makedirs(out, exist_ok=True)
        except Exception as e:
            self._emit("toast", {"type": "error",
                                 "message": f"Папка недоступна: {e}"})
            return None
        if is_running():
            self._emit("toast", {"type": "warning",
                                 "message": "Парсер уже выполняется"})
            return None
        return out

    def continue_dobrocen_captcha(self):
        """
        Сигнал парсеру Доброцен, что капча в браузере решена вручную —
        по нажатию кнопки «▶ Продолжить (капча решена)».

        Скрипт не может использовать input()/консоль (собранное приложение
        оконное, console=False, sys.stdin недоступен) — вместо этого он
        ждёт файл-флаг в папке результатов текущего парсинга.
        """
        out = self._parsing_output()
        if not out or not os.path.isdir(out):
            self._emit("toast", {"type": "warning",
                                 "message": "Папка результатов не выбрана"})
            return {"ok": False}
        try:
            open(os.path.join(out, "dobrocen_continue.flag"), "w").close()
        except Exception as e:
            self._emit("toast", {"type": "error", "message": f"Не удалось: {e}"})
            return {"ok": False}
        return {"ok": True}

    def run_parser_one(self, data: dict):
        key = (data or {}).get("key", "")
        out = self._check_ready()
        if not out:
            return {"ok": False}

        self._stop_event.clear()

        def _worker():
            self._emit("parse_started", {"key": key})
            try:
                res = run_parser(out, key, self._log, self._stop_event,
                                 api_keys=self._api_keys())
            except Exception as e:
                logging.exception("[api.parsing] run_parser_one")
                res = {"ok": False, "msg": str(e), "outputs": []}
            self._emit("parse_done", {"key": key, **res})
            self._emit("toast", {
                "type": "success" if res["ok"] else "error",
                "message": ("Парсинг завершён" if res["ok"]
                            else f"Ошибка парсинга: {res['msg']}"),
            })
            self._emit("done")

        threading.Thread(target=_worker, daemon=True).start()
        return {"ok": True}

    def run_parser_batch(self, data: dict):
        keys = (data or {}).get("keys") or []
        if not keys:
            self._emit("toast", {"type": "warning",
                                 "message": "Не выбрано ни одной сети"})
            return {"ok": False}
        out = self._check_ready()
        if not out:
            return {"ok": False}

        self._stop_event.clear()

        def _worker():
            self._emit("parse_started", {"key": ",".join(keys)})
            res = run_many(out, keys, self._log, self._stop_event,
                           api_keys=self._api_keys())
            self._emit("parse_done", {"key": "", **res})
            self._emit("done")

        threading.Thread(target=_worker, daemon=True).start()
        return {"ok": True}

    # ── Результаты ───────────────────────────────────────────────────────

    def open_parsing_folder(self):
        out = self._parsing_output()
        if out and os.path.isdir(out):
            try:
                os.startfile(out)
                return {"ok": True}
            except Exception as e:
                logging.error(f"[api.parsing] open folder: {e}")
        self._emit("toast", {"type": "warning",
                             "message": "Папка результатов не выбрана или недоступна"})
        return {"ok": False}

    def open_parser_result(self, path: str):
        if path and os.path.isfile(path):
            try:
                os.startfile(path)
                return {"ok": True}
            except Exception as e:
                logging.error(f"[api.parsing] open file: {e}")
        self._emit("toast", {"type": "warning", "message": "Файл не найден"})
        return {"ok": False}

    # ── Обновления ───────────────────────────────────────────────────────

    def check_updates_manual(self):
        from updater.updater import get_update_info
        return get_update_info()

    def install_update_now(self):
        from updater.updater import install_now
        win = getattr(self, "_window", None)
        return install_now(on_exit=(lambda: win.destroy()) if win else None)
