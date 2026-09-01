"""app/orphans.py — чистка зависших процессов до старта окна."""

import os
import logging
import threading


def _cleanup_orphans():
    """Убивает только невидимый Excel и другие экземпляры нашего приложения."""
    try:
        import psutil
    except ImportError:
        return  # psutil не установлен — пропускаем

    current_pid = os.getpid()
    killed = []

    try:
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                pid = proc.info['pid']
                name = (proc.info['name'] or '').lower()

                if pid == current_pid:
                    continue

                # Другой экземпляр нашего приложения
                if 'efko-flowmanager' in name:
                    proc.kill()
                    killed.append(f"EFKO-FlowManager (PID {pid})")

                # Невидимый Excel — зависший от COM автоматизации
                elif name == 'excel.exe':
                    try:
                        import ctypes as _ct
                        hwnd = _ct.windll.user32.FindWindowA(b'XLMAIN', None)
                        if hwnd and not _ct.windll.user32.IsWindowVisible(hwnd):
                            proc.kill()
                            killed.append(f"EXCEL.EXE невидимый (PID {pid})")
                    except Exception:
                        pass

            except Exception:
                continue
    except Exception:
        pass

    if killed:
        logging.info(f"Очищены зависшие процессы: {', '.join(killed)}")


def cleanup_orphans_bg():
    """Обход списка процессов через psutil — не держим им старт окна."""
    def _run():
        try:
            _cleanup_orphans()
        except Exception:
            pass

    threading.Thread(target=_run, daemon=True).start()
