"""
Tedarikçi Fiyat Karşılaştırma Modülü
Veritabanına kaydedilen tedarikçi fiyatlarını karşılaştırır.
"""

from typing import Optional, Dict, List, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class TedarikciEngine:
    """
    Tedarikçi fiyat karşılaştırma sınıfı.
    Veritabanındaki tedarikci_fiyatlari tablosunu kullanır.
    """

    def __init__(self, db=None):
        self.db = db

    def get_tedarikci_listesi(self) -> List[Dict]:
        """Tüm tedarikçileri listele."""
        if self.db:
            items = self.db.get_tedarikci_listesi()
            if items:
                for item in items:
                    item['aktif'] = bool(item.get('aktif', 1))
                return items
        return []

    def karsilastir_fiyatlar(
        self,
        malzeme_kodu: str,
        miktar: float = 1.0
    ) -> List[Dict[str, Any]]:
        """
        Verilen malzeme kodu için tüm tedarikçilerin DB'deki fiyatlarını karşılaştırır.
        En ucuzdan en pahalıya sıralı liste döndürür.
        """
        if not self.db or not malzeme_kodu:
            return []

        kayitlar = self.db.get_tedarikci_fiyatlari(malzeme_kodu=malzeme_kodu)

        if not kayitlar:
            return []

        fiyatlar = []
        for kayit in kayitlar:
            birim_fiyat = kayit.get('birim_fiyat', 0) or 0
            indirim_orani = kayit.get('indirim_orani', 0) or 0
            kdv_orani = kayit.get('kdv_orani', 20) or 20

            indirimli_birim_fiyat = birim_fiyat * (1 - indirim_orani / 100)
            toplam_fiyat = indirimli_birim_fiyat * miktar
            kdv_tutari = toplam_fiyat * (kdv_orani / 100)
            genel_toplam = toplam_fiyat + kdv_tutari

            fiyatlar.append({
                'fiyat_id': kayit.get('id'),
                'tedarikci_id': kayit.get('tedarikci_id'),
                'tedarikci_ad': kayit.get('tedarikci_ad', ''),
                'malzeme_kodu': malzeme_kodu,
                'malzeme_adi': kayit.get('malzeme_adi', ''),
                'miktar': miktar,
                'birim': kayit.get('birim', ''),
                'birim_fiyat': round(birim_fiyat, 2),
                'indirim_orani': indirim_orani,
                'indirimli_birim_fiyat': round(indirimli_birim_fiyat, 2),
                'kdv': round(kdv_tutari, 2),
                'kdv_orani': kdv_orani,
                'genel_toplam': round(genel_toplam, 2),
                'teslimat_suresi': kayit.get('teslimat_suresi', '') or '',
                'stok_durumu': kayit.get('stok_durumu', '') or '',
                'gecerlilik_tarihi': kayit.get('gecerlilik_tarihi', '') or '',
                'notlar': kayit.get('notlar', '') or '',
            })

        # En ucuzdan en pahalıya sırala
        fiyatlar.sort(key=lambda x: x['genel_toplam'])

        if fiyatlar:
            fiyatlar[0]['en_ucuz'] = True
            fiyatlar[-1]['en_pahali'] = True
            ortalama = sum(f['genel_toplam'] for f in fiyatlar) / len(fiyatlar)
            for f in fiyatlar:
                fark = f['genel_toplam'] - ortalama
                f['ortalamadan_fark'] = round(fark, 2)
                f['ortalamadan_fark_yuzde'] = round((fark / ortalama) * 100, 2) if ortalama else 0

        return fiyatlar

    def hesapla_tasarruf(self, fiyatlar: List[Dict]) -> Dict[str, Any]:
        """
        Verilen karşılaştırma listesinden tasarruf bilgisi hesaplar.
        (fiyatlar zaten karsilastir_fiyatlar() sonucu olmalı)
        """
        if len(fiyatlar) < 2:
            return {
                'tasarruf': 0.0,
                'tasarruf_yuzde': 0.0,
                'en_ucuz_tedarikci': fiyatlar[0]['tedarikci_ad'] if fiyatlar else '',
                'en_ucuz_fiyat': fiyatlar[0]['genel_toplam'] if fiyatlar else 0,
                'en_pahali_tedarikci': '',
                'en_pahali_fiyat': 0,
                'mesaj': 'Karşılaştırma için en az 2 tedarikçi fiyatı gerekli'
            }

        en_ucuz = fiyatlar[0]
        en_pahali = fiyatlar[-1]
        tasarruf = en_pahali['genel_toplam'] - en_ucuz['genel_toplam']
        tasarruf_yuzde = (tasarruf / en_pahali['genel_toplam']) * 100 if en_pahali['genel_toplam'] else 0

        return {
            'en_ucuz_tedarikci': en_ucuz['tedarikci_ad'],
            'en_ucuz_fiyat': en_ucuz['genel_toplam'],
            'en_pahali_tedarikci': en_pahali['tedarikci_ad'],
            'en_pahali_fiyat': en_pahali['genel_toplam'],
            'tasarruf': round(tasarruf, 2),
            'tasarruf_yuzde': round(tasarruf_yuzde, 2),
            'mesaj': (
                f'{en_ucuz["tedarikci_ad"]} tercih edilerek '
                f'{round(tasarruf, 2):,.2f} ₺ tasarruf edilir '
                f'(%{round(tasarruf_yuzde, 2):.1f})'
            )
        }
