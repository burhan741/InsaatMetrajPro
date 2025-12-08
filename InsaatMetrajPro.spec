# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('app', 'app'), ('assets', 'assets'), ('data', 'data')]
binaries = []
hiddenimports = ['PyQt6', 'PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.QtWidgets', 'pandas', 'openpyxl', 'reportlab', 'ezdxf', 'sqlite3', 'pdfplumber', 'matplotlib', 'app.core.database', 'app.core.calculator', 'app.core.material_calculator', 'app.core.dxf_engine', 'app.core.cad_manager', 'app.ui.main_window', 'app.ui.dialogs', 'app.ui.startup_dialog', 'app.ui.taseron_window', 'app.ui.styles', 'app.utils.data_loader', 'app.utils.export_manager', 'app.utils.helpers', 'app.utils.pdf_importer', 'app.data.konut_is_kalemleri', 'app.data.malzeme_formulleri', 'app.data.fire_oranlari']
tmp_ret = collect_all('PyQt6')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='InsaatMetrajPro',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets\\app_icon.ico'],
)
