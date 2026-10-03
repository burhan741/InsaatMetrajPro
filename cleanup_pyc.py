import os, glob

targets = [
    r"E:\İNŞAAT METRAJ PRO\yeni_proje\app\core\__pycache__\claude_engine.cpython-311.pyc",
    r"E:\İNŞAAT METRAJ PRO\yeni_proje\app\ui\__pycache__\asistan_panel.cpython-311.pyc",
]

results = []
for path in targets:
    if os.path.exists(path):
        os.remove(path)
        results.append(f"Silindi: {os.path.basename(path)}")
    else:
        results.append(f"Yok (atlandı): {os.path.basename(path)}")

output = "\n".join(results)
print(output)
with open(r"E:\İNŞAAT METRAJ PRO\yeni_proje\cleanup_result.txt", "w", encoding="utf-8") as fp:
    fp.write(output + "\n")
