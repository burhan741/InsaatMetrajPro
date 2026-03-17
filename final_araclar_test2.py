import sys, os, ast

os.chdir(r"E:\İNŞAAT METRAJ PRO\yeni_proje")
sys.path.insert(0, r"E:\İNŞAAT METRAJ PRO\yeni_proje")

results = []

# 1. AST CHECK
for fpath in [
    r"E:\İNŞAAT METRAJ PRO\yeni_proje\app\core\mermer_hesaplama.py",
    r"E:\İNŞAAT METRAJ PRO\yeni_proje\app\core\pvc_dograma_hesaplama.py",
]:
    try:
        src = open(fpath, encoding='utf-8').read()
        ast.parse(src)
        results.append(f"AST_OK: {os.path.basename(fpath)}")
    except SyntaxError as e:
        results.append(f"AST_ERR: {os.path.basename(fpath)} — {e}")

# 2. IMPORT TEST
modules = [
    'app.ui.demir_hesaplama_window',
    'app.ui.saha_demiri_window',
    'app.ui.boya_maliyet_window',
    'app.ui.sap_maliyet_window',
    'app.ui.parke_maliyet_window',
    'app.ui.mantolama_dialog',
    'app.ui.mermer_dialog',
    'app.ui.pvc_dograma_dialog',
    'app.ui.mobilya_maliyet_window',
    'app.ui.yalitim_maliyet_window',
    'app.ui.vitrifiye_maliyet_window',
    'app.ui.duvar_maliyet_window',
    'app.ui.alci_maliyet_window',
    'app.ui.kara_siva_window',
    'app.ui.fayans_hesaplama_window',
    'app.ui.elektrik_maliyet_window',
    'app.ui.kaba_yapi_maliyet_window',
]

for m in modules:
    try:
        __import__(m)
        results.append(f'OK: {m}')
    except Exception as e:
        results.append(f'FAIL: {m} — {type(e).__name__}: {str(e)[:100]}')

output = '\n'.join(results)
with open(r"E:\İNŞAAT METRAJ PRO\yeni_proje\final_araclar_test2.txt", 'w', encoding='utf-8') as f:
    f.write(output)
