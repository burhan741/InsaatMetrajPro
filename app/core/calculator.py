"""
Hesaplama Motoru
Metraj ve maliyet hesaplamaları için core modül
"""

from typing import List, Dict, Any, Optional
from decimal import Decimal, ROUND_HALF_UP
import math


# =============================================================================
# SABİTLER - Verimlilik ve Malzeme Sarfiyat Veritabanları
# =============================================================================

# Verimlilik (Hız) Veritabanı (m²/Gün - 1 Usta + 1 Yardımcı Ekip İçin)
VERIMLILIK_VERITABANI = {
 'piyasa': {
 # Özel Sektör - Hızlı çalışma temposu
 'bims_19': 22, # Bims 19 cm
 'tugla_13.5': 20, # Tuğla 13.5 cm
 'gazbeton_15': 28 # Gazbeton 15 cm
 },
 'csb_resmi': {
 # Çevre Şehircilik Bakanlığı Resmi Analizi - Yavaş (resmi)
 'bims_19': 14,
 'tugla_13.5': 12,
 'gazbeton_15': 16
 }
}

# Malzeme Sarfiyatları (Sabit Değerler)
MALZEME_SARFIYAT = {
 'bims_19': {
 'adet_m2': 13, # adet/m²
 'harc_m3_m2': 0.035 # m³/m² harç
 },
 'tugla_13.5': {
 'adet_m2': 26, # adet/m²
 'harc_m3_m2': 0.035 # m³/m² harç
 },
 'gazbeton_15': {
 'adet_m2': 13, # adet/m²
 'yapistirici_kg_m2': 4 # kg/m² yapıştırıcı
 }
}

# Harç Karışım Oranları (1 m³ Harç için)
HARC_KARISIM = {
 'kum_m3': 1, # 1 m³ Kum
 'cimento_torba': 6 # 6 Torba (50 kg) Çimento
}

# =============================================================================
# ALÇI (SIVA) SABİTLERİ
# =============================================================================

# Makine Alçı Sarfiyat Sabitleri
ALCI_SARFIYAT = {
 'kg_m2_cm': 10.5, # 1 m² ve 1 cm kalınlık için kg alçı
 'torba_kg': 25, # Torba ağırlığı (kg)
 'ano_profil_m_m2': 0.70, # m² başına köşe profili (metre)
 'astar_kg_m2': 0.25 # m² başına astar sarfiyatı (kg)
}

# Alçı İşçilik Hızları (m²/Gün - Perdah Dahil)
ALCI_VERIMLILIK = {
 'piyasa': 90, # Özel Sektör: 80-100 m²/gün ortalaması
 'csb_resmi': 45 # ÇŞB Resmi: 40-50 m²/gün ortalaması
}

# =============================================================================
# KARA SIVA (EL İLE) SABİTLERİ
# =============================================================================

# Kara Sıva Harç Karışım Oranları (1 m³ Harç için)
KARA_SIVA_KARISIM = {
 'kum_m3': 1.1, # 1 m³ harç için 1.1 m³ kum (sıkışma payı dahil)
 'cimento_torba': 6, # 1 m³ harç için 6 torba (300 kg) çimento
 'torba_kg': 50 # Çimento torba ağırlığı (kg)
}

# Kara Sıva İşçilik Hızları (m²/Gün - 1 Usta + 1 Yardımcı, El ile)
KARA_SIVA_VERIMLILIK = {
 'piyasa': 22, # Özel Sektör: 20-25 m²/gün ortalaması
 'csb_resmi': 13 # ÇŞB Resmi Poz 27.501: 12-14 m²/gün ortalaması
}


def hesapla_kara_siva_manuel(
 duvar_m2: float,
 cimento_torba_fiyat: float,
 kum_m3_fiyat: float,
 ekip_gunluk_ucret: float,
 fire_orani: float,
 verim_kaynagi: str,
 ortalama_kalinlik_cm: float = 2.0,
 manuel_hiz: Optional[float] = None
) -> Dict[str, Any]:
 """
 Geleneksel kara sıva (el ile) maliyet hesaplama fonksiyonu.

 Harç yerde karılarak veya taşınarak uygulanan klasik sıva yöntemi.

 Args:
 duvar_m2: Toplam sıva yapılacak alan (m²)
 cimento_torba_fiyat: 50 kg'lık çimento torba fiyatı (TL)
 kum_m3_fiyat: Kum m³ fiyatı - nakliye dahil (TL)
 ekip_gunluk_ucret: Ekip günlük ücreti (1 Usta + 1 Yardımcı, TL)
 fire_orani: Fire oranı (Örn: 0.05 = %5)
 verim_kaynagi: Verimlilik kaynağı ('piyasa', 'csb_resmi', 'manuel')
 ortalama_kalinlik_cm: Ortalama sıva kalınlığı (cm), varsayılan 2.0
 manuel_hiz: Manuel hız değeri (m²/gün, sadece verim_kaynagi='manuel' ise)

 Returns:
 Dict: Detaylı maliyet analizi sonuçları

 Raises:
 ValueError: Geçersiz parametre değerleri için
 """

 # =========================================================================
 # 1. GİRDİ VALİDASYONU
 # =========================================================================

 gecerli_verim_kaynaklari = ['piyasa', 'csb_resmi', 'manuel']

 if verim_kaynagi not in gecerli_verim_kaynaklari:
 raise ValueError(
 f"Geçersiz verim kaynağı: '{verim_kaynagi}'. "
 f"Geçerli seçenekler: {gecerli_verim_kaynaklari}"
 )

 if duvar_m2 <= 0:
 raise ValueError("Duvar alanı 0'dan büyük olmalıdır.")

 if ortalama_kalinlik_cm <= 0:
 raise ValueError("Ortalama kalınlık 0'dan büyük olmalıdır.")

 if cimento_torba_fiyat < 0:
 raise ValueError("Çimento torba fiyatı negatif olamaz.")

 if kum_m3_fiyat < 0:
 raise ValueError("Kum m³ fiyatı negatif olamaz.")

 if ekip_gunluk_ucret < 0:
 raise ValueError("Ekip günlük ücreti negatif olamaz.")

 if fire_orani < 0 or fire_orani > 1:
 raise ValueError("Fire oranı 0 ile 1 arasında olmalıdır.")

 if verim_kaynagi == 'manuel':
 if manuel_hiz is None or manuel_hiz <= 0:
 raise ValueError(
 "Manuel verim kaynağı seçildiğinde 'manuel_hiz' değeri "
 "sıfırdan büyük bir değer olmalıdır."
 )

 # =========================================================================
 # 2. HIZ BELİRLEME
 # =========================================================================

 if verim_kaynagi == 'manuel':
 secilen_hiz = manuel_hiz
 else:
 secilen_hiz = KARA_SIVA_VERIMLILIK[verim_kaynagi]

 # =========================================================================
 # 3. HARÇ HACMİ HESAPLAMA
 # =========================================================================

 # Harç hacmi (m³) = Alan × (Kalınlık / 100)
 harc_hacmi_m3 = duvar_m2 * (ortalama_kalinlik_cm / 100)

 fire_katsayisi = 1 + fire_orani

 # =========================================================================
 # 4. MALZEME İHTİYACI HESAPLAMA (Fire Dahil)
 # =========================================================================

 # Kum ihtiyacı (m³)
 kum_ihtiyac_m3 = harc_hacmi_m3 * KARA_SIVA_KARISIM['kum_m3'] * fire_katsayisi
 gereken_kum_m3 = round(kum_ihtiyac_m3, 3)

 # Çimento ihtiyacı (torba - yukarı yuvarla)
 cimento_ihtiyac = harc_hacmi_m3 * KARA_SIVA_KARISIM['cimento_torba'] * fire_katsayisi
 gereken_cimento_torba = math.ceil(cimento_ihtiyac)

 # =========================================================================
 # 5. SÜRE HESAPLAMA (Yukarı Yuvarlama)
 # =========================================================================

 tahmini_sure_gun = math.ceil(duvar_m2 / secilen_hiz)

 # =========================================================================
 # 6. MALİYET HESAPLAMA
 # =========================================================================

 # İşçilik maliyeti
 toplam_iscilik_tl = tahmini_sure_gun * ekip_gunluk_ucret

 # Malzeme maliyetleri
 kum_maliyet = gereken_kum_m3 * kum_m3_fiyat
 cimento_maliyet = gereken_cimento_torba * cimento_torba_fiyat
 toplam_malzeme_tl = kum_maliyet + cimento_maliyet

 # =========================================================================
 # 7. GENEL TOPLAM MALİYET HESAPLAMA
 # =========================================================================

 genel_toplam_maliyet_tl = toplam_iscilik_tl + toplam_malzeme_tl

 # =========================================================================
 # 8. SONUÇ SÖZLÜĞÜ OLUŞTURMA
 # =========================================================================

 sonuc = {
 'baz_alinan_hiz_m2': secilen_hiz,
 'tahmini_sure_gun': tahmini_sure_gun,
 'gereken_kum_m3': gereken_kum_m3,
 'gereken_cimento_torba': gereken_cimento_torba,
 'kum_maliyet_tl': round(kum_maliyet, 2),
 'cimento_maliyet_tl': round(cimento_maliyet, 2),
 'toplam_iscilik_tl': round(toplam_iscilik_tl, 2),
 'toplam_malzeme_tl': round(toplam_malzeme_tl, 2),
 'genel_toplam_maliyet_tl': round(genel_toplam_maliyet_tl, 2)
 }

 return sonuc


def hesapla_alci_maliyet_detayli(
 uygulama_alani_m2: float,
 torba_birim_fiyat: float,
 ekip_gunluk_ucret: float,
 fire_orani: float,
 verim_kaynagi: str,
 ortalama_kalinlik_cm: float = 1.5,
 manuel_hiz: Optional[float] = None,
 ano_kullanimi: bool = False
) -> Dict[str, Any]:
 """
 Makine alçı (sıva) maliyet hesaplama fonksiyonu.

 Perdah dahil detaylı maliyet analizi yapar.

 Args:
 uygulama_alani_m2: Toplam uygulama alanı (m²)
 torba_birim_fiyat: 25 kg'lık torba birim fiyatı (TL)
 ekip_gunluk_ucret: Ekip günlük ücreti (TL)
 fire_orani: Fire oranı (Örn: 0.05 = %5)
 verim_kaynagi: Verimlilik kaynağı ('piyasa', 'csb_resmi', 'manuel')
 ortalama_kalinlik_cm: Ortalama alçı kalınlığı (cm), varsayılan 1.5
 manuel_hiz: Manuel hız değeri (m²/gün, sadece verim_kaynagi='manuel' ise)
 ano_kullanimi: Köşe profili/Ano kullanılacak mı?

 Returns:
 Dict: Detaylı maliyet analizi sonuçları

 Raises:
 ValueError: Geçersiz parametre değerleri için
 """

 # =========================================================================
 # 1. GİRDİ VALİDASYONU
 # =========================================================================

 gecerli_verim_kaynaklari = ['piyasa', 'csb_resmi', 'manuel']

 if verim_kaynagi not in gecerli_verim_kaynaklari:
 raise ValueError(
 f"Geçersiz verim kaynağı: '{verim_kaynagi}'. "
 f"Geçerli seçenekler: {gecerli_verim_kaynaklari}"
 )

 if uygulama_alani_m2 <= 0:
 raise ValueError("Uygulama alanı 0'dan büyük olmalıdır.")

 if ortalama_kalinlik_cm <= 0:
 raise ValueError("Ortalama kalınlık 0'dan büyük olmalıdır.")

 if torba_birim_fiyat < 0:
 raise ValueError("Torba birim fiyatı negatif olamaz.")

 if ekip_gunluk_ucret < 0:
 raise ValueError("Ekip günlük ücreti negatif olamaz.")

 if fire_orani < 0 or fire_orani > 1:
 raise ValueError("Fire oranı 0 ile 1 arasında olmalıdır.")

 if verim_kaynagi == 'manuel':
 if manuel_hiz is None or manuel_hiz <= 0:
 raise ValueError(
 "Manuel verim kaynağı seçildiğinde 'manuel_hiz' değeri "
 "sıfırdan büyük bir değer olmalıdır."
 )

 # =========================================================================
 # 2. HIZ BELİRLEME
 # =========================================================================

 if verim_kaynagi == 'manuel':
 secilen_hiz = manuel_hiz
 else:
 secilen_hiz = ALCI_VERIMLILIK[verim_kaynagi]

 # =========================================================================
 # 3. ALÇI MİKTARI HESAPLAMA
 # =========================================================================

 # Sabitler
 kg_m2_cm = ALCI_SARFIYAT['kg_m2_cm']
 torba_kg = ALCI_SARFIYAT['torba_kg']
 fire_katsayisi = 1 + fire_orani

 # Net alçı ihtiyacı (kg)
 net_alci_kg = uygulama_alani_m2 * ortalama_kalinlik_cm * kg_m2_cm

 # Fireli alçı ihtiyacı (kg)
 fireli_alci_kg = net_alci_kg * fire_katsayisi

 # Torba sayısı (yukarı yuvarla)
 gereken_torba_adet = math.ceil(fireli_alci_kg / torba_kg)

 # =========================================================================
 # 4. SÜRE HESAPLAMA (Yukarı Yuvarlama)
 # =========================================================================

 tahmini_sure_gun = math.ceil(uygulama_alani_m2 / secilen_hiz)

 # =========================================================================
 # 5. İŞÇİLİK TUTARI HESAPLAMA
 # =========================================================================

 toplam_iscilik_tl = tahmini_sure_gun * ekip_gunluk_ucret

 # =========================================================================
 # 6. MALZEME MALİYETİ HESAPLAMA
 # =========================================================================

 toplam_malzeme_tl = gereken_torba_adet * torba_birim_fiyat

 # =========================================================================
 # 7. YAN ÜRÜNLER HESAPLAMA
 # =========================================================================

 # Ano profil (köşe profili) - sadece kullanılacaksa
 if ano_kullanimi:
 gereken_ano_profil_mt = round(
 uygulama_alani_m2 * ALCI_SARFIYAT['ano_profil_m_m2'] * fire_katsayisi,
 2
 )
 else:
 gereken_ano_profil_mt = 0.0

 # Astar ihtiyacı (fire dahil)
 gereken_astar_kg = round(
 uygulama_alani_m2 * ALCI_SARFIYAT['astar_kg_m2'] * fire_katsayisi,
 2
 )

 # =========================================================================
 # 8. GENEL TOPLAM MALİYET HESAPLAMA
 # =========================================================================

 # Not: Profil ve astar maliyetleri dahil değil (sadece miktarlar verildi)
 genel_toplam_maliyet_tl = toplam_iscilik_tl + toplam_malzeme_tl

 # =========================================================================
 # 9. SONUÇ SÖZLÜĞÜ OLUŞTURMA
 # =========================================================================

 sonuc = {
 'baz_alinan_hiz_m2': secilen_hiz,
 'tahmini_sure_gun': tahmini_sure_gun,
 'toplam_alci_kg': round(fireli_alci_kg, 2),
 'gereken_torba_adet': gereken_torba_adet,
 'gereken_ano_profil_mt': gereken_ano_profil_mt,
 'gereken_astar_kg': gereken_astar_kg,
 'toplam_iscilik_tl': round(toplam_iscilik_tl, 2),
 'toplam_malzeme_tl': round(toplam_malzeme_tl, 2),
 'genel_toplam_maliyet_tl': round(genel_toplam_maliyet_tl, 2)
 }

 return sonuc


def hesapla_duvar_maliyet_detayli(
 duvar_tipi: str,
 duvar_m2: float,
 malzeme_birim_fiyat: float,
 ekip_gunluk_ucret: float,
 fire_orani: float,
 verim_kaynagi: str,
 manuel_hiz: Optional[float] = None
) -> Dict[str, Any]:
 """
 Detaylı duvar maliyet hesaplama fonksiyonu.

 İşçilik hızı kaynağını seçerek esnek maliyet analizi yapar.

 Args:
 duvar_tipi: Duvar tipi ('bims_19', 'tugla_13.5', 'gazbeton_15')
 duvar_m2: Toplam duvar alanı (m²)
 malzeme_birim_fiyat: Malzeme birim fiyatı (TL/adet)
 ekip_gunluk_ucret: Ekip günlük ücreti (1 Usta + 1 Yardımcı toplamı, TL)
 fire_orani: Fire oranı (Örn: 0.05 = %5)
 verim_kaynagi: Verimlilik kaynağı ('piyasa', 'csb_resmi', 'manuel')
 manuel_hiz: Manuel hız değeri (m²/gün, sadece verim_kaynagi='manuel' ise)

 Returns:
 Dict: Detaylı maliyet analizi sonuçları

 Raises:
 ValueError: Geçersiz parametre değerleri için
 """

 # =========================================================================
 # 1. GİRDİ VALİDASYONU
 # =========================================================================

 gecerli_duvar_tipleri = ['bims_19', 'tugla_13.5', 'gazbeton_15']
 gecerli_verim_kaynaklari = ['piyasa', 'csb_resmi', 'manuel']

 if duvar_tipi not in gecerli_duvar_tipleri:
 raise ValueError(
 f"Geçersiz duvar tipi: '{duvar_tipi}'. "
 f"Geçerli seçenekler: {gecerli_duvar_tipleri}"
 )

 if verim_kaynagi not in gecerli_verim_kaynaklari:
 raise ValueError(
 f"Geçersiz verim kaynağı: '{verim_kaynagi}'. "
 f"Geçerli seçenekler: {gecerli_verim_kaynaklari}"
 )

 if duvar_m2 <= 0:
 raise ValueError("Duvar alanı 0'dan büyük olmalıdır.")

 if malzeme_birim_fiyat < 0:
 raise ValueError("Malzeme birim fiyatı negatif olamaz.")

 if ekip_gunluk_ucret < 0:
 raise ValueError("Ekip günlük ücreti negatif olamaz.")

 if fire_orani < 0 or fire_orani > 1:
 raise ValueError("Fire oranı 0 ile 1 arasında olmalıdır.")

 if verim_kaynagi == 'manuel':
 if manuel_hiz is None or manuel_hiz <= 0:
 raise ValueError(
 "Manuel verim kaynağı seçildiğinde 'manuel_hiz' değeri "
 "sıfırdan büyük bir değer olmalıdır."
 )

 # =========================================================================
 # 2. HIZ BELİRLEME
 # =========================================================================

 if verim_kaynagi == 'manuel':
 secilen_hiz = manuel_hiz
 else:
 secilen_hiz = VERIMLILIK_VERITABANI[verim_kaynagi][duvar_tipi]

 # =========================================================================
 # 3. SÜRE HESAPLAMA (Yukarı Yuvarlama)
 # =========================================================================

 tahmini_sure_gun = math.ceil(duvar_m2 / secilen_hiz)

 # =========================================================================
 # 4. İŞÇİLİK TUTARI HESAPLAMA
 # =========================================================================

 toplam_iscilik_tl = tahmini_sure_gun * ekip_gunluk_ucret

 # =========================================================================
 # 5. MALZEME MİKTARI HESAPLAMA (Fire Dahil)
 # =========================================================================

 sarfiyat = MALZEME_SARFIYAT[duvar_tipi]
 fire_katsayisi = 1 + fire_orani

 # Ana malzeme (Bims/Tuğla/Gazbeton bloğu)
 ana_malzeme_adet_ham = duvar_m2 * sarfiyat['adet_m2'] * fire_katsayisi
 ana_malzeme_adet = math.ceil(ana_malzeme_adet_ham) # Yukarı yuvarla (adet)

 # Ana malzeme maliyeti
 ana_malzeme_maliyet_tl = ana_malzeme_adet * malzeme_birim_fiyat

 # =========================================================================
 # 6. YAN ÜRÜNLER HESAPLAMA (Harç veya Yapıştırıcı)
 # =========================================================================

 gereken_kum_m3 = 0.0
 gereken_cimento_torba = 0
 gereken_yapistirici_kg = 0.0

 if duvar_tipi in ['bims_19', 'tugla_13.5']:
 # Harç gereken duvar tipleri (Bims ve Tuğla)
 harc_m3_ham = duvar_m2 * sarfiyat['harc_m3_m2'] * fire_katsayisi

 # Kum hesabı (m³)
 gereken_kum_m3 = round(harc_m3_ham * HARC_KARISIM['kum_m3'], 3)

 # Çimento hesabı (torba - yukarı yuvarla)
 cimento_ham = harc_m3_ham * HARC_KARISIM['cimento_torba']
 gereken_cimento_torba = math.ceil(cimento_ham)

 elif duvar_tipi == 'gazbeton_15':
 # Yapıştırıcı gereken duvar tipi (Gazbeton)
 yapistirici_ham = duvar_m2 * sarfiyat['yapistirici_kg_m2'] * fire_katsayisi
 gereken_yapistirici_kg = round(yapistirici_ham, 2)

 # =========================================================================
 # 7. GENEL TOPLAM MALİYET HESAPLAMA
 # =========================================================================

 # Not: Yan ürün maliyetleri bu hesaba dahil değil (sadece ana malzeme + işçilik)
 # Kullanıcı kum, çimento, yapıştırıcı fiyatlarını ayrıca ekleyebilir
 genel_toplam_maliyet_tl = toplam_iscilik_tl + ana_malzeme_maliyet_tl

 # =========================================================================
 # 8. SONUÇ SÖZLÜĞÜ OLUŞTURMA
 # =========================================================================

 sonuc = {
 'kullanilan_hiz_m2_gun': secilen_hiz,
 'tahmini_sure_gun': tahmini_sure_gun,
 'toplam_iscilik_tl': round(toplam_iscilik_tl, 2),
 'ana_malzeme_adet': ana_malzeme_adet,
 'ana_malzeme_maliyet_tl': round(ana_malzeme_maliyet_tl, 2),
 'gereken_kum_m3': gereken_kum_m3,
 'gereken_cimento_torba': gereken_cimento_torba,
 'gereken_yapistirici_kg': gereken_yapistirici_kg,
 'genel_toplam_maliyet_tl': round(genel_toplam_maliyet_tl, 2)
 }

 return sonuc


class Calculator:
 """
 Metraj ve maliyet hesaplama sınıfı.
 
 Tüm matematiksel işlemler Decimal kullanarak yüksek hassasiyetle yapılır.
 """
 
 @staticmethod
 def calculate_total(quantity: float, unit_price: float) -> float:
 """
 Toplam tutarı hesapla.
 
 Args:
 quantity: Miktar
 unit_price: Birim fiyat
 
 Returns:
 float: Toplam tutar (2 ondalık basamak)
 """
 qty = Decimal(str(quantity))
 price = Decimal(str(unit_price))
 total = qty * price
 return float(total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
 
 @staticmethod
 def calculate_project_total(metraj_items: List[Dict[str, Any]]) -> float:
 """
 Proje toplam maliyetini hesapla.
 
 Args:
 metraj_items: Metraj kalemleri listesi
 
 Returns:
 float: Toplam maliyet
 """
 total = Decimal('0')
 for item in metraj_items:
 quantity = Decimal(str(item.get('miktar', 0)))
 unit_price = Decimal(str(item.get('birim_fiyat', 0)))
 total += quantity * unit_price
 
 return float(total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
 
 @staticmethod
 def calculate_kdv(amount: float, kdv_rate: float = 20.0) -> float:
 """
 KDV hesapla.
 
 Args:
 amount: Tutar
 kdv_rate: KDV oranı (varsayılan %20)
 
 Returns:
 float: KDV tutarı
 """
 amount_decimal = Decimal(str(amount))
 rate = Decimal(str(kdv_rate)) / Decimal('100')
 kdv = amount_decimal * rate
 return float(kdv.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
 
 @staticmethod
 def calculate_with_kdv(amount: float, kdv_rate: float = 20.0) -> Dict[str, float]:
 """
 KDV dahil ve hariç tutarları hesapla.
 
 Args:
 amount: KDV hariç tutar
 kdv_rate: KDV oranı
 
 Returns:
 Dict: {'kdv_haric', 'kdv', 'kdv_dahil'}
 """
 kdv_haric = Decimal(str(amount))
 kdv = Calculator.calculate_kdv(amount, kdv_rate)
 kdv_decimal = Decimal(str(kdv))
 kdv_dahil = kdv_haric + kdv_decimal
 
 return {
 'kdv_haric': float(kdv_haric),
 'kdv': kdv,
 'kdv_dahil': float(kdv_dahil.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
 }
 
 @staticmethod
 def compare_taseron_offers(offers: List[Dict[str, Any]]) -> Dict[str, Any]:
 """
 Taşeron tekliflerini karşılaştır.
 
 Args:
 offers: Taşeron teklifleri listesi
 
 Returns:
 Dict: Karşılaştırma sonuçları
 """
 if not offers:
 return {
 'en_dusuk': None,
 'en_yuksek': None,
 'ortalama': 0.0,
 'firma_sayisi': 0
 }
 
 totals = [offer.get('toplam', 0) for offer in offers if offer.get('toplam', 0) > 0]
 
 if not totals:
 return {
 'en_dusuk': None,
 'en_yuksek': None,
 'ortalama': 0.0,
 'firma_sayisi': len(offers)
 }
 
 totals_decimal = [Decimal(str(t)) for t in totals]
 en_dusuk = min(totals_decimal)
 en_yuksek = max(totals_decimal)
 ortalama = sum(totals_decimal) / Decimal(str(len(totals_decimal)))
 
 # En düşük ve en yüksek teklifleri bul
 en_dusuk_offer = next(
 (o for o in offers if Decimal(str(o.get('toplam', 0))) == en_dusuk),
 None
 )
 en_yuksek_offer = next(
 (o for o in offers if Decimal(str(o.get('toplam', 0))) == en_yuksek),
 None
 )
 
 return {
 'en_dusuk': {
 'firma': en_dusuk_offer.get('firma_adi', '') if en_dusuk_offer else '',
 'tutar': float(en_dusuk)
 },
 'en_yuksek': {
 'firma': en_yuksek_offer.get('firma_adi', '') if en_yuksek_offer else '',
 'tutar': float(en_yuksek)
 },
 'ortalama': float(ortalama.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
 'firma_sayisi': len(offers)
 }
 
 @staticmethod
 def calculate_materials_for_poz(poz_miktar: float, formuller: List[Dict[str, Any]], 
 fire_orani: float = 0.0, 
 sub_formulas: Optional[Dict[str, List[Dict[str, Any]]]] = None) -> List[Dict[str, Any]]:
 """
 Poz miktarına göre gereken malzemeleri hesapla.
 Alt formüller (harç, beton karışımı) desteklenir.
 
 Args:
 poz_miktar: Poz miktarı (örn: 100 m²)
 formuller: Poz için malzeme formülleri listesi
 fire_orani: Fire/atık oranı (0.05 = %5)
 sub_formulas: Alt formüller (formul_tipi -> formül listesi)
 
 Returns:
 List[Dict]: Hesaplanan malzeme listesi
 """
 materials = []
 poz_decimal = Decimal(str(poz_miktar))
 fire_katsayi = Decimal('1') + Decimal(str(fire_orani))
 
 if sub_formulas is None:
 sub_formulas = {}
 
 for formul in formuller:
 miktar = Decimal(str(formul.get('miktar', 0)))
 birim = formul.get('birim', '')
 malzeme_adi = formul.get('malzeme_adi', '')
 malzeme_birim = formul.get('malzeme_birim', birim)
 formul_tipi = formul.get('formul_tipi', 'direkt')
 
 # Alt formül kontrolü (harç, beton_karisimi vb.)
 if formul_tipi in sub_formulas:
 # Alt formülün miktarını hesapla
 alt_formul_miktar = poz_decimal * miktar * fire_katsayi
 
 # Alt formülün içindeki malzemeleri hesapla
 alt_formul_listesi = sub_formulas[formul_tipi]
 for alt_formul in alt_formul_listesi:
 alt_miktar = Decimal(str(alt_formul.get('miktar', 0)))
 alt_malzeme_adi = alt_formul.get('malzeme_adi', '')
 alt_birim = alt_formul.get('birim', '')
 
 # Alt formül miktarı × alt formül oranı
 toplam_alt_miktar = alt_formul_miktar * alt_miktar
 
 materials.append({
 'malzeme_id': alt_formul.get('malzeme_id'),
 'malzeme_adi': alt_malzeme_adi,
 'miktar': float(toplam_alt_miktar.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
 'birim': alt_birim,
 'formul_tipi': 'direkt',
 'aciklama': f"{malzeme_adi} ({formul_tipi}) içinde"
 })
 else:
 # Normal direkt formül
 toplam_miktar = poz_decimal * miktar * fire_katsayi
 
 materials.append({
 'malzeme_id': formul.get('malzeme_id'),
 'malzeme_adi': malzeme_adi,
 'miktar': float(toplam_miktar.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
 'birim': malzeme_birim,
 'formul_tipi': formul_tipi,
 'aciklama': formul.get('aciklama', '')
 })
 
 return materials
 
 @staticmethod
 def aggregate_materials(material_lists: List[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
 """
 Birden fazla poz için hesaplanan malzemeleri birleştir.
 Aynı malzemeler toplanır.
 
 Args:
 material_lists: Malzeme listelerinin listesi
 
 Returns:
 List[Dict]: Birleştirilmiş malzeme listesi
 """
 aggregated = {}
 
 for material_list in material_lists:
 for material in material_list:
 malzeme_id = material.get('malzeme_id')
 malzeme_adi = material.get('malzeme_adi', '')
 birim = material.get('birim', '')
 
 # Key: malzeme_id veya malzeme_adi + birim
 key = f"{malzeme_id}_{birim}" if malzeme_id else f"{malzeme_adi}_{birim}"
 
 if key in aggregated:
 # Mevcut malzemeye ekle
 mevcut_miktar = Decimal(str(aggregated[key]['miktar']))
 yeni_miktar = Decimal(str(material.get('miktar', 0)))
 toplam = mevcut_miktar + yeni_miktar
 aggregated[key]['miktar'] = float(toplam.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
 else:
 # Yeni malzeme ekle
 aggregated[key] = {
 'malzeme_id': malzeme_id,
 'malzeme_adi': malzeme_adi,
 'miktar': material.get('miktar', 0),
 'birim': birim,
 'formul_tipi': material.get('formul_tipi', 'direkt')
 }
 
 # Listeye dönüştür ve sırala
 result = list(aggregated.values())
 result.sort(key=lambda x: (x.get('malzeme_adi', ''), x.get('birim', '')))
 
 return result
 
 @staticmethod
 def convert_unit(value: float, from_unit: str, to_unit: str, 
 conversion_factor: Optional[float] = None) -> float:
 """
 Birim dönüştür.
 
 Args:
 value: Dönüştürülecek değer
 from_unit: Kaynak birim
 to_unit: Hedef birim
 conversion_factor: Dönüşüm katsayısı (None ise standart dönüşümler kullanılır)
 
 Returns:
 float: Dönüştürülmüş değer
 """
 if conversion_factor is not None:
 return float(Decimal(str(value)) * Decimal(str(conversion_factor)))
 
 # Standart birim dönüşümleri
 from_unit = from_unit.lower().strip()
 to_unit = to_unit.lower().strip()
 
 # Aynı birimse dönüştürme yapma
 if from_unit == to_unit:
 return value
 
 # Uzunluk dönüşümleri
 length_units = {
 'mm': 0.001, 'cm': 0.01, 'dm': 0.1, 'm': 1.0, 'km': 1000.0,
 'in': 0.0254, 'ft': 0.3048, 'yd': 0.9144, 'mi': 1609.344
 }
 
 # Alan dönüşümleri
 area_units = {
 'mm²': 0.000001, 'cm²': 0.0001, 'dm²': 0.01, 'm²': 1.0, 'km²': 1000000.0,
 'ha': 10000.0, 'acre': 4046.856, 'in²': 0.00064516, 'ft²': 0.092903, 'yd²': 0.836127
 }
 
 # Hacim dönüşümleri
 volume_units = {
 'mm³': 0.000000001, 'cm³': 0.000001, 'dm³': 0.001, 'm³': 1.0, 'l': 0.001, 'ml': 0.000001,
 'in³': 0.000016387, 'ft³': 0.0283168, 'yd³': 0.764555, 'gal': 0.00378541
 }
 
 # Ağırlık dönüşümleri
 weight_units = {
 'mg': 0.000001, 'g': 0.001, 'kg': 1.0, 't': 1000.0, 'ton': 1000.0,
 'oz': 0.0283495, 'lb': 0.453592, 'st': 6.35029
 }
 
 # Birim tipini belirle ve dönüştür
 if from_unit in length_units and to_unit in length_units:
 base_value = value * length_units[from_unit]
 return base_value / length_units[to_unit]
 elif from_unit in area_units and to_unit in area_units:
 base_value = value * area_units[from_unit]
 return base_value / area_units[to_unit]
 elif from_unit in volume_units and to_unit in volume_units:
 base_value = value * volume_units[from_unit]
 return base_value / volume_units[to_unit]
 elif from_unit in weight_units and to_unit in weight_units:
 base_value = value * weight_units[from_unit]
 return base_value / weight_units[to_unit]
 else:
 # Bilinmeyen birimler için hata
 raise ValueError(f"Birim dönüşümü desteklenmiyor: {from_unit} -> {to_unit}")
 
 @staticmethod
 def get_auto_fire_rate(kategori: str) -> float:
 """
 Kategori bazlı otomatik fire oranı hesapla.
 
 Args:
 kategori: Poz kategorisi
 
 Returns:
 float: Fire oranı (0.05 = %5)
 """
 if not kategori:
 return 0.05 # Varsayılan %5
 
 kategori_lower = kategori.lower()
 
 # Kategori bazlı fire oranları
 fire_rates = {
 'beton': 0.03, # %3
 'demir': 0.05, # %5
 'kalıp': 0.10, # %10
 'sıva': 0.08, # %8
 'boya': 0.05, # %5
 'fayans': 0.03, # %3
 'seramik': 0.03, # %3
 'tuğla': 0.05, # %5
 'çimento': 0.05, # %5
 'kum': 0.10, # %10
 'çakıl': 0.10, # %10
 'izolasyon': 0.05, # %5
 'elektrik': 0.05, # %5
 'tesisat': 0.05, # %5
 'kapı': 0.02, # %2
 'pencere': 0.02, # %2
 }
 
 # Kategori içinde anahtar kelime ara
 for key, rate in fire_rates.items():
 if key in kategori_lower:
 return rate
 
 # Varsayılan
 return 0.05


# =============================================================================
# MOBİLYA MALİYET HESAPLAMA FONKSİYONLARI
# =============================================================================

def hesapla_mobilya_maliyet(
 urun_listesi: list,
 mutfak_vestiyer_m2_fiyat: float,
 banyo_dolabi_m2_fiyat: float,
 ahsap_kapi_adet_fiyat: float,
 montaj_nakliye_sabit_bedel: float = 0
) -> dict:
 """
 Mobilya maliyetlerini hesaplar.
 Mutfak ve Vestiyer aynı üretim mantığıyla (Gövde+Kapak) hesaplanır.

 Args:
 urun_listesi: Ürün listesi. Her ürün dict formatında:
 - tip: 'mutfak', 'vestiyer', 'banyo', 'kapi'
 - adet: Ürün adedi (varsayılan 1)
 - en_cm: Ürün eni (cm) - mutfak/vestiyer/banyo için
 - boy_cm: Ürün boyu (cm) - mutfak/vestiyer/banyo için
 mutfak_vestiyer_m2_fiyat: Mutfak ve vestiyer m² birim fiyatı (TL)
 banyo_dolabi_m2_fiyat: Banyo dolabı m² birim fiyatı (TL)
 ahsap_kapi_adet_fiyat: Ahşap kapı adet fiyatı (TL)
 montaj_nakliye_sabit_bedel: Montaj ve nakliye sabit bedeli (TL)

 Returns:
 dict: Hesaplama sonuçları (detaylar, maliyet kırılımı, genel toplam)
 """

 # 1. Toplam Değişkenleri
 toplam_mutfak_vestiyer_m2 = 0.0
 toplam_banyo_m2 = 0.0
 toplam_kapi_adet = 0

 # 2. Liste Döngüsü
 for urun in urun_listesi:
 tip = urun.get('tip', '')
 adet = urun.get('adet', 1)

 # A. ALAN HESAPLAMALI MODÜLLER (En x Boy)
 if tip in ['mutfak', 'vestiyer', 'banyo']:
 en = urun.get('en_cm', 0)
 boy = urun.get('boy_cm', 0)

 # cm -> m2 Dönüşümü
 alan_m2 = ((en * boy) / 10000) * adet

 if tip == 'banyo':
 toplam_banyo_m2 += alan_m2
 else:
 # Mutfak ve Vestiyer aynı havuza gider
 toplam_mutfak_vestiyer_m2 += alan_m2

 # B. ADET BAZLI MODÜLLER
 elif tip == 'kapi':
 toplam_kapi_adet += adet

 # 3. Genel Maliyet Hesapları
 # Not: Mutfak ve Vestiyer tek kalemde, aynı birim fiyattan toplanır
 maliyet_mutfak_vestiyer = toplam_mutfak_vestiyer_m2 * mutfak_vestiyer_m2_fiyat
 maliyet_banyo = toplam_banyo_m2 * banyo_dolabi_m2_fiyat
 maliyet_kapi = toplam_kapi_adet * ahsap_kapi_adet_fiyat

 genel_toplam = (
 maliyet_mutfak_vestiyer +
 maliyet_banyo +
 maliyet_kapi +
 montaj_nakliye_sabit_bedel
 )

 # 4. ÇIKTI FORMATI (Return)
 return {
 "ozet_bilgi": "Mobilya İmalat Dökümü",
 "detaylar": {
 "toplam_mutfak_vestiyer_alani_m2": round(toplam_mutfak_vestiyer_m2, 2),
 "toplam_banyo_dolabi_alani_m2": round(toplam_banyo_m2, 2),
 "toplam_kapi_adedi": toplam_kapi_adet
 },
 "maliyet_kirilimi": {
 "mutfak_vestiyer_grup_tl": round(maliyet_mutfak_vestiyer, 2),
 "banyo_dolabi_tl": round(maliyet_banyo, 2),
 "ahsap_kapi_tl": round(maliyet_kapi, 2),
 "montaj_nakliye_tl": round(montaj_nakliye_sabit_bedel, 2)
 },
 "genel_toplam_maliyet_tl": round(genel_toplam, 2)
 }


# =============================================================================
# SU YALITIM MALİYET HESAPLAMA FONKSİYONLARI
# =============================================================================

def hesapla_yalitim_maliyeti(
 is_listesi: list,
 fiyatlar: dict
) -> dict:
 """
 Su yalıtımı metraj ve maliyet hesaplaması yapar.

 Yalıtım türleri:
 - bez: Bitümlü örtü (Rulo membran) - %10 bindirme payı eklenir
 - toz: Çimento esaslı (Torba)
 - surme: Likit/PU/Bitüm (Kova)

 Args:
 is_listesi: İş kalemleri listesi. Her kalem dict formatında:
 - alan_m2: Uygulama alanı (m²)
 - tur: 'bez', 'toz', 'surme'
 - aciklama: İsteğe bağlı açıklama
 fiyatlar: Birim fiyatlar dict'i:
 - bez_membran_m2_fiyat: TL/m²
 - toz_membran_m2_fiyat: TL/m²
 - surme_membran_m2_fiyat: TL/m²
 - astar_m2_fiyat: TL/m² (opsiyonel)
 - iscilik_m2_fiyat: TL/m² (opsiyonel)

 Returns:
 dict: Metraj analizi, maliyet detayı ve genel toplam
 """

 # 1. Değişkenler
 toplam_uygulama_alani_net = 0.0

 # Detaylı Metrajlar
 bez_net_m2 = 0.0
 toz_net_m2 = 0.0
 surme_net_m2 = 0.0

 # Sarfiyatlı (Satın Alma) Metrajları
 bez_brut_m2 = 0.0 # %10 Bindirme payı dahil

 # 2. Liste Analizi
 for is_kalemi in is_listesi:
 alan = is_kalemi.get('alan_m2', 0)
 tur = is_kalemi.get('tur', '')

 toplam_uygulama_alani_net += alan

 if tur == 'bez':
 bez_net_m2 += alan
 # KRİTİK KURAL: Rulo membranlarda ek yerleri için %10 bindirme payı eklenir
 bez_brut_m2 += alan * 1.10

 elif tur == 'toz':
 toz_net_m2 += alan

 elif tur == 'surme':
 surme_net_m2 += alan

 # 3. Maliyet Hesaplama
 # Not: Bez membran maliyeti BRÜT (bindirme dahil) metraj üzerinden hesaplanır
 maliyet_bez = bez_brut_m2 * fiyatlar.get('bez_membran_m2_fiyat', 0)
 maliyet_toz = toz_net_m2 * fiyatlar.get('toz_membran_m2_fiyat', 0)
 maliyet_surme = surme_net_m2 * fiyatlar.get('surme_membran_m2_fiyat', 0)

 # Yan Giderler (Tüm alana astar veya işçilik uygulanacaksa)
 maliyet_astar = toplam_uygulama_alani_net * fiyatlar.get('astar_m2_fiyat', 0)
 maliyet_iscilik = toplam_uygulama_alani_net * fiyatlar.get('iscilik_m2_fiyat', 0)

 genel_toplam = maliyet_bez + maliyet_toz + maliyet_surme + maliyet_astar + maliyet_iscilik

 return {
 "ozet_baslik": "Su Yalitimi Metraj ve Maliyet Dokumu",
 "metraj_analizi": {
 "bez_membran_rulo": {
 "uygulanan_net_alan": round(bez_net_m2, 2),
 "satin_alma_metraji_bini_dahil": round(bez_brut_m2, 2),
 "aciklama": "%10 binme payi eklenmistir."
 },
 "toz_sistem_net_m2": round(toz_net_m2, 2),
 "surme_sistem_net_m2": round(surme_net_m2, 2),
 "toplam_is_alani_m2": round(toplam_uygulama_alani_net, 2)
 },
 "maliyet_detayi_tl": {
 "bez_membran_tutari": round(maliyet_bez, 2),
 "toz_membran_tutari": round(maliyet_toz, 2),
 "surme_membran_tutari": round(maliyet_surme, 2),
 "astar_tutari": round(maliyet_astar, 2),
 "iscilik_tutari": round(maliyet_iscilik, 2)
 },
 "genel_toplam_tl": round(genel_toplam, 2)
 }


# =============================================================================
# ELEKTRİK TESİSAT MALİYET HESAPLAMA FONKSİYONLARI
# =============================================================================

def hesapla_elektrik_ozel(
 envanter: dict,
 fiyatlar: dict
) -> dict:
 """
 Elektrik tesisat envanter ve maliyet hesaplaması yapar.

 Envanter kalemleri:
 - Lamba/Armatür
 - Priz
 - Diyafon Ünitesi
 - Şartel Pano/Sigorta Kutusu
 - Lamba Açma Tuşu/Anahtar

 Args:
 envanter: Adet bilgileri dict'i:
 - lamba_adet: Lamba/Armatür sayısı
 - priz_adet: Priz sayısı
 - diyafon_adet: Diyafon ünitesi sayısı
 - sartel_pano_adet: Şartel pano sayısı
 - tus_kilit_adet: Lamba açma tuşu sayısı
 fiyatlar: Birim fiyatlar dict'i (malzeme + işçilik dahil):
 - lamba_birim_fiyat: TL/adet
 - priz_birim_fiyat: TL/adet
 - diyafon_birim_fiyat: TL/adet
 - pano_birim_fiyat: TL/adet
 - anahtar_birim_fiyat: TL/adet

 Returns:
 dict: Adet bilgileri, maliyet detayı ve genel toplam
 """

 # 1. Veri Alma (Kullanıcı Girdisi)
 adet_lamba = envanter.get('lamba_adet', 0)
 adet_priz = envanter.get('priz_adet', 0)
 adet_diyafon = envanter.get('diyafon_adet', 0)
 adet_pano = envanter.get('sartel_pano_adet', 0)
 adet_anahtar = envanter.get('tus_kilit_adet', 0)

 # 2. Maliyet Hesaplama
 maliyet_lamba = adet_lamba * fiyatlar.get('lamba_birim_fiyat', 0)
 maliyet_priz = adet_priz * fiyatlar.get('priz_birim_fiyat', 0)
 maliyet_diyafon = adet_diyafon * fiyatlar.get('diyafon_birim_fiyat', 0)
 maliyet_pano = adet_pano * fiyatlar.get('pano_birim_fiyat', 0)
 maliyet_anahtar = adet_anahtar * fiyatlar.get('anahtar_birim_fiyat', 0)

 genel_toplam = (
 maliyet_lamba +
 maliyet_priz +
 maliyet_diyafon +
 maliyet_pano +
 maliyet_anahtar
 )

 # 3. Çıktı Üretme
 return {
 "ozet_baslik": "Elektrik Tesisat Envanter Dokumu",
 "adet_bilgileri": {
 "lamba_sayisi": adet_lamba,
 "priz_sayisi": adet_priz,
 "diyafon_sayisi": adet_diyafon,
 "sartel_pano_sayisi": adet_pano,
 "lamba_acma_tusu_sayisi": adet_anahtar
 },
 "maliyet_detayi_tl": {
 "lamba_tutari": round(maliyet_lamba, 2),
 "priz_tutari": round(maliyet_priz, 2),
 "diyafon_tutari": round(maliyet_diyafon, 2),
 "pano_tutari": round(maliyet_pano, 2),
 "tus_kilit_tutari": round(maliyet_anahtar, 2)
 },
 "genel_toplam_tl": round(genel_toplam, 2)
 }


# =============================================================================
# VİTRİFİYE VE ARMATÜR MALİYET HESAPLAMA FONKSİYONLARI
# =============================================================================

def hesapla_vitrifiye_armatur(
 urun_listesi: list,
 fiyatlar: dict
) -> dict:
 """
 Vitrifiye, armatür ve petek maliyet hesaplaması yapar.
 Boru ve altyapı hariç; sadece montajı yapılan son ürünler.

 Ürün tipleri:
 - batarya: Lavabo/Banyo Bataryası (Mix)
 - musluk: Tekli Musluk (Taharet/Çamaşır)
 - klozet: Klozet + Kapak + İç Takım
 - alaturka: Alaturka Tuvalet Taşı
 - dus: Robot duş veya sürgülü set
 - petek: Radyatör Paneli veya Havlupan

 Args:
 urun_listesi: Ürün listesi. Her ürün dict formatında:
 - tip: 'batarya', 'musluk', 'klozet', 'alaturka', 'dus', 'petek'
 - adet: Ürün adedi (varsayılan 1)
 fiyatlar: Birim fiyatlar dict'i:
 - batarya_fiyat: TL/adet
 - musluk_fiyat: TL/adet
 - klozet_takim_fiyat: TL/adet
 - alaturka_tas_fiyat: TL/adet
 - dus_basligi_set_fiyat: TL/adet
 - petek_fiyat: TL/adet
 - montaj_ucreti_adet: TL/adet (her parça için)

 Returns:
 dict: Adet dökümü, maliyet detayı ve genel toplam
 """

 # 1. Envanter Sayımı
 stok = {
 "batarya_adet": 0,
 "musluk_adet": 0,
 "klozet_adet": 0,
 "alaturka_adet": 0,
 "dus_set_adet": 0,
 "petek_adet": 0
 }

 # 2. Liste Ayrıştırma
 for urun in urun_listesi:
 tip = urun.get('tip', '')
 adet = urun.get('adet', 1)

 if tip == 'batarya':
 stok['batarya_adet'] += adet
 elif tip == 'musluk':
 stok['musluk_adet'] += adet
 elif tip == 'klozet':
 stok['klozet_adet'] += adet
 elif tip == 'alaturka':
 stok['alaturka_adet'] += adet
 elif tip == 'dus':
 stok['dus_set_adet'] += adet
 elif tip == 'petek':
 stok['petek_adet'] += adet

 # 3. Maliyet Hesaplama
 # Toplam Ürün Maliyeti
 malzeme_tutari = (
 (stok['batarya_adet'] * fiyatlar.get('batarya_fiyat', 0)) +
 (stok['musluk_adet'] * fiyatlar.get('musluk_fiyat', 0)) +
 (stok['klozet_adet'] * fiyatlar.get('klozet_takim_fiyat', 0)) +
 (stok['alaturka_adet'] * fiyatlar.get('alaturka_tas_fiyat', 0)) +
 (stok['dus_set_adet'] * fiyatlar.get('dus_basligi_set_fiyat', 0)) +
 (stok['petek_adet'] * fiyatlar.get('petek_fiyat', 0))
 )

 # Toplam Montaj Maliyeti (Toplam Parça Sayısı x Montaj Bedeli)
 toplam_parca_sayisi = sum(stok.values())
 iscilik_tutari = toplam_parca_sayisi * fiyatlar.get('montaj_ucreti_adet', 0)

 genel_toplam = malzeme_tutari + iscilik_tutari

 return {
 "ozet_baslik": "Vitrifiye ve Armatur Listesi",
 "stok_detay": stok,
 "adet_dokumu": {
 "batarya_musluk_grubu": f"{stok['batarya_adet']} Batarya, {stok['musluk_adet']} Musluk",
 "tuvalet_grubu": f"{stok['klozet_adet']} Klozet, {stok['alaturka_adet']} Alaturka Tas",
 "banyo_ve_isitma": f"{stok['dus_set_adet']} Dus Seti, {stok['petek_adet']} Petek",
 "toplam_parca_sayisi": toplam_parca_sayisi
 },
 "maliyet_detayi_tl": {
 "urun_malzeme_bedeli": round(malzeme_tutari, 2),
 "montaj_iscilik_bedeli": round(iscilik_tutari, 2)
 },
 "genel_toplam_tl": round(genel_toplam, 2)
 }


# =============================================================================
# KABA YAPI (HAFRİYAT - DEMİR - BETON) MALİYET HESAPLAMA FONKSİYONLARI
# =============================================================================

def hesapla_kaba_yapi_manuel(
 girdiler: dict,
 fiyatlar: dict,
 fire_oranlari: dict
) -> dict:
 """
 Kaba yapı (Hafriyat, Demir, Beton) maliyet hesaplaması yapar.
 Fire oranları kullanıcı tarafından belirlenir.

 Args:
 girdiler: Miktar bilgileri dict'i:
 - hafriyat_miktar: m³ veya sefer sayısı
 - demir_ince_ton: 8-12mm arası demir tonajı
 - demir_kalin_ton: 14mm ve üzeri demir tonajı
 - beton_m3: Hazır beton m³
 fiyatlar: Birim fiyatlar dict'i:
 - hafriyat_birim_fiyat: TL/birim
 - demir_ince_ton_fiyat: TL/ton
 - demir_kalin_ton_fiyat: TL/ton
 - beton_m3_fiyat: TL/m³
 - beton_pompa_fiyat: TL/m³ (opsiyonel)
 fire_oranlari: Fire yüzdeleri dict'i:
 - demir_fire_yuzde: % olarak (örn: 3 = %3)
 - beton_fire_yuzde: % olarak (örn: 5 = %5)

 Returns:
 dict: Metraj detayları, fire oranları, maliyet tablosu ve genel toplam
 """

 # 1. HAFRİYAT HESABI
 # Kullanıcı ne girdiyse direkt o hesaplanır
 mik_hafriyat = girdiler.get('hafriyat_miktar', 0)
 mal_hafriyat = mik_hafriyat * fiyatlar.get('hafriyat_birim_fiyat', 0)

 # 2. DEMİR HESABI (İnce ve Kalın Ayrımı)
 demir_fire = fire_oranlari.get('demir_fire_yuzde', 0)

 # İnce Demir (8-12mm)
 girilen_ince_ton = girdiler.get('demir_ince_ton', 0)
 hesaplanan_ince_ton = girilen_ince_ton * (1 + (demir_fire / 100))
 mal_demir_ince = hesaplanan_ince_ton * fiyatlar.get('demir_ince_ton_fiyat', 0)

 # Kalın Demir (14mm+)
 girilen_kalin_ton = girdiler.get('demir_kalin_ton', 0)
 hesaplanan_kalin_ton = girilen_kalin_ton * (1 + (demir_fire / 100))
 mal_demir_kalin = hesaplanan_kalin_ton * fiyatlar.get('demir_kalin_ton_fiyat', 0)

 # 3. BETON HESABI
 beton_fire = fire_oranlari.get('beton_fire_yuzde', 0)
 girilen_beton_m3 = girdiler.get('beton_m3', 0)
 hesaplanan_beton_m3 = girilen_beton_m3 * (1 + (beton_fire / 100))

 # Beton Maliyeti (Malzeme + Pompa)
 birim_beton_toplam = fiyatlar.get('beton_m3_fiyat', 0) + fiyatlar.get('beton_pompa_fiyat', 0)
 mal_beton = hesaplanan_beton_m3 * birim_beton_toplam

 # 4. TOPLAM
 genel_toplam = mal_hafriyat + mal_demir_ince + mal_demir_kalin + mal_beton

 return {
 "ozet_baslik": "Kaba Yapi Malzeme Dokumu",
 "metraj_detaylari": {
 "hafriyat": {
 "miktar": mik_hafriyat,
 "birim": "m3/Sefer"
 },
 "demir_ince_8_12mm": {
 "proje_tonaji": girilen_ince_ton,
 "satin_alinacak_tonaj_fireli": round(hesaplanan_ince_ton, 3)
 },
 "demir_kalin_14mm_plus": {
 "proje_tonaji": girilen_kalin_ton,
 "satin_alinacak_tonaj_fireli": round(hesaplanan_kalin_ton, 3)
 },
 "hazir_beton": {
 "proje_m3": girilen_beton_m3,
 "siparis_m3_fireli": round(hesaplanan_beton_m3, 2)
 }
 },
 "kullanilan_fire_oranlari": {
 "demir_fire": f"%{demir_fire}",
 "beton_fire": f"%{beton_fire}"
 },
 "maliyet_tablosu_tl": {
 "hafriyat_tutari": round(mal_hafriyat, 2),
 "ince_demir_tutari": round(mal_demir_ince, 2),
 "kalin_demir_tutari": round(mal_demir_kalin, 2),
 "beton_tutari": round(mal_beton, 2)
 },
 "genel_toplam_tl": round(genel_toplam, 2)
 }


# =============================================================================
# METAL İŞLERİ (DEMİR DOĞRAMA & ALÜMİNYUM) HESAPLAMA FONKSİYONLARI
# =============================================================================

def hesapla_metal_isleri(
 girdiler: list,
 fiyatlar: dict
) -> dict:
 """
 Demir doğrama ve alüminyum maliyet hesaplaması yapar.
 Korkuluk, pencere demiri ve bahçe kapısı maliyetlerini hesaplar.

 İş türleri:
 - balkon_korkuluk: Balkon korkuluğu (metretül)
 - merdiven_korkuluk: Merdiven korkuluğu/küpeşte (metretül)
 - pencere_demiri: Pencere koruma demiri (m² veya en x boy)
 - bahce_kapisi: Bahçe/garaj kapısı (adet)

 Args:
 girdiler: İş kalemleri listesi. Her kalem dict formatında:
 - tur: 'balkon_korkuluk', 'merdiven_korkuluk', 'pencere_demiri', 'bahce_kapisi'
 - miktar: Uzunluk (mt) veya alan (m²)
 - en, boy: Pencere demiri için ölçüler (cm) - opsiyonel
 - adet: Adet sayısı (varsayılan 1)
 fiyatlar: Birim fiyatlar dict'i:
 - korkuluk_mt_fiyat: TL/mt
 - pencere_demiri_m2_fiyat: TL/m²
 - bahce_kapisi_fiyat: TL/adet

 Returns:
 dict: Metrajlar, maliyet tablosu ve genel toplam
 """

 # Metraj Sayaçları
 metraj = {
 "korkuluk_mt": 0.0,
 "pencere_demir_m2": 0.0,
 "bahce_kapi_adet": 0
 }

 for is_kalemi in girdiler:
 tur = is_kalemi.get('tur', '')
 miktar = is_kalemi.get('miktar', 0)

 # 1. KORKULUKLAR (Metretül)
 if tur in ['balkon_korkuluk', 'merdiven_korkuluk']:
 metraj['korkuluk_mt'] += miktar

 # 2. PENCERE DEMİRLERİ (m²)
 elif tur == 'pencere_demiri':
 # Kullanıcı en x boy girerse alanı hesapla, direkt m² girerse ekle
 if 'en' in is_kalemi and 'boy' in is_kalemi:
 alan = (is_kalemi['en'] * is_kalemi['boy']) / 10000
 metraj['pencere_demir_m2'] += alan * is_kalemi.get('adet', 1)
 else:
 metraj['pencere_demir_m2'] += miktar

 # 3. BAHÇE KAPISI (Adet)
 elif tur == 'bahce_kapisi':
 metraj['bahce_kapi_adet'] += is_kalemi.get('adet', 1)

 # MALİYET HESABI
 korkuluk_tutari = metraj['korkuluk_mt'] * fiyatlar.get('korkuluk_mt_fiyat', 0)
 pencere_tutari = metraj['pencere_demir_m2'] * fiyatlar.get('pencere_demiri_m2_fiyat', 0)
 kapi_tutari = metraj['bahce_kapi_adet'] * fiyatlar.get('bahce_kapisi_fiyat', 0)

 genel_toplam = korkuluk_tutari + pencere_tutari + kapi_tutari

 return {
 "ozet": "Demir ve Aluminyum Dograma Dokumu",
 "metrajlar": {
 "toplam_korkuluk_mt": round(metraj['korkuluk_mt'], 2),
 "pencere_koruma_m2": round(metraj['pencere_demir_m2'], 2),
 "bahce_kapisi_adet": metraj['bahce_kapi_adet']
 },
 "maliyet_tablosu_tl": {
 "korkuluk_tutari": round(korkuluk_tutari, 2),
 "pencere_demir_tutari": round(pencere_tutari, 2),
 "kapi_tutari": round(kapi_tutari, 2)
 },
 "genel_toplam_tl": round(genel_toplam, 2)
 }

