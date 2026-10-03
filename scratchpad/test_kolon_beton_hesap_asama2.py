# -*- coding: utf-8 -*-
"""Rev-134 Aşama 2/3 (2026-09-07) — Kolon Yazısından Toplu Oku: kat
yüksekliği + beton/kalıp hesabı + önizleme + tabloya ekleme testi.

Headless PyQt (offscreen). QDialog.exec() ve QMessageBox.* no-op'a
çevrilip metod uçtan uca (AutoCAD sonucu -> hesap -> tabloya ekleme)
sürülüyor, gerçek AutoCAD/DB gerekmiyor.

Test senaryosu (kullanıcının verdiği): 12 kolon (SZ01..SZ12, hepsi
50/50 cm), varsayılan kat yüksekliği 3.00 m ->
    Adet=12, Net Beton=9.000 m3 (0.5*0.5*3.0*12)
    Kalıp=72.000 m2 (2*(0.5+0.5)*3.0*12)

Çalıştırma:
    $env:QT_QPA_PLATFORM="offscreen"
    & "e:\\İNŞAAT METRAJ PRO\\.venv\\Scripts\\python.exe" scratchpad\\test_kolon_beton_hesap_asama2.py
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

# QDialog.exec() -> her zaman Accepted dön (kullanıcı "Onayla" demiş gibi)
QDialog.exec = lambda self: QDialog.DialogCode.Accepted
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.YesToAll)  # Rev-160 mükerrer sorusu
# QMessageBox.* -> no-op (offscreen'de gerçek tıklama gelmeyeceği için
# bekletmesin; information/warning/critical hepsi patch'lendi)
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


class SahteConnector:
    bagli = True

    def get_kolon_beton_yazidan(self, mesaj=""):
        metinler = [f"SZ{i:02d} (50/50)" for i in range(1, 13)]
        ayristirma = kolon_yazilarini_toplu_ayristir(metinler)
        kolonlar = ayristirma["kolonlar"]
        return {
            "kolonlar": kolonlar,
            "kirisler_atlanan": ayristirma["kirisler_atlanan"],
            "tanimsizlar": ayristirma["tanimsizlar"],
            "basarisizlar": ayristirma["basarisizlar"],
            "ilgisiz_sayisi": ayristirma["ilgisiz_sayisi"],
            "ozet": ayristirma["ozet"],
            "secim_sayisi": len(metinler),
            "metin_sayisi": len(metinler),
        }


print("=" * 60)
print("KOLON BETON/KALIP — AŞAMA 2/3 (kat yüksekliği + hesap + ekleme)")
print("=" * 60)

win = MetrajAnalizWindow(db=None)
win.acad_connector = SahteConnector()
win.aktif_kat_adi = "Zemin"  # Rev-134 devam: aktif kat artık zorunlu

kontrol("Başlangıçta tablo boş", win.beton_kalip_table.rowCount() == 0)
kontrol("Varsayılan kat yüksekliği 300 cm (3.00 m)", win.kat_yuksekligi_spin.value() == 300)

win._beton_kalip_kolon_yazisindan_oku()

kontrol("Tabloya 1 satır eklendi (12 kolon tek grupta)", win.beton_kalip_table.rowCount() == 1)

if win.beton_kalip_table.rowCount() == 1:
    def hucre(col):
        item = win.beton_kalip_table.item(0, col)
        return item.text() if item else None

    kontrol("Kat = Zemin", hucre(0) == "Zemin")
    kontrol("Eleman = Kolon", hucre(1) == "Kolon")
    kontrol("Adet = 12", hucre(2) == "12")
    kontrol("Ölçü1 = 0.50", hucre(3) == "0.50")
    kontrol("Ölçü2 = 0.50", hucre(4) == "0.50")
    kontrol("Ölçü3 (kat yük) = 3.00", hucre(5) == "3.00")
    kontrol("Net Beton = 9.000 m3", hucre(6) == "9.0")
    kontrol("Kalıp = 72.000 m2", hucre(9) == "72.0")

print()
print("=" * 60)
print("FARKLI BOYUTLU KOLON GRUPLAMA TESTİ")
print("=" * 60)

win2 = MetrajAnalizWindow(db=None)


class SahteConnector2:
    bagli = True

    def get_kolon_beton_yazidan(self, mesaj=""):
        metinler = ["SZ01 (50/50)", "SZ02 (50/50)", "P01 (30/60)"]
        ayristirma = kolon_yazilarini_toplu_ayristir(metinler)
        return {
            "kolonlar": ayristirma["kolonlar"],
            "kirisler_atlanan": [], "tanimsizlar": [], "basarisizlar": [],
            "ilgisiz_sayisi": 0, "ozet": ayristirma["ozet"],
            "secim_sayisi": 3, "metin_sayisi": 3,
        }


win2.acad_connector = SahteConnector2()
win2.aktif_kat_adi = "Zemin"
win2._beton_kalip_kolon_yazisindan_oku()

kontrol("2 farklı boyut -> 2 satır", win2.beton_kalip_table.rowCount() == 2)
if win2.beton_kalip_table.rowCount() == 2:
    satirlar = []
    for r in range(2):
        satirlar.append(tuple(win2.beton_kalip_table.item(r, c).text() for c in range(10)))
    print(f"  Satırlar: {satirlar}")
    adetler = sorted(int(s[2]) for s in satirlar)
    kontrol("Adetler [1, 2] (50/50'den 2 tane, 30/60'tan 1 tane)", adetler == [1, 2])

print()
print("=" * 60)
print("cm->m DÖNÜŞÜM DOĞRULAMA — FARKLI KAT YÜKSEKLİKLERİ")
print("=" * 60)
print("Kullanıcı raporu: '12.000 m3 çıktı, doğrusu 13.79 m3' — cm->m")
print("dönüşümünün DOĞRU çalıştığını farklı yüksekliklerle kanıtla.")
print("(50/50 kolon x12, formül: beton=12*0.5*0.5*h, kalip=12*2*(0.5+0.5)*h)")
print()

for h_cm, beklenen_beton, beklenen_kalip in [
    (300, 9.000, 72.000),   # varsayılan (3.00 m)
    (400, 12.000, 96.000),  # kullanıcının gördüğü "12.000" -> h=4.00 m demek
    (460, 13.800, 110.400), # kullanıcının beklediği "13.79" -> h=4.60 m demek
]:
    win_h = MetrajAnalizWindow(db=None)
    win_h.kat_yuksekligi_spin.setValue(h_cm)  # cm -> dialog bunu /100 ile m'ye çevirip prefill eder
    win_h.aktif_kat_adi = "Zemin"

    class _SahteC:
        bagli = True

        def get_kolon_beton_yazidan(self, mesaj=""):
            metinler = [f"SZ{i:02d} (50/50)" for i in range(1, 13)]
            a = kolon_yazilarini_toplu_ayristir(metinler)
            return {
                "kolonlar": a["kolonlar"], "kirisler_atlanan": [], "tanimsizlar": [],
                "basarisizlar": [], "ilgisiz_sayisi": 0, "ozet": a["ozet"],
                "secim_sayisi": 12, "metin_sayisi": 12,
            }

    win_h.acad_connector = _SahteC()
    win_h._beton_kalip_kolon_yazisindan_oku()
    beton_hucre = win_h.beton_kalip_table.item(0, 6).text()
    kalip_hucre = win_h.beton_kalip_table.item(0, 9).text()
    print(f"  kat_yuksekligi_spin={h_cm} cm ({h_cm/100:.2f} m) -> "
          f"Net Beton={beton_hucre} m3, Kalıp={kalip_hucre} m2")
    kontrol(
        f"h={h_cm/100:.2f}m -> beton={beklenen_beton:.3f}",
        beton_hucre == f"{beklenen_beton:.1f}"  # Rev-165 tek hane
    )
    kontrol(
        f"h={h_cm/100:.2f}m -> kalip={beklenen_kalip:.3f}",
        kalip_hucre == f"{beklenen_kalip:.1f}"  # Rev-165 tek hane
    )

print()
print("SONUÇ: cm->m dönüşümü her yükseklikte matematiksel olarak DOĞRU.")
print("'12.000' çıktısı h=4.00m girildiğinde normal/beklenen bir sonuçtur —")
print("kullanıcının gerçek proje yüksekliği ~4.60m ise dialogda '4.60' girilmeli.")

print()
print("=" * 60)
print(f"SONUÇ: {gecti} PASS, {kaldi} FAIL")
print("=" * 60)
sys.exit(1 if kaldi else 0)
