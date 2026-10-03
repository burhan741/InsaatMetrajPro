# -*- mode: python ; coding: utf-8 -*-
# QuantixPro — PyInstaller Spec  (Rev-31, 2026-03-31)
# Tum Windows sistemlerinde calisan tek-dosya EXE

from PyInstaller.utils.hooks import collect_all, collect_submodules, collect_data_files

datas = [
    ('app', 'app'),
    ('assets', 'assets'),
    ('data', 'data'),
]
binaries = []

hiddenimports = [
    # --- PyQt6 ---
    'PyQt6', 'PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.QtWidgets',
    'PyQt6.QtOpenGLWidgets', 'PyQt6.QtOpenGL', 'PyQt6.sip',
    # --- Veri / Raporlama ---
    'pandas', 'pandas.core', 'pandas.io.formats.style',
    'openpyxl', 'openpyxl.styles', 'openpyxl.chart', 'openpyxl.drawing',
    'reportlab', 'reportlab.platypus', 'reportlab.pdfgen',
    'ezdxf', 'pdfplumber',
    'fitz', 'pymupdf',
    'cryptography', 'cryptography.hazmat.primitives.ciphers',
    'cryptography.hazmat.primitives.padding',
    'cryptography.hazmat.backends',
    'matplotlib', 'matplotlib.backends.backend_qt5agg',
    'matplotlib.backends.backend_agg',
    'numpy',
    'sqlite3',
    # --- Network / API ---
    'requests', 'requests.adapters', 'requests.auth',
    'urllib3', 'certifi', 'charset_normalizer', 'idna',
    'anthropic',
    'flask', 'flask_cors',
    # --- QR Kod ---
    'qrcode', 'qrcode.image.base', 'qrcode.image.pure', 'qrcode.image.pil',
    'PIL', 'PIL.Image', 'PIL.ImageDraw', 'PIL.ImageFont',
    # --- OpenGL (3D Gorsellik) ---
    'OpenGL', 'OpenGL.GL', 'OpenGL.GLU', 'OpenGL.platform',
    'OpenGL.platform.win32', 'OpenGL.arrays', 'OpenGL.arrays.ctypesarrays',
    'OpenGL.arrays.ctypesparameters', 'OpenGL.arrays.ctypespointers',
    'OpenGL.arrays.numpymodule', 'OpenGL.arrays.lists',
    'OpenGL.arrays.numbers', 'OpenGL.arrays.strings',
    'OpenGL.converters', 'OpenGL.error',
    # --- Win32 (AutoCAD Connector) ---
    'win32com', 'win32com.client', 'win32con', 'pywintypes',
    'pythoncom',
    # --- Stdlib (pkg_resources icin zorunlu) ---
    'email', 'email.mime', 'email.mime.text', 'email.mime.multipart',
    'email.mime.base', 'email.encoders', 'email.charset',
    'pkg_resources', 'setuptools',
    # --- Paketleme ---
    'packaging', 'packaging.version', 'packaging.requirements',
    # --- Core Engine Modulleri ---
    'app.core.database', 'app.core.calculator', 'app.core.calculator_minimal',
    'app.core.material_calculator',
    'app.core.cad_manager', 'app.core.room_3d_builder',
    'app.core.demir_engine', 'app.core.bi_engine',
    'app.core.enflasyon_engine', 'app.core.tedarikci_engine',
    'app.core.surdurulebilirlik_engine', 'app.core.gantt_engine',
    'app.core.qr_hakedis_engine', 'app.core.pert_engine',
    'app.core.beton_kurleme_engine', 'app.core.proje_sablonlari',
    'app.core.hava_durumu', 'app.core.autocad_connector',
    'app.core.fayans_hesaplama', 'app.core.sap_hesaplama',
    'app.core.parke_hesaplama', 'app.core.mantolama_hesaplama',
    'app.core.pvc_dograma_hesaplama', 'app.core.mermer_hesaplama',
    'app.core.birim_fiyat_analiz_engine', 'app.core.evm_engine',
    'app.core.fatura_engine', 'app.core.fiyat_farki_engine',
    'app.core.gecikme_ceza_engine', 'app.core.hakedis_kesinti_engine',
    'app.core.sgk_iscilik_engine', 'app.core.teklif_engine',
    'app.core.teminat_engine', 'app.core.yaklasik_maliyet_engine',
    'app.core.kaynak_dengeleme_engine',
    'app.core.claude_engine',
    # --- Rev-67~83 Yeni Core Modulleri ---
    'app.core.csb_poz_engine', 'app.core.pdf_metraj_engine',
    'app.core.bfa_engine', 'app.core.atasaman_engine',
    'app.core.santiye_gunluk_engine', 'app.core.nakit_akis_engine',
    'app.core.ince_isler_hizli_engine',
    # --- UI Modulleri ---
    'app.ui.main_window', 'app.ui.dialogs', 'app.ui.dialogs_minimal',
    'app.ui.startup_dialog', 'app.ui.taseron_window', 'app.ui.styles',
    'app.ui.ince_isler_3d_widget', 'app.ui.metraj_analiz_window',
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
    'app.ui.bugun_paneli', 'app.ui.sablon_sihirbazi',
    'app.ui.gecikme_ceza_window', 'app.ui.sgk_iscilik_window',
    'app.ui.birim_fiyat_analiz_window', 'app.ui.birim_fiyat_guncelle_dialog',
    'app.ui.fiyat_farki_window', 'app.ui.hakedis_kesinti_window',
    'app.ui.yaklasik_maliyet_window', 'app.ui.devlet_ihalesi_widget',
    'app.ui.fatura_window', 'app.ui.teklif_window', 'app.ui.teminat_window',
    'app.ui.saha_demiri_window', 'app.ui.asistan_pencere', 'app.ui.asistan_panel',
    'app.ui.demir_hesaplama_window',
    # --- Rev-67~83 Yeni UI Modulleri ---
    'app.ui.pdf_metraj_window', 'app.ui.bfa_window',
    'app.ui.atasaman_window', 'app.ui.santiye_gunluk_window',
    'app.ui.nakit_akis_window', 'app.ui.ince_isler_hizli_window',
    'app.ui.hakedis_window', 'app.ui.yaklasik_maliyet_window',
    # --- Utils ---
    'app.utils.data_loader', 'app.utils.export_manager',
    'app.utils.helpers', 'app.utils.pdf_importer', 'app.utils.excel_importer',
    'app.utils.data_loader_minimal', 'app.utils.font_utils',
    # --- Data ---
    'app.data.konut_is_kalemleri', 'app.data.malzeme_formulleri',
    'app.data.fire_oranlari', 'app.data.gantt_templates',
    'app.data.malzeme_renkleri',
]

# PyQt6 tum alt modulleri + DLL'leri
tmp_ret = collect_all('PyQt6')
datas += tmp_ret[0]
binaries += tmp_ret[1]
hiddenimports += tmp_ret[2]

# PyOpenGL + DLL'leri
tmp_ret = collect_all('OpenGL')
datas += tmp_ret[0]
binaries += tmp_ret[1]
hiddenimports += tmp_ret[2]

# numpy alt modulleri
hiddenimports += collect_submodules('numpy')

# matplotlib backends
hiddenimports += collect_submodules('matplotlib')
datas += collect_data_files('matplotlib')

# app paketinin TUM alt modulleri
hiddenimports += collect_submodules('app')

# reportlab data dosyalari (fontlar vb.)
datas += collect_data_files('reportlab')

# PyMuPDF (fitz) — DLL ve kaynak dosyalari
try:
    tmp_ret = collect_all('fitz')
    datas += tmp_ret[0]
    binaries += tmp_ret[1]
    hiddenimports += tmp_ret[2]
except Exception:
    pass  # PyMuPDF kurulu degilse atla

# certifi SSL sertifikalari (requests/anthropic icin)
datas += collect_data_files('certifi')


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['runtime_hook_db.py'],
    excludes=[
        'tkinter', 'test', 'unittest', 'http.server',
        'xmlrpc', 'pydoc', 'doctest', 'difflib',
        'calculator_BACKUP_1space',
    ],
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
    upx_exclude=['vcruntime140.dll', 'msvcp140.dll', 'Qt6Core.dll', 'Qt6Gui.dll', 'Qt6Widgets.dll'],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets\\quantix_icon.ico'],
    version_file=None,
)
