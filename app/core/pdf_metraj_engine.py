import math
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except Exception:
    PYMUPDF_AVAILABLE = False

try:
    from PyQt6.QtGui import QImage
    PYQT_AVAILABLE = True
except Exception:
    PYQT_AVAILABLE = False

logger = logging.getLogger(__name__)


class OlcuTipi(Enum):
    UZUNLUK = "uzunluk"
    ALAN = "alan"
    SAYIM = "sayim"


@dataclass
class Olcu:
    id: int
    tip: OlcuTipi
    noktalar: list
    gercek_deger: float
    birim: str
    aciklama: str = ""


class PDFMetrajEngine:
    """
    PDF dosyasını yükler, sayfa render eder, ölçüm hesaplar.

    PDF koordinat sistemi: PyMuPDF fitz kullanır — origin sol-üst, y aşağı artar.
    Ölçek kalibrasyonu: kullanıcı 2 nokta seçer + gerçek mesafeyi girer → px_per_m hesaplanır.
    """

    def __init__(self):
        self._doc = None
        self._mevcut_sayfa = 0
        self._zoom = 1.5
        self._olcu_listesi: list[Olcu] = []
        self._olcu_sayac = 0
        self._olcek_px_per_m: Optional[float] = None
        self._sayfa_genislik_px = 0
        self._sayfa_yukseklik_px = 0

    def pdf_yukle(self, dosya_yolu: str) -> bool:
        """PDF dosyasını yükler. Başarılı ise True döner."""
        if not PYMUPDF_AVAILABLE:
            logger.error("PyMuPDF (fitz) kurulu değil.")
            return False
        try:
            if self._doc is not None:
                self._doc.close()
                self._doc = None
            self._doc = fitz.open(dosya_yolu)
            self._mevcut_sayfa = 0
            self._olcu_listesi = []
            self._olcu_sayac = 0
            self._olcek_px_per_m = None
            logger.info("PDF yüklendi: %s (%d sayfa)", dosya_yolu, len(self._doc))
            return True
        except Exception as exc:
            logger.error("PDF yüklenemedi: %s", exc)
            return False

    def sayfa_render(self, sayfa_no: int, zoom: float = None):
        """
        Belirtilen sayfayı QImage olarak render eder.
        zoom: None ise self._zoom kullanılır.
        """
        if not PYMUPDF_AVAILABLE or self._doc is None:
            return None
        if not PYQT_AVAILABLE:
            return None
        if sayfa_no < 0 or sayfa_no >= len(self._doc):
            logger.warning("Geçersiz sayfa numarası: %d", sayfa_no)
            return None
        try:
            efektif_zoom = zoom if zoom is not None else self._zoom
            sayfa = self._doc[sayfa_no]
            mat = fitz.Matrix(efektif_zoom, efektif_zoom)
            pix = sayfa.get_pixmap(matrix=mat)
            self._sayfa_genislik_px = pix.width
            self._sayfa_yukseklik_px = pix.height
            self._mevcut_sayfa = sayfa_no
            img = QImage(
                pix.samples,
                pix.width,
                pix.height,
                pix.stride,
                QImage.Format.Format_RGB888,
            )
            return img.copy()
        except Exception as exc:
            logger.error("Sayfa render hatası (sayfa=%d): %s", sayfa_no, exc)
            return None

    def sayfa_sayisi(self) -> int:
        if self._doc is None:
            return 0
        return len(self._doc)

    def olcek_ayarla(self, p1_ekran, p2_ekran, gercek_mesafe_m: float):
        """
        İki ekran koordinatı noktası ve gerçek mesafe ile ölçek faktörünü hesaplar.
        px_per_m = piksel_mesafe / gercek_mesafe_m
        """
        if gercek_mesafe_m <= 0:
            logger.error("Gerçek mesafe sıfır veya negatif olamaz.")
            return
        dx = p2_ekran[0] - p1_ekran[0]
        dy = p2_ekran[1] - p1_ekran[1]
        piksel_mesafe = math.sqrt(dx * dx + dy * dy)
        if piksel_mesafe < 1e-6:
            logger.error("Kalibrasyon noktaları aynı konumda.")
            return
        self._olcek_px_per_m = piksel_mesafe / gercek_mesafe_m
        logger.info(
            "Ölçek ayarlandı: %.4f px/m (piksel=%.2f, gerçek=%.4f m)",
            self._olcek_px_per_m,
            piksel_mesafe,
            gercek_mesafe_m,
        )

    def olcek_var_mi(self) -> bool:
        return self._olcek_px_per_m is not None

    def uzunluk_hesapla(self, noktalar_ekran: list) -> float:
        """Polyline noktaları için toplam uzunluğu metre cinsinden hesaplar."""
        if not self.olcek_var_mi():
            raise RuntimeError("Ölçek kalibrasyonu yapılmamış.")
        if len(noktalar_ekran) < 2:
            return 0.0
        toplam_px = 0.0
        for i in range(len(noktalar_ekran) - 1):
            x1, y1 = noktalar_ekran[i]
            x2, y2 = noktalar_ekran[i + 1]
            dx = x2 - x1
            dy = y2 - y1
            toplam_px += math.sqrt(dx * dx + dy * dy)
        return toplam_px / self._olcek_px_per_m

    def alan_hesapla(self, noktalar_ekran: list) -> float:
        """Shoelace (Gauss) formülü ile poligon alanını m2 cinsinden hesaplar."""
        if not self.olcek_var_mi():
            raise RuntimeError("Ölçek kalibrasyonu yapılmamış.")
        n = len(noktalar_ekran)
        if n < 3:
            return 0.0
        toplam = 0.0
        for i in range(n):
            x1, y1 = noktalar_ekran[i]
            x2, y2 = noktalar_ekran[(i + 1) % n]
            toplam += x1 * y2 - x2 * y1
        alan_px2 = abs(toplam) / 2.0
        px_per_m = self._olcek_px_per_m
        return alan_px2 / (px_per_m * px_per_m)

    def olcu_ekle(self, tip: OlcuTipi, noktalar_ekran: list, aciklama: str = "") -> Olcu:
        """Ölçümü hesaplar, listeye ekler ve döner."""
        self._olcu_sayac += 1
        olcu_id = self._olcu_sayac

        if tip == OlcuTipi.UZUNLUK:
            deger = self.uzunluk_hesapla(noktalar_ekran)
            birim = "m"
        elif tip == OlcuTipi.ALAN:
            deger = self.alan_hesapla(noktalar_ekran)
            birim = "m2"
        elif tip == OlcuTipi.SAYIM:
            deger = float(len(noktalar_ekran))
            birim = "adet"
        else:
            deger = 0.0
            birim = ""

        olcu = Olcu(
            id=olcu_id,
            tip=tip,
            noktalar=list(noktalar_ekran),
            gercek_deger=round(deger, 4),
            birim=birim,
            aciklama=aciklama,
        )
        self._olcu_listesi.append(olcu)
        logger.debug("Ölçüm eklendi: id=%d tip=%s deger=%.4f %s", olcu_id, tip.value, deger, birim)
        return olcu

    def olcu_sil(self, olcu_id: int):
        onceki_uzunluk = len(self._olcu_listesi)
        self._olcu_listesi = [o for o in self._olcu_listesi if o.id != olcu_id]
        if len(self._olcu_listesi) < onceki_uzunluk:
            logger.debug("Ölçüm silindi: id=%d", olcu_id)
        else:
            logger.warning("Silinecek ölçüm bulunamadı: id=%d", olcu_id)

    def olcu_listesi_al(self) -> list[Olcu]:
        return list(self._olcu_listesi)

    def olculeri_temizle(self):
        self._olcu_listesi = []
        self._olcu_sayac = 0
        logger.debug("Tüm ölçümler temizlendi.")

    def kapat(self):
        if self._doc:
            self._doc.close()
            self._doc = None
        logger.debug("PDF belgesi kapatıldı.")
