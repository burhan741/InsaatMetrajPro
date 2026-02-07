"""
Tedarikçi API Entegrasyonu ve Fiyat Karşılaştırma Modülü
Çeşitli tedarikçilerden güncel fiyat bilgilerini çeker
"""

import requests
import json
from typing import Optional, Dict, List, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class TedarikciEngine:
    """
    Tedarikçi API entegrasyonu ve fiyat karşılaştırma sınıfı.

    Çeşitli tedarikçilerden (Demirbaş, Seval, vb.) güncel malzeme fiyatlarını
    çeker ve karşılaştırma yapar.
    """

    def __init__(self):
        """Tedarikçi motoru başlat."""
        self.tedarikci_listesi = [
            {
                'id': 1,
                'ad': 'Demirbaş İnşaat',
                'api_url': None,  # Gerçek API URL'si eklenecek
                'aktif': True
            },
            {
                'id': 2,
                'ad': 'Seval Yapı',
                'api_url': None,
                'aktif': True
            },
            {
                'id': 3,
                'ad': 'Hilti Türkiye',
                'api_url': None,
                'aktif': True
            },
            {
                'id': 4,
                'ad': 'Çimsa Çimento',
                'api_url': None,
                'aktif': True
            },
            {
                'id': 5,
                'ad': 'İzocam',
                'api_url': None,
                'aktif': True
            }
        ]
        self.cache = {}

    def get_tedarikci_listesi(self) -> List[Dict]:
        """
        Tüm tedarikçileri listele.

        Returns:
            Tedarikçi listesi
        """
        return self.tedarikci_listesi

    def get_tedarikci_fiyati(
        self,
        tedarikci_id: int,
        malzeme_kodu: str,
        miktar: float = 1.0
    ) -> Optional[Dict[str, Any]]:
        """
        Belirli bir tedarikçiden malzeme fiyatı çeker.

        Args:
            tedarikci_id: Tedarikçi ID
            malzeme_kodu: Malzeme/ürün kodu
            miktar: Miktar (varsayılan: 1)

        Returns:
            Fiyat bilgisi veya None
        """
        tedarikci = next((t for t in self.tedarikci_listesi if t['id'] == tedarikci_id), None)

        if not tedarikci:
            logger.error(f"Tedarikçi bulunamadı: {tedarikci_id}")
            return None

        if not tedarikci['aktif']:
            logger.warning(f"Tedarikçi aktif değil: {tedarikci['ad']}")
            return None

        # Cache kontrolü
        cache_key = f"{tedarikci_id}_{malzeme_kodu}_{miktar}"
        if cache_key in self.cache:
            logger.info(f"Cache'den fiyat döndürülüyor: {cache_key}")
            return self.cache[cache_key]

        # Gerçek API entegrasyonu buraya eklenecek
        # Şimdilik örnek veri döndürelim
        fiyat_bilgisi = self._get_sample_fiyat(tedarikci_id, malzeme_kodu, miktar)

        if fiyat_bilgisi:
            self.cache[cache_key] = fiyat_bilgisi

        return fiyat_bilgisi

    def _get_sample_fiyat(
        self,
        tedarikci_id: int,
        malzeme_kodu: str,
        miktar: float
    ) -> Dict[str, Any]:
        """
        Örnek fiyat verisi döndürür (gerçek API entegrasyonu için placeholder).

        Args:
            tedarikci_id: Tedarikçi ID
            malzeme_kodu: Malzeme kodu
            miktar: Miktar

        Returns:
            Örnek fiyat bilgisi
        """
        tedarikci = next((t for t in self.tedarikci_listesi if t['id'] == tedarikci_id), None)

        # Örnek fiyat hesaplama (tedarikçiye göre değişken)
        base_price = 100.0

        # Tedarikçiye göre fiyat varyasyonu
        tedarikci_carpanlari = {
            1: 1.0,   # Demirbaş
            2: 0.95,  # Seval (%5 daha ucuz)
            3: 1.15,  # Hilti (%15 daha pahalı - premium)
            4: 1.02,  # Çimsa
            5: 0.98   # İzocam
        }

        carpan = tedarikci_carpanlari.get(tedarikci_id, 1.0)
        birim_fiyat = base_price * carpan

        # Miktar indirimi
        if miktar > 100:
            indirim_orani = 0.10  # %10 indirim
        elif miktar > 50:
            indirim_orani = 0.05  # %5 indirim
        else:
            indirim_orani = 0.0

        indirimli_fiyat = birim_fiyat * (1 - indirim_orani)
        toplam_fiyat = indirimli_fiyat * miktar

        return {
            'tedarikci_id': tedarikci_id,
            'tedarikci_ad': tedarikci['ad'] if tedarikci else 'Bilinmeyen',
            'malzeme_kodu': malzeme_kodu,
            'miktar': miktar,
            'birim': 'm³',  # Dinamik olarak ayarlanabilir
            'birim_fiyat': round(birim_fiyat, 2),
            'indirim_orani': indirim_orani * 100,
            'indirimli_birim_fiyat': round(indirimli_fiyat, 2),
            'toplam_fiyat': round(toplam_fiyat, 2),
            'kdv': round(toplam_fiyat * 0.20, 2),  # %20 KDV
            'genel_toplam': round(toplam_fiyat * 1.20, 2),
            'para_birimi': 'TL',
            'tarih': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'teslimat_suresi': '3-5 gün',
            'stok_durumu': 'Stokta var',
            'notlar': f'{tedarikci["ad"]} örnek fiyat bilgisi'
        }

    def karsilastir_fiyatlar(
        self,
        malzeme_kodu: str,
        miktar: float = 1.0
    ) -> List[Dict[str, Any]]:
        """
        Tüm tedarikçilerden fiyat çeker ve karşılaştırır.

        Args:
            malzeme_kodu: Malzeme kodu
            miktar: Miktar

        Returns:
            Fiyat karşılaştırma listesi (en ucuzdan en pahalıya)
        """
        fiyatlar = []

        for tedarikci in self.tedarikci_listesi:
            if not tedarikci['aktif']:
                continue

            fiyat = self.get_tedarikci_fiyati(
                tedarikci['id'],
                malzeme_kodu,
                miktar
            )

            if fiyat:
                fiyatlar.append(fiyat)

        # En ucuzdan en pahalıya sırala
        fiyatlar.sort(key=lambda x: x['genel_toplam'])

        # En ucuz ve en pahalı işaretle
        if fiyatlar:
            fiyatlar[0]['en_ucuz'] = True
            fiyatlar[-1]['en_pahali'] = True

            # Ortalama fiyat hesapla
            ortalama = sum(f['genel_toplam'] for f in fiyatlar) / len(fiyatlar)

            for fiyat in fiyatlar:
                fark = fiyat['genel_toplam'] - ortalama
                fark_yuzde = (fark / ortalama) * 100
                fiyat['ortalamadan_fark'] = round(fark, 2)
                fiyat['ortalamadan_fark_yuzde'] = round(fark_yuzde, 2)

        return fiyatlar

    def get_en_ucuz_tedarikci(
        self,
        malzeme_kodu: str,
        miktar: float = 1.0
    ) -> Optional[Dict[str, Any]]:
        """
        En ucuz tedarikçiyi bul.

        Args:
            malzeme_kodu: Malzeme kodu
            miktar: Miktar

        Returns:
            En ucuz fiyat bilgisi
        """
        fiyatlar = self.karsilastir_fiyatlar(malzeme_kodu, miktar)

        if fiyatlar:
            return fiyatlar[0]

        return None

    def hesapla_tasarruf(
        self,
        malzeme_kodu: str,
        miktar: float = 1.0
    ) -> Dict[str, Any]:
        """
        En ucuz ve en pahalı arasındaki tasarrufu hesaplar.

        Args:
            malzeme_kodu: Malzeme kodu
            miktar: Miktar

        Returns:
            Tasarruf bilgisi
        """
        fiyatlar = self.karsilastir_fiyatlar(malzeme_kodu, miktar)

        if len(fiyatlar) < 2:
            return {
                'tasarruf': 0.0,
                'tasarruf_yuzde': 0.0,
                'mesaj': 'Yeterli fiyat verisi yok'
            }

        en_ucuz = fiyatlar[0]['genel_toplam']
        en_pahali = fiyatlar[-1]['genel_toplam']

        tasarruf = en_pahali - en_ucuz
        tasarruf_yuzde = (tasarruf / en_pahali) * 100

        return {
            'en_ucuz_tedarikci': fiyatlar[0]['tedarikci_ad'],
            'en_ucuz_fiyat': round(en_ucuz, 2),
            'en_pahali_tedarikci': fiyatlar[-1]['tedarikci_ad'],
            'en_pahali_fiyat': round(en_pahali, 2),
            'tasarruf': round(tasarruf, 2),
            'tasarruf_yuzde': round(tasarruf_yuzde, 2),
            'mesaj': f'{fiyatlar[0]["tedarikci_ad"]} tercih ederek {round(tasarruf, 2)} TL tasarruf edilir (%{round(tasarruf_yuzde, 2)})'
        }

    def export_fiyat_karsilastirma(
        self,
        malzeme_kodu: str,
        miktar: float = 1.0
    ) -> Dict[str, Any]:
        """
        Fiyat karşılaştırmasını export için formatlar.

        Args:
            malzeme_kodu: Malzeme kodu
            miktar: Miktar

        Returns:
            Export için formatlanmış veri
        """
        fiyatlar = self.karsilastir_fiyatlar(malzeme_kodu, miktar)
        tasarruf = self.hesapla_tasarruf(malzeme_kodu, miktar)

        return {
            'malzeme_kodu': malzeme_kodu,
            'miktar': miktar,
            'tarih': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'fiyatlar': fiyatlar,
            'tasarruf_bilgisi': tasarruf,
            'tedarikci_sayisi': len(fiyatlar)
        }


# Test kodu
if __name__ == "__main__":
    # Loglama ayarla
    logging.basicConfig(level=logging.INFO)

    # Motor oluştur
    engine = TedarikciEngine()

    print("\n=== TEDARİKÇİ LİSTESİ ===")
    for tedarikci in engine.get_tedarikci_listesi():
        print(f"- {tedarikci['ad']} (ID: {tedarikci['id']})")

    print("\n=== FİYAT KARŞILAŞTIRMA ===")
    karsilastirma = engine.karsilastir_fiyatlar("BETON-C30", miktar=10)

    for fiyat in karsilastirma:
        ucuz_tag = " [EN UCUZ]" if fiyat.get('en_ucuz') else ""
        pahali_tag = " [EN PAHALI]" if fiyat.get('en_pahali') else ""
        print(f"\n{fiyat['tedarikci_ad']}{ucuz_tag}{pahali_tag}")
        print(f"  Birim Fiyat: {fiyat['birim_fiyat']} TL")
        print(f"  İndirim: %{fiyat['indirim_orani']}")
        print(f"  Genel Toplam: {fiyat['genel_toplam']} TL (KDV Dahil)")
        print(f"  Ortalamadan Fark: {fiyat.get('ortalamadan_fark', 0)} TL")

    print("\n=== TASARRUF ANALİZİ ===")
    tasarruf = engine.hesapla_tasarruf("BETON-C30", miktar=10)
    print(tasarruf['mesaj'])
