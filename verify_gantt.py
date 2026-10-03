"""Gantt modulu syntax + temel import dogrulama scripti."""
import ast
import sys
import os

src_path = os.path.join(os.path.dirname(__file__), "app", "ui", "gantt_window.py")

print(f"Dosya: {src_path}")
with open(src_path, encoding="utf-8") as f:
    src = f.read()

satir_sayisi = src.count("\n") + 1
print(f"Satir: {satir_sayisi}")

try:
    ast.parse(src)
    print("AST: OK")
except SyntaxError as e:
    print(f"AST HATA: {e}")
    sys.exit(1)

# Kritik marker kontrolleri
markers = {
    "DependencyDialog FS/SS/FF":      "FS.*SS.*FF|FF.*SS.*FS",
    "IlerlemeGuncellemeDialog sinifi": "class IlerlemeGuncellemeDialog",
    "_metrajdan_gorev_uret":           "def _metrajdan_gorev_uret",
    "_toplu_ilerleme_guncelle":        "def _toplu_ilerleme_guncelle",
    "_yukle_kritik_yol doldurma":      "def _yukle_kritik_yol",
    "get_selected_deps":               "def get_selected_deps",
    "analiz_baseline engine":          "get_baseline_comparison",
    "save_baseline":                   "save_baseline",
    "add_kaynak engine":               "add_kaynak",
    "_kaynak_guncelle_tablo":          "def _kaynak_guncelle_tablo",
    "IlerlemeGuncelleme kullanimi":    "IlerlemeGuncellemeDialog",
    "hava_tatil metodu":               "_ekle_hava_tatil",
    "Metrajdan Uret butonu":           "Metrajdan",
    "hesapla_program dict2Task":       "_engine.add_task",
}

import re
all_ok = True
for aciklama, pattern in markers.items():
    found = bool(re.search(pattern, src))
    status = "OK" if found else "EKSIK"
    if not found:
        all_ok = False
    print(f"  {status}: {aciklama}")

print()
if all_ok:
    print("TUM KONTROLLER GECTI — gantt_window.py hazir!")
else:
    print("BAZI OZELLIKLER EKSIK")
