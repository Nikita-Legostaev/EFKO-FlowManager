"""app/orphans.py — чистка зависших процессов до старта окна."""

import os
import logging
import threading


def _has_visible_window(pid: int) -> bool:
    """
    Есть ли у процесса хоть одно видимое окно верхнего уровня.

    Раньше здесь был FindWindowA(b'XLMAIN', None) — он ищет ПЕРВОЕ окно
    Excel во всей системе и никак не связан с конкретным процессом. То
    есть если у одного (любого) экземпляра Excel окно оказывалось
    скрытым, приложение убивало ВСЕ excel.exe разом — вместе с открытыми
    у человека книгами и несохранёнными правками. Здесь окна
    сопоставляются с PID явно.
    """
    try:
        import ctypes
        from ctypes import wintypes
    except Exception:
        return True  # не Windows — считаем, что окно есть, и не трогаем процесс

    try:
        user32 = ctypes.windll.user32
        visible = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def _on_window(hwnd, _lparam):
            wnd_pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wnd_pid))
            if wnd_pid.value == pid and user32.IsWindowVisible(hwnd):
                visible.append(hwnd)
                return False  # нашли — дальше можно не искать
            return True

        user32.EnumWindows(_on_window, 0)
        return bool(visible)
    except Exception:
        # Не смогли проверить — считаем, что окно есть: лучше оставить
        # лишний процесс, чем убить чужую работу.
        return True


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

                # Excel без единого видимого окна — зависший от COM-автоматизации.
                # У книги, открытой человеком, окно есть, её не трогаем.
                elif name == 'excel.exe' and not _has_visible_window(pid):
                    proc.kill()
                    killed.append(f"EXCEL.EXE без окон (PID {pid})")

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
