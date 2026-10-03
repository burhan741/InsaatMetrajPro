import py_compile, os

f = r"E:\İNŞAAT METRAJ PRO\yeni_proje\app\ui\main_window.py"
try:
    py_compile.compile(f, doraise=True)
    result = "OK: main_window.py"
except py_compile.PyCompileError as e:
    result = f"HATA: main_window.py -> {e}"

print(result)
with open(r"E:\İNŞAAT METRAJ PRO\yeni_proje\main_check_result.txt", "w", encoding="utf-8") as fp:
    fp.write(result + "\n")
