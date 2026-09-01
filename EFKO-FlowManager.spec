# -*- mode: python ; coding: utf-8 -*-

import os
import importlib.util

# Абсолютный путь к папке проекта — SPEC это встроенная переменная PyInstaller
PROJECT_DIR = os.path.dirname(os.path.abspath(SPEC))

try:
    import pytz
    pytz_dir = os.path.join(os.path.dirname(pytz.__file__), 'zoneinfo')
except ImportError:
    pytz_dir = None

datas = [
    (os.path.join(PROJECT_DIR, 'web'),           'web'),
    (os.path.join(PROJECT_DIR, 'icon', 'ico.ico'), 'icon'),
    (os.path.join(PROJECT_DIR, 'config.json'),   '.'),
    (os.path.join(PROJECT_DIR, 'version.txt'),   '.'),
]

# Скрипты парсинга сетей + registry.json едут внутри сборки.
# Папка внутри exe обязана называться parsers — под этим именем её ищет
# services/parsing_runner.py (SCRIPTS_DIRNAME).
_parsing_dir = os.path.join(PROJECT_DIR, 'parsers')
if os.path.isdir(_parsing_dir):
    datas.append((_parsing_dir, 'parsers'))
else:
    print('[spec] ВНИМАНИЕ: папки parsers/ нет — вкладка парсинга будет пустой')

if pytz_dir and os.path.exists(pytz_dir):
    datas.append((pytz_dir, 'pytz/zoneinfo'))

# Библиотеки, нужные только парсерам (скрипты запускаются через runpy,
# PyInstaller не видит их импорты статически). Добавляем лишь те, что
# реально установлены, — иначе PyInstaller сыплет предупреждениями на
# пустом месте.
_optional = [
    'requests', 'urllib3', 'certifi', 'idna', 'charset_normalizer',
    'bs4', 'soupsieve', 'lxml', 'lxml.etree', 'lxml._elementpath',
    'html5lib', 'fake_useragent',
    'playwright', 'playwright.async_api', 'playwright.sync_api',
]
_parser_libs = []
for _mod in _optional:
    _root = _mod.split('.')[0]
    try:
        if importlib.util.find_spec(_root) is not None:
            _parser_libs.append(_mod)
    except (ImportError, ValueError):
        pass
print('[spec] библиотеки парсеров в сборке:', ', '.join(_parser_libs) or 'нет')

a = Analysis(
    [os.path.join(PROJECT_DIR, 'main.py')],
    pathex=[PROJECT_DIR],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'tkinter', 'tkinter.ttk', '_tkinter',
        'webview', 'webview.platforms.winforms', 'webview.platforms.edgechromium',
        'clr',
        'pythoncom', 'pywintypes',
        'win32com', 'win32com.client', 'win32com.client.gencache',
        'win32com.server', 'win32com.server.util',
        'win32api', 'win32con', 'win32process', 'win32timezone',
        'psutil',
        'polars', 'fastexcel',
        'pandas', 'pandas.core.arrays.masked',
        'numpy', 'numpy.core._multiarray_umath',
        'openpyxl', 'openpyxl.styles', 'openpyxl.styles.differential',
        'openpyxl.utils', 'openpyxl.workbook', 'openpyxl.worksheet',
        'et_xmlfile',
        'pytz', 'dateutil', 'dateutil.tz', 'dateutil.zoneinfo',
        # ── пакеты проекта (core/api/services/app/updater) ──
        'core', 'core.paths', 'core.logging', 'core.config',
        'app', 'app.splash', 'app.orphans', 'app.window',
        'api', 'api.core', 'api.promodate', 'api.competitors',
        'api.production', 'api.price', 'api.scheduler', 'api.oos',
        'api.parsing',
        'services', 'services.scheduler', 'services.promodate',
        'services.sku_matcher', 'services.competitors', 'services.nielsen',
        'services.production', 'services.price_comparison', 'services.oos',
        'services.oos_ketchup', 'services.parsing_runner',
        'updater', 'updater.updater',
        'runpy', 'contextlib', 'shutil', 'webbrowser', 'csv', 're',
        'pkg_resources', 'packaging', 'json', 'threading', 'subprocess', 'uuid',
    ] + _parser_libs,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'scipy', 'IPython', 'jupyter', 'PyQt5', 'PyQt6'],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    name='EFKO-FlowManager',
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon=os.path.join(PROJECT_DIR, 'icon', 'ico.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='EFKO-FlowManager',
)
