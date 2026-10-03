"""Radye temel kayıtları: hesap + Excel "Radye" sayfası (saf — PyQt/AutoCAD bağımsız).

Neyi çözüyoruz?
    Projede birden fazla radye parçası olabilir (bina + çekme kat bloğu,
    dilatasyonla ayrılmış radyeler). Her radyenin adı, NET alanı, kalınlığı
    (cm), dış çevresi ve adlı iç boşlukları (asansör/merdiven kuyusu) tutulur.
    Hesap tek kaynaktan: `radye_hesapla` (autocad_connector). Excel sayfasında
    beton/kalıp/toplamlar FORMÜL olarak yazılır — kullanıcı alan/kalınlığı
    elle düzeltirse sonuçlar da güncellenir.

Nasıl test ederiz?
    scratchpad/test_radye_ozet_excel.py: 250 m², 60 cm, dış çevre 70,
    boşluklar 9 + 6 -> beton 150.00, kalıp 51.00; aynı değerler kat özetinde
    ve Excel formüllerinin değerlendirilmiş sonucunda.
"""

from typing import Any, Dict, Iterable, List

try:
    from app.core.autocad_connector import radye_hesapla
except Exception:  # pragma: no cover - çekirdek yoksa modül kullanılamaz
    radye_hesapla = None

# Radye pratikte 30-250 cm; 25 cm altı büyük olasılıkla metre girilmiştir (0.60 gibi)
RADYE_KALINLIK_ALT_UYARI_CM = 25.0

RADYE_EXCEL_KOLONLAR = ["Radye adı", "Alan (m²)", "Kalınlık (cm)", "Beton (m³)",
                        "Dış çevre (m)", "İç boşluk çevreleri toplamı (m)", "Kalıp (m²)"]

RADYE_KABULLERI = [
    "Kalınlık santimetre (cm) girilir; hesapta 100'e bölünerek metreye çevrilir.",
    "Beton = Alan × Kalınlık. Alan, iç boşluklar düşülmüş NET alandır (AutoCAD AREA ile ölçülür).",
    "Kalıp = (Dış çevre + iç boşluk çevreleri toplamı) × Kalınlık. İç boşlukların (asansör/merdiven "
    "kuyusu) yan yüzleri de kalıplandığı için çevreleri kalıba EKLENİR; alt yüz grobetona oturur, kalıba girmez.",
    "Beton değerleri NET'tir (fire hariç).",
    "Beton, kalıp ve toplam hücreleri Excel formülüdür; alan, kalınlık veya çevre elle düzeltilirse "
    "sonuçlar kendiliğinden güncellenir.",
]


def _sayi(deger: Any) -> float:
    try:
        return float(str(deger).replace(",", ".")) if deger not in (None, "") else 0.0
    except (TypeError, ValueError):
        return 0.0


def radye_kaydi_hesapla(kayit: Dict[str, Any]) -> Dict[str, Any]:
    """Tek radye kaydı -> radye_hesapla sonucu (+ kalınlık cm uyarısı).

    kayit: {"ad", "alan_m2", "kalinlik_cm", "dis_cevre_m",
            "bosluklar": [{"ad", "cevre_m"}]}
    """
    if radye_hesapla is None:
        return {"hata": "Hesap modülü yüklenemedi", "uyari": "", "beton_m3": 0.0,
                "kalip_m2": 0.0, "dis_cevre_m": 0.0, "ic_cevre_m": 0.0, "toplam_cevre_m": 0.0}
    kal_cm = _sayi(kayit.get("kalinlik_cm"))
    cevreler = [_sayi(b.get("cevre_m")) for b in kayit.get("bosluklar", [])]
    h = radye_hesapla(_sayi(kayit.get("alan_m2")), kal_cm / 100.0,
                      _sayi(kayit.get("dis_cevre_m")), cevreler)
    # Çekirdeğin metre uyarısı cm girişinde anlamsız (300 cm = 3 m sınırı) -> cm diline çevir
    uyarilar = [u for u in h["uyari"].split("; ") if u and "cm girilmiş" not in u]
    if not h["hata"] and kal_cm < RADYE_KALINLIK_ALT_UYARI_CM:
        uyarilar.insert(0, f"Kalınlık {kal_cm:g} cm — çok ince, metre girilmiş olabilir (cm girin: 60 gibi)")
    if not h["hata"] and kal_cm > 300:
        uyarilar.insert(0, f"Kalınlık {kal_cm:g} cm — çok kalın, mm girilmiş olabilir")
    h["uyari"] = "; ".join(uyarilar)
    h["kalinlik_cm"] = kal_cm
    return h


def radye_toplamlari(kayitlar: Iterable[Dict[str, Any]]) -> Dict[str, float]:
    """Hatasız kayıtların alan/beton/çevre/kalıp toplamı (3 hane)."""
    t = {"adet": 0, "alan_m2": 0.0, "beton_m3": 0.0, "dis_cevre_m": 0.0, "ic_cevre_m": 0.0, "kalip_m2": 0.0}
    for k in kayitlar:
        h = radye_kaydi_hesapla(k)
        if h["hata"]:
            continue
        t["adet"] += 1
        t["alan_m2"] += h["alan_m2"]
        for alan in ("beton_m3", "dis_cevre_m", "ic_cevre_m", "kalip_m2"):
            t[alan] += h[alan]
    return {a: (round(v, 3) if isinstance(v, float) else v) for a, v in t.items()}


def _sum_formulu(sutun: str, satirlar: List[int]) -> str:
    # Alt satırlar (boşluklar) arada olduğu için ana satırlar tek tek listelenir
    return "=SUM(" + ",".join(f"{sutun}{r}" for r in satirlar) + ")" if satirlar else "=0"


def radye_sayfasi_yaz(ws, kayitlar: List[Dict[str, Any]], proje_adi: str, tarih_metni: str) -> Dict[str, Any]:
    """openpyxl çalışma sayfasına Radye metrajını yazar.

    Hatalı (alan/kalınlık 0) kayıtlar atlanır. Dönüş: {"baslik_satiri",
    "ana_satirlar", "toplam_satiri"} — test ve çağıran için konum bilgisi.
    """
    from openpyxl.styles import Border, Font, Side, Alignment

    ince = Side(style="thin")
    kenar = Border(left=ince, right=ince, top=ince, bottom=ince)
    kalin = Font(bold=True)

    ws.cell(row=1, column=1, value="RADYE TEMEL — BETON + KALIP METRAJI").font = Font(bold=True, size=12)
    ws.cell(row=2, column=1, value=f"Proje: {proje_adi or '—'}")
    ws.cell(row=3, column=1, value=f"Tarih: {tarih_metni}")
    ws.cell(row=4, column=1, value="Kabuller:").font = kalin
    satir = 5
    for metin in RADYE_KABULLERI:
        ws.cell(row=satir, column=1, value=f"• {metin}")
        satir += 1
    satir += 1

    baslik = satir
    for col, ad in enumerate(RADYE_EXCEL_KOLONLAR, start=1):
        c = ws.cell(row=baslik, column=col, value=ad)
        c.font = kalin
        c.border = kenar
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    satir = baslik + 1

    # Rev-166: beton (D) ve kalıp (G) tek ondalık görünür — hücredeki formül değeri tam kalır
    bicim = {2: "0.00", 3: "0.0", 4: "#,##0.0", 5: "0.00", 6: "0.00", 7: "#,##0.0"}
    alt_font = Font(italic=True, color="666666")
    ana_satirlar: List[int] = []
    for k in kayitlar:
        if radye_kaydi_hesapla(k)["hata"]:
            continue
        r = satir
        bosluklar = [b for b in k.get("bosluklar", []) if _sayi(b.get("cevre_m")) > 0]
        degerler = {
            1: k.get("ad") or "Radye",
            2: _sayi(k.get("alan_m2")),
            3: _sayi(k.get("kalinlik_cm")),
            4: f"=B{r}*C{r}/100",
            5: _sayi(k.get("dis_cevre_m")),
            6: f"=SUM(F{r + 1}:F{r + len(bosluklar)})" if bosluklar else 0,
            7: f"=(E{r}+F{r})*C{r}/100",
        }
        for col, deger in degerler.items():
            c = ws.cell(row=r, column=col, value=deger)
            c.border = kenar
            if col in bicim:
                c.number_format = bicim[col]
        for i, b in enumerate(bosluklar, start=1):
            a = ws.cell(row=r + i, column=1, value=f"    └ {b.get('ad') or f'Boşluk {i}'}")
            a.font = alt_font
            f = ws.cell(row=r + i, column=6, value=_sayi(b.get("cevre_m")))
            f.font = alt_font
            f.number_format = "0.00"
        ana_satirlar.append(r)
        satir = r + 1 + len(bosluklar)

    toplam = satir
    ws.cell(row=toplam, column=1, value="TOPLAM")
    for col, harf in ((2, "B"), (4, "D"), (5, "E"), (6, "F"), (7, "G")):
        c = ws.cell(row=toplam, column=col, value=_sum_formulu(harf, ana_satirlar))
        c.number_format = "#,##0.0" if harf in ("D", "G") else "0.00"
    for col in range(1, len(RADYE_EXCEL_KOLONLAR) + 1):
        c = ws.cell(row=toplam, column=col)
        c.font = kalin
        c.border = kenar

    for harf, gen in zip("ABCDEFG", (26, 12, 13, 12, 14, 18, 12)):
        ws.column_dimensions[harf].width = gen
    ws.row_dimensions[baslik].height = 32
    return {"baslik_satiri": baslik, "ana_satirlar": ana_satirlar, "toplam_satiri": toplam}
