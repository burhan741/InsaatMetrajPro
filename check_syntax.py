import py_compile, sys, os

files = [
    r"E:\İNŞAAT METRAJ PRO\yeni_proje\app\core\claude_engine.py",
    r"E:\İNŞAAT METRAJ PRO\yeni_proje\app\ui\asistan_panel.py",
]

results = []
for f in files:
    try:
        py_compile.compile(f, doraise=True)
        results.append(f"OK: {os.path.basename(f)}")
    except py_compile.PyCompileError as e:
        results.append(f"HATA: {os.path.basename(f)} -> {e}")

output = "\n".join(results)
print(output)
with open(r"E:\İNŞAAT METRAJ PRO\yeni_proje\syntax_check_result.txt", "w", encoding="utf-8") as fp:
    fp.write(output + "\n")
