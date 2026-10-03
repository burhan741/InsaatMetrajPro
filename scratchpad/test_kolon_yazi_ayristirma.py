# -*- coding: utf-8 -*-
"""Rev-134 devam (2026-09-07) — Parantezli kolon yazı regex düzeltmesi testi.

Doğrulanmış gerçek format: "SZ12 (50/50)" — isim (S/P ile başlar) +
boşluk + parantez içinde en/boy. Boyut HER ZAMAN parantez içinde.

Nasıl çalıştırılır:
    & "e:\\İNŞAAT METRAJ PRO\\.venv\\Scripts\\python.exe" scratchpad\\test_kolon_yazi_ayristirma.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.autocad_connector import (
    kolon_yazisini_ayristir,
    kolon_yazilarini_toplu_ayristir,
)

gecti = 0
kaldi = 0


def kontrol(ad, kosul):
    global gecti, kaldi
    if kosul:
        gecti += 1
        print(f"  PASS: {ad}")
    else:
        kaldi += 1
        print(f"  FAIL: {ad}")


print("=" * 60)
print("TEK METİN TESTLERİ")
print("=" * 60)

r = kolon_yazisini_ayristir("SZ12 (50/50)")
kontrol("SZ12 (50/50) -> basarili", r["basarili"])
kontrol("SZ12 (50/50) -> ad=SZ12", r["ad"] == "SZ12")
kontrol("SZ12 (50/50) -> tip=kolon", r["tip"] == "kolon")
kontrol("SZ12 (50/50) -> en_m=0.50", r["en_m"] == 0.50)
kontrol("SZ12 (50/50) -> boy_m=0.50", r["boy_m"] == 0.50)

r = kolon_yazisini_ayristir("P129 (30/180)")
kontrol("P129 (30/180) -> basarili", r["basarili"])
kontrol("P129 (30/180) -> tip=kolon", r["tip"] == "kolon")
kontrol("P129 (30/180) -> en_cm=30, boy_cm=180", r["en_cm"] == 30 and r["boy_cm"] == 180)

r = kolon_yazisini_ayristir("KB110 (40/80)")
kontrol("KB110 (40/80) -> basarili", r["basarili"])
kontrol("KB110 (40/80) -> tip=kiris", r["tip"] == "kiris")

r = kolon_yazisini_ayristir("birsey")
kontrol("birsey -> basarisiz", not r["basarili"])
kontrol("birsey -> ilgisiz=True", r["ilgisiz"] is True)

r = kolon_yazisini_ayristir("3Ø12")
kontrol("3Ø12 -> basarisiz", not r["basarili"])
kontrol("3Ø12 -> ilgisiz=True", r["ilgisiz"] is True)

r = kolon_yazisini_ayristir("(50/50)")
kontrol("(50/50) isimsiz -> basarili", r["basarili"])
kontrol("(50/50) isimsiz -> ad=None", r["ad"] is None)
kontrol("(50/50) isimsiz -> tip=tanimsiz", r["tip"] == "tanimsiz")
kontrol("(50/50) isimsiz -> ilgisiz=False", r["ilgisiz"] is False)

# Eski (parantezsiz) format artık YAKALANMAMALI (ilgisiz sayılmalı)
r = kolon_yazisini_ayristir("SZ07 50/50")
kontrol("SZ07 50/50 (parantezsiz, ESKİ FORMAT) -> ilgisiz=True", r["ilgisiz"] is True)

print()
print("=" * 60)
print("KULLANICI SENARYOSU — TOPLU AYRIŞTIRMA")
print("=" * 60)

metinler = [
    "SZ12 (50/50)",
    "P129 (30/180)",
    "SZ07 (40/60)",
    "KB110 (40/80)",
    "birsey",
    "3Ø12",
]
sonuc = kolon_yazilarini_toplu_ayristir(metinler)

print(f"  Kolonlar: {[k['ad'] for k in sonuc['kolonlar']]}")
print(f"  Kirişler (atlanan): {[k['ad'] for k in sonuc['kirisler_atlanan']]}")
print(f"  Tanımsızlar: {len(sonuc['tanimsizlar'])}")
print(f"  Başarısızlar: {len(sonuc['basarisizlar'])}")
print(f"  İlgisiz (sessizce atlanan): {sonuc['ilgisiz_sayisi']}")
print(f"  Özet: {sonuc['ozet']}")

kontrol("3 kolon bulundu", len(sonuc["kolonlar"]) == 3)
kontrol("kolon isimleri doğru", {k["ad"] for k in sonuc["kolonlar"]} == {"SZ12", "P129", "SZ07"})
kontrol("1 kiriş atlandı (KB110)", len(sonuc["kirisler_atlanan"]) == 1 and sonuc["kirisler_atlanan"][0]["ad"] == "KB110")
kontrol("0 tanımsız", len(sonuc["tanimsizlar"]) == 0)
kontrol("0 başarısız (ilgisiz metinler basarisizlar'a girmiyor)", len(sonuc["basarisizlar"]) == 0)
kontrol("2 ilgisiz sessizce atlandı (birsey, 3Ø12)", sonuc["ilgisiz_sayisi"] == 2)

print()
print("=" * 60)
print("BÜYÜK ÖLÇEK — 1023 SEÇİM SİMÜLASYONU (çoğu ilgisiz)")
print("=" * 60)
buyuk_liste = ["3Ø12", "çizgi", "12", "L=350"] * 250 + [
    "SZ01 (40/40)", "SZ02 (40/40)", "P01 (30/60)",
]
sonuc2 = kolon_yazilarini_toplu_ayristir(buyuk_liste)
kontrol("1000 ilgisiz metin sessizce atlandı", sonuc2["ilgisiz_sayisi"] == 1000)
kontrol("3 gerçek kolon doğru bulundu", len(sonuc2["kolonlar"]) == 3)
kontrol("0 başarısız (gürültü basarisizlar'a hiç girmedi)", len(sonuc2["basarisizlar"]) == 0)

print()
print("=" * 60)
print(f"SONUÇ: {gecti} PASS, {kaldi} FAIL")
print("=" * 60)
sys.exit(1 if kaldi else 0)
