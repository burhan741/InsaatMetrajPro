"""
3D Oda Veri Katmanı
===================
AutoCAD koordinatları + malzeme seçimi → Oda3D objeleri üretir.

Neyi çözer?
Kullanıcı AutoCAD'de bir oda sınırı (kapalı polyline) seçer.
Bu modül o koordinatları ve seçilen malzemeleri alıp
3D render için hazır veri yapısı üretir.

Polyline yoksa yalnızca m² değeri ile kare oda tahmini yapar.

Nasıl test edilir?
builder = Room3DBuilder()
oda = builder.kare_oda_olustur("Salon", alan_m2=25.0, yukseklik=2.80,
zemin_malzeme="Laminat Parke")
assert len(oda.yuzeyler) >= 6 # zemin + 4 duvar + tavan
assert oda.alan > 0
"""

import math
import logging
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict

logger = logging.getLogger(__name__)

# ── Malzeme renk sistemi ────────────────────────────────────────────────────
try:
    from app.data.malzeme_renkleri import (
    MALZEME_RENKLERI,
    ODA_TIPI_RENKLERI,
    get_surface_color,
    )
    _RENKLER_OK = True
except ImportError:
    _RENKLER_OK = False
    MALZEME_RENKLERI = {}
    ODA_TIPI_RENKLERI = {}

    def get_surface_color(malzeme_adi, surface_type="DUVAR", oda_turu="KURU"):
        _FALLBACK = {
        "ZEMIN": (0.55, 0.35, 0.17, 0.90),
        "DUVAR": (0.95, 0.95, 0.95, 0.85),
        "TAVAN": (0.95, 0.95, 0.92, 0.25),
        }
        return _FALLBACK.get(surface_type, (0.70, 0.70, 0.70, 0.70))


# ── Veri Sınıfları ──────────────────────────────────────────────────────────

@dataclass
class OdaYuzeyi:
    """
    Tek bir 3D yüzey: zemin, duvar segmenti veya tavan.

    vertices → [(x, y, z), ...] cm cinsinden, 3 veya 4 köşe.
    rgba → (r, g, b, a) 0.0-1.0 arası, Matplotlib uyumlu.
    """
    surface_type: str # 'ZEMIN' | 'DUVAR' | 'TAVAN'
    vertices: List[Tuple] # [(x, y, z), ...]
    rgba: Tuple # (r, g, b, a)
    malzeme_adi: str = "" # "Laminat Parke"
    label: str = "" # Görsel etiket


@dataclass
class Oda3D:
    """
    Tek bir odanın tam 3D verisi.

    taban_polygon → [(x, y), ...] cm cinsinden taban poligonu.
    yuzeyler → render edilecek OdaYuzeyi listesi.
    """
    oda_adi: str
    alan: float # m²
    yukseklik: float # metre
    taban_polygon: List[Tuple[float, float]] # [(x, y), ...] cm
    yuzeyler: List[OdaYuzeyi] = field(default_factory=list)
    zemin_malzeme: str = "Laminat Parke"
    duvar_malzeme: str = "Duvar Boyası"
    tavan_malzeme: str = "Tavan Boyası"
    merkez: Tuple[float, float] = (0.0, 0.0) # taban centroid cm


# ── Malzeme Kataloğu ────────────────────────────────────────────────────────

# Kullanıcıya sunulacak zemin malzemeleri (ComboBox için)
ZEMIN_MALZEMELERI: List[str] = [
"Laminat Parke",
"Yer Fayansı + Derz",
"Şap Çimentosu",
"Tezgah Arası Seramik",
]

# Kullanıcıya sunulacak duvar malzemeleri
DUVAR_MALZEMELERI: List[str] = [
"Duvar Boyası",
"Duvar Fayansı + Derz",
"Saten Alçı",
"Kaba Alçı",
]

# Oda adı → otomatik zemin malzeme tahmini
_ZEMIN_TAHMIN: Dict[str, str] = {
"BANYO": "Yer Fayansı + Derz",
"WC": "Yer Fayansı + Derz",
"DUŞ": "Yer Fayansı + Derz",
"TUVALET": "Yer Fayansı + Derz",
"MUTFAK": "Yer Fayansı + Derz",
"SALON": "Laminat Parke",
"YATAK": "Laminat Parke",
"KORİDOR": "Laminat Parke",
"HOL": "Laminat Parke",
"GİRİŞ": "Laminat Parke",
}

_DUVAR_TAHMIN: Dict[str, str] = {
"BANYO": "Duvar Fayansı + Derz",
"WC": "Duvar Fayansı + Derz",
"DUŞ": "Duvar Fayansı + Derz",
"TUVALET": "Duvar Fayansı + Derz",
"MUTFAK": "Duvar Fayansı + Derz",
}


# ── Builder ─────────────────────────────────────────────────────────────────

class Room3DBuilder:
    """
    3D oda verisi üretici.

    İki mod:
    1. Koordinatlardan: AutoCAD polyline koordinatları verilerek
    2. Kare tahmini: Sadece m² değeri ile kare oda

    Kullanım:
    builder = Room3DBuilder()

    # Mod 1 — AutoCAD polyline koordinatları:
    oda = builder.koordinatlardan_oda(
    oda_adi="Salon",
    koordinatlar=[(0,0),(500,0),(500,400),(0,400)], # cm
    yukseklik=2.80,
    zemin_malzeme="Laminat Parke",
    )

    # Mod 2 — Sadece m²:
    oda = builder.kare_oda_olustur("Banyo", alan_m2=6.5,
    zemin_malzeme="Yer Fayansı + Derz")

    # Toplu üretim (sap_eslestirme listesinden):
    odalar = builder.sap_eslestirmeden_odalar(self.sap_eslestirme, 2.80)
    """

    # ── Yardımcılar ──────────────────────────────────────────────────────

    @staticmethod
    def _oda_turu(oda_adi: str) -> str:
        """Oda adından ISLAK / MUTFAK / KORIDOR / KURU tahmini."""
        ad = oda_adi.upper()
        if any(k in ad for k in ["BANYO", "WC", "DUŞ", "TUVALET", "LAVABO"]):
            return "ISLAK"
            if "MUTFAK" in ad:
                return "MUTFAK"
                if any(k in ad for k in ["KORİDOR", "HOL", "GİRİŞ", "KORIDOR"]):
                    return "KORIDOR"
                    return "KURU"

                    def _renk_al(self, malzeme_adi: str, surface_type: str,
                    oda_adi: str = "") -> tuple:
                        """Malzeme adına göre RGBA rengi döndür."""
                    return get_surface_color(malzeme_adi, surface_type,
                    self._oda_turu(oda_adi))

                    @staticmethod
                    def _centroid(polygon: List[Tuple[float, float]]) -> Tuple[float, float]:
                        """Poligon ağırlık merkezi (cm)."""
                        if not polygon:
                            return (0.0, 0.0)
                            return (
                            sum(p[0] for p in polygon) / len(polygon),
                            sum(p[1] for p in polygon) / len(polygon),
                            )

                            @staticmethod
                            def _shoelace_alan(polygon: List[Tuple[float, float]]) -> float:
                                """Shoelace formülü ile poligon alanı (cm²)."""
                                n = len(polygon)
                                if n < 3:
                                    return 0.0
                                    return abs(sum(
                                    polygon[i][0] * polygon[(i + 1) % n][1] -
                                    polygon[(i + 1) % n][0] * polygon[i][1]
                                    for i in range(n)
                                    )) / 2.0

                                    @staticmethod
                                    def _tahmin_zemin(oda_adi: str) -> str:
                                        """Oda adından zemin malzeme tahmini."""
                                        ad = oda_adi.upper()
                                        for anahtar, malzeme in _ZEMIN_TAHMIN.items():
                                            if anahtar in ad:
                                                return malzeme
                                                return "Laminat Parke"

                                                @staticmethod
                                                def _tahmin_duvar(oda_adi: str) -> str:
                                                    """Oda adından duvar malzeme tahmini."""
                                                    ad = oda_adi.upper()
                                                    for anahtar, malzeme in _DUVAR_TAHMIN.items():
                                                        if anahtar in ad:
                                                            return malzeme
                                                            return "Duvar Boyası"

                                                            # ── Yüzey Üretimi ────────────────────────────────────────────────────

                                                            def _yuzeyler_uret(
                                                            self,
                                                            polygon: List[Tuple[float, float]],
                                                            yukseklik_cm: float,
                                                            zemin_malzeme: str,
                                                            duvar_malzeme: str,
                                                            tavan_malzeme: str,
                                                            oda_adi: str,
                                                            ) -> List[OdaYuzeyi]:
                                                                """
                                                            Kapalı 2D poligon + yükseklik → 3D yüzey listesi.

                                                            Çıktı:
                                                            1 zemin yüzeyi (polygon @ z=0)
                                                            N duvar yüzeyi (her kenar için 1 dikdörtgen)
                                                            1 tavan yüzeyi (polygon @ z=yukseklik_cm, yarı şeffaf)
                                                            """
                                                            yuzeyler: List[OdaYuzeyi] = []
                                                            h = yukseklik_cm

                                                            # ─── Zemin ──────────────────────────────────────────────────────
                                                            zemin_rgba = self._renk_al(zemin_malzeme, "ZEMIN", oda_adi)
                                                            yuzeyler.append(OdaYuzeyi(
                                                            surface_type="ZEMIN",
                                                            vertices=[(x, y, 0.0) for x, y in polygon],
                                                            rgba=zemin_rgba,
                                                            malzeme_adi=zemin_malzeme,
                                                            label=zemin_malzeme,
                                                            ))

                                                            # ─── Duvarlar (her kenar = 1 dikdörtgen) ───────────────────────
                                                            duvar_rgba = self._renk_al(duvar_malzeme, "DUVAR", oda_adi)
                                                            n = len(polygon)
                                                            for i in range(n):
                                                                x1, y1 = polygon[i]
                                                                x2, y2 = polygon[(i + 1) % n]
                                                                yuzeyler.append(OdaYuzeyi(
                                                                surface_type="DUVAR",
                                                                vertices=[
                                                                (x1, y1, 0.0),
                                                                (x2, y2, 0.0),
                                                                (x2, y2, h),
                                                                (x1, y1, h),
                                                                ],
                                                                rgba=duvar_rgba,
                                                                malzeme_adi=duvar_malzeme,
                                                                ))

                                                                # ─── Tavan (yarı şeffaf) ─────────────────────────────────────────
                                                                tavan_rgba = self._renk_al(tavan_malzeme, "TAVAN", oda_adi)
                                                                tavan_rgba = (*tavan_rgba[:3], 0.20) # alpha'yı zorla düşür
                                                                yuzeyler.append(OdaYuzeyi(
                                                                surface_type="TAVAN",
                                                                vertices=[(x, y, h) for x, y in polygon],
                                                                rgba=tavan_rgba,
                                                                malzeme_adi=tavan_malzeme,
                                                                ))

                                                                return yuzeyler

                                                                # ── Genel Fabrika: koordinatlardan ──────────────────────────────────

                                                                def koordinatlardan_oda(
                                                                self,
                                                                oda_adi: str,
                                                                koordinatlar: List[Tuple[float, float]],
                                                                yukseklik: float = 2.80,
                                                                zemin_malzeme: Optional[str] = None,
                                                                duvar_malzeme: Optional[str] = None,
                                                                tavan_malzeme: str = "Tavan Boyası",
                                                                ) -> Oda3D:
                                                                    """
                                                                AutoCAD polyline koordinatlarından (cm) Oda3D üret.

                                                                Args:
                                                                koordinatlar: [(x, y), ...] cm cinsinden kapalı poligon
                                                                yukseklik: Kat yüksekliği metre cinsinden (ör. 2.80)
                                                                """
                                                                if not koordinatlar or len(koordinatlar) < 3:
                                                                    logger.warning(
                                                                    f"'{oda_adi}' için koordinat yetersiz "
                                                                    f"({len(koordinatlar)}), kare oda kullanılıyor."
                                                                    )
                                                                    kenar = 300.0 # 3 m × 3 m fallback
                                                                    koordinatlar = [
                                                                    (0.0, 0.0), (kenar, 0.0),
                                                                    (kenar, kenar), (0.0, kenar),
                                                                    ]

                                                                    zemin = zemin_malzeme or self._tahmin_zemin(oda_adi)
                                                                    duvar = duvar_malzeme or self._tahmin_duvar(oda_adi)

                                                                    alan_m2 = self._shoelace_alan(koordinatlar) / 10_000
                                                                    yukseklik_cm = yukseklik * 100.0

                                                                    yuzeyler = self._yuzeyler_uret(
                                                                    koordinatlar, yukseklik_cm, zemin, duvar, tavan_malzeme, oda_adi
                                                                    )

                                                                    return Oda3D(
                                                                    oda_adi=oda_adi,
                                                                    alan=round(alan_m2, 2),
                                                                    yukseklik=yukseklik,
                                                                    taban_polygon=list(koordinatlar),
                                                                    yuzeyler=yuzeyler,
                                                                    zemin_malzeme=zemin,
                                                                    duvar_malzeme=duvar,
                                                                    tavan_malzeme=tavan_malzeme,
                                                                    merkez=self._centroid(koordinatlar),
                                                                    )

                                                                    # ── Kare Oda (sadece m² varsa) ───────────────────────────────────────

                                                                    def kare_oda_olustur(
                                                                    self,
                                                                    oda_adi: str,
                                                                    alan_m2: float,
                                                                    yukseklik: float = 2.80,
                                                                    zemin_malzeme: Optional[str] = None,
                                                                    duvar_malzeme: Optional[str] = None,
                                                                    tavan_malzeme: str = "Tavan Boyası",
                                                                    offset_x: float = 0.0,
                                                                    offset_y: float = 0.0,
                                                                    ) -> Oda3D:
                                                                        """
                                                                    Sadece m² değeri varsa kare oda tahmini üret.

                                                                    offset_x / offset_y ile yan yana yerleştirme yapılabilir.
                                                                    """
                                                                    kenar_cm = math.sqrt(max(alan_m2, 0.5)) * 100.0
                                                                    koordinatlar = [
                                                                    (offset_x, offset_y),
                                                                    (offset_x + kenar_cm, offset_y),
                                                                    (offset_x + kenar_cm, offset_y + kenar_cm),
                                                                    (offset_x, offset_y + kenar_cm),
                                                                    ]
                                                                    return self.koordinatlardan_oda(
                                                                    oda_adi=oda_adi,
                                                                    koordinatlar=koordinatlar,
                                                                    yukseklik=yukseklik,
                                                                    zemin_malzeme=zemin_malzeme,
                                                                    duvar_malzeme=duvar_malzeme,
                                                                    tavan_malzeme=tavan_malzeme,
                                                                    )

                                                                    # ── Toplu üretim: sap_eslestirme listesinden ────────────────────────

                                                                    def sap_eslestirmeden_odalar(
                                                                    self,
                                                                    sap_eslestirme: List[dict],
                                                                    yukseklik: float = 2.80,
                                                                    malzeme_haritasi: Optional[Dict[str, str]] = None,
                                                                    ) -> List[Oda3D]:
                                                                        """
                                                                    sap_eslestirme listesinden Oda3D listesi üret.

                                                                    Her oda m² değerine göre kare olarak modellenir,
                                                                    odalar X ekseninde yan yana dizilir.

                                                                    Args:
                                                                    sap_eslestirme: [{"mahal_adi": str, "deger": float, ...}, ...]
                                                                    malzeme_haritasi: {"SALON": "Laminat Parke", ...} ← kullanıcı seçimi
                                                                    """
                                                                    malzeme_haritasi = malzeme_haritasi or {}
                                                                    odalar: List[Oda3D] = []
                                                                    x_ofset = 0.0

                                                                    for kayit in sap_eslestirme:
                                                                        oda_adi = (
                                                                        kayit.get("mahal_adi")
                                                                        or kayit.get("oda_adi")
                                                                        or "Oda"
                                                                        )
                                                                        alan_m2 = float(kayit.get("deger", 10.0))

                                                                        zemin = malzeme_haritasi.get(oda_adi) or self._tahmin_zemin(oda_adi)
                                                                        duvar = self._tahmin_duvar(oda_adi)

                                                                        kenar_cm = math.sqrt(max(alan_m2, 0.5)) * 100.0
                                                                        oda = self.kare_oda_olustur(
                                                                        oda_adi=oda_adi,
                                                                        alan_m2=alan_m2,
                                                                        yukseklik=yukseklik,
                                                                        zemin_malzeme=zemin,
                                                                        duvar_malzeme=duvar,
                                                                        offset_x=x_ofset,
                                                                        )
                                                                        odalar.append(oda)
                                                                        x_ofset += kenar_cm + 60.0 # 60 cm aralık

                                                                        logger.info(f"Room3DBuilder: {len(odalar)} oda üretildi")
                                                                        return odalar

                                                                        # ── AutoCAD MetrajObjesi'nden ────────────────────────────────────────

                                                                        def autocad_objesinden_oda(
                                                                        self,
                                                                        metraj_obj,
                                                                        oda_adi: str,
                                                                        yukseklik: float = 2.80,
                                                                        zemin_malzeme: Optional[str] = None,
                                                                        duvar_malzeme: Optional[str] = None,
                                                                        ) -> Optional[Oda3D]:
                                                                            """
                                                                        AutoCAD MetrajObjesi (koordinatlar listesi içeren) → Oda3D.

                                                                        Döner None: koordinat listesi yetersizse.
                                                                        """
                                                                        koordinatlar = getattr(metraj_obj, "koordinatlar", []) or []
                                                                        if len(koordinatlar) < 3:
                                                                            logger.warning(
                                                                            f"AutoCAD objesi '{oda_adi}' koordinat yetersiz "
                                                                            f"({len(koordinatlar)} nokta)."
                                                                            )
                                                                            return None

                                                                            return self.koordinatlardan_oda(
                                                                            oda_adi=oda_adi,
                                                                            koordinatlar=list(koordinatlar),
                                                                            yukseklik=yukseklik,
                                                                            zemin_malzeme=zemin_malzeme,
                                                                            duvar_malzeme=duvar_malzeme,
                                                                            )


# ════════════════════════════════════════════════════════════════════════════
# Dış Cephe Veri Sınıfları
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class DisCepheYuzeyi:
    """
    Binanın dış kabuğundan tek bir yüzey.

    yon → 'GUNEY' | 'KUZEY' | 'DOGU' | 'BATI' | 'CATI'
    vertices → [(x, y, z), ...] cm cinsinden 4 köşe
    alan_m2 → Bu yüzeyin brüt alanı (pencere/kapı düşülmemiş)
    """
    yon: str
    vertices: List[Tuple]
    rgba: Tuple
    malzeme_adi: str = ""
    alan_m2: float = 0.0


@dataclass
class DisCephe3D:
    """
    Tüm bina dış cephe zarfı — 4 duvar + çatı.

    toplam_cephe_alani: Brüt dış cephe alanı (m²).
    """
    yuzeyler: List[DisCepheYuzeyi]
    bina_genisligi: float # metre
    bina_derinligi: float # metre
    bina_yuksekligi: float # metre
    toplam_cephe_alani: float # m²
    malzeme_adi: str = "Cephe Boyası (Beyaz)"


# ── Dış Cephe Malzeme Kataloğu ───────────────────────────────────────────
CEPHE_MALZEMELERI: List[str] = [
"Mantolama (EPS Karbonlu)",
"Mantolama (Taş Yünü)",
"Cephe Boyası (Beyaz)",
"Cephe Boyası (Krem)",
"Dekoratif Sıva",
"Dış Cephe Kaplama (Taş)",
"Klinker Tuğla",
"Alüminyum Kompozit Panel",
"Cam Cephe (Curtain Wall)",
"Doğal Taş (Granit)",
]


# ════════════════════════════════════════════════════════════════════════════
# DisCepheBuilder
# ════════════════════════════════════════════════════════════════════════════

class DisCepheBuilder:
    """
    Oda3D listesinin bounding box'ından bina dış cephe zarfı üretir.

    Neyi çözer?
    İç mekan odaları tanımlandıktan sonra binanın dış görünüşünü
    3D'de gösterir: cephe malzemesi rengiyle kaplı 4 dış duvar + çatı.

    Nasıl test edilir?
    builder = DisCepheBuilder()
    odalar = Room3DBuilder().sap_eslestirmeden_odalar(sap, 2.80)
    dc = builder.odalardan_dis_cephe(odalar, duvar_kalinligi=30.0,
    malzeme_adi="Mantolama (EPS Karbonlu)")
    assert dc is not None
    assert dc.toplam_cephe_alani > 0
    assert len(dc.yuzeyler) == 5 # 4 duvar + çatı

    Yaklaşım:
    1. Tüm odaların taban poligonundan global bounding box hesapla
    2. Duvar + yalıtım kalınlığı kadar dışarıya offset uygula
    3. Güney / Kuzey / Doğu / Batı olmak üzere 4 dış yüzey oluştur
    4. İsteğe bağlı yarı şeffaf çatı ekle (içi görülebilsin diye)
    """

    # Malzeme adı → RGBA (0.0-1.0 arası, Matplotlib facecolor uyumlu)
    CEPHE_RENKLERI: Dict[str, Tuple] = {
    "Mantolama (EPS Karbonlu)": (0.96, 0.87, 0.70, 0.88), # krem/bej
    "Mantolama (Taş Yünü)": (0.78, 0.78, 0.78, 0.88), # açık gri
    "Cephe Boyası (Beyaz)": (0.97, 0.97, 0.97, 0.88), # beyaz
    "Cephe Boyası (Krem)": (0.98, 0.94, 0.82, 0.88), # krem
    "Dekoratif Sıva": (0.92, 0.86, 0.76, 0.88), # kum
    "Dış Cephe Kaplama (Taş)": (0.62, 0.58, 0.52, 0.90), # taş gri
    "Klinker Tuğla": (0.72, 0.36, 0.22, 0.90), # tuğla kırmızısı
    "Alüminyum Kompozit Panel": (0.68, 0.74, 0.80, 0.92), # metalik gri
    "Cam Cephe (Curtain Wall)": (0.55, 0.78, 0.95, 0.35), # şeffaf mavi
    "Doğal Taş (Granit)": (0.55, 0.52, 0.48, 0.90), # granit
    }

    def odalardan_dis_cephe(
    self,
    odalar: List[Oda3D],
    duvar_kalinligi: float = 30.0,
    malzeme_adi: str = "Cephe Boyası (Beyaz)",
    cati_goster: bool = True,
    ) -> Optional[DisCephe3D]:
        """
    Oda listesinin bounding box'ından dış cephe zarfı üret.

    Args:
    odalar: Oda3D listesi (Room3DBuilder çıktısı)
    duvar_kalinligi: Toplam dış duvar kalınlığı cm.
    Örnek: 20 cm betonarme + 10 cm EPS = 30 cm
    malzeme_adi: CEPHE_RENKLERI anahtarı (görsel renk için)
    cati_goster: True → yarı şeffaf çatı yüzeyi ekler
    """
        if not odalar:
            return None

        # ─ Global bounding box ────────────────────────────────────────────
        all_x: List[float] = []
        all_y: List[float] = []
        for oda in odalar:
            for px, py in oda.taban_polygon:
                all_x.append(px)
                all_y.append(py)

        if not all_x:
            return None

        min_x, max_x = min(all_x), max(all_x)
        min_y, max_y = min(all_y), max(all_y)
        max_z = max(oda.yukseklik * 100.0 for oda in odalar)

        # ─ Dış offset ────────────────────────────────────────────────────
        t = duvar_kalinligi
        ox, oy = min_x - t, min_y - t  # sol-alt
        ex, ey = max_x + t, max_y + t  # sağ-üst

        rgba = self.CEPHE_RENKLERI.get(malzeme_adi, (0.95, 0.95, 0.95, 0.88))

        # ─ Boyutlar (cm) ─────────────────────────────────────────────────
        w_cm = ex - ox  # bina genişliği (x yönünde)
        d_cm = ey - oy  # bina derinliği (y yönünde)

        # ─ 4 Cephe yüzeyi ────────────────────────────────────────────────
        yuzeyler: List[DisCepheYuzeyi] = [
            DisCepheYuzeyi(
                yon="GUNEY",
                vertices=[(ox, oy, 0), (ex, oy, 0), (ex, oy, max_z), (ox, oy, max_z)],
                rgba=rgba, malzeme_adi=malzeme_adi,
                alan_m2=round((w_cm / 100.0) * (max_z / 100.0), 2),
            ),
            DisCepheYuzeyi(
                yon="KUZEY",
                vertices=[(ex, ey, 0), (ox, ey, 0), (ox, ey, max_z), (ex, ey, max_z)],
                rgba=rgba, malzeme_adi=malzeme_adi,
                alan_m2=round((w_cm / 100.0) * (max_z / 100.0), 2),
            ),
            DisCepheYuzeyi(
                yon="DOGU",
                vertices=[(ex, oy, 0), (ex, ey, 0), (ex, ey, max_z), (ex, oy, max_z)],
                rgba=rgba, malzeme_adi=malzeme_adi,
                alan_m2=round((d_cm / 100.0) * (max_z / 100.0), 2),
            ),
            DisCepheYuzeyi(
                yon="BATI",
                vertices=[(ox, ey, 0), (ox, oy, 0), (ox, oy, max_z), (ox, ey, max_z)],
                rgba=rgba, malzeme_adi=malzeme_adi,
                alan_m2=round((d_cm / 100.0) * (max_z / 100.0), 2),
            ),
        ]

        # ─ Çatı (yarı şeffaf) ─────────────────────────────────────────────
        if cati_goster:
            yuzeyler.append(DisCepheYuzeyi(
                yon="CATI",
                vertices=[(ox, oy, max_z), (ex, oy, max_z), (ex, ey, max_z), (ox, ey, max_z)],
                rgba=(*rgba[:3], 0.18),
                malzeme_adi="Çatı",
                alan_m2=round((w_cm / 100.0) * (d_cm / 100.0), 2),
            ))

        toplam_alan = sum(y.alan_m2 for y in yuzeyler if y.yon != "CATI")

        logger.info(
            f"DisCepheBuilder: {malzeme_adi!r} | "
            f"{w_cm/100:.2f}×{d_cm/100:.2f}×{max_z/100:.2f} m | "
            f"brüt cephe: {toplam_alan:.1f} m²"
        )
        return DisCephe3D(
            yuzeyler=yuzeyler,
            bina_genisligi=round(w_cm / 100.0, 2),
            bina_derinligi=round(d_cm / 100.0, 2),
            bina_yuksekligi=round(max_z / 100.0, 2),
            toplam_cephe_alani=round(toplam_alan, 2),
            malzeme_adi=malzeme_adi,
        )
