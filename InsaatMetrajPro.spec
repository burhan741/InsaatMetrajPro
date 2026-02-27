# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_submodules

datas = [('app', 'app'), ('assets', 'assets'), ('data', 'data')]
binaries = []
hiddenimports = [
    # PyQt6
    'PyQt6', 'PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.QtWidgets',
    'PyQt6.QtOpenGLWidgets', 'PyQt6.QtOpenGL',
    # Veri / Raporlama
    'pandas', 'openpyxl', 'reportlab', 'ezdxf', 'sqlite3',
    'pdfplumber', 'matplotlib', 'numpy',
    # OpenGL (3D Gorsellestirme)
    'OpenGL', 'OpenGL.GL', 'OpenGL.GLU', 'OpenGL.platform',
    'OpenGL.platform.win32', 'OpenGL.arrays', 'OpenGL.arrays.ctypesarrays',
    'OpenGL.arrays.ctypesparameters', 'OpenGL.arrays.ctypespointers',
    'OpenGL.arrays.numpymodule', 'OpenGL.arrays.lists',
    'OpenGL.arrays.numbers', 'OpenGL.arrays.strings',
    'OpenGL.converters', 'OpenGL.error',
    # Core Engine Modulleri
    'app.core.database', 'app.core.calculator',
    'app.core.material_calculator', 'app.core.dxf_engine',
    'app.core.cad_manager', 'app.core.room_3d_builder',
    'app.core.demir_engine', 'app.core.bi_engine',
    'app.core.enflasyon_engine', 'app.core.tedarikci_engine',
    'app.core.surdurulebilirlik_engine', 'app.core.gantt_engine',
    'app.core.qr_hakedis_engine',
    'app.core.fayans_hesaplama', 'app.core.sap_hesaplama',
    'app.core.parke_hesaplama', 'app.core.mantolama_hesaplama',
    'app.core.pvc_dograma_hesaplama', 'app.core.mermer_hesaplama',
    # UI Modulleri
    'app.ui.main_window', 'app.ui.dialogs', 'app.ui.startup_dialog',
    'app.ui.taseron_window', 'app.ui.styles',
    'app.ui.ince_isler_3d_widget', 'app.ui.metraj_analiz_window',
    'app.ui.oda_isimleri_window',
    'app.ui.hakedis_window', 'app.ui.is_takip_window',
    'app.ui.gantt_window', 'app.ui.bi_dashboard_window',
    'app.ui.enflasyon_window', 'app.ui.tedarikci_window',
    'app.ui.surdurulebilirlik_window', 'app.ui.qr_hakedis_window',
    'app.ui.puantaj_server_window', 'app.ui.puantaj_rapor_window',
    'app.ui.duvar_maliyet_window', 'app.ui.alci_maliyet_window',
    'app.ui.kara_siva_window', 'app.ui.boya_maliyet_window',
    'app.ui.fayans_hesaplama_window', 'app.ui.sap_maliyet_window',
    'app.ui.parke_maliyet_window', 'app.ui.mantolama_dialog',
    'app.ui.mermer_dialog', 'app.ui.pvc_dograma_dialog',
    'app.ui.mobilya_maliyet_window', 'app.ui.yalitim_maliyet_window',
    'app.ui.elektrik_maliyet_window', 'app.ui.vitrifiye_maliyet_window',
    'app.ui.kaba_yapi_maliyet_window', 'app.ui.metal_isleri_maliyet_window',
    # Utils
    'app.utils.data_loader', 'app.utils.export_manager',
    'app.utils.helpers', 'app.utils.pdf_importer', 'app.utils.excel_importer',
    # Data
    'app.data.konut_is_kalemleri', 'app.data.malzeme_formulleri',
    'app.data.fire_oranlari', 'app.data.gantt_templates',
    'app.data.malzeme_renkleri',
]

# PyQt6 tum alt modulleri
tmp_ret = collect_all('PyQt6')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# PyOpenGL tum alt modulleri ve DLL'leri
tmp_ret = collect_all('OpenGL')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# numpy alt modulleri
hiddenimports += collect_submodules('numpy')


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
    name='QuantixPro',
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
