"""
Yaklaşık Maliyet ve Keşif Özeti Motoru
4734 Sayılı Kamu İhale Kanunu kapsamında yaklaşık maliyet hesabı.

Desteklenen kurum fiyat listeleri:
- ÇŞB : Çevre, Şehircilik ve İklim Bakanlığı (Yapım işleri)
- DSİ : Devlet Su İşleri
- KGM : Karayolları Genel Müdürlüğü
- İLBANK: İller Bankası (Belediye altyapısı)

Hesaplanan değerler:
- Poz bazlı tutar (miktar × birim fiyat)
- Toplam yapım bedeli
- KDV tutarı
- Genel toplam (KDV dahil)
- Aşırı düşük teklif sınır değeri
- Resmi keşif özeti formatında export
"""

from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
from typing import Optional, Dict, List, Any, Tuple
import logging

logger = logging.getLogger(__name__)

# ============================================================
# KURUM FİYAT LİSTESİ TANIMLARI
# ============================================================

KURUM_LISTESI = {
'csb': 'ÇŞB — Çevre, Şehircilik ve İklim Bakanlığı',
'dsi': 'DSİ — Devlet Su İşleri',
'kgm': 'KGM — Karayolları Genel Müdürlüğü',
'ilbank': 'İLBANK — İller Bankası',
'ozel': 'Özel / Piyasa Fiyatı',
}

# KDV oranları (%)
KDV_ORANLARI = {
'standard': Decimal('20'), # Genel KDV oranı (2023 sonrası)
'insaat': Decimal('20'), # İnşaat KDV oranı
'muaf': Decimal('0'), # KDV muaf (bazı kamu ihaleleri)
}

# Aşırı düşük teklif hesabı için eşik katılımcı sayıları
# 4734 KİK md.38: Sınır değer = (teklifler toplamı - en yüksek - en düşük) / (n-2) × 0.80
ASIRI_DUSUK_KATSAYI = Decimal('0.80')


# ============================================================
# ÖRNEK RESMİ POZ VERİTABANI (ÇŞB 2025 Yapım Birim Fiyatları)
# Gerçek uygulamada PDF'ten veya API'den çekilecek
# ============================================================

CSB_BIRIM_FIYATLARI_2025: Dict[str, Dict[str, Any]] = {
# ---- TOPRAK İŞLERİ ----
'16.001': {'tanim': 'Her derinlikte kaya olmayan zeminlerde makineyle kazı', 'birim': 'm³', 'fiyat': Decimal('148.50')},
'16.002': {'tanim': 'Bitkisel toprak sıyrılması', 'birim': 'm²', 'fiyat': Decimal('28.40')},
'16.003': {'tanim': 'Dolguda kullanılan zeminin serilip sıkıştırılması', 'birim': 'm³', 'fiyat': Decimal('112.00')},

# ---- BETON İŞLERİ ----
'21.001': {'tanim': 'C16/20 beton - Grobeton', 'birim': 'm³', 'fiyat': Decimal('3_820.00')},
'21.002': {'tanim': 'C25/30 beton - Temel', 'birim': 'm³', 'fiyat': Decimal('4_650.00')},
'21.003': {'tanim': 'C25/30 beton - Kolon, kiriş, döşeme', 'birim': 'm³', 'fiyat': Decimal('4_890.00')},
'21.004': {'tanim': 'C30/37 beton - Perde', 'birim': 'm³', 'fiyat': Decimal('5_120.00')},
'21.011': {'tanim': 'Kalıp yapılması, sökülmesi (Kolon, kiriş, döşeme)', 'birim': 'm²', 'fiyat': Decimal('580.00')},
'21.012': {'tanim': 'Kalıp yapılması, sökülmesi (Temel, perde)', 'birim': 'm²', 'fiyat': Decimal('520.00')},
'21.021': {'tanim': 'Çelik hasır donatı (Q131 - Q335)', 'birim': 'kg', 'fiyat': Decimal('42.80')},
'21.022': {'tanim': 'Nervürlü çelik çubuk donatı (S420)', 'birim': 'kg', 'fiyat': Decimal('38.50')},

# ---- DUVAR İŞLERİ ----
'22.001': {'tanim': 'Tuğla duvar örülmesi (19×19×13.5)', 'birim': 'm²', 'fiyat': Decimal('820.00')},
'22.002': {'tanim': 'Gazbeton duvar örülmesi (20 cm)', 'birim': 'm²', 'fiyat': Decimal('760.00')},
'22.003': {'tanim': 'Briket duvar (20 cm)', 'birim': 'm²', 'fiyat': Decimal('680.00')},

# ---- SIVA İŞLERİ ----
'23.001': {'tanim': 'İç sıva (Kireç harçlı, el ile)', 'birim': 'm²', 'fiyat': Decimal('285.00')},
'23.002': {'tanim': 'Dış sıva (Çimento harçlı)', 'birim': 'm²', 'fiyat': Decimal('340.00')},
'23.003': {'tanim': 'Alçı sıva (İnce, makine ile)', 'birim': 'm²', 'fiyat': Decimal('220.00')},

# ---- BOYA İŞLERİ ----
'24.001': {'tanim': 'İç cephe su bazlı boya (2 kat + astar)', 'birim': 'm²', 'fiyat': Decimal('185.00')},
'24.002': {'tanim': 'Dış cephe silikon esaslı boya', 'birim': 'm²', 'fiyat': Decimal('320.00')},
'24.003': {'tanim': 'Antipas + yağlı boya (Çelik yüzey)', 'birim': 'm²', 'fiyat': Decimal('280.00')},

# ---- DÖŞEME İŞLERİ ----
'25.001': {'tanim': 'Seramik döşeme (30×30 - 60×60)', 'birim': 'm²', 'fiyat': Decimal('520.00')},
'25.002': {'tanim': 'Granit / mermer döşeme', 'birim': 'm²', 'fiyat': Decimal('1_250.00')},
'25.003': {'tanim': 'Şap (Tesviye betonu, 5 cm)', 'birim': 'm²', 'fiyat': Decimal('195.00')},

# ---- YALITIM ----
'26.001': {'tanim': 'Isı yalıtımı (EPS 5 cm, mantolama)', 'birim': 'm²', 'fiyat': Decimal('480.00')},
'26.002': {'tanim': 'Su yalıtımı (Bitümlü membran, 2 kat)', 'birim': 'm²', 'fiyat': Decimal('380.00')},
'26.003': {'tanim': 'XPS yalıtım (5 cm, teras çatı)', 'birim': 'm²', 'fiyat': Decimal('520.00')},

# ---- ÇATI ----
'27.001': {'tanim': 'Kiremit kaplama (Beton kiremit)', 'birim': 'm²', 'fiyat': Decimal('620.00')},
'27.002': {'tanim': 'Trapez sac çatı kaplama', 'birim': 'm²', 'fiyat': Decimal('780.00')},

# ---- ELEKTRİK ----
'30.001': {'tanim': 'Sıva altı tesisat borusu + kablo', 'birim': 'm', 'fiyat': Decimal('180.00')},
'30.002': {'tanim': 'Priz (Topraklı, 16A)', 'birim': 'adet', 'fiyat': Decimal('320.00')},
'30.003': {'tanim': 'Aydınlatma armatürü montajı (LED panel)', 'birim': 'adet', 'fiyat': Decimal('480.00')},

# ---- MEKANİK TESİSAT ----
'31.001': {'tanim': 'Plastik boru tesisat (Ø32-Ø110)', 'birim': 'm', 'fiyat': Decimal('285.00')},
'31.002': {'tanim': 'Kombi montajı (24 kW)', 'birim': 'adet', 'fiyat': Decimal('8_500.00')},
'31.003': {'tanim': 'Banyo tesisatı (Klozet, lavabo, duş)', 'birim': 'set', 'fiyat': Decimal('12_800.00')},

# ---- PENCERE / KAPI ----
'33.001': {'tanim': 'PVC pencere (Tek kanat, Enerji sınıfı A)', 'birim': 'm²', 'fiyat': Decimal('2_800.00')},
'33.002': {'tanim': 'PVC balkon kapısı (Çift kanat)', 'birim': 'm²', 'fiyat': Decimal('3_200.00')},
'33.003': {'tanim': 'Çelik kapı montajı', 'birim': 'adet', 'fiyat': Decimal('4_500.00')},
}


class YaklasikMaliyetKalemi:
    """
    Keşif / yaklaşık maliyet cetveli tek satırı.

    Her satır bir poz kalemini temsil eder:
    poz_no × miktar × birim_fiyat = tutar
    """

    def __init__(
    self,
    sira_no: int,
    poz_no: str,
    tanim: str,
    birim: str,
    miktar: Decimal,
    birim_fiyat: Decimal,
    kurum: str = 'csb',
    aciklama: str = '',
    ):
        self.sira_no = sira_no
    self.poz_no = poz_no
    self.tanim = tanim
    self.birim = birim
    self.miktar = miktar
    self.birim_fiyat = birim_fiyat
    self.kurum = kurum
    self.aciklama = aciklama

    @property
    def tutar(self) -> Decimal:
        """Kalem tutarı = miktar × birim fiyat (2 ondalık hassasiyet)."""
        return (self.miktar * self.birim_fiyat).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP
        )

        def to_dict(self) -> Dict[str, Any]:
            return {
            'sira_no': self.sira_no,
            'poz_no': self.poz_no,
            'tanim': self.tanim,
            'birim': self.birim,
            'miktar': float(self.miktar),
            'birim_fiyat': float(self.birim_fiyat),
            'tutar': float(self.tutar),
            'kurum': self.kurum,
            'aciklama': self.aciklama,
            }


class YaklasikMaliyetEngine:
    """
    Yaklaşık maliyet hesaplama motoru.

    Neyi çözüyoruz:
    4734 KİK kapsamında müteahhitin ihaleye girmeden önce
    kendi keşfini yapması ve teklifini konumlandırması.
    Aşırı düşük sınırın tespiti teklif reddini önler.

    Nasıl test ederiz:
    - Bilinen poz + miktar girişiyle beklenen toplam doğrula
    - KDV tutarı = toplam × kdv_orani / 100 kontrolü
    - Aşırı düşük sınır = yaklaşık maliyet × 0.80 kontrolü
    """

    def __init__(self):
        self.kalemler: List[YaklasikMaliyetKalemi] = []
        self.proje_adi: str = ''
        self.ihale_no: str = ''
        self.idare: str = ''
        self.kurum: str = 'csb' # Varsayılan fiyat listesi
        self.kdv_orani: Decimal = KDV_ORANLARI['standard']
        self.olusturma_tarihi: datetime = datetime.now()
        self._sira_sayac: int = 0

        # ------------------------------------------------------------------ #
        # KALEM YÖNETİMİ
        # ------------------------------------------------------------------ #

        def kalem_ekle(
        self,
        poz_no: str,
        miktar: float,
        birim_fiyat: Optional[float] = None,
        tanim: Optional[str] = None,
        birim: Optional[str] = None,
        aciklama: str = '',
        ) -> YaklasikMaliyetKalemi:
            """
        Keşif cetveline yeni kalem ekle.

        Poz no resmi listede varsa otomatik doldurur; birim fiyat
        override edilmek istenirse açıkça verilir.

        Args:
        poz_no : Resmi poz numarası (örn: '21.003')
        miktar : Metraj miktarı
        birim_fiyat : Opsiyonel override; yoksa resmi fiyat alınır
        tanim : Opsiyonel override; yoksa resmi tanım alınır
        birim : Opsiyonel override; yoksa resmi birim alınır
        aciklama : Serbest not alanı

        Returns:
        Eklenen YaklasikMaliyetKalemi nesnesi
        """
        self._sira_sayac += 1

        # Resmi listeden fiyat çek
        resmi = CSB_BIRIM_FIYATLARI_2025.get(poz_no, {})

        kalem = YaklasikMaliyetKalemi(
        sira_no=self._sira_sayac,
        poz_no=poz_no,
        tanim=tanim or resmi.get('tanim', 'Tanımsız Kalem'),
        birim=birim or resmi.get('birim', 'adet'),
        miktar=Decimal(str(miktar)),
        birim_fiyat=Decimal(str(birim_fiyat)) if birim_fiyat else resmi.get('fiyat', Decimal('0')),
        kurum=self.kurum,
        aciklama=aciklama,
        )
        self.kalemler.append(kalem)
        logger.debug(f"Kalem eklendi: {poz_no} — {kalem.tanim} — {float(kalem.tutar):,.2f} TL")
        return kalem

        def kalem_sil(self, sira_no: int) -> bool:
            """Sıra numarasına göre kalem sil."""
            onceki_uzunluk = len(self.kalemler)
            self.kalemler = [k for k in self.kalemler if k.sira_no != sira_no]
            return len(self.kalemler) < onceki_uzunluk

            def kalem_guncelle(self, sira_no: int, miktar: Optional[float] = None,
            birim_fiyat: Optional[float] = None) -> bool:
                """Miktar veya birim fiyatı güncelle."""
            for kalem in self.kalemler:
                if kalem.sira_no == sira_no:
                    if miktar is not None:
                        kalem.miktar = Decimal(str(miktar))
                        if birim_fiyat is not None:
                            kalem.birim_fiyat = Decimal(str(birim_fiyat))
                            return True
                            return False

                            def poz_ara(self, arama: str) -> List[Dict[str, Any]]:
                                """
                                Resmi poz listesinde poz no veya tanımda arama yap.

                                Args:
                                arama: Aranacak metin (poz no veya tanım kelimesi)

                                Returns:
                                Eşleşen pozların listesi
                                """
                                arama_lower = arama.lower()
                                sonuclar = []
                                for poz_no, bilgi in CSB_BIRIM_FIYATLARI_2025.items():
                                    if (arama_lower in poz_no.lower() or
                                    arama_lower in bilgi['tanim'].lower()):
                                        sonuclar.append({
                                    'poz_no': poz_no,
                                    'tanim': bilgi['tanim'],
                                    'birim': bilgi['birim'],
                                    'fiyat': float(bilgi['fiyat']),
                                    })
                                    return sorted(sonuclar, key=lambda x: x['poz_no'])

                                    # ------------------------------------------------------------------ #
                                    # ANA HESAPLAMA
                                    # ------------------------------------------------------------------ #

                                    def hesapla(self) -> Dict[str, Any]:
                                        """
                                        Tam yaklaşık maliyet hesabını yap.

                                        Returns:
                                        {
                                        'toplam_yapim': float, # KDV hariç yapım bedeli
                                        'kdv_tutari': float,
                                        'genel_toplam': float, # KDV dahil
                                        'asiri_dusuk_sinir': float, # %80 sınır
                                        'kdv_orani': float,
                                        'kalem_sayisi': int,
                                        'kalemler': List[dict],
                                        }
                                        """
                                        if not self.kalemler:
                                            return {'hata': 'Keşif cetveli boş. Lütfen kalem ekleyin.'}

                                            toplam_yapim = sum(k.tutar for k in self.kalemler)
                                            kdv_tutari = (toplam_yapim * self.kdv_orani / Decimal('100')).quantize(
                                            Decimal('0.01'), rounding=ROUND_HALF_UP
                                            )
                                            genel_toplam = toplam_yapim + kdv_tutari

                                            # Aşırı düşük sınır: yaklaşık maliyetin %80'i
                                            # (4734 md.38 — gerçekte rekabet ortamına göre değişir)
                                            asiri_dusuk_sinir = (toplam_yapim * ASIRI_DUSUK_KATSAYI).quantize(
                                            Decimal('0.01'), rounding=ROUND_HALF_UP
                                            )

                                            return {
                                            'toplam_yapim': float(toplam_yapim),
                                            'kdv_tutari': float(kdv_tutari),
                                            'genel_toplam': float(genel_toplam),
                                            'asiri_dusuk_sinir': float(asiri_dusuk_sinir),
                                            'kdv_orani': float(self.kdv_orani),
                                            'kalem_sayisi': len(self.kalemler),
                                            'kalemler': [k.to_dict() for k in self.kalemler],
                                            'proje_adi': self.proje_adi,
                                            'ihale_no': self.ihale_no,
                                            'idare': self.idare,
                                            'kurum': KURUM_LISTESI.get(self.kurum, self.kurum),
                                            'tarih': self.olusturma_tarihi.strftime('%d.%m.%Y'),
                                            }

                                            def kategori_ozeti(self) -> List[Dict[str, Any]]:
                                                """
                                                Poz numarası prefix'ine göre kategori bazlı özet.
                                                Örn: 16.xxx = Toprak, 21.xxx = Beton ...
                                                """
                                                KATEGORI_MAP = {
                                                '16': 'Toprak İşleri',
                                                '21': 'Beton ve Betonarme',
                                                '22': 'Duvar İşleri',
                                                '23': 'Sıva İşleri',
                                                '24': 'Boya İşleri',
                                                '25': 'Döşeme İşleri',
                                                '26': 'Yalıtım',
                                                '27': 'Çatı İşleri',
                                                '30': 'Elektrik Tesisat',
                                                '31': 'Mekanik Tesisat',
                                                '33': 'Pencere ve Kapı',
                                                }

                                                kategori_tutarlar: Dict[str, Decimal] = {}
                                                for kalem in self.kalemler:
                                                    prefix = kalem.poz_no.split('.')[0]
                                                    kategori = KATEGORI_MAP.get(prefix, f'Diğer ({prefix})')
                                                    kategori_tutarlar[kategori] = (
                                                    kategori_tutarlar.get(kategori, Decimal('0')) + kalem.tutar
                                                    )

                                                    toplam = sum(kategori_tutarlar.values()) or Decimal('1')
                                                    return [
                                                    {
                                                    'kategori': kat,
                                                    'tutar': float(tutar),
                                                    'yuzde': float((tutar / toplam * 100).quantize(Decimal('0.1'))),
                                                    }
                                                    for kat, tutar in sorted(kategori_tutarlar.items(),
                                                    key=lambda x: x[1], reverse=True)
                                                    ]

                                                    # ------------------------------------------------------------------ #
                                                    # ASIRI DÜŞÜK TEKLİF ANALİZİ
                                                    # ------------------------------------------------------------------ #

                                                    def asiri_dusuk_analiz(self, teklifler: List[float]) -> Dict[str, Any]:
                                                        """
                                                        Birden fazla teklif varken aşırı düşük sınır değerini hesapla.
                                                        4734 KİK md.38 formülü: n >= 5 katılımcı olunca devreye girer.

                                                        Sınır değer = Geçerli tekliflerin aritmetik ortalaması × 0.80

                                                        Args:
                                                        teklifler: Geçerli teklif tutarları (TL, KDV hariç)

                                                        Returns:
                                                        Sınır değer, durum ve analiz detayı
                                                        """
                                                        if len(teklifler) < 2:
                                                            return {
                                                            'sinir_deger': None,
                                                            'durum': 'Yetersiz teklif sayısı (min 2 gerekli)',
                                                            'katilimci_sayisi': len(teklifler),
                                                            }

                                                            teklifler_dec = [Decimal(str(t)) for t in teklifler]
                                                            teklifler_dec.sort()

                                                            # 5 ve üzeri teklifte en yüksek ve en düşük çıkarılır
                                                            if len(teklifler_dec) >= 5:
                                                                hesap_listesi = teklifler_dec[1:-1]
                                                            else:
                                                                hesap_listesi = teklifler_dec

                                                                ortalama = sum(hesap_listesi) / len(hesap_listesi)
                                                                sinir_deger = (ortalama * ASIRI_DUSUK_KATSAYI).quantize(
                                                                Decimal('0.01'), rounding=ROUND_HALF_UP
                                                                )

                                                                analizler = []
                                                                for i, teklif in enumerate(teklifler_dec):
                                                                    durum = 'Normal' if teklif >= sinir_deger else 'Aşırı Düşük'
                                                                    analizler.append({
                                                                    'sira': i + 1,
                                                                    'teklif': float(teklif),
                                                                    'durum': durum,
                                                                    'sinirin_yuzdesi': float(
                                                                    (teklif / sinir_deger * 100).quantize(Decimal('0.1'))
                                                                    ),
                                                                    })

                                                                    return {
                                                                    'sinir_deger': float(sinir_deger),
                                                                    'ortalama_teklif': float(ortalama),
                                                                    'katilimci_sayisi': len(teklifler),
                                                                    'asiri_dusuk_sayisi': sum(1 for a in analizler if a['durum'] == 'Aşırı Düşük'),
                                                                    'teklifler': analizler,
                                                                    }

                                                                    # ------------------------------------------------------------------ #
                                                                    # EXPORT
                                                                    # ------------------------------------------------------------------ #

                                                                    def export_kesif_ozeti_dict(self) -> Dict[str, Any]:
                                                                        """
                                                                        Resmi keşif özeti formatında veri döndür.
                                                                        Excel/PDF export için hazır yapı.
                                                                        """
                                                                        sonuc = self.hesapla()
                                                                        if 'hata' in sonuc:
                                                                            return sonuc

                                                                            return {
                                                                            'baslik': {
                                                                            'idare': self.idare or 'İdare Adı Girilmedi',
                                                                            'proje_adi': self.proje_adi or 'Proje Adı Girilmedi',
                                                                            'ihale_no': self.ihale_no or '---',
                                                                            'fiyat_listesi': KURUM_LISTESI.get(self.kurum, self.kurum),
                                                                            'tarih': self.olusturma_tarihi.strftime('%d.%m.%Y'),
                                                                            'yil': self.olusturma_tarihi.year,
                                                                            },
                                                                            'kalemler': sonuc['kalemler'],
                                                                            'ozet': {
                                                                            'toplam_yapim_bedeli': sonuc['toplam_yapim'],
                                                                            'kdv_orani': sonuc['kdv_orani'],
                                                                            'kdv_tutari': sonuc['kdv_tutari'],
                                                                            'genel_toplam': sonuc['genel_toplam'],
                                                                            'asiri_dusuk_sinir': sonuc['asiri_dusuk_sinir'],
                                                                            },
                                                                            'kategori_dagilimi': self.kategori_ozeti(),
                                                                            }

                                                                            def to_excel_rows(self) -> List[List[Any]]:
                                                                                """
                                                                                Excel export için satır listesi döndür.
                                                                                Her satır: [Sıra, Poz No, Tanım, Birim, Miktar, Birim Fiyat, Tutar]
                                                                                """
                                                                                rows = []
                                                                                for k in self.kalemler:
                                                                                    rows.append([
                                                                                    k.sira_no,
                                                                                    k.poz_no,
                                                                                    k.tanim,
                                                                                    k.birim,
                                                                                    float(k.miktar),
                                                                                    float(k.birim_fiyat),
                                                                                    float(k.tutar),
                                                                                    ])
                                                                                    return rows

                                                                                    def __repr__(self):
                                                                                        sonuc = self.hesapla()
                                                                                        if 'hata' in sonuc:
                                                                                            return f"YaklasikMaliyetEngine(boş)"
                                                                                            return (
                                                                                            f"YaklasikMaliyetEngine("
                                                                                            f"kalem={sonuc['kalem_sayisi']}, "
                                                                                            f"toplam={sonuc['genel_toplam']:,.2f} TL)"
                                                                                            )
