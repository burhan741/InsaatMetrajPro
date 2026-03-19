"""
Betonarme Proje Metraj Doldurma Scripti
========================================
Aktif projeye 30 kalem + Gantt görevleri ekler.
CŞB birim fiyat verimliliklerine göre süreler otomatik hesaplanır.

Kullanım:
    python doldur_metraj.py           -> Proje listesi gösterir, seçim ister
    python doldur_metraj.py --proje 1 -> ID=1 projeye ekle
    python doldur_metraj.py --liste   -> Sadece proje listesi
"""
import sys
import json
import math
import os
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import DatabaseManager

# ============================================================
# 30 KALEM TANIMI
# Format: (poz_no, tanim, birim, miktar, birim_fiyat, kategori)
# ============================================================
KALEMLER = [
    # ── 1. HAFRİYAT ve TEMEL ALT YAPI ──────────────────────
    ("01.001", "Hafriyat kazisi (1. grup zemin)",        "m3",    450,      95.00,    "hafriyat"),
    ("01.002", "Hafriyat nakli (piste)",                  "m3",    450,      45.00,    "hafriyat"),
    ("01.003", "Geri dolgu ve sikistirma",                "m3",    150,      55.00,    "hafriyat"),
    ("01.004", "Sap beton / grobeton (C16)",              "m3",     25,    1800.00,    "hafriyat"),
    # ── 2. TEMEL BETONARME ──────────────────────────────────
    ("02.001", "Temel kalıbı",                            "m2",    120,     280.00,    "temel"),
    ("02.002", "Temel demiri (nervurlu)",                 "kg",   8500,      18.50,    "temel"),
    ("02.003", "Temel betonu (C25/30)",                   "m3",     60,    2200.00,    "temel"),
    # ── 3. KOLON BETONARME ──────────────────────────────────
    ("03.001", "Kolon kalıbı",                            "m2",    220,     320.00,    "kolon"),
    ("03.002", "Kolon demiri (nervurlu)",                 "kg",  12000,      18.50,    "kolon"),
    ("03.003", "Kolon betonu (C25/30)",                   "m3",    100,    2600.00,    "kolon"),
    # ── 4. KİRİŞ ve DÖŞEME ──────────────────────────────────
    ("04.001", "Doseme kalıbı",                           "m2",    350,     240.00,    "doseme"),
    ("04.002", "Kiri kalıbı",                             "m2",    180,     290.00,    "doseme"),
    ("04.003", "Doseme + kiris demiri (nervurlu)",        "kg",  15000,      18.50,    "doseme"),
    ("04.004", "Doseme betonu (C25/30)",                  "m3",     85,    2400.00,    "doseme"),
    ("04.005", "Kalıp sokumu",                            "m2",    730,      45.00,    "doseme"),
    # ── 5. KABA YAPI (DUVAR) ────────────────────────────────
    ("05.001", "Tugla duvar (19cm)",                      "m2",    420,     380.00,    "kaba_yapi"),
    ("05.002", "Bolme duvar (10cm)",                      "m2",    280,     290.00,    "kaba_yapi"),
    ("05.003", "Lento betonu",                            "m3",      8,    2400.00,    "kaba_yapi"),
    ("05.004", "Cati (betonarme)",                        "m2",    130,     850.00,    "kaba_yapi"),
    # ── 6. İNCE YAPI — SIVA ─────────────────────────────────
    ("06.001", "Ic siva (alci + cimento)",                "m2",    850,     120.00,    "siva"),
    ("06.002", "Dis siva",                                "m2",    420,     165.00,    "siva"),
    ("06.003", "Tavan alci siva",                         "m2",    350,      95.00,    "siva"),
    # ── 7. KAPLAMA VE BOYA ──────────────────────────────────
    ("07.001", "Ic boya (2 kat)",                         "m2",    850,      75.00,    "kaplama"),
    ("07.002", "Dis cephe boyasi",                        "m2",    420,     120.00,    "kaplama"),
    ("07.003", "Seramik doseme (ic)",                     "m2",    280,     350.00,    "kaplama"),
    ("07.004", "Fayans (banyo/mutfak)",                   "m2",    120,     380.00,    "kaplama"),
    ("07.005", "Mermer merdiven",                         "m2",     35,     950.00,    "kaplama"),
    # ── 8. MEKANİK VE ELEKTRİK ──────────────────────────────
    ("08.001", "Sihhi tesisat (goturu)",                  "goturu",  1, 180000.00,    "mekanik"),
    ("08.002", "Elektrik tesisati (goturu)",              "goturu",  1, 150000.00,    "mekanik"),
    ("08.003", "Isitma / dogalgaz (goturu)",              "goturu",  1, 120000.00,    "mekanik"),
]

# ============================================================
# CŞB VERİMLİLİK SABİTLERİ (3 usta varsayılan)
# ============================================================
VERIMLILIK = {
    "hafriyat": ("m3",   120.0),   # is makinesi
    "kalip_temel": ("m2",   2.86),  # usta/gun
    "kalip_kolon": ("m2",   1.82),
    "kalip_doseme": ("m2",  4.00),
    "kalip_kiri": ("m2",    2.86),
    "kalip_sokim": ("m2",   8.00),
    "demir_baglama": ("kg", 333.0),
    "demir_soguk": ("kg",  250.0),
    "beton":       ("m3",   15.0),
    "tugla":       ("m2",    6.0),
    "siva_ic":     ("m2",   25.0),
    "siva_dis":    ("m2",   20.0),
    "boya_ic":     ("m2",   45.0),
    "boya_dis":    ("m2",   30.0),
    "seramik":     ("m2",    8.0),
    "mermer":      ("m2",    4.0),
}
USTA_SAYISI = 3


def sure_hesapla(kalem_tanim: str, birim: str, miktar: float) -> int:
    """CŞB verimliliklerine göre iş günü hesapla."""
    t = kalem_tanim.lower()
    m = miktar

    if birim in ("goturu", "adet") or m <= 0:
        return 20

    # Kalıp
    if "kalıp" in t or "kalip" in t:
        if "sokim" in t or "sökü" in t:
            v = VERIMLILIK["kalip_sokim"][1]
        elif "kolon" in t:
            v = VERIMLILIK["kalip_kolon"][1]
        elif "kiri" in t:
            v = VERIMLILIK["kalip_kiri"][1]
        elif "doseme" in t or "döşeme" in t:
            v = VERIMLILIK["kalip_doseme"][1]
        else:
            v = VERIMLILIK["kalip_temel"][1]
        return max(1, math.ceil(m / (v * USTA_SAYISI)))

    # Demir
    if "demir" in t or "nervur" in t:
        if "nervur" in t or "soguk" in t:
            v = VERIMLILIK["demir_soguk"][1]
        else:
            v = VERIMLILIK["demir_baglama"][1]
        return max(1, math.ceil(m / (v * USTA_SAYISI)))

    # Beton
    if "beton" in t:
        return max(1, math.ceil(m / (VERIMLILIK["beton"][1] * USTA_SAYISI)))

    # Hafriyat
    if "hafriy" in t or "kazi" in t or "dolgu" in t or "nakl" in t:
        return max(1, math.ceil(m / VERIMLILIK["hafriyat"][1]))

    # Duvar
    if "tugla" in t or "duvar" in t or "bolme" in t:
        return max(1, math.ceil(m / (VERIMLILIK["tugla"][1] * USTA_SAYISI)))

    # Sıva
    if "siva" in t or "alci" in t:
        if "dis" in t:
            return max(1, math.ceil(m / (VERIMLILIK["siva_dis"][1] * USTA_SAYISI)))
        return max(1, math.ceil(m / (VERIMLILIK["siva_ic"][1] * USTA_SAYISI)))

    # Boya
    if "boya" in t:
        if "dis" in t or "cephe" in t:
            return max(1, math.ceil(m / (VERIMLILIK["boya_dis"][1] * USTA_SAYISI)))
        return max(1, math.ceil(m / (VERIMLILIK["boya_ic"][1] * USTA_SAYISI)))

    # Seramik / fayans
    if "seramik" in t or "fayans" in t:
        return max(1, math.ceil(m / (VERIMLILIK["seramik"][1] * USTA_SAYISI)))

    # Mermer
    if "mermer" in t:
        return max(1, math.ceil(m / (VERIMLILIK["mermer"][1] * USTA_SAYISI)))

    return max(1, math.ceil(m / 10))  # varsayılan


# ============================================================
# GANTT GÖREVLERİ (FS bağımlılıklarıyla)
# Her görev metraj tablosundaki POZ_NO ile eşleştirilir.
# ============================================================
GANTT_GOREVLER = [
    # (id, tanim, sure, [oncul_idler_FS], ekip, kaynak, poz_eşleme_liste, kur_gun)
    (1,  "Santiye Kurulumu",                    3,  [],       "Sef",                    "Yonetim",    [],              0),
    (2,  "Hafriyat Kazisi",                     5,  [1],      "Is Makinesi",            "Ekskavatör", ["01.001","01.002"], 0),
    (3,  "Grobeton (C16)",                      2,  [2],      "Beton Ekibi",            "Beton Ekibi",["01.004"],      0),
    (4,  "Temel Kalıbı",                        0,  [3],      "Kalıpçı Ekibi",          "Kalıp",      ["02.001"],      0),
    (5,  "Temel Demiri",                        0,  [4],      "Demirci",                "Demir",      ["02.002"],      0),
    (6,  "Temel Betonu (C25/30)",               0,  [5],      "Beton Ekibi",            "Beton Ekibi",["02.003"],      0),
    (7,  "Temel Kuru Bekleme",                 21,  [6],      "",                       "",           [],              21),
    (8,  "Kolon Demiri",                        0,  [7],      "Demirci",                "Demir",      ["03.002"],      0),
    (9,  "Kolon Kalıbı",                        0,  [8],      "Kalıpçı Ekibi",          "Kalıp",      ["03.001"],      0),
    (10, "Kolon Betonu (C25/30)",               0,  [9],      "Beton Ekibi",            "Beton Ekibi",["03.003"],      0),
    (11, "Kolon Kuru",                          7,  [10],     "",                       "",           [],              7),
    (12, "Doseme Kalıbı",                       0,  [11],     "Kalıpçı Ekibi",          "Kalıp",      ["04.001"],      0),
    (13, "Kiri Kalıbı",                         0,  [12],     "Kalıpçı Ekibi",          "Kalıp",      ["04.002"],      0),
    (14, "Doseme + Kiri Demiri",                0,  [13],     "Demirci",                "Demir",      ["04.003"],      0),
    (15, "Doseme Betonu (C25/30)",              0,  [14],     "Beton Ekibi",            "Beton Ekibi",["04.004"],      0),
    (16, "Doseme Kuru Bekleme",                28,  [15],     "",                       "",           [],              28),
    (17, "Kalıp Sokumu",                        0,  [16],     "Kalıpçı Ekibi",          "Kalıp",      ["04.005"],      0),
    (18, "Geri Dolgu ve Tesviye",               3,  [17],     "Is Makinesi",            "Ekskavatör", ["01.003"],      0),
    (19, "Tugla Duvar (19cm)",                  0,  [17],     "Duvarcı",                "Duvarcı",    ["05.001"],      0),
    (20, "Bolme Duvar (10cm)",                  0,  [19],     "Duvarcı",                "Duvarcı",    ["05.002"],      0),
    (21, "Lento Betonu",                        2,  [19],     "Beton Ekibi",            "Beton Ekibi",["05.003"],      0),
    (22, "Cati (Betonarme)",                    0,  [17],     "Cati Ekibi",             "Cati",       ["05.004"],      0),
    (23, "Ic Siva",                             0,  [20,21],  "Sivaci",                 "Sivaci",     ["06.001","06.003"], 0),
    (24, "Dis Siva",                            0,  [20],     "Sivaci",                 "Sivaci",     ["06.002"],      0),
    (25, "Tesisat (Sihhi + Elektrik + Isitma)", 0,  [17],     "Tesisat Ekibi",          "Tesisat",    ["08.001","08.002","08.003"], 0),
    (26, "Ic Boya",                             0,  [23],     "Boyaci",                 "Boyaci",     ["07.001"],      0),
    (27, "Dis Cephe Boyasi",                    0,  [24],     "Boyaci",                 "Boyaci",     ["07.002"],      0),
    (28, "Seramik Doseme",                      0,  [26],     "Fayansci",               "Fayansci",   ["07.003"],      0),
    (29, "Fayans (Banyo/Mutfak)",               0,  [26],     "Fayansci",               "Fayansci",   ["07.004"],      0),
    (30, "Mermer Merdiven",                     0,  [28],     "Mermer Ustasi",          "Mermer",     ["07.005"],      0),
    (31, "Kaba Yapi + Ince Yapi Teslim",        1,  [22,25,27,29,30], "Sef",             "Yonetim",   [],              0),
]


def liste_projeler(db):
    """Tüm projeleri listele."""
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, ad, durum FROM projeler ORDER BY id")
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print(f"Proje listesi alinamadi: {e}")
        return []


def metraj_var_mi(db, proje_id):
    """Projede zaten kaç kalem var?"""
    try:
        kalemler = db.get_project_metraj(proje_id)
        return len(kalemler)
    except Exception:
        return 0


def ekle_metraj(db, proje_id):
    """30 metraj kalemini veritabanına ekle."""
    eklenen = 0
    for poz_no, tanim, birim, miktar, birim_fiyat, kategori in KALEMLER:
        try:
            db.add_metraj_kalem(
                proje_id=proje_id,
                tanim=tanim,
                miktar=float(miktar),
                birim=birim,
                birim_fiyat=float(birim_fiyat),
                poz_no=poz_no,
                kategori=kategori,
            )
            toplam = miktar * birim_fiyat
            print(f"  + [{poz_no}] {tanim[:45]:<45} {birim:<8} {miktar:>7,.0f}  {toplam:>12,.0f} TL")
            eklenen += 1
        except Exception as e:
            print(f"  HATA [{poz_no}]: {e}")
    return eklenen


def ekle_gantt(db, proje_id, kalem_map):
    """
    Gantt görevlerini iş_programi tablosuna ekle (varsa).
    kalem_map: poz_no -> metraj kalem satırı
    """
    # Gantt veritabanı tablosunu kontrol et
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='gantt_gorevleri'")
        tablo_var = cursor.fetchone() is not None
        conn.close()
    except Exception:
        tablo_var = False

    # JSON olarak kaydet (gantt_window yuklemesi icin)
    gorevler = []
    id_to_sure = {}  # Süre hesabı için

    for (gid, tanim, sure_sabit, oncul_ids, ekip, kaynak, poz_refs, kur_gun) in GANTT_GOREVLER:
        # Süreyi metraj verilerinden hesapla
        if sure_sabit > 0:
            sure = sure_sabit
            miktar = 0.0
            butce = 0.0
        else:
            # İlgili poz kalemlerinin miktarlarını topla
            miktar_toplam = 0.0
            butce_toplam = 0.0
            for poz in poz_refs:
                kalem = kalem_map.get(poz)
                if kalem:
                    m = float(kalem.get("miktar", 0) or 0)
                    bf = float(kalem.get("birim_fiyat", 0) or 0)
                    birim = kalem.get("birim", "")
                    miktar_toplam += m
                    butce_toplam += m * bf
            sure = sure_hesapla(tanim, "m2", miktar_toplam) if miktar_toplam > 0 else 5
            miktar = miktar_toplam
            butce = butce_toplam

        id_to_sure[gid] = sure

        gorev = {
            "id": gid,
            "ad": tanim,
            "sure": sure,
            "miktar": round(miktar, 2),
            "ekip": ekip,
            "kaynak": kaynak,
            "milestone": gid == 31,
            "bagimliliklar": oncul_ids,
            "bagimliliklar_detay": [{"id": o, "tip": "FS", "lag": 0} for o in oncul_ids],
            "tamamlanma_yuzdesi": 0,
            "butce": round(butce, 2),
        }
        gorevler.append(gorev)

    # JSON dosyasına kaydet (Gantt yukleyebilsin)
    out_path = os.path.join(os.path.dirname(__file__), "data", f"gantt_proje_{proje_id}.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"versiyon": "2.0", "proje_id": proje_id, "tasks": gorevler}, f,
                  ensure_ascii=False, indent=2)
    print(f"\n  Gantt JSON kaydedildi: {out_path}")
    print(f"  Gantt modulunde 'Yukle' butonu ile bu dosyayi acabilirsiniz.")
    return len(gorevler)


def main():
    args = sys.argv[1:]
    db = DatabaseManager()

    if "--liste" in args:
        projeler = liste_projeler(db)
        print("\nMevcut Projeler:")
        for p in projeler:
            print(f"  ID={p[0]:3d}  {p[1]:<40}  {p[2]}")
        return

    # Proje ID belirle
    proje_id = None
    if "--proje" in args:
        idx = args.index("--proje")
        try:
            proje_id = int(args[idx + 1])
        except (IndexError, ValueError):
            print("Hata: --proje parametresi gecersiz.")
            return
    else:
        projeler = liste_projeler(db)
        if not projeler:
            print("Veritabaninda proje bulunamadi. Once program uzerinden proje olusturun.")
            return
        print("\nMevcut Projeler:")
        for p in projeler:
            mevcut = metraj_var_mi(db, p[0])
            print(f"  [{p[0]:3d}]  {p[1]:<40}  {p[2]}  (mevcut kalem: {mevcut})")
        secim = input("\nKalemlerin ekleneceği proje ID girin: ").strip()
        try:
            proje_id = int(secim)
        except ValueError:
            print("Gecersiz ID.")
            return

    # Mevcut kalem sayısı
    mevcut = metraj_var_mi(db, proje_id)
    if mevcut > 0:
        onay = input(
            f"Projede {mevcut} kalem mevcut. Uzerine {len(KALEMLER)} kalem eklenecek. Devam? (e/h): "
        ).strip().lower()
        if onay not in ("e", "evet", "y", "yes"):
            print("Iptal edildi.")
            return

    print(f"\nProje ID={proje_id} icin {len(KALEMLER)} kalem ekleniyor...")
    print("-" * 75)
    n = ekle_metraj(db, proje_id)
    print("-" * 75)
    print(f"Eklenen kalem: {n}/{len(KALEMLER)}")

    # Kalem haritası oluştur
    try:
        all_kalemler = db.get_project_metraj(proje_id)
        kalem_map = {}
        for k in all_kalemler:
            poz = k.get("poz_no", "")
            if poz:
                kalem_map[poz] = k
    except Exception:
        kalem_map = {}

    # Gantt JSON
    print(f"\n{len(GANTT_GOREVLER)} Gantt gorevi olusturuluyor (FS bagimliliklar)...")
    m = ekle_gantt(db, proje_id, kalem_map)
    print(f"Olusturulan Gantt gorevi: {m}")

    print("\n" + "=" * 75)
    print("TAMAMLANDI!")
    print("Sonraki Adimlar:")
    print("  1. Programi acin -> Projeyi secin")
    print("  2. Gantt sekmesi -> 'Yukle' butonu -> gantt_proje_{}.json secin".format(proje_id))
    print("  3. 'Hesapla (CPM)' ile kritik yolu hesaplayin")
    print("  4. Gecikme sekmesinde sozlesme bedelini girin -> ceza uyarisi aktif olur")
    print("=" * 75)


if __name__ == "__main__":
    main()
