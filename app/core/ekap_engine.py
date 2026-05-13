"""
EKAP (Elektronik Kamu Alımları Platformu) API Engine
Kamu İhale Kurumu ihaleleri sorgulama motoru

Doğru API (ekapv2.kik.gov.tr):
  POST /b_ihalearama/api/Ihale/GetListByParameters
  Header: api-version: v1
"""
import base64
import logging
import json
import os
import ssl
import time
import urllib.request
import urllib.parse
import urllib.error
import http.cookiejar
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime

# AES şifreleme (cryptography paketi) — EKAP v2 güvenlik headerları için
try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives import padding as crypto_padding
    _CRYPTO_OK = True
except ImportError:
    _CRYPTO_OK = False

logger = logging.getLogger(__name__)

EKAP_BASE_URL = "https://ekapv2.kik.gov.tr"
IHALE_ARAMA_ENDPOINT = "/b_ihalearama/api/Ihale/GetListByParameters"
IHALE_DETAY_ENDPOINT = "/b_ihalearama/api/IhaleDetay/GetByIhaleIdIhaleDetay"
ILAN_LIST_ENDPOINT = "/b_ihalearama/api/Ilan/GetList"

IHALE_TURLERI = {
    1: "Yapım İşi",
    2: "Hizmet Alımı",
    3: "Mal Alımı",
    4: "Danışmanlık Hizmet Alımı",
}

IHALE_USULLERI = {
    1: "Açık İhale Usulü",
    2: "Belli İstekliler Arasında",
    3: "Pazarlık Usulü",
    4: "Doğrudan Temin",
}

IHALE_DURUMLARI = {
    1: "İhale Öncesi",
    2: "İhale İlanı",
    3: "Sonuçlandı",
    4: "İptal Edildi",
    5: "Düzeltme İlanı",
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

# İl adı → ID eşleştirmesi (EKAP il ID listesi)
IL_ID_MAP = {
    "Adana": 1, "Adıyaman": 2, "Afyonkarahisar": 3, "Ağrı": 4, "Amasya": 5,
    "Ankara": 6, "Antalya": 7, "Artvin": 8, "Aydın": 9, "Balıkesir": 10,
    "Bilecik": 11, "Bingöl": 12, "Bitlis": 13, "Bolu": 14, "Burdur": 15,
    "Bursa": 16, "Çanakkale": 17, "Çankırı": 18, "Çorum": 19, "Denizli": 20,
    "Diyarbakır": 21, "Edirne": 22, "Elazığ": 23, "Erzincan": 24, "Erzurum": 25,
    "Eskişehir": 26, "Gaziantep": 27, "Giresun": 28, "Gümüşhane": 29, "Hakkari": 30,
    "Hatay": 31, "Isparta": 32, "Mersin": 33, "İstanbul": 34, "İzmir": 35,
    "Kars": 36, "Kastamonu": 37, "Kayseri": 38, "Kırklareli": 39, "Kırşehir": 40,
    "Kocaeli": 41, "Konya": 42, "Kütahya": 43, "Malatya": 44, "Manisa": 45,
    "Kahramanmaraş": 46, "Mardin": 47, "Muğla": 48, "Muş": 49, "Nevşehir": 50,
    "Niğde": 51, "Ordu": 52, "Rize": 53, "Sakarya": 54, "Samsun": 55,
    "Siirt": 56, "Sinop": 57, "Sivas": 58, "Tekirdağ": 59, "Tokat": 60,
    "Trabzon": 61, "Tunceli": 62, "Şanlıurfa": 63, "Uşak": 64, "Van": 65,
    "Yozgat": 66, "Zonguldak": 67, "Aksaray": 68, "Bayburt": 69, "Karaman": 70,
    "Kırıkkale": 71, "Batman": 72, "Şırnak": 73, "Bartın": 74, "Ardahan": 75,
    "Iğdır": 76, "Yalova": 77, "Karabük": 78, "Kilis": 79, "Osmaniye": 80,
    "Düzce": 81,
}


def _ssl_context() -> ssl.SSLContext:
    """
    EKAP (kik.gov.tr) SSL bağlantı bağlamı.

    Sorun: OpenSSL 3.0+ varsayılan SECLEVEL=2 Türk devlet sunucularının
    kullandığı eski/zayıf cipher suite'leri reddeder →
    'SSLV3_ALERT_HANDSHAKE_FAILURE' hatası.

    Çözüm: SECLEVEL=0 ile tüm cipher kısıtlamaları kaldırılır,
    sertifika doğrulaması devre dışı bırakılır.
    """
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    # SECLEVEL=0: eski/zayıf cipher suite'lere izin ver (kik.gov.tr için gerekli)
    try:
        ctx.set_ciphers("DEFAULT:@SECLEVEL=0")
    except ssl.SSLError:
        try:
            ctx.set_ciphers("ALL:@SECLEVEL=0")
        except ssl.SSLError:
            pass

    # OP_LEGACY_SERVER_CONNECT: OpenSSL 3.0'da kaldırılan eski TLS renegotiation
    try:
        ctx.options |= getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0)
    except Exception:
        pass

    # TLS 1.0+ destekle (bazı devlet sunucuları TLS 1.2 altı kullanıyor)
    try:
        ctx.minimum_version = ssl.TLSVersion.TLSv1
    except (AttributeError, ssl.SSLError):
        pass

    return ctx


def _default_headers(api_version: str = "v1") -> Dict[str, str]:
    """
    Gerçek Chrome 122 browser request ile birebir eşleşen header seti.
    Browser DevTools'dan doğrulandı: sec-ch-ua, sec-fetch-* headerları
    sunucunun bot filtresi geçmesi için zorunlu.
    """
    return {
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
        "api-version": api_version,
        "Connection": "keep-alive",
        "Content-Type": "application/json",
        "Origin": "https://ekapv2.kik.gov.tr",
        "Referer": "https://ekapv2.kik.gov.tr/ekap/search/ihale-arama",
        "sec-ch-ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "X-Requested-With": "XMLHttpRequest",
    }


class EKAPSonucu:
    """Tek bir EKAP ihale kaydı"""

    def __init__(self, veri: Dict[str, Any]):
        # API farklı formatlarda dönebilir — Türkçe/İngilizce/ihale-mcp formatları
        self.ihale_id = str(veri.get("id", "") or veri.get("ihaleId", ""))
        self.ihale_no = str(
            veri.get("ikn", "")
            or veri.get("ihaleKayitNumarasi", "")
            or veri.get("ihaleNo", "")
        )
        self.ihale_adi = str(
            veri.get("ihaleAdi", "")     # ihale-mcp gerçek alan adı
            or veri.get("name", "")
            or veri.get("ad", "")
        )
        self.idare_adi = str(
            veri.get("idareAdi", "")     # ihale-mcp gerçek alan adı
            or veri.get("authority", "")
            or (veri.get("idare", {}) or {}).get("ad", "")
        )

        # İhale tarihi — gerçek API alanı "ihaleTarihSaat"
        tarih_raw = (
            veri.get("ihaleTarihSaat", "")   # ihale-mcp gerçek alan adı
            or veri.get("tender_datetime", "")
            or veri.get("ihaleTarihi", "")
        )
        self.ihale_tarihi = self._format_tarih(tarih_raw)

        # İhale türü — ihale-mcp: ihaleTip (int) + ihaleTipAciklama (str)
        tur_aciklama = str(veri.get("ihaleTipAciklama", ""))
        tur = veri.get("type", {}) or {}
        tur_id = int(veri.get("ihaleTip", 0) or (tur.get("code", 0) if isinstance(tur, dict) else 0))
        self.ihale_turu = (
            tur_aciklama
            or (tur.get("description", "") if isinstance(tur, dict) else "")
            or IHALE_TURLERI.get(tur_id, str(tur_id))
        )

        # Durum — ihale-mcp: ihaleDurum (int) + ihaleDurumAciklama (str)
        durum_aciklama = str(veri.get("ihaleDurumAciklama", ""))
        durum = veri.get("status", {}) or {}
        durum_id = int(veri.get("ihaleDurum", 0) or (durum.get("code", 0) if isinstance(durum, dict) else 0))
        self.durum = (
            durum_aciklama
            or (durum.get("description", "") if isinstance(durum, dict) else "")
            or IHALE_DURUMLARI.get(durum_id, str(durum_id))
        )

        self.il = str(veri.get("province", "") or veri.get("il", "") or veri.get("ihaleIl", ""))
        self.tahmini_bedel = float(
            veri.get("tahminiMaliyet", 0)
            or veri.get("tahminiDeger", 0)
            or 0
        )
        self.ihale_usulu = str(veri.get("ihaleUsulu", "") or veri.get("usul", ""))
        self.teklif_son_tarihi = self._format_tarih(
            veri.get("teklifSonTarihi", "") or veri.get("teklif_son_tarihi", "")
        )
        self.dokuman_url = str(veri.get("document_url", "") or veri.get("dokumanUrl", ""))
        self.kayit_no = self.ihale_no or self.ihale_id

        # Kazanan firma (sözleşme imzalayan yüklenici) — sonuçlanmış ihalelerde gelir
        self.kazanan_firma = str(
            veri.get("kazananFirma", "")
            or veri.get("sozlesmeYapilacakFirma", "")
            or veri.get("istekliAdi", "")
            or veri.get("teklifSahibi", "")
            or veri.get("winner", "")
            or veri.get("contractor", "")
            or ""
        )

    @staticmethod
    def _format_tarih(tarih_str: str) -> str:
        """ISO tarih → dd.mm.yyyy formatına çevir"""
        if not tarih_str:
            return ""
        try:
            if "T" in tarih_str:
                dt = datetime.fromisoformat(tarih_str.replace("Z", "+00:00"))
                return dt.strftime("%d.%m.%Y %H:%M")
            return tarih_str
        except Exception:
            return tarih_str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ihale_no":          self.ihale_no,
            "ihale_adi":         self.ihale_adi,
            "idare_adi":         self.idare_adi,
            "ihale_tarihi":      self.ihale_tarihi,
            "teklif_son_tarihi": self.teklif_son_tarihi,
            "ihale_turu":        self.ihale_turu,
            "ihale_usulu":       self.ihale_usulu,
            "durum":             self.durum,
            "tahmini_bedel":     self.tahmini_bedel,
            "para_birimi":       "TL",
            "il":                self.il,
            "kayit_no":          self.kayit_no,
            "ihale_url":         self.dokuman_url,
            "ihale_id":          self.ihale_id,
            "kazanan_firma":     self.kazanan_firma,
        }


class EKAPEngine:
    """EKAP v2 REST API istemcisi"""

    # api-version fallback sırası: v1 → 1 → 2 → boş
    _API_VERSIONS = ["v1", "1", "2", ""]
    _aktif_api_version: str = "v1"

    def __init__(self):
        self._son_istek_zamani: float = 0.0
        self._min_istek_araligi: float = 1.0
        self._cache: Dict[str, Any] = {}
        self._cache_suresi: int = 300
        self._cache_zamanlari: Dict[str, float] = {}
        # Cookie jar — SPA session cookie'lerini sakla
        self._cookie_jar = http.cookiejar.CookieJar()
        self._cookie_handler = urllib.request.HTTPCookieProcessor(self._cookie_jar)
        self._opener = urllib.request.build_opener(
            self._cookie_handler,
            urllib.request.HTTPSHandler(context=_ssl_context()),
        )
        self._session_hazir: bool = False
        self._xsrf_token: str = ""
        self._aktif_api_version: str = "v1"
        # Ardışık hata sayacı: 3 kez boş yanıt gelirse session yenile
        self._ardisik_hata_sayisi: int = 0
        self._max_ardisik_hata: int = 3
        # EKAP v2 AES güvenlik anahtarı (frontend kaynak kodundan doğrulandı)
        self._r8fact_key: bytes = b'Qm2LtXR0aByP69vZNKef4wMJ'

    def _session_baslat(self) -> None:
        """
        Ana sayfaya GET yaparak session cookie ve XSRF token al.
        Token hem cookie'den hem de HTML meta tag'inden çekilir.
        """
        if self._session_hazir:
            return
        try:
            req = urllib.request.Request(
                EKAP_BASE_URL + "/ekap/search/ihale-arama",
                headers={
                    "User-Agent": _default_headers()["User-Agent"],
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "tr-TR,tr;q=0.9",
                },
            )
            with self._opener.open(req, timeout=15) as resp:
                html_body = resp.read().decode("utf-8", errors="replace")

            # Tüm cookie'leri logla (debug)
            cookie_listesi = list(self._cookie_jar)
            logger.info(
                f"EKAP session başlatıldı — {len(cookie_listesi)} cookie: "
                + ", ".join(c.name for c in cookie_listesi)
            )

            # 1) Cookie'den XSRF token çek
            xsrf_isimler = ("xsrf", "csrf", "antiforgery", "requestverification")
            for cookie in cookie_listesi:
                if any(k in cookie.name.lower() for k in xsrf_isimler):
                    self._xsrf_token = cookie.value
                    logger.info(f"EKAP XSRF token (cookie): {cookie.name}={cookie.value[:20]}...")
                    break

            # 2) Cookie'de yoksa HTML'den çek (meta name="RequestVerificationToken")
            if not self._xsrf_token:
                import re as _re
                # <meta name="RequestVerificationToken" content="..." />
                meta_match = _re.search(
                    r'<meta[^>]+name=["\']RequestVerificationToken["\'][^>]+content=["\']([^"\']+)["\']',
                    html_body, _re.IGNORECASE
                )
                if not meta_match:
                    # Sıra ters olabilir: content="..." name="..."
                    meta_match = _re.search(
                        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']RequestVerificationToken["\']',
                        html_body, _re.IGNORECASE
                    )
                if meta_match:
                    self._xsrf_token = meta_match.group(1)
                    logger.info(f"EKAP XSRF token (HTML meta): {self._xsrf_token[:20]}...")

            # 3) Hâlâ yoksa window.__INITIAL_STATE__ veya JSON bootstrap içinde ara
            if not self._xsrf_token:
                import re as _re
                token_match = _re.search(
                    r'"(?:xsrfToken|csrfToken|antiForgeryToken|token)"\s*:\s*"([^"]{16,})"',
                    html_body, _re.IGNORECASE
                )
                if token_match:
                    self._xsrf_token = token_match.group(1)
                    logger.info(f"EKAP XSRF token (JSON bootstrap): {self._xsrf_token[:20]}...")

            if not self._xsrf_token:
                logger.info("EKAP XSRF token bulunamadı — token'sız devam edilecek.")

            self._session_hazir = True
        except Exception as e:
            logger.warning(f"EKAP session başlatma uyarısı: {e}")
            self._session_hazir = True  # yine de devam et

    def _aes_cbc_encrypt(self, plaintext: str, key: bytes, iv: bytes) -> bytes:
        """AES-CBC + PKCS7 padding ile şifrele (EKAP frontend ile aynı algoritma)."""
        if not _CRYPTO_OK:
            return b""
        padder = crypto_padding.PKCS7(128).padder()
        padded = padder.update(plaintext.encode()) + padder.finalize()
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        enc = cipher.encryptor()
        return enc.update(padded) + enc.finalize()

    def _guvenik_headerlari_olustur(self) -> Dict[str, str]:
        """
        EKAP v2 API'nin zorunlu kıldığı şifreli güvenlik headerlarını oluşturur.

        Kaynak: github.com/saidsurucu/ihale-mcp (ihale_client.py)
        Algoritma: AES-CBC, PKCS7 padding, key=b'Qm2LtXR0aByP69vZNKef4wMJ'

        Bu headerlar olmadan sunucu 26-byte boş yanıt döndürüyor.
        """
        if not _CRYPTO_OK:
            logger.debug("cryptography paketi yok — güvenlik headerları atlanıyor")
            return {}
        try:
            guid = str(uuid.uuid4())
            iv = os.urandom(16)
            ts_ms = str(int(time.time() * 1000))

            r8id_enc = base64.b64encode(
                self._aes_cbc_encrypt(guid, self._r8fact_key, iv)
            ).decode()
            ts_enc = base64.b64encode(
                self._aes_cbc_encrypt(ts_ms, self._r8fact_key, iv)
            ).decode()
            siv = base64.b64encode(iv).decode()

            return {
                "X-Custom-Request-Guid": guid,
                "X-Custom-Request-Siv": siv,
                "X-Custom-Request-Ts": ts_enc,
                "X-Custom-Request-R8id": r8id_enc,
            }
        except Exception as e:
            logger.warning(f"Güvenlik headerları oluşturulamadı: {e}")
            return {}

    def _post(self, endpoint: str, payload: Dict[str, Any],
              api_version: Optional[str] = None) -> Optional[Any]:
        """Rate-limited POST isteği — JSON body, ham yanıt loglama, gzip decompress."""
        gecen = time.time() - self._son_istek_zamani
        if gecen < self._min_istek_araligi:
            time.sleep(self._min_istek_araligi - gecen)

        _ver = api_version if api_version is not None else self._aktif_api_version
        cache_key = (
            f"POST|{endpoint}|{_ver}|"
            f"{json.dumps(payload, sort_keys=True, ensure_ascii=False)}"
        )
        if cache_key in self._cache:
            if time.time() - self._cache_zamanlari.get(cache_key, 0) < self._cache_suresi:
                return self._cache[cache_key]

        # Ardışık hata eşiği aşıldıysa session sıfırla (yeni cookie + token al)
        if self._ardisik_hata_sayisi >= self._max_ardisik_hata:
            logger.info(
                f"EKAP {self._ardisik_hata_sayisi} ardışık hata — session sıfırlanıyor..."
            )
            self._session_hazir = False
            self._xsrf_token = ""
            self._cookie_jar.clear()
            self._ardisik_hata_sayisi = 0

        # İlk istekte session başlat (cookie + XSRF token al)
        self._session_baslat()

        url = EKAP_BASE_URL + endpoint
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = _default_headers(api_version=_ver)
        if self._xsrf_token:
            headers["X-XSRF-TOKEN"] = self._xsrf_token
            headers["RequestVerificationToken"] = self._xsrf_token
        # AES şifreli güvenlik headerları — EKAP v2'nin boş yanıt vermemesi için zorunlu
        headers.update(self._guvenik_headerlari_olustur())

        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with self._opener.open(req, timeout=30) as resp:
                status = resp.getcode()
                raw = resp.read()
                content_encoding = resp.getheader("Content-Encoding", "")
                content_type = resp.getheader("Content-Type", "")

                # Gzip / deflate decompress
                if "gzip" in content_encoding:
                    import gzip as _gzip
                    raw = _gzip.decompress(raw)
                elif "deflate" in content_encoding:
                    import zlib as _zlib
                    raw = _zlib.decompress(raw)

                ham_snippet = raw[:500].decode("utf-8", errors="replace")
                logger.info(
                    f"EKAP POST [{endpoint}] HTTP {status} — {len(raw)} byte | "
                    f"api-version={_ver} | Content-Type={content_type} | "
                    f"Encoding={content_encoding} | Ham={ham_snippet!r}"
                )

                if not raw.strip():
                    logger.warning(f"EKAP POST [{endpoint}] boş yanıt (26-byte)")
                    self._ardisik_hata_sayisi += 1
                    return None

                veri = json.loads(raw.decode("utf-8"))
                # Başarılı yanıt — hata sayacını sıfırla
                self._ardisik_hata_sayisi = 0
                self._cache[cache_key] = veri
                self._cache_zamanlari[cache_key] = time.time()
                self._son_istek_zamani = time.time()
                return veri
        except urllib.error.HTTPError as e:
            body_snippet = ""
            try:
                body_snippet = e.read().decode("utf-8", errors="replace")[:500]
            except Exception:
                pass
            logger.error(
                f"EKAP POST [{endpoint}] HTTP {e.code} {e.reason} | "
                f"api-version={_ver} | body: {body_snippet}"
            )
            self._ardisik_hata_sayisi += 1
            self._son_istek_zamani = time.time()
            return None
        except urllib.error.URLError as e:
            logger.error(f"EKAP POST [{endpoint}] URL hatası: {e.reason}")
            self._ardisik_hata_sayisi += 1
            self._son_istek_zamani = time.time()
            return None
        except Exception as e:
            logger.error(
                f"EKAP POST [{endpoint}] beklenmeyen hata: {type(e).__name__}: {e}"
            )
            self._ardisik_hata_sayisi += 1
            self._son_istek_zamani = time.time()
            return None

    def _yanit_gecerli_mi(self, yanit: Any) -> bool:
        """
        API yanıtının gerçek veri içerip içermediğini kontrol eder.
        26-byte boş yanıt veya null data gibi durumları filtreler.
        """
        if yanit is None:
            return False
        if isinstance(yanit, list):
            return True  # Direkt liste — geçerli
        if not isinstance(yanit, dict):
            return False
        # Bilinen "başarısız" yapılar
        if yanit.get("isSuccess") is False or yanit.get("success") is False:
            return False
        # Tüm alanlar null/0 ise muhtemelen boş yanıt
        # "list" — ihale-mcp projesinden doğrulanan gerçek API key
        data_keys = ("list", "data", "ihaleler", "tenders", "items", "liste", "result", "results")
        for k in data_keys:
            v = yanit.get(k)
            if isinstance(v, list):
                return True  # Liste var (boş olsa bile geçerli format)
        # totalCount veya count varsa geçerli
        count_keys = ("totalCount", "toplamKayit", "total_count", "toplam", "count", "total")
        for k in count_keys:
            if k in yanit:
                return True
        return False

    def ihale_ara(
        self,
        anahtar_kelime: str = "",
        il: str = "",
        ihale_turu: str = "",
        durum: str = "",
        baslangic_tarihi: str = "",
        bitis_tarihi: str = "",
        min_bedel: float = 0,
        max_bedel: float = 0,
        sayfa: int = 1,
        sayfa_boyutu: int = 50,
        ikn_yili: Optional[int] = None,
        ikn_sayi: Optional[int] = None,
    ) -> Dict[str, Any]:
        """İhale ara — ekapv2 POST API"""

        skip = (sayfa - 1) * sayfa_boyutu

        # İl ID listesi
        il_id_list = []
        if il and il in IL_ID_MAP:
            il_id_list = [IL_ID_MAP[il]]

        # İhale türü ID listesi
        ihale_turu_list = []
        if ihale_turu:
            try:
                ihale_turu_list = [int(ihale_turu)]
            except ValueError:
                pass

        # Durum ID listesi
        durum_id_list = []
        if durum:
            try:
                durum_id_list = [int(durum)]
            except ValueError:
                pass

        # Tarih parametreleri
        ihale_tarih_baslangic = None
        ihale_tarih_bitis = None
        if baslangic_tarihi:
            # dd.mm.yyyy → YYYY-MM-DD
            try:
                parts = baslangic_tarihi.split(".")
                if len(parts) == 3:
                    ihale_tarih_baslangic = f"{parts[2]}-{parts[1]}-{parts[0]}"
                else:
                    ihale_tarih_baslangic = baslangic_tarihi
            except Exception:
                ihale_tarih_baslangic = baslangic_tarihi
        if bitis_tarihi:
            try:
                parts = bitis_tarihi.split(".")
                if len(parts) == 3:
                    ihale_tarih_bitis = f"{parts[2]}-{parts[1]}-{parts[0]}"
                else:
                    ihale_tarih_bitis = bitis_tarihi
            except Exception:
                ihale_tarih_bitis = bitis_tarihi

        payload = {
            "searchText": anahtar_kelime or "",
            "filterType": None,
            "ikNdeAra": True,
            "ihaleAdindaAra": True,
            "ihaleIlanindaAra": False,
            "teknikSartnamedeAra": False,
            "idariSartnamedeAra": False,
            "benzerIsMaddesindeAra": False,
            "isinYapilacagiYerMaddesindeAra": False,
            "nitelikTurMiktarMaddesindeAra": False,
            "ihaleBilgilerindeAra": False,
            "sozlesmeTasarisindaAra": False,
            "teklifCetvelindeAra": False,
            "searchType": "GirdigimGibi",
            "iknYili": ikn_yili,
            "iknSayi": ikn_sayi,
            "ihaleTarihSaatBaslangic": ihale_tarih_baslangic,
            "ihaleTarihSaatBitis": ihale_tarih_bitis,
            "ilanTarihSaatBaslangic": None,
            "ilanTarihSaatBitis": None,
            "yasaKapsami4734List": [],
            "ihaleTuruIdList": ihale_turu_list,
            "ihaleUsulIdList": [],
            "ihaleUsulAltIdList": [],
            "ihaleIlIdList": il_id_list,
            "ihaleDurumIdList": durum_id_list,
            "idareIdList": [],
            "ihaleIlanTuruIdList": [],
            "teklifTuruIdList": [],
            "asiriDusukTeklifIdList": [],
            "istisnaMaddeIdList": [],
            "okasBransKodList": [],
            "okasBransAdiList": [],
            "titubbKodList": [],
            "gmdnKodList": [],
            "eIhale": None,
            "eEksiltmeYapilacakMi": None,
            "ortakAlimMi": None,
            "kismiTeklifMi": None,
            "fiyatDisiUnsurVarmi": None,
            "ekonomikVeMaliYeterlilikBelgeleriIsteniyorMu": None,
            "meslekiTeknikYeterlilikBelgeleriIsteniyorMu": None,
            "isDeneyimiGosterenBelgelerIsteniyorMu": None,
            "yerliIstekliyeFiyatAvantajiUgulaniyorMu": None,
            "yabanciIsteklilereIzinVeriliyorMu": None,
            "alternatifTeklifVerilebilirMi": None,
            "konsorsiyumKatilabilirMi": None,
            "altYukleniciCalistirilabilirMi": None,
            "fiyatFarkiVerilecekMi": None,
            "avansVerilecekMi": None,
            "cerceveAnlasmaMi": None,
            "personelCalistirilmasinaDayaliMi": None,
            "orderBy": "ihaleTarihi",
            "siralamaTipi": "desc",
            "paginationSkip": skip,
            "paginationTake": sayfa_boyutu,
        }

        # api-version fallback: v1 → 1 → 2 → "" sırası ile dene
        yanit = None
        basarili_version = None
        for ver in self._API_VERSIONS:
            yanit = self._post(IHALE_ARAMA_ENDPOINT, payload, api_version=ver)
            if yanit is not None and self._yanit_gecerli_mi(yanit):
                basarili_version = ver
                self._aktif_api_version = ver
                logger.info(f"EKAP api-version={ver!r} ile geçerli yanıt alındı.")
                break
            logger.info(f"EKAP api-version={ver!r} geçerli veri döndürmedi — sonraki deneniyor.")
            # Rate limit ihlalini önle
            time.sleep(0.5)

        if yanit is None or not self._yanit_gecerli_mi(yanit):
            # Minimal payload ile son bir deneme
            minimal = {
                "searchText": anahtar_kelime or "",
                "ihaleAdindaAra": True,
                "searchType": "GirdigimGibi",
                "orderBy": "ihaleTarihi",
                "siralamaTipi": "desc",
                "paginationSkip": skip,
                "paginationTake": sayfa_boyutu,
            }
            logger.info("EKAP minimal payload ile son deneme yapılıyor...")
            for ver in self._API_VERSIONS[:2]:
                yanit = self._post(IHALE_ARAMA_ENDPOINT, minimal, api_version=ver)
                if yanit is not None and self._yanit_gecerli_mi(yanit):
                    basarili_version = ver
                    break
                time.sleep(0.3)

        if yanit is None:
            return {
                "basarili": False,
                "toplam": 0,
                "ihaleler": [],
                "hata": (
                    "EKAP API'ye bağlanılamadı.\n"
                    "Sunucu yanıt vermedi veya internet bağlantısı yok.\n"
                    "Gerçek ihaleler için: https://ekapv2.kik.gov.tr/ekap/search"
                ),
            }

        # Yanıt parse — API birkaç farklı yapıda dönebilir
        try:
            # "list" key — ihale-mcp projesinden doğrulanan gerçek API yanıt formatı
            liste = (
                yanit.get("list")
                or yanit.get("data")
                or yanit.get("ihaleler")
                or yanit.get("tenders")
                or yanit.get("items")
                or yanit.get("liste")
                or yanit.get("result")
                or yanit.get("results")
                or (yanit if isinstance(yanit, list) else [])
            )
            # 0 değerini kaybetmemek için "or" zinciri yerine None kontrolü
            _toplam_val = None
            for _tk in ("totalCount", "toplamKayit", "total_count", "toplam", "count", "total"):
                _v = yanit.get(_tk)
                if _v is not None:
                    _toplam_val = _v
                    break
            toplam = int(_toplam_val) if _toplam_val is not None else (
                len(liste) if isinstance(liste, list) else 0
            )

            if not isinstance(liste, list):
                # Yanıt veri içermiyor — ham yanıtı hata mesajına ekle
                logger.warning(
                    f"EKAP yanıt liste değil: {type(liste)} | ham: {str(yanit)[:300]}"
                )
                return {
                    "basarili": False,
                    "toplam": 0,
                    "ihaleler": [],
                    "hata": (
                        f"API yanıtı beklenen formatta değil.\n"
                        f"Ham yanıt ({len(str(yanit))} karakter): {str(yanit)[:300]}\n"
                        f"Kullanılan api-version: {basarili_version!r}"
                    ),
                }

            ihaleler = [EKAPSonucu(k) for k in liste]
            return {
                "basarili": True,
                "toplam": int(toplam),
                "ihaleler": ihaleler,
                "hata": None,
                "_kaynak": "api",
                "_api_version": basarili_version,
            }
        except Exception as e:
            logger.error(f"EKAP yanıt parse hatası: {e} | yanıt: {str(yanit)[:300]}")
            return {
                "basarili": False,
                "toplam": 0,
                "ihaleler": [],
                "hata": (
                    f"API yanıtı işlenemedi: {e}\n"
                    f"Ham yanıt: {str(yanit)[:300]}"
                ),
            }

    def ihale_detay(self, ihale_id: str) -> Optional[Dict[str, Any]]:
        """İhale detayını getir"""
        yanit = self._post(IHALE_DETAY_ENDPOINT, {"ihaleId": ihale_id})
        return yanit

    def baglanabilirlik_test(self) -> bool:
        """EKAP v2'ye erişilebilir mi?"""
        try:
            req = urllib.request.Request(
                EKAP_BASE_URL,
                headers={"User-Agent": "InsaatMetrajPro/1.0"},
            )
            with urllib.request.urlopen(req, timeout=6, context=_ssl_context()):
                return True
        except Exception:
            return False

    def il_listesi(self) -> List[str]:
        return sorted(ILLER)

    def ihale_istatistik_yillik(
        self,
        yil: int,
        ihale_turu: str = "",
        il: str = "",
        anahtar_kelime: str = "",
    ) -> Dict[str, Any]:
        """
        Belirli bir yıla ait sonuçlanmış ihaleleri çeker.
        İstatistik sekmesinde yıl bazlı özet üretmek için kullanılır.
        """
        bas = f"01.01.{yil}"
        bit = f"31.12.{yil}"
        return self.ihale_ara(
            anahtar_kelime=anahtar_kelime,
            baslangic_tarihi=bas,
            bitis_tarihi=bit,
            ihale_turu=ihale_turu,
            il=il,
            durum="3",          # Sonuçlandı — kazanan firma bilgisi olan ihaleler
            sayfa_boyutu=200,   # Yıl başına max 200 kayıt
        )
