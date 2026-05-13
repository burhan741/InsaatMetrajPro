"""
Proje Şablonları Modülü
İnşaat projesi türlerine göre hazır iş programı şablonları

Özellikler:
- 12 hazır proje şablonu (KONUT, TİCARİ, ENDÜSTRİYEL, ALTYAPI, YENİLEME)
- Her şablon için detaylı iş kalemleri, bağımlılıklar, kaynaklar
- GanttEngine ile doğrudan entegrasyon
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


@dataclass
class SablonGorev:
    """Şablon içindeki iş kalemi tanımı"""
    ad: str
    sure_gun: int
    bagimlilik_indexler: List[int] = field(default_factory=list)  # Aynı şablondaki görev sıra numaraları (0-tabanlı)
    kaynak: str = ""                  # "Kalıpçı Ekibi", "Demir Ustası" vb.
    wbs_kodu: str = ""
    aciklama: str = ""
    renk: str = "#3498db"
    milestone: bool = False


@dataclass
class ProjeSablonu:
    """Hazır proje şablonu"""
    kategori: str      # "KONUT", "TİCARİ", "ENDÜSTRİYEL", "ALTYAPI", "YENİLEME"
    tip: str           # "Villa", "Apartman" vb.
    aciklama: str
    gorevler: List[SablonGorev] = field(default_factory=list)
    ikon: str = ""

    @property
    def tahmini_sure_gun(self) -> int:
        """Şablonun kritik yol uzunluğunu basit toplamla tahmin et"""
        if not self.gorevler:
            return 0
        # Bağımlılık zinciri ile maksimum süre hesapla
        sure_toplam = [0] * len(self.gorevler)
        for i, gorev in enumerate(self.gorevler):
            if gorev.bagimlilik_indexler:
                max_oncul = max(
                    sure_toplam[j] for j in gorev.bagimlilik_indexler
                    if j < i
                )
                sure_toplam[i] = max_oncul + gorev.sure_gun
            else:
                sure_toplam[i] = gorev.sure_gun
        return max(sure_toplam) if sure_toplam else 0


# ==================== ŞABLON VERİTABANI ====================

def _villa_sablon() -> ProjeSablonu:
    gorevler = [
        SablonGorev("Arazi Düzenleme ve Hafriyat",  10, [],    "Hafriyat Ekibi",  "1.1", "Temel hafriyatı"),
        SablonGorev("Temel Kazısı",                   5, [0],   "Hafriyat Ekibi",  "1.2"),
        SablonGorev("Temel Demiri",                   6, [1],   "Demir Ustası",    "1.3", renk="#e74c3c"),
        SablonGorev("Temel Betonlama",                3, [2],   "Beton Ekibi",     "1.4", renk="#e74c3c"),
        SablonGorev("Bodrum Kat Duvarları",           8, [3],   "Duvarcı Ustası",  "2.1"),
        SablonGorev("Bodrum Döşeme Demiri",           5, [4],   "Demir Ustası",    "2.2", renk="#e74c3c"),
        SablonGorev("Bodrum Döşeme Betonlama",        2, [5],   "Beton Ekibi",     "2.3", renk="#e74c3c"),
        SablonGorev("1. Kat Kalıbı",                  6, [6],   "Kalıpçı Ekibi",   "3.1"),
        SablonGorev("1. Kat Demiri",                  5, [7],   "Demir Ustası",    "3.2", renk="#e74c3c"),
        SablonGorev("1. Kat Betonlama",               2, [8],   "Beton Ekibi",     "3.3", renk="#e74c3c"),
        SablonGorev("2. Kat Kalıbı",                  6, [9],   "Kalıpçı Ekibi",   "4.1"),
        SablonGorev("2. Kat Demiri",                  5, [10],  "Demir Ustası",    "4.2", renk="#e74c3c"),
        SablonGorev("2. Kat Betonlama",               2, [11],  "Beton Ekibi",     "4.3", renk="#e74c3c"),
        SablonGorev("Çatı Taşıyıcı Sistemi",         10, [12],  "Çatı Ustası",     "5.1"),
        SablonGorev("Çatı Örtüsü ve Su Yalıtımı",    8, [13],  "Çatı Ustası",     "5.2"),
        SablonGorev("Dış Cephe İnce İşler",           7, [14],  "Sıvacı Ustası",   "5.3"),
        SablonGorev("İç Kaba Sıva",                  12, [14],  "Sıvacı Ustası",   "6.1"),
        SablonGorev("Dış İnce Sıva / Mantolama",     10, [16],  "Sıvacı Ustası",   "6.2"),
        SablonGorev("Pencere ve Kapı Montajı",         8, [16],  "Doğrama Ekibi",  "6.3"),
        SablonGorev("Elektrik Tesisatı (Ham)",         8, [16],  "Elektrik Ustası", "7.1"),
        SablonGorev("Sıhhi Tesisat (Ham)",             7, [16],  "Tesisatçı",       "7.2"),
        SablonGorev("İç İnce Sıva",                  10, [19, 20], "Sıvacı Ustası","6.4"),
        SablonGorev("Fayans / Seramik",               10, [21],  "Fayans Ustası",  "8.1"),
        SablonGorev("Parke / Laminant Döşeme",         7, [21],  "Parke Ustası",   "8.2"),
        SablonGorev("Elektrik Tesisatı (Ön Yüz)",     5, [21],  "Elektrik Ustası", "7.3"),
        SablonGorev("Sıhhi Tesisat (Ön Yüz)",         5, [21],  "Tesisatçı",       "7.4"),
        SablonGorev("İç Boya",                         8, [22, 23], "Boyacı",       "9.1"),
        SablonGorev("Dış Boya / Son Kat Sıva",         7, [17],  "Boyacı",         "9.2"),
        SablonGorev("Peyzaj ve Çevre Düzenleme",       5, [26, 27], "Peyzaj Ekibi","10.1"),
        SablonGorev("Proje Teslim",                    1, [28],  "",               "10.2",
                    "Yapı kullanım izni", milestone=True),
    ]
    return ProjeSablonu(
        kategori="KONUT", tip="Villa",
        aciklama="Müstakil villa inşaatı (2 katlı, yakl. 8-9 ay)",
        gorevler=gorevler, ikon="🏡"
    )


def _mustakil_ev_sablon() -> ProjeSablonu:
    gorevler = [
        SablonGorev("Hafriyat ve Temel Kazısı",     7,  [],   "Hafriyat Ekibi", "1.1"),
        SablonGorev("Temel Demiri",                  5,  [0],  "Demir Ustası",   "1.2", renk="#e74c3c"),
        SablonGorev("Temel Betonlama",               2,  [1],  "Beton Ekibi",    "1.3", renk="#e74c3c"),
        SablonGorev("Zemin Kat Duvarları",           7,  [2],  "Duvarcı Ustası", "2.1"),
        SablonGorev("Zemin Kat Döşeme Demiri",       4,  [3],  "Demir Ustası",   "2.2", renk="#e74c3c"),
        SablonGorev("Zemin Kat Döşeme Betonu",       2,  [4],  "Beton Ekibi",    "2.3", renk="#e74c3c"),
        SablonGorev("Çatı",                          8,  [5],  "Çatı Ustası",    "3.1"),
        SablonGorev("İç Kaba Sıva",                 10,  [6],  "Sıvacı Ustası",  "4.1"),
        SablonGorev("Pencere - Kapı Montajı",        5,  [6],  "Doğrama Ekibi",  "4.2"),
        SablonGorev("Elektrik ve Tesisat",          10,  [7, 8], "Usta Ekibi",   "5.1"),
        SablonGorev("İnce Sıva",                     8,  [9],  "Sıvacı Ustası",  "4.3"),
        SablonGorev("Fayans ve Döşeme",              8,  [10], "Fayans Ustası",  "6.1"),
        SablonGorev("Boya",                          6,  [11], "Boyacı",         "7.1"),
        SablonGorev("Dış Sıva ve Boya",              6,  [12], "Sıvacı/Boyacı",  "7.2"),
        SablonGorev("Teslim",                        1,  [13], "",               "8.1", milestone=True),
    ]
    return ProjeSablonu(
        kategori="KONUT", tip="Müstakil Ev",
        aciklama="1 katlı müstakil konut (yakl. 5-6 ay)",
        gorevler=gorevler, ikon="🏠"
    )


def _apartman_5kat_sablon() -> ProjeSablonu:
    gorevler = [
        SablonGorev("Hafriyat ve Temel Kazısı",     15,  [],    "Hafriyat Ekibi",  "1.1"),
        SablonGorev("Zemin İyileştirme ve Dolgu",    8,  [0],   "Hafriyat Ekibi",  "1.2"),
        SablonGorev("Temel Radye/Döşeme Demiri",    10,  [1],   "Demir Ustası",    "1.3", renk="#e74c3c"),
        SablonGorev("Temel Betonlama",               4,  [2],   "Beton Ekibi",     "1.4", renk="#e74c3c"),
        SablonGorev("Bodrum Kalıp/Demir/Beton",     20,  [3],   "Kaba Yapı Ekibi", "2.1", renk="#e74c3c"),
        SablonGorev("Zemin Kat Kalıp/Demir/Beton",  15,  [4],   "Kaba Yapı Ekibi", "3.1", renk="#e74c3c"),
        SablonGorev("1. Kat Kalıp/Demir/Beton",     15,  [5],   "Kaba Yapı Ekibi", "4.1", renk="#e74c3c"),
        SablonGorev("2. Kat Kalıp/Demir/Beton",     15,  [6],   "Kaba Yapı Ekibi", "5.1", renk="#e74c3c"),
        SablonGorev("3. Kat Kalıp/Demir/Beton",     15,  [7],   "Kaba Yapı Ekibi", "6.1", renk="#e74c3c"),
        SablonGorev("4. Kat Kalıp/Demir/Beton",     15,  [8],   "Kaba Yapı Ekibi", "7.1", renk="#e74c3c"),
        SablonGorev("5. Kat ve Çatı Katı",          20,  [9],   "Kaba Yapı Ekibi", "8.1", renk="#e74c3c"),
        SablonGorev("Çatı Örtüsü",                   8,  [10],  "Çatı Ustası",     "8.2"),
        SablonGorev("Dış Cephe Kaplama Hazırlık",   10,  [11],  "Sıvacı Ustası",   "9.1"),
        SablonGorev("Tüm Kat Kaba İç Sıva",         30,  [11],  "Sıvacı Ustası",   "9.2"),
        SablonGorev("Pencere-Kapı Tüm Katlar",      15,  [13],  "Doğrama Ekibi",   "9.3"),
        SablonGorev("Elektrik Ham Tesisat",          20,  [13],  "Elektrik Ustası", "10.1"),
        SablonGorev("Sıhhi Tesisat Ham",             20,  [13],  "Tesisatçı",       "10.2"),
        SablonGorev("Isıtma Sistemi",                15,  [15, 16], "Tesisatçı",    "10.3"),
        SablonGorev("Asansör Tesis",                 20,  [13],  "Asansör Firması", "10.4"),
        SablonGorev("İnce Sıva Tüm Katlar",         30,  [14, 15, 16], "Sıvacı",  "11.1"),
        SablonGorev("Fayans ve Seramik",             25,  [19],  "Fayans Ustası",   "11.2"),
        SablonGorev("Parke Döşeme",                  20,  [19],  "Parke Ustası",    "11.3"),
        SablonGorev("İç Boya",                       20,  [20, 21], "Boyacı",       "12.1"),
        SablonGorev("Dış Cephe Sıva/Boya",          20,  [12],  "Sıvacı/Boyacı",   "12.2"),
        SablonGorev("Elektrik Ön Yüz",              10,  [22],  "Elektrik Ustası", "13.1"),
        SablonGorev("Sıhhi Tesisat Ön Yüz",         10,  [22],  "Tesisatçı",       "13.2"),
        SablonGorev("Ortak Alan Düzenleme",          15,  [23],  "Genel Ekip",      "13.3"),
        SablonGorev("İskan ve Teslim",               1,   [26],  "",                "14.1", milestone=True),
    ]
    return ProjeSablonu(
        kategori="KONUT", tip="Apartman (5 Kat)",
        aciklama="5 katlı konut apartmanı (yakl. 18-20 ay)",
        gorevler=gorevler, ikon="🏢"
    )


def _toplu_konut_sablon() -> ProjeSablonu:
    gorevler = [
        SablonGorev("Altyapı ve İnfrastrüktür",      30,  [],    "Alt Yapı Ekibi",  "1.1"),
        SablonGorev("A Blok Kaba Yapı",               90,  [0],   "Kaba Yapı Ekibi", "2.1", renk="#e74c3c"),
        SablonGorev("B Blok Kaba Yapı",               90,  [0],   "Kaba Yapı Ekibi", "2.2", renk="#e74c3c"),
        SablonGorev("A Blok İnce İşler",              60,  [1],   "İnce İş Ekibi",   "3.1"),
        SablonGorev("B Blok İnce İşler",              60,  [2],   "İnce İş Ekibi",   "3.2"),
        SablonGorev("Çevre Peyzaj ve Altyapı",        30,  [3, 4],"Peyzaj Ekibi",    "4.1"),
        SablonGorev("Ortak Alan ve Sosyal Donatılar", 20,  [5],   "Genel Ekip",      "4.2"),
        SablonGorev("Toplu İskan",                     1,  [6],   "",                "5.1", milestone=True),
    ]
    return ProjeSablonu(
        kategori="KONUT", tip="Toplu Konut",
        aciklama="2 bloklu toplu konut projesi (yakl. 18 ay)",
        gorevler=gorevler, ikon="🏘"
    )


def _dukkan_ofis_sablon() -> ProjeSablonu:
    gorevler = [
        SablonGorev("Hafriyat ve Temel",              10,  [],    "Hafriyat Ekibi",  "1.1"),
        SablonGorev("Temel Beton ve Kür",             18,  [0],   "Beton Ekibi",     "1.2", renk="#e74c3c"),
        SablonGorev("Kaba Yapı (İskelet)",            25,  [1],   "Kaba Yapı Ekibi", "2.1", renk="#e74c3c"),
        SablonGorev("Çatı",                            8,  [2],   "Çatı Ustası",     "2.2"),
        SablonGorev("Cephe Kaplama",                  15,  [3],   "Cephe Ekibi",     "3.1"),
        SablonGorev("İç Bölmeler ve Sıva",            20,  [2],   "Duvarcı/Sıvacı",  "3.2"),
        SablonGorev("Tesisat (Elektrik/Su/Isıtma)",  15,  [5],   "Tesisat Ekibi",   "4.1"),
        SablonGorev("Zemin Döşeme",                   10,  [6],   "Döşeme Ustası",   "4.2"),
        SablonGorev("Boya ve Son Kat",                10,  [7],   "Boyacı",          "5.1"),
        SablonGorev("Teslim",                          1,  [8],   "",                "5.2", milestone=True),
    ]
    return ProjeSablonu(
        kategori="TİCARİ", tip="Dükkan / Ofis",
        aciklama="Ticari dükkan veya ofis binası (yakl. 5-6 ay)",
        gorevler=gorevler, ikon="🏪"
    )


def _otel_sablon() -> ProjeSablonu:
    gorevler = [
        SablonGorev("Zemin Etüdü ve Hafriyat",       20,  [],    "Hafriyat Ekibi",  "1.1"),
        SablonGorev("Temel Sistem",                   25,  [0],   "Beton Ekibi",     "1.2", renk="#e74c3c"),
        SablonGorev("Bodrum ve Otopark Katı",         40,  [1],   "Kaba Yapı Ekibi", "2.1", renk="#e74c3c"),
        SablonGorev("1-3 Kat Kaba Yapı",              60,  [2],   "Kaba Yapı Ekibi", "3.1", renk="#e74c3c"),
        SablonGorev("4-6 Kat Kaba Yapı",              60,  [3],   "Kaba Yapı Ekibi", "3.2", renk="#e74c3c"),
        SablonGorev("Çatı Katı ve Teras",             25,  [4],   "Çatı/Kaba Yapı",  "3.3"),
        SablonGorev("Cephe Sistemi",                  40,  [5],   "Cephe Ekibi",     "4.1"),
        SablonGorev("Mekanik ve Elektrik Tesisatı",   50,  [3],   "M/E Ekibi",       "5.1"),
        SablonGorev("Asansör ve Yürüyen Merdiven",    30,  [7],   "Asansör Firması", "5.2"),
        SablonGorev("Oda İnce İşleri (Ham)",          60,  [7],   "İnce İş Ekibi",   "6.1"),
        SablonGorev("Mutfak ve Restoranlar",          40,  [9],   "Özel Ekip",       "6.2"),
        SablonGorev("Oda İnce İşleri (Boya/Kaplama)", 50, [10],  "Dekoratör",       "7.1"),
        SablonGorev("Ortak Alan ve Lobi",             30,  [11],  "Dekoratör",       "7.2"),
        SablonGorev("Bahçe ve Havuz",                 25,  [11],  "Peyzaj Ekibi",    "8.1"),
        SablonGorev("Açılış",                          1,  [12, 13], "",             "9.1", milestone=True),
    ]
    return ProjeSablonu(
        kategori="TİCARİ", tip="Otel",
        aciklama="Butik otel (6 katlı, yakl. 24 ay)",
        gorevler=gorevler, ikon="🏨"
    )


def _fabrika_depo_sablon() -> ProjeSablonu:
    gorevler = [
        SablonGorev("Zemin Sıkıştırma ve Dolgu",     15,  [],    "İş Makinesi",     "1.1"),
        SablonGorev("Temel Kazık/Radye",              20,  [0],   "Temel Ekibi",     "1.2", renk="#e74c3c"),
        SablonGorev("Prefabrik Beton Kolonlar",       15,  [1],   "Montaj Ekibi",    "2.1"),
        SablonGorev("Prefabrik Çatı Kirişleri",       10,  [2],   "Montaj Ekibi",    "2.2"),
        SablonGorev("Çatı Paneli Montajı",            12,  [3],   "Çatı Ekibi",      "2.3"),
        SablonGorev("Cephe Panel / Sandviç Panel",    15,  [4],   "Cephe Ekibi",     "3.1"),
        SablonGorev("Sanayi Tipi Zemin Döşeme",       20,  [5],   "Beton Ekibi",     "3.2", renk="#e74c3c"),
        SablonGorev("Elektrik Güç ve Aydınlatma",     15,  [6],   "Elektrik Ustası", "4.1"),
        SablonGorev("Yangın Söndürme ve Havalandırma",12, [7],   "Tesisat Ekibi",   "4.2"),
        SablonGorev("Kapı ve Rampa Sistemleri",       10,  [8],   "Montaj Ekibi",    "4.3"),
        SablonGorev("Ofis Alanı İnce İşler",          15,  [9],   "İnce İş Ekibi",   "5.1"),
        SablonGorev("Teslim",                          1,  [10],  "",                "6.1", milestone=True),
    ]
    return ProjeSablonu(
        kategori="ENDÜSTRİYEL", tip="Fabrika / Depo",
        aciklama="Sanayi tipi prefabrik yapı (yakl. 5-6 ay)",
        gorevler=gorevler, ikon="🏭"
    )


def _yol_sablon() -> ProjeSablonu:
    gorevler = [
        SablonGorev("Kamulaştırma ve Güzergah Hazırlık", 20, [],   "Proje Ekibi",  "1.1"),
        SablonGorev("Hafriyat ve Dolgu (km 0-5)",        25, [0],  "İş Makinesi",  "2.1"),
        SablonGorev("Hafriyat ve Dolgu (km 5-10)",       25, [1],  "İş Makinesi",  "2.2"),
        SablonGorev("Menfez ve Sanat Yapıları",          30, [1],  "İnşaat Ekibi", "3.1"),
        SablonGorev("Alt Temel Serimi (km 0-5)",         20, [2],  "Yol Makinesi", "4.1"),
        SablonGorev("Alt Temel Serimi (km 5-10)",        20, [3],  "Yol Makinesi", "4.2"),
        SablonGorev("Temel Serimi ve Sıkıştırma",        25, [4, 5], "Yol Makinesi","5.1"),
        SablonGorev("Binder Asfalt",                     15, [6],  "Asfalt Ekibi", "6.1"),
        SablonGorev("Aşınma Tabakası Asfalt",            12, [7],  "Asfalt Ekibi", "6.2"),
        SablonGorev("Trafik İşaretleme ve Levhalar",      8, [8],  "İşaret Ekibi", "7.1"),
        SablonGorev("Teslim",                             1, [9],  "",             "8.1", milestone=True),
    ]
    return ProjeSablonu(
        kategori="ALTYAPI", tip="Yol",
        aciklama="10 km'lik asfalt yol projesi (yakl. 6 ay)",
        gorevler=gorevler, ikon="🛣"
    )


def _istinat_duvari_sablon() -> ProjeSablonu:
    gorevler = [
        SablonGorev("Hafriyat ve Kazı",               10,  [],   "Hafriyat Ekibi", "1.1"),
        SablonGorev("Temel Temizleme ve Hazırlık",      5,  [0],  "Genel Ekip",     "1.2"),
        SablonGorev("Temel Kalıbı ve Demiri",           6,  [1],  "Demir Ustası",   "1.3", renk="#e74c3c"),
        SablonGorev("Temel Betonlama",                  3,  [2],  "Beton Ekibi",    "1.4", renk="#e74c3c"),
        SablonGorev("Duvar Kalıp ve Demiri",           12,  [3],  "Demir Ustası",   "2.1", renk="#e74c3c"),
        SablonGorev("Duvar Betonlama",                  5,  [4],  "Beton Ekibi",    "2.2", renk="#e74c3c"),
        SablonGorev("Kalıp Sökümü",                     2,  [5],  "Kalıpçı Ekibi", "2.3"),
        SablonGorev("Drenaj Sistemi",                   8,  [6],  "Genel Ekip",     "3.1"),
        SablonGorev("Geri Dolgu ve Sıkıştırma",        6,  [7],  "İş Makinesi",    "3.2"),
        SablonGorev("Teslim",                           1,  [8],  "",               "4.1", milestone=True),
    ]
    return ProjeSablonu(
        kategori="ALTYAPI", tip="İstinat Duvarı",
        aciklama="Betonarme istinat duvarı (yakl. 3-4 ay)",
        gorevler=gorevler, ikon="🧱"
    )


def _tadilat_sablon() -> ProjeSablonu:
    gorevler = [
        SablonGorev("Mevcut Malzeme Sökümü",           5,  [],   "Yıkım Ekibi",    "1.1"),
        SablonGorev("Elektrik Tesisatı Yenileme",       8,  [0],  "Elektrik Ustası","2.1"),
        SablonGorev("Sıhhi Tesisat Yenileme",           7,  [0],  "Tesisatçı",      "2.2"),
        SablonGorev("İç Sıva (Yamama/Yenileme)",        6,  [1, 2], "Sıvacı",       "3.1"),
        SablonGorev("Fayans / Banyo Yenileme",          6,  [3],  "Fayans Ustası",  "3.2"),
        SablonGorev("Zemin Döşeme Yenileme",            5,  [3],  "Döşeme Ustası",  "3.3"),
        SablonGorev("Mutfak Dolap ve Tezgah",           5,  [4, 5], "Marangoz",     "4.1"),
        SablonGorev("İç Boya",                          5,  [6],  "Boyacı",         "5.1"),
        SablonGorev("Kapı - Pencere Yenileme",          4,  [6],  "Doğrama Ekibi",  "5.2"),
        SablonGorev("Teslim",                           1,  [7, 8], "",             "6.1", milestone=True),
    ]
    return ProjeSablonu(
        kategori="YENİLEME", tip="Tadilat",
        aciklama="Daire/konut iç mekan tadilatı (yakl. 2 ay)",
        gorevler=gorevler, ikon="🔨"
    )


def _mantolama_sablon() -> ProjeSablonu:
    gorevler = [
        SablonGorev("İskele Kurulumu",                  5,  [],   "İskele Ekibi",   "1.1"),
        SablonGorev("Mevcut Kaplama Temizliği",         6,  [0],  "Genel Ekip",     "1.2"),
        SablonGorev("Yüzey Sıva Tamiri",                5,  [1],  "Sıvacı Ustası",  "1.3"),
        SablonGorev("XPS/EPS Levha Yapıştırma",        10,  [2],  "Mantolama Ekibi","2.1"),
        SablonGorev("Dübel Uygulaması",                 3,  [3],  "Mantolama Ekibi","2.2"),
        SablonGorev("Sıva Donatısı (File ve Köşebent)", 5,  [4],  "Sıvacı Ustası",  "2.3"),
        SablonGorev("Baz Sıva",                         7,  [5],  "Sıvacı Ustası",  "3.1"),
        SablonGorev("Dış Cephe Boyası / Kaplama",       6,  [6],  "Boyacı",         "3.2"),
        SablonGorev("İskele Sökümü ve Temizlik",        3,  [7],  "İskele Ekibi",   "4.1"),
        SablonGorev("Teslim",                           1,  [8],  "",               "5.1", milestone=True),
    ]
    return ProjeSablonu(
        kategori="YENİLEME", tip="Dış Cephe Mantolama",
        aciklama="Bina dış cephe ısı yalıtımı ve mantolama (yakl. 2-3 ay)",
        gorevler=gorevler, ikon="🧊"
    )


def _betonarme_kaba_yapi_sablon() -> ProjeSablonu:
    """
    Betonarme yapı kaba inşaat şablonu — CŞB birim fiyat analizlerine göre.
    Her yapısal eleman (temel / kolon / döşeme) için Kalıp → Demir → Beton → Kür sırası.
    Yaklaşık süre: 90-120 gün (3-4 usta, tek kat).
    """
    gorevler = [
        # ── 1. HAZIRLIK ─────────────────────────────────────────────────
        SablonGorev(
            "Şantiye Kurulumu ve Hazırlık", 3, [],
            "Şef / Yönetim", "1.1",
            "Konteyner, elektrik, su bağlantısı, şantiye tabelası",
        ),
        SablonGorev(
            "Hafriyat ve İksa", 10, [0],
            "Hafriyat Ekibi (İş Makinesi)", "1.2",
            "Temel kazısı; iksa/şev gerekli ise uygula — zemin raporu referans alınmalı",
            renk="#795548",
        ),
        # ── 2. TEMEL ────────────────────────────────────────────────────
        SablonGorev(
            "Temel Grobeton (C16)", 2, [1],
            "Beton Ekibi", "2.1",
            "5 cm grobeton — temel kalıbını taşır, zemin sertleştirme",
            renk="#607d8b",
        ),
        SablonGorev(
            "Temel Kalıbı", 4, [2],
            "Kalıpçı Ekibi", "2.2",
            "CŞB verimlilik: 2.86 m²/gün/usta — sürgülü sistem tercih edilmeli",
        ),
        SablonGorev(
            "Temel Demiri", 6, [3],
            "Demirci (Bağlama/Bükme)", "2.3",
            "CŞB: 333 kg/gün/usta — nervürlü, min Ø12 — pas payı 4 cm zemin",
            renk="#e74c3c",
        ),
        SablonGorev(
            "Temel Betonu (C25/C30)", 2, [4],
            "Beton Ekibi", "2.4",
            "Beton Sınıfı: C25/C30 min. — vibrasyon zorunlu — gece dökümünden kaçın",
            renk="#e74c3c",
        ),
        SablonGorev(
            "Temel Kalıbı Sökümü", 2, [5],
            "Kalıpçı Ekibi", "2.5",
            "CŞB: 8.0 m²/gün/usta sökme verimliliği",
        ),
        # ── 3. KOLON ────────────────────────────────────────────────────
        SablonGorev(
            "Kolon Demiri (Filiz + Bağlama)", 5, [6],
            "Demirci (Bağlama/Bükme)", "3.1",
            "Temel filizleri ekleme + kolon demirleri; bindirme boyu min 40∅",
            renk="#e74c3c",
        ),
        SablonGorev(
            "Kolon Kalıbı", 4, [7],
            "Kalıpçı Ekibi", "3.2",
            "CŞB: 1.82 m²/gün/usta (kolon) — çift taraflı şaplı kalıp",
        ),
        SablonGorev(
            "Kolon Betonu (C25/C30)", 1, [8],
            "Beton Ekibi", "3.3",
            "Kolonlar önce dökülür — döşeme ile aynı günde dökme — TS500 uyumu",
            renk="#e74c3c",
        ),
        SablonGorev(
            "Kolon Kalıbı Sökümü", 2, [9],
            "Kalıpçı Ekibi", "3.4",
        ),
        # ── 4. DÖŞEME ───────────────────────────────────────────────────
        SablonGorev(
            "Döşeme Kalıbı (Aşıklar + Levha)", 6, [10],
            "Kalıpçı Ekibi", "4.1",
            "CŞB: 4.0 m²/gün/usta — alüminyum kalıp mevcut ise verimlilik 2x",
        ),
        SablonGorev(
            "Döşeme Demiri (Alt + Üst Donatı)", 8, [11],
            "Demirci (Bağlama/Bükme)", "4.2",
            "CŞB: 250 kg/gün/usta nervürlü soğuk demir — mesnet donatıları unutulmamalı",
            renk="#e74c3c",
        ),
        SablonGorev(
            "Döşeme Betonu (C25/C30)", 2, [12],
            "Beton Ekibi", "4.3",
            "Pompalı beton önerilir — perdah beton yüzeyinde — bölge kotuna dikkat",
            renk="#e74c3c",
        ),
        SablonGorev(
            "Döşeme Kalıbı Sökümü", 3, [13],
            "Kalıpçı Ekibi", "4.4",
            "CŞB: 8.0 m²/gün/usta sökme — döşeme betonu yeterince sertleşmeli",
        ),
        # ── 5. TAMAMLAMA ────────────────────────────────────────────────
        SablonGorev(
            "Dolgu ve Tesviye", 5, [14],
            "Hafriyat Ekibi", "5.1",
            "Temel çevresi geri dolgu — sıkıştırma kademeleri max 30 cm",
            renk="#795548",
        ),
        SablonGorev(
            "Kaba Yapı Kontrolü ve Teslim", 1, [15],
            "Şef / Kontrol Mühendisi", "6.1",
            "Röperli kontrol, beton dayanım raporu, TSE belgesi — Milestone",
            milestone=True,
        ),
    ]
    return ProjeSablonu(
        kategori="KONUT",
        tip="Betonarme Kaba Yapı",
        aciklama=(
            "Tek katlı betonarme yapı kaba inşaat şablonu — CŞB birim fiyat verimlilik "
            "değerlerine göre. Temel → Kolon → Döşeme sırası, her eleman için "
            "Kalıp / Demir / Beton / Kalıp Sökümü ayrı görev (yakl. 60-80 gün)."
        ),
        gorevler=gorevler,
        ikon="🏗️",
    )


# Tüm şablonlar listesi
_TUM_SABLONLAR: List[ProjeSablonu] = [
    _betonarme_kaba_yapi_sablon(),
    _villa_sablon(),
    _mustakil_ev_sablon(),
    _apartman_5kat_sablon(),
    _toplu_konut_sablon(),
    _dukkan_ofis_sablon(),
    _otel_sablon(),
    _fabrika_depo_sablon(),
    _yol_sablon(),
    _istinat_duvari_sablon(),
    _tadilat_sablon(),
    _mantolama_sablon(),
]


# ==================== YÖNETİCİ SINIFI ====================

class SablonYoneticisi:
    """
    Proje şablonları yönetimi.

    Neyi çözüyoruz?
    - Teknik proje yönetimi bilgisine sahip olmayan kullanıcıların boş iş programı
      yerine hazır şablonla başlamasını sağlıyoruz.
    - Hata Payı: Sıfır. Şablon verileri sabit ve doğrulanmış.

    Test:
    - ym = SablonYoneticisi()
    - kategoriler = ym.get_kategoriler()  # ["KONUT", "TİCARİ", ...]
    - sablonlar = ym.get_sablonlar("KONUT")  # [Villa, Müstakil Ev, ...]
    """

    def __init__(self):
        self._sablonlar = _TUM_SABLONLAR

    def get_kategoriler(self) -> List[str]:
        """Mevcut kategori listesini döndür (benzersiz, sıralı)"""
        seen = []
        for s in self._sablonlar:
            if s.kategori not in seen:
                seen.append(s.kategori)
        return seen

    def get_sablonlar(self, kategori: str) -> List[ProjeSablonu]:
        """Belirli bir kategorideki şablonları döndür"""
        return [s for s in self._sablonlar if s.kategori == kategori]

    def get_sablon(self, kategori: str, tip: str) -> Optional[ProjeSablonu]:
        """Kategori ve tip ile şablon bul"""
        for s in self._sablonlar:
            if s.kategori == kategori and s.tip == tip:
                return s
        return None

    def engine_yukle(
        self,
        engine,          # GanttEngine instance
        sablon: ProjeSablonu,
        baslangic_tarihi: datetime,
        mevcut_max_id: int = 0
    ) -> Dict[str, Any]:
        """
        Şablondaki görevleri GanttEngine'e ekle.

        Args:
            engine: GanttEngine instance
            sablon: Yüklenecek şablon
            baslangic_tarihi: İlk görevin başlangıç tarihi
            mevcut_max_id: Mevcut maksimum task_id (çakışma önleme)

        Returns:
            {'success': bool, 'eklenen_gorev': int, 'hata': str}
        """
        try:
            from app.core.gantt_engine import Task

            # Task ID başlangıcı: mevcut maksimuma göre ayarla
            id_offset = mevcut_max_id + 1

            # Tüm görevleri oluştur ve engine'e ekle
            task_map: Dict[int, int] = {}  # sablon_index -> engine_task_id

            for idx, sg in enumerate(sablon.gorevler):
                task_id = id_offset + idx
                task = Task(
                    task_id=task_id,
                    ad=sg.ad,
                    sure_gun=sg.sure_gun,
                    baslangic_tarihi=baslangic_tarihi,
                    kaynak=sg.kaynak,
                    wbs_kodu=sg.wbs_kodu if sg.wbs_kodu else f"{idx+1}",
                    aciklama=sg.aciklama,
                    milestone=sg.milestone,
                    renk=sg.renk,
                )
                engine.add_task(task)
                task_map[idx] = task_id

            # Bağımlılıkları ekle
            for idx, sg in enumerate(sablon.gorevler):
                for dep_idx in sg.bagimlilik_indexler:
                    if dep_idx < len(sablon.gorevler) and dep_idx in task_map:
                        engine.add_dependency(
                            predecessor_id=task_map[dep_idx],
                            successor_id=task_map[idx],
                            dep_type='FS'
                        )

            # CPM hesapla
            engine.calculate_schedule(baslangic_tarihi)

            logger.info(
                f"Şablon yüklendi: {sablon.kategori}/{sablon.tip} "
                f"({len(sablon.gorevler)} görev)"
            )

            return {
                'success': True,
                'eklenen_gorev': len(sablon.gorevler),
                'sablon_adi': f"{sablon.ikon} {sablon.tip}",
            }

        except Exception as e:
            logger.error(f"Şablon yükleme hatası: {e}")
            return {'success': False, 'hata': str(e)}

    def get_ozet(self, sablon: ProjeSablonu) -> str:
        """Şablon özet metni"""
        return (
            f"{sablon.aciklama}\n"
            f"{len(sablon.gorevler)} iş kalemi · "
            f"~{sablon.tahmini_sure_gun} iş günü tahmini süre"
        )
