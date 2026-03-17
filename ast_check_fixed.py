import ast, sys

files = [
    r"E:\İNŞAAT METRAJ PRO\yeni_proje\app\core\mermer_hesaplama.py",
    r"E:\İNŞAAT METRAJ PRO\yeni_proje\app\core\pvc_dograma_hesaplama.py",
]

for f in files:
    try:
        src = open(f, encoding='utf-8').read()
        ast.parse(src)
        print(f"AST OK: {f}")
    except SyntaxError as e:
        print(f"AST ERROR: {f} — {e}")
