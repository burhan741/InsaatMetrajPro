# -*- coding: utf-8 -*-
"""Rev-134 devam (2026-09-07) — Kolon Beton/Kalıp: aktif kat + mükerrer
engelleme testi.

Kullanıcı senaryosu:
1) 12 kolonu aktif kat "Zemin"e oku (y=4.6) -> toplam 13.80 m3.
2) Aynı 12 kolonu TEKRAR oku -> toplam YİNE 13.80 (34.8 değil) —
   mükerrer engellendi (kat+kolon adı anahtarıyla).
3) Aktif katı "1.Kat" yap, aynı 12 kolonu oku -> toplam 27.60
   (iki kat ayrı ayrı biriktiği için).

Headless PyQt (offscreen). QDialog.exec() ve QMessageBox.* no-op.

Çalıştırma:
    $env:QT_QPA_PLATFORM="offscreen"
    & "e:\\İNŞAAT METRAJ PRO\\.venv\\Scripts\\python.exe" scratchpad\\test_kolon_beton_aktif_kat_mukerrer.py
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox

app = QApplication.instance() or QApplication([])

from app.ui.metraj_analiz_window import MetrajAnalizWindow
from app.core.autocad_connector import kolon_yazilarini_toplu_ayristir

QDialog.exec = lambda self: QDialog.DialogCode.Accepted
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.YesToAll)  # Rev-160 mükerrer sorusu
QMessageBox.information = staticmethod(lambda *a, **k: None)
QMessageBox.warning = staticmethod(lambda *a, **k: None)
QMessageBox.critical = staticmethod(lambda *a, **k: None)

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


class SahteConnector12x50:
    bagli = True

    def get_kolon_beton_yazidan(self, mesaj=""):
        metinler = [f"SZ{i:02d} (50/50)" for i in range(1, 13)]
        a = kolon_yazilarini_toplu_ayristir(metinler)
        return {
            "kolonlar": a["kolonlar"], "kirisler_atlanan": [], "tanimsizlar": [],
            "basarisizlar": [], "ilgisiz_sayisi": 0, "ozet": a["ozet"],
            "secim_sayisi": 12, "metin_sayisi": 12,
        }


def toplam_beton(win):
    return sum(v["beton"] for v in win.beton_kalip_kolon_kayitlari.values())


print("=" * 60)
print("AKTİF KAT KONTROLÜ — kat seçilmeden okuma reddedilmeli")
print("=" * 60)

win0 = MetrajAnalizWindow(db=None)
win0.acad_connector = SahteConnector12x50()
kontrol("Başlangıçta aktif_kat_adi boş", win0.aktif_kat_adi == "")
win0._beton_kalip_kolon_yazisindan_oku()
kontrol("Kat seçilmeden okuma yapılmadı (tablo hâlâ boş)", win0.beton_kalip_table.rowCount() == 0)
kontrol("Registry hâlâ boş", len(win0.beton_kalip_kolon_kayitlari) == 0)

print()
print("=" * 60)
print("SENARYO 1 — 12 kolonu 'Zemin' katına h=4.60 ile oku")
print("=" * 60)

win = MetrajAnalizWindow(db=None)
win.acad_connector = SahteConnector12x50()
win.kat_yuksekligi_spin.setValue(460)  # dialog varsayılanı 4.60 m'yi göstersin
win.aktif_kat_adi = "Zemin"

win._beton_kalip_kolon_yazisindan_oku()

tb1 = toplam_beton(win)
print(f"  Registry toplam beton (1. okuma sonrası): {tb1:.3f} m3 ({len(win.beton_kalip_kolon_kayitlari)} kayıt)")
kontrol("1. okuma sonrası registry'de 12 kayıt var", len(win.beton_kalip_kolon_kayitlari) == 12)
kontrol("1. okuma sonrası toplam beton = 13.80 m3", abs(tb1 - 13.80) < 1e-6)
kontrol("Tabloda 'Zemin' + 'Kolon' 1 satır var", win.beton_kalip_table.rowCount() == 1)
if win.beton_kalip_table.rowCount() == 1:
    kontrol("Satırın Kat hücresi = 'Zemin'", win.beton_kalip_table.item(0, 0).text() == "Zemin")
    kontrol("Satırın Adet hücresi = 12", win.beton_kalip_table.item(0, 2).text() == "12")
    kontrol("Satırın Net Beton hücresi = 13.800", win.beton_kalip_table.item(0, 6).text() == "13.8")
    kontrol("Satırın Kalıp hücresi = 110.400", win.beton_kalip_table.item(0, 9).text() == "110.4")

print()
print("=" * 60)
print("SENARYO 2 — AYNI 12 kolonu 'Zemin'e TEKRAR oku (mükerrer engelleme)")
print("=" * 60)

win._beton_kalip_kolon_yazisindan_oku()

tb2 = toplam_beton(win)
print(f"  Registry toplam beton (2. okuma sonrası): {tb2:.3f} m3 ({len(win.beton_kalip_kolon_kayitlari)} kayıt)")
kontrol("2. okuma sonrası registry HÂLÂ 12 kayıt (12000 veya 24 değil)", len(win.beton_kalip_kolon_kayitlari) == 12)
kontrol("2. okuma sonrası toplam beton YİNE 13.80 m3 (34.8 DEĞİL)", abs(tb2 - 13.80) < 1e-6)
kontrol("Tabloda HÂLÂ sadece 1 'Zemin'+'Kolon' satırı var (2 değil)", win.beton_kalip_table.rowCount() == 1)
if win.beton_kalip_table.rowCount() == 1:
    kontrol("Adet hâlâ 12 (24 değil)", win.beton_kalip_table.item(0, 2).text() == "12")

print()
print("=" * 60)
print("SENARYO 3 — Aktif kat '1.Kat' yapılıp AYNI 12 kolon okunuyor")
print("=" * 60)

win.aktif_kat_adi = "1.Kat"
win._beton_kalip_kolon_yazisindan_oku()

tb3 = toplam_beton(win)
print(f"  Registry toplam beton (3. okuma sonrası, 2 kat): {tb3:.3f} m3 ({len(win.beton_kalip_kolon_kayitlari)} kayıt)")
kontrol("3. okuma sonrası registry'de 24 kayıt var (12 Zemin + 12 1.Kat)", len(win.beton_kalip_kolon_kayitlari) == 24)
kontrol("3. okuma sonrası TOPLAM beton = 27.60 m3 (iki kat birikti)", abs(tb3 - 27.60) < 1e-6)
kontrol("Tabloda 2 satır var ('Zemin' + '1.Kat', ayrı ayrı)", win.beton_kalip_table.rowCount() == 2)

kat_isimleri = sorted(win.beton_kalip_table.item(r, 0).text() for r in range(win.beton_kalip_table.rowCount()))
kontrol("Satır kat isimleri ['1.Kat', 'Zemin']", kat_isimleri == ["1.Kat", "Zemin"])

for r in range(win.beton_kalip_table.rowCount()):
    kat = win.beton_kalip_table.item(r, 0).text()
    beton_h = win.beton_kalip_table.item(r, 6).text()
    kontrol(f"'{kat}' satırının Net Beton hücresi = 13.800", beton_h == "13.8")

print()
print("=" * 60)
print("MANUEL '+ EKLE' SATIRI DEDUP'TAN ETKİLENMEMELİ (regresyon)")
print("=" * 60)

win.bk_eleman_combo.setCurrentText("Kiriş")
win.bk_adet_spin.setValue(1)
win.bk_dim1_spin.setValue(0.30)
win.bk_dim2_spin.setValue(0.60)
win.bk_dim3_spin.setValue(4.60)
win._beton_kalip_kalem_ekle()

kontrol("Manuel ekleme sonrası tabloda 3 satır var (2 kolon-yazı + 1 manuel)",
        win.beton_kalip_table.rowCount() == 3)

# Aynı katı tekrar okuyunca manuel satır SİLİNMEMELİ
win.aktif_kat_adi = "Zemin"
win._beton_kalip_kolon_yazisindan_oku()
kontrol("Zemin'i tekrar okuduktan sonra hâlâ 3 satır var (manuel satır korundu)",
        win.beton_kalip_table.rowCount() == 3)

print()
print("=" * 60)
print(f"SONUÇ: {gecti} PASS, {kaldi} FAIL")
print("=" * 60)
sys.exit(1 if kaldi else 0)
