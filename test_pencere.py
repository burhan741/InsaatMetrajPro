import sys
sys.path.insert(0, r"E:\İNŞAAT METRAJ PRO\yeni_proje")

try:
    from app.ui.asistan_pencere import AsistanPencere
    print("AsistanPencere import OK")
except Exception as e:
    print(f"HATA: {e}")
    import traceback; traceback.print_exc()

# main_window değişikliklerini doğrula
try:
    import ast
    with open(r"E:\İNŞAAT METRAJ PRO\yeni_proje\app\ui\main_window.py", encoding="utf-8") as f:
        src = f.read()
    ast.parse(src)
    print("main_window AST OK")
    # Kritik değişiklikler var mı kontrol
    assert "_asistan_pencere" in src, "_asistan_pencere referansı yok!"
    assert "_asistan_ac" in src, "_asistan_ac metodu yok!"
    assert "AI Danışmanı" in src or "AI Dani" in src, "AI menüsü yok!"
    print("main_window değişiklikler doğrulandı")
except Exception as e:
    print(f"main_window HATA: {e}")
