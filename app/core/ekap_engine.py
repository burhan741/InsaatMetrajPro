"""
EKAP (Elektronik Kamu Alımları Platformu) API Engine
Kamu İhale Kurumu ihaleleri sorgulama motoru
API Referans: https://ekap.kik.gov.tr/EKAP/rest/ws/
"""
import logging
import json
import time
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

EKAP_BASE_URL = "https://ekap.kik.gov.tr/EKAP/rest/ws"

IHALE_TURLERI = {
    "1": "Yapım İşi",
    "2": "Hizmet Alımı",
    "3": "Mal Alımı",
    "4": "Danışmanlık Hizmet Alımı",
}

IHALE_USULLERI = {
    "1": "Açık İhale Usulü",
    "2": "Belli İstekliler Arasında",
    "3": "Pazarlık Usulü",
    "4": "Doğrudan Temin",
    "5": "Design-Build",
}

IHALE_DURUMLARI = {
    "1": "Ön İlan",
    "2": "İhale İlanı",
    "3": "Sonuçlandı",
    "4": "İptal Edildi",
    "5": "Düzeltme İlanı",
}

ILLER = [
    "Adana", "Adıyaman", "Afyonkarahisar", "Ağrı", "Amasya",
    "Ankara", "Antalya", "Artvin", "Aydın", "Balıkesir",
    "Bilecik", "Bingöl", "Bitlis", "Bolu", "Burdur",
    "Bursa", "Çanakkale", "Çankırı", "Çorum", "Denizli",
    "Diyarbakır", "Edirne", "Elazığ", "Erzincan", "Erzurum",
    "Eskişehir", "Gaziantep", "Giresun", "Gümüşhane", "Hakkari",
    "Hatay", "Isparta", "Mersin", "İstanbul", "İzmir",
    "Kars", "Kastamonu", "Kayseri", "Kırklareli", "Kırşehir",
    "Kocaeli", "Konya", "Kütahya", "Malatya", "Manisa",
    "Kahramanmaraş", "Mardin", "Muğla", "Muş", "Nevşehir",
    "Niğde", "Ordu", "Rize", "Sakarya", "Samsun",
    "Siirt", "Sinop", "Sivas", "Tekirdağ", "Tokat",
    "Trabzon", "Tunceli", "Şanlıurfa", "Uşak", "Van",
    "Yozgat", "Zonguldak", "Aksaray", "Bayburt", "Karaman",
    "Kırıkkale", "Batman", "Şırnak", "Bartın", "Ardahan",
    "Iğdır", "Yalova", "Karabük", "Kilis", "Osmaniye", "Düzce",
]


class EKAPSonucu:
    """Tek bir EKAP ihale kaydı"""

    def __init__(self, veri: Dict[str, Any]):
        self.ihale_no = str(veri.get("ihaleNo", "") or veri.get("ilanNo", ""))
        self.ihale_adi = str(veri.get("ihaleAdi", "") or veri.get("ilanAdi", ""))
        self.idare_adi = str(veri.get("idareAdi", "") or veri.get("idareler", {}).get("idareAdi", ""))
        self.ihale_tarihi = str(veri.get("ihaleTarihi", "") or veri.get("teklifTarihi", ""))
        self.teklif_son_tarihi = str(veri.get("teklifSonTarihi", ""))
        tur_kodu = str(veri.get("ihaleTuru", "") or veri.get("ilanTuru", ""))
        self.ihale_turu = IHALE_TURLERI.get(tur_kodu, veri.get("ihaleTuruAdi", tur_kodu))
        usul_kodu = str(veri.get("ihaleUsulu", ""))
        self.ihale_usulu = IHALE_USULLERI.get(usul_kodu, veri.get("ihaleUsuluAdi", usul_kodu))
        durum_kodu = str(veri.get("durum", "") or veri.get("ilanDurumu", ""))
        self.durum = IHALE_DURUMLARI.get(durum_kodu, veri.get("durumAdi", durum_kodu))
        self.tahmini_bedel = float(veri.get("tahminiMaliyet", 0) or veri.get("tahminiDeger", 0) or 0)
        self.para_birimi = str(veri.get("paraBirimi", "TL"))
        self.il = str(veri.get("il", "") or veri.get("ihaleSehri", ""))
        self.kayit_no = str(veri.get("kayitNo", "") or veri.get("ilanNo", ""))
        self.ihale_url = str(veri.get("ihaleUrl", ""))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ihale_no":        self.ihale_no,
            "ihale_adi":       self.ihale_adi,
            "idare_adi":       self.idare_adi,
            "ihale_tarihi":    self.ihale_tarihi,
            "teklif_son_tarihi": self.teklif_son_tarihi,
            "ihale_turu":      self.ihale_turu,
            "ihale_usulu":     self.ihale_usulu,
            "durum":           self.durum,
            "tahmini_bedel":   self.tahmini_bedel,
            "para_birimi":     self.para_birimi,
            "il":              self.il,
            "kayit_no":        self.kayit_no,
            "ihale_url":       self.ihale_url,
        }


class EKAPEngine:
    """EKAP REST API istemcisi"""

    def __init__(self):
        self._son_istek_zamani: float = 0.0
        self._min_istek_araligi: float = 1.0
        self._cache: Dict[str, Any] = {}
        self._cache_suresi: int = 300
        self._cache_zamanlari: Dict[str, float] = {}

    # ── HTTP ─────────────────────────────────────────────────────────────────

    def _istek_gonder(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> Optional[Any]:
        """Rate-limited GET isteği"""
        gecen = time.time() - self._son_istek_zamani
        if gecen < self._min_istek_araligi:
            time.sleep(self._min_istek_araligi - gecen)

        url = f"{EKAP_BASE_URL}/{endpoint}"
        cache_key = f"{url}|{json.dumps(params or {}, sort_keys=True)}"

        if cache_key in self._cache:
            if time.time() - self._cache_zamanlari.get(cache_key, 0) < self._cache_suresi:
                return self._cache[cache_key]

        try:
            import urllib.request
            import urllib.parse

            if params:
                url = url + "?" + urllib.parse.urlencode(params)

            req = urllib.request.Request(
                url,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "InsaatMetrajPro/1.0",
                    "Accept-Language": "tr-TR,tr;q=0.9",
                },
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                veri = json.loads(resp.read().decode("utf-8"))
                self._cache[cache_key] = veri
                self._cache_zamanlari[cache_key] = time.time()
                self._son_istek_zamani = time.time()
                return veri
        except Exception as e:
            logger.error(f"EKAP API isteği başarısız [{endpoint}]: {e}")
            return None

    # ── Sorgular ─────────────────────────────────────────────────────────────

    def ihale_ara(
        self,
        anahtar_kelime: str = "",
        il: str = "",
        ihale_turu: str = "",
        durum: str = "2",
        baslangic_tarihi: str = "",
        bitis_tarihi: str = "",
        min_bedel: float = 0,
        max_bedel: float = 0,
        sayfa: int = 1,
        sayfa_boyutu: int = 50,
    ) -> Dict[str, Any]:
        """İhale ara — EKAP /ilanlar"""
        params: Dict[str, Any] = {"sayfa": sayfa, "sayfaBoyutu": sayfa_boyutu}
        if anahtar_kelime:
            params["aramaKelimesi"] = anahtar_kelime
        if il:
            params["il"] = il
        if ihale_turu:
            params["ihaleTuru"] = ihale_turu
        if durum:
            params["durum"] = durum
        if baslangic_tarihi:
            params["baslangicTarihi"] = baslangic_tarihi
        if bitis_tarihi:
            params["bitisTarihi"] = bitis_tarihi
        if min_bedel > 0:
            params["minBedel"] = min_bedel
        if max_bedel > 0:
            params["maxBedel"] = max_bedel

        yanit = self._istek_gonder("ilanlar", params)

        if yanit is None:
            return {
                "basarili": False,
                "toplam": 0,
                "ihaleler": [],
                "hata": "EKAP API bağlantı hatası. İnternet bağlantınızı kontrol edin.",
            }

        try:
            # EKAP API farklı anahtar isimleri kullanabilir
            liste = (
                yanit.get("ilanlar")
                or yanit.get("data")
                or yanit.get("liste")
                or yanit.get("ihaleler")
                or []
            )
            ihaleler = [EKAPSonucu(k) for k in liste]
            return {
                "basarili": True,
                "toplam": yanit.get("toplamKayit", len(ihaleler)),
                "ihaleler": ihaleler,
                "hata": None,
            }
        except Exception as e:
            logger.error(f"EKAP yanıt ayrıştırma hatası: {e}")
            return {
                "basarili": False,
                "toplam": 0,
                "ihaleler": [],
                "hata": f"Yanıt işleme hatası: {e}",
            }

    def ihale_detay(self, kayit_no: str) -> Optional[Dict[str, Any]]:
        return self._istek_gonder(f"ilan/{kayit_no}")

    def baglanabilirlik_test(self) -> bool:
        """EKAP'a erişilebilir mi?"""
        try:
            import urllib.request
            req = urllib.request.Request(
                "https://ekap.kik.gov.tr",
                headers={"User-Agent": "InsaatMetrajPro/1.0"},
            )
            with urllib.request.urlopen(req, timeout=6):
                return True
        except Exception:
            return False

    def il_listesi(self) -> List[str]:
        return sorted(ILLER)

    # ── Demo verisi ──────────────────────────────────────────────────────────

    def demo_veri_uret(self, anahtar_kelime: str = "") -> Dict[str, Any]:
        """EKAP erişilemezse gösterim amaçlı gerçekçi demo veri"""
        import random

        idareler = [
            "Çevre, Şehircilik ve İklim Değişikliği Bakanlığı",
            "Devlet Su İşleri Genel Müdürlüğü",
            "Karayolları Genel Müdürlüğü",
            "İller Bankası A.Ş.",
            "İstanbul Büyükşehir Belediyesi",
            "Ankara Büyükşehir Belediyesi",
            "İzmir Büyükşehir Belediyesi",
            "TOKİ — Toplu Konut İdaresi",
            "Milli Eğitim Bakanlığı",
            "Sağlık Bakanlığı",
        ]
        iller_kisa = ["İstanbul", "Ankara", "İzmir", "Bursa", "Antalya", "Konya", "Adana"]
        isler = [
            "Okul Yapım İşi",
            "Yol Yapım ve Onarım İşi",
            "Hastane İnşaatı",
            "Kanalizasyon ve Altyapı İşleri",
            "Bina Renovasyon İşi",
            "Köprü Yapım İşi",
            "Baraj İnşaatı",
            "Kanal Yapım İşi",
            "Spor Tesisi Yapım İşi",
            "Konut İnşaatı",
        ]
        if anahtar_kelime:
            isler = [f"{anahtar_kelime} — {is_}" for is_ in isler[:6]]

        bugun = datetime.now()
        ihaleler = []
        for i in range(20):
            gun_fark = random.randint(-20, 70)
            tarih = bugun + timedelta(days=gun_fark)
            durum = "2" if gun_fark > 0 else "3"
            ihaleler.append(
                EKAPSonucu({
                    "ihaleNo":        f"2026/{random.randint(1000, 9999)}",
                    "ihaleAdi":       random.choice(isler) + f" (Lot {i + 1})",
                    "idareAdi":       random.choice(idareler),
                    "ihaleTarihi":    tarih.strftime("%d.%m.%Y"),
                    "teklifSonTarihi": (tarih - timedelta(days=3)).strftime("%d.%m.%Y"),
                    "ihaleTuru":      random.choice(["1", "2"]),
                    "ihaleUsulu":     random.choice(["1", "2", "3"]),
                    "durum":          durum,
                    "tahminiMaliyet": random.uniform(500_000, 50_000_000),
                    "paraBirimi":     "TL",
                    "il":             random.choice(iller_kisa),
                    "kayitNo":        str(random.randint(100_000, 999_999)),
                })
            )
        return {
            "basarili": True,
            "toplam":   len(ihaleler),
            "ihaleler": ihaleler,
            "hata":     None,
            "_demo":    True,
        }
