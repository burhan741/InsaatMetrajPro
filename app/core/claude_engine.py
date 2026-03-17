"""
Claude AI Asistan Engine
İnşaat Metraj Pro için yapay zeka destekli danışman motoru
"""
import logging
import json
from pathlib import Path
from typing import Optional, Dict, Any, List

from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent.parent.parent / "data" / "claude_config.json"

SISTEM_PROMPT = """Sen İnşaat Metraj Pro yazılımının yapay zeka danışmanısın.
Türk inşaat sektörü, metraj, maliyet analizi, hakediş, şantiye yönetimi ve
ilgili yasal mevzuat (4734/4735 Sayılı KİK Kanunu, Çevre Şehircilik Bakanlığı
birim fiyatları, TS standartları) konularında uzman bir inşaat mühendisi olarak yanıt verirsin.

Görevin:
- İnşaat ve yapı işleri ile ilgili sorulara Türkçe olarak kapsamlı ve doğru cevaplar vermek
- Maliyet analizleri ve metraj hesaplamalarında yardımcı olmak
- 4734/4735 Sayılı KİK mevzuatı hakkında bilgi vermek
- Çevre Şehircilik Bakanlığı birim fiyatları ve analizleri hakkında rehberlik etmek
- Hakediş, gecikme cezası, teminat hesapları gibi konularda Türk mevzuatına göre yanıtlar üretmek
- Proje bağlamı sağlandığında projeye özel analizler sunmak

Temel İnşaat Mevzuatı Sabitleri:
- Gecikme Cezası (4735 md.20): Günlük binde beş (‰5 = %0.5/gün), fesih eşiği %30
- Geçici Teminat: İhale bedelinin %3'ü
- Kesin Teminat: Sözleşme bedelinin %6'sı
- Damga Vergisi: %0.948 | Gelir Vergisi Stopajı: %3 | KDV: %20

CŞB Verimlilik Sabitleri:
- Demir Bağlama/Bükme: 333 kg/gün/usta (1 ton = ~3 demirci.gün)
- Nervürlü Soğuk Demir: 250 kg/gün/usta
- Kalıp (Döşeme): 4.00 m2/gün | Kiriş: 2.86 | Kolon: 1.82 | Sökme: 8.00
- İç Sıva: 25 m2/gün | Dış Sıva: 20 | İç Boya: 45 | Dış Boya: 30
- Fayans/Seramik: 8 m2/gün | Mermer: 4 | Parke Laminat: 25

Kurallar:
- Her zaman Türkçe yanıt ver
- Teknik terimleri Türkçe kullan
- Yanıtlarını kısa, net ve uygulanabilir tut
- Sayısal değerlerde Türk standartlarını ve mevzuatını uygula
"""


class ClaudeAsistanThread(QThread):
    """Claude API'ya async istek gönderen ve streaming yanıt alan thread"""
    yanit_parcasi = pyqtSignal(str)
    hata_olustu = pyqtSignal(str)
    islem_bitti = pyqtSignal()

    def __init__(self, api_key: str, mesajlar: list, model: str):
        super().__init__()
        self.api_key = api_key
        self.mesajlar = mesajlar
        self.model = model
        self._iptal = False

    def iptal_et(self):
        self._iptal = True

    def run(self):
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=self.api_key)
            with client.messages.stream(
                model=self.model,
                max_tokens=2048,
                system=SISTEM_PROMPT,
                messages=self.mesajlar,
            ) as stream:
                for text in stream.text_stream:
                    if self._iptal:
                        break
                    self.yanit_parcasi.emit(text)
            self.islem_bitti.emit()
        except Exception as e:
            self.hata_olustu.emit(str(e))
            self.islem_bitti.emit()


class ClaudeEngine:
    """Claude API yönetim sınıfı — İnşaat asistanı"""

    DESTEKLENEN_MODELLER = [
        ("claude-sonnet-4-6",          "Claude Sonnet 4.6 (Önerilen)"),
        ("claude-opus-4-6",            "Claude Opus 4.6 (Güçlü)"),
        ("claude-haiku-4-5-20251001",  "Claude Haiku 4.5 (Hızlı)"),
    ]

    def __init__(self):
        self.api_key: str = ""
        self.model: str = "claude-sonnet-4-6"
        self.gecmis: List[Dict[str, str]] = []
        self._active_thread: Optional[ClaudeAsistanThread] = None
        self._yukle_config()

    # ── Config ────────────────────────────────────────────────────────────────

    def _yukle_config(self):
        try:
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            if CONFIG_PATH.exists():
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                self.api_key = cfg.get("api_key", "")
                self.model = cfg.get("model", "claude-sonnet-4-6")
        except Exception as e:
            logger.warning(f"Claude config yüklenemedi: {e}")

    def kaydet_config(self, api_key: str, model: str = "claude-sonnet-4-6"):
        self.api_key = api_key.strip()
        self.model = model
        try:
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump({"api_key": self.api_key, "model": model}, f,
                          ensure_ascii=False, indent=2)
            logger.info("Claude config kaydedildi.")
        except Exception as e:
            logger.error(f"Claude config kaydedilemedi: {e}")

    def api_key_gecerli(self) -> bool:
        return bool(self.api_key and self.api_key.startswith("sk-ant-"))

    # ── Sohbet geçmişi ────────────────────────────────────────────────────────

    def gecmis_temizle(self):
        self.gecmis.clear()

    def mesaj_ekle_kullanici(self, icerik: str):
        self.gecmis.append({"role": "user", "content": icerik})
        self._gecmis_kisalt()

    def mesaj_ekle_asistan(self, icerik: str):
        self.gecmis.append({"role": "assistant", "content": icerik})
        self._gecmis_kisalt()

    def _gecmis_kisalt(self):
        if len(self.gecmis) > 20:
            self.gecmis = self.gecmis[-20:]

    # ── Thread oluşturma ─────────────────────────────────────────────────────

    def sorgu_thread_olustur(self) -> Optional[ClaudeAsistanThread]:
        if not self.api_key_gecerli():
            return None
        thread = ClaudeAsistanThread(self.api_key, list(self.gecmis), self.model)
        self._active_thread = thread
        return thread

    def aktif_istegi_iptal_et(self):
        if self._active_thread and self._active_thread.isRunning():
            self._active_thread.iptal_et()

    # ── Bağlam üreticiler ────────────────────────────────────────────────────

    def proje_baglam_olustur(self, proje_data: Dict[str, Any]) -> str:
        satirlar = ["=== AKTİF PROJE BİLGİLERİ ==="]
        if proje_data.get("ad"):
            satirlar.append(f"Proje Adı: {proje_data['ad']}")
        if proje_data.get("toplam_maliyet"):
            satirlar.append(f"Toplam Maliyet: {proje_data['toplam_maliyet']:,.2f} ₺")
        if proje_data.get("kalem_sayisi"):
            satirlar.append(f"Kalem Sayısı: {proje_data['kalem_sayisi']}")
        if proje_data.get("durum"):
            satirlar.append(f"Durum: {proje_data['durum']}")
        if proje_data.get("notlar"):
            satirlar.append(f"Notlar: {proje_data['notlar']}")
        return "\n".join(satirlar)

    def hizli_sor(self, soru: str, ekstra_baglam: str = "") -> Optional[ClaudeAsistanThread]:
        tam_soru = f"{ekstra_baglam}\n\n{soru}" if ekstra_baglam else soru
        self.mesaj_ekle_kullanici(tam_soru)
        return self.sorgu_thread_olustur()
