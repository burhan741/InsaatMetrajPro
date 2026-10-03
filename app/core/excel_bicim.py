"""Excel çıktılarında beton / kalıp sütunlarına TEK ONDALIK sayı biçimi (Rev-166).

Neyi çözüyoruz?
    Ekranda beton/kalıp tek haneyle gösteriliyor (Rev-165); Excel çıktısında da aynı
    görünüm isteniyor. Değeri yuvarlamak yerine hücreye "#,##0.0" biçimi verilir:
    Excel ekranda tek hane gösterir (yarım yukarı), ama hücredeki sayı TAM kalır —
    kullanıcının Excel'de yapacağı SUM / formüller yuvarlanmış değerden hesaplanmaz.

Nasıl test ederiz?
    scratchpad/test_excel_tek_hane.py — başlık satırı otomatik bulunur (en az 2 beton/
    kalıp başlığı olan ilk satır), sadece sayısal hücreler biçimlenir; "Beton Yüksekliği",
    "Fire", alan / uzunluk sütunları dokunulmaz.
"""
from typing import Any, List

TEK_HANE_BICIMI = "#,##0.0"
_ANAHTAR = ("beton", "kalıp", "kalip", "sipariş", "siparis")
_HARIC = ("yük", "yuk", "fire", "esas", "kalınlık", "kalinlik")   # "Beton Yük. (m)" yüksekliktir


def _beton_kalip_basligi_mi(deger: Any) -> bool:
    if not isinstance(deger, str):
        return False
    m = deger.lower()
    return any(a in m for a in _ANAHTAR) and not any(h in m for h in _HARIC)


def beton_kalip_sutunlari_tek_hane(ws, ara_satir: int = 40) -> List[int]:
    """Sayfadaki tablo başlığını bulur ve beton/kalıp/sipariş sütunlarının sayısal
    hücrelerine tek ondalık biçim verir. Dönüş: biçimlenen sütun numaraları (1 tabanlı)."""
    baslik_satiri, sutunlar = None, []
    for r in range(1, min(ws.max_row, ara_satir) + 1):
        bulunan = [c.column for c in ws[r] if _beton_kalip_basligi_mi(c.value)]
        if len(bulunan) >= 2:
            baslik_satiri, sutunlar = r, bulunan
            break
    if baslik_satiri is None:
        return []
    for r in range(baslik_satiri + 1, ws.max_row + 1):
        for col in sutunlar:
            c = ws.cell(row=r, column=col)
            if isinstance(c.value, (int, float)) and not isinstance(c.value, bool):
                c.number_format = TEK_HANE_BICIMI
    return sutunlar
