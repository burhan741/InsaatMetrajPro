"""
Claude AI Asistan Engine
İnşaat Metraj Pro için yapay zeka destekli danışman motoru

Özellikler:
- Sohbet modu: Streaming yanıt (ClaudeAsistanThread)
- Hesap Asistanı modu: Tool use döngüsü (ClaudeAracliThread)
  - verimlilik_sure_hesapla: CŞB birim fiyat analizleri
  - kaba_yapi_maliyet: Alan × yapı sistemi katsayısı
  - proje_metraj_listesi: DB'den gerçek metraj kalemleri
  - gantt_gorevleri_getir: Gantt iş programı görevleri
- Proje Analizi: Yapılandırılmış proje değerlendirme
- Gantt Planlama: AI destekli iş programı oluşturma
"""
import sys
import os
import base64
import logging
import json
import math
from decimal import Decimal
from pathlib import Path
from typing import Optional, Dict, Any, List

from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)

# ── Anthropic paketi varlık kontrolü ───────────────────────────────────────
# Venv dışında başlatılırsa site-packages'ı manuel ekle
_VENV_SITE = Path(__file__).parent.parent.parent.parent / ".venv" / "Lib" / "site-packages"
if _VENV_SITE.exists() and str(_VENV_SITE) not in sys.path:
    sys.path.insert(0, str(_VENV_SITE))

try:
    import anthropic as _anthropic_mod
    _ANTHROPIC_OK = True
    _ANTHROPIC_VER = getattr(_anthropic_mod, "__version__", "?")
    logger.info(f"anthropic {_ANTHROPIC_VER} yüklendi.")
except ImportError as _e:
    _ANTHROPIC_OK = False
    _ANTHROPIC_VER = None
    logger.error(f"anthropic paketi bulunamadı: {_e}")

CONFIG_PATH = Path(__file__).parent.parent.parent / "data" / "claude_config.json"

# ── Sistem Promptu ─────────────────────────────────────────────────────────

SISTEM_PROMPT = """Sen İnşaat Metraj Pro yazılımının yapay zeka danışmanısın.
Türk inşaat sektörü, metraj, maliyet analizi, hakediş, şantiye yönetimi ve
ilgili yasal mevzuat (4734/4735 Sayılı KİK Kanunu, Çevre Şehircilik Bakanlığı
birim fiyatları, TS standartları) konularında uzman bir inşaat mühendisi olarak yanıt verirsin.

Görevin:
- İnşaat ve yapı işleri ile ilgili sorulara Türkçe olarak kapsamlı ve doğru cevaplar vermek
- Maliyet analizleri ve metraj hesaplamalarında yardımcı olmak
- Verimlilik ve süre hesaplamalarında CŞB birim fiyat analizlerini kullanmak
- Hesap araçlarını kullanarak kesin matematiksel sonuçlar üretmek
- Proje bağlamı sağlandığında projeye özel analizler sunmak
- Kullanıcı izin verdiğinde metraj kalemlerini ve Gantt görevlerini doğrudan sisteme aktarmak

VERİ AKTARIM YETKİN (AKTIF):
- metraj_kalem_ekle veya metraj_toplu_ekle ile metraj kalemleri ekleyebilirsin
- gantt_gorev_ekle veya gantt_toplu_ekle ile Gantt görevleri oluşturabilirsin
- Veri aktarmadan önce kalemleri kullanıcıya özet olarak göster, sonra yaz
- Toplu aktarımda gantt_toplu_ekle kullan — tek tek eklemek yerine tüm listeyi bir çağrıda gönder
- sure=0 gönderirsen sistem CŞB verimlilikten otomatik hesaplar

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
- Sayısal hesaplar için daima hesap araçlarını kullan, tahminde bulunma
- Yanıtlarını kısa, net ve uygulanabilir tut
- Saha müteahhidinin anlayabileceği sade bir dil kullan
- Veri yazarken hata olursa kullanıcıya açıkça bildir
"""

# ── Araç Tanımları ─────────────────────────────────────────────────────────

ARACLAR = [
    {
        "name": "verimlilik_sure_hesapla",
        "description": (
            "CŞB birim fiyat analizlerine göre bir iş için gereken iş günü sayısını hesaplar. "
            "Formül: süre = ceil(miktar / (verimlilik × usta_sayısı)). "
            "Verimlilik değerleri Çevre Şehircilik Bakanlığı resmi analizlerine dayanır."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "is_tipi": {
                    "type": "string",
                    "description": (
                        "İş tipi adı. Örnek: 'Kalıp Döşeme', 'Demir Bağlama', "
                        "'İç Sıva', 'Fayans/Seramik', 'Nervürlü Soğuk Demir'"
                    )
                },
                "miktar": {
                    "type": "number",
                    "description": "İş miktarı (birim cinsinden: m², kg, m³)"
                },
                "usta_sayisi": {
                    "type": "integer",
                    "description": "Çalışacak usta/işçi sayısı (en az 1)"
                }
            },
            "required": ["is_tipi", "miktar", "usta_sayisi"]
        }
    },
    {
        "name": "kaba_yapi_maliyet",
        "description": (
            "İnşaat alanı ve yapı sistemine göre kaba yapı maliyet tahmini hesaplar. "
            "Katsayılar CŞB standartlarına dayalıdır (beton m³/m², kalıp m²/m², demir kg/m²). "
            "2026 Q1 piyasa fiyatları kullanılır."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "alan_m2": {
                    "type": "number",
                    "description": "Toplam inşaat alanı (m²)"
                },
                "yapi_sistemi": {
                    "type": "string",
                    "description": (
                        "Yapı sistemi. Seçenekler: 'Betonarme Çerçeve', "
                        "'Betonarme Perde+Çerçeve', 'Yığma Tuğla', 'Çelik Konstrüksiyon'"
                    )
                },
                "birim_fiyat_beton": {
                    "type": "number",
                    "description": "Hazır beton birim fiyatı TL/m³ (opsiyonel, varsayılan: 4800)"
                },
                "birim_fiyat_demir": {
                    "type": "number",
                    "description": "Demir birim fiyatı TL/kg (opsiyonel, varsayılan: 38)"
                }
            },
            "required": ["alan_m2", "yapi_sistemi"]
        }
    },
    {
        "name": "proje_metraj_listesi",
        "description": (
            "Aktif projenin metraj kalemlerini, miktarlarını, birim fiyatlarını ve "
            "toplam maliyetini listeler. Proje analizi ve optimizasyon için kullanılır."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "gantt_gorevleri_getir",
        "description": (
            "Aktif Gantt iş programındaki mevcut görevleri listeler. "
            "İş planı hazırlamak için projenin mevcut durumunu görmek amacıyla kullanılır."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "metraj_kalem_ekle",
        "description": (
            "Aktif projeye tek bir metraj kalemi ekler. "
            "Poz no, iş kalemi adı, miktar, birim, birim fiyat ve kategori bilgilerini alır. "
            "Ekleme sonrası kalem ID'si ve hesaplanan toplam tutarı döndürür."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "poz_no": {
                    "type": "string",
                    "description": "Poz numarası (örn: '16.001/1')"
                },
                "is_kalemi": {
                    "type": "string",
                    "description": "İş kalemi tanımı / açıklaması"
                },
                "miktar": {
                    "type": "number",
                    "description": "Metraj miktarı (sayısal değer)"
                },
                "birim": {
                    "type": "string",
                    "description": "Birim (m², m³, ton, adet, m, kg vb.)"
                },
                "birim_fiyat": {
                    "type": "number",
                    "description": "Birim fiyat (TL)"
                },
                "kategori": {
                    "type": "string",
                    "description": "Kategori (Hafriyat, Beton İşleri, Demir İşleri, Kalıp İşleri, Duvar İşleri, Sıva/Boya, Kaplama, Tesisat, vb.)"
                }
            },
            "required": ["poz_no", "is_kalemi", "miktar", "birim", "birim_fiyat"]
        }
    },
    {
        "name": "metraj_toplu_ekle",
        "description": (
            "Aktif projeye birden fazla metraj kalemini tek seferde ekler. "
            "kalemler listesindeki her öğe: poz_no, is_kalemi, miktar, birim, birim_fiyat, kategori içermelidir. "
            "Toplu aktarım için bu aracı kullan — tek tek metraj_kalem_ekle çağırmak yerine daha verimlidir."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "kalemler": {
                    "type": "array",
                    "description": "Eklenecek metraj kalemleri listesi",
                    "items": {
                        "type": "object",
                        "properties": {
                            "poz_no": {"type": "string"},
                            "is_kalemi": {"type": "string"},
                            "miktar": {"type": "number"},
                            "birim": {"type": "string"},
                            "birim_fiyat": {"type": "number"},
                            "kategori": {"type": "string"}
                        },
                        "required": ["poz_no", "is_kalemi", "miktar", "birim", "birim_fiyat"]
                    }
                }
            },
            "required": ["kalemler"]
        }
    },
    {
        "name": "gantt_gorev_ekle",
        "description": (
            "Aktif Gantt iş programına tek bir görev ekler. "
            "sure=0 gönderilirse CŞB verimlilik tablosundan otomatik hesaplanır. "
            "oncul: bağımlı olduğu görev ID'leri virgülle ayrılmış (örn: '1,2,3'). "
            "Başarılı eklemede görev ID'si ve hesaplanan süre döner."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ad": {
                    "type": "string",
                    "description": "Görev adı (iş kalemi)"
                },
                "sure_gun": {
                    "type": "integer",
                    "description": "Süre (iş günü). 0 gönderilirse miktar+is_tipi'nden CŞB ile hesaplanır."
                },
                "miktar": {
                    "type": "number",
                    "description": "İş miktarı (CŞB süre hesabı için gerekli)"
                },
                "birim": {
                    "type": "string",
                    "description": "Birim (m², m³, kg, ton vb.)"
                },
                "is_tipi": {
                    "type": "string",
                    "description": "İş tipi — CŞB verimlilik eşleştirmesi için (örn: 'Kalıp Döşeme', 'Demir Bağlama')"
                },
                "ekip_sayisi": {
                    "type": "integer",
                    "description": "Ekip/usta sayısı (varsayılan: 3)"
                },
                "oncul": {
                    "type": "string",
                    "description": "Öncül görev ID'leri virgülle ayrılmış (örn: '1,2'). FS bağımlılığı."
                },
                "kaynak": {
                    "type": "string",
                    "description": "Atanan kaynak/ekip adı"
                },
                "baslangic_gun": {
                    "type": "integer",
                    "description": "Başlangıç günü (gün offset, varsayılan: 0)"
                }
            },
            "required": ["ad"]
        }
    },
    {
        "name": "gantt_toplu_ekle",
        "description": (
            "Gantt iş programına birden fazla görevi tek seferde ekler. "
            "Tüm 30 kalemlik bir iş programını tek çağrıda oluşturmak için kullanılır. "
            "gorevler listesindeki her öğe: ad, sure_gun, miktar, birim, is_tipi, ekip_sayisi, oncul, kaynak içerebilir."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "gorevler": {
                    "type": "array",
                    "description": "Eklenecek görev listesi",
                    "items": {
                        "type": "object",
                        "properties": {
                            "ad": {"type": "string"},
                            "sure_gun": {"type": "integer"},
                            "miktar": {"type": "number"},
                            "birim": {"type": "string"},
                            "is_tipi": {"type": "string"},
                            "ekip_sayisi": {"type": "integer"},
                            "oncul": {"type": "string"},
                            "kaynak": {"type": "string"},
                            "baslangic_gun": {"type": "integer"}
                        },
                        "required": ["ad"]
                    }
                }
            },
            "required": ["gorevler"]
        }
    },
    {
        "name": "gantt_dosya_iceri_aktar",
        "description": (
            "Bir dosyadan (Excel .xlsx, CSV .csv veya JSON .json) Gantt görevlerini içeri aktarır. "
            "dosya_yolu parametresi tam dosya yolunu alır. "
            "mod='yenile' mevcut programı sıfırlar, mod='ekle' mevcut programa ekler (varsayılan). "
            "Kullanıcı sana bir dosya yolu verdiğinde bunu kullan."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "dosya_yolu": {
                    "type": "string",
                    "description": "İçeri aktarılacak dosyanın tam yolu (.xlsx, .csv veya .json)"
                },
                "mod": {
                    "type": "string",
                    "description": "İçeri aktarma modu: 'ekle' (varsayılan) veya 'yenile'"
                }
            },
            "required": ["dosya_yolu"]
        }
    },
]

# ── Analiz ve Planlama Promptları ──────────────────────────────────────────

PROJE_ANALIZ_PROMPT = """Aktif projenin aşağıdaki verilerine dayanarak kapsamlı bir proje analizi yap:

{proje_baglam}

Lütfen sırasıyla şu başlıklar altında analiz et:

1. **Genel Değerlendirme** — Proje kapsamı, maliyet seviyesi, genel izlenim
2. **Maliyet Analizi** — Hangi iş kalemleri toplam maliyette büyük pay tutuyor? Birim fiyatlar piyasayla uyumlu mu?
3. **Risk Alanları** — Gecikme, maliyet aşımı, eksik kalem riski taşıyan konular
4. **Eksik Kalemler** — Bu tür bir projede genellikle bulunması gereken ancak listede görünmeyen kalemler
5. **Optimizasyon Önerileri** — Maliyet düşürme veya etkinlik artırma fırsatları
6. **Yasal Kontrol** — KDV, stopaj, damga vergisi, teminat açısından dikkat edilmesi gerekenler

Yanıtını madde madde, net ve uygulanabilir tut. Saha müteahhidine hitap eden sade bir dil kullan."""

GANTT_PLAN_PROMPT = """Sen deneyimli bir inşaat proje yöneticisisin.

Aşağıdaki proje bilgilerine dayanarak gerçekçi ve uygulanabilir bir Gantt iş programı hazırla:

{proje_baglam}

KURALLAR:
- CŞB birim fiyat analizlerindeki verimlilik değerlerini kullan
- Türkiye resmi tatillerini ve mevsimsel kısıtları göz önünde bulundur
- Mantıklı bir bağımlılık sırası kur (temel bitmeden kolon olmaz vb.)
- Gerçekçi süreler ver, iş kalemlerini fazla bölme

ÇIKTI FORMATI — Açıklamadan sonra mutlaka şu bloku yaz:

GANTT_PLAN_BASLANGIC
sıra|iş_adı|süre_gün|kaynak|bağımlılık
1|Hafriyat ve Kazı|10|Kazıcı/Hafriyatçı|Yok
2|Temel Kalıp ve Demiri|8|Kalıpçı + Demirci|1
3|Temel Betonu|5|Betoncu|2
GANTT_PLAN_BITIS

Bağımlılık sütununa önceki görevin sıra numarasını yaz; bağımsızsa "Yok" yaz.
Birden fazla bağımlılık varsa "2,3" formatında yaz."""


# ── Yardımcı Fonksiyon ─────────────────────────────────────────────────────

def _content_blocks_to_dict(content_blocks) -> list:
    """Anthropic SDK content bloklarını mesaj formatına uygun dict listesine dönüştürür."""
    result = []
    for block in content_blocks:
        if not hasattr(block, "type"):
            continue
        if block.type == "text":
            result.append({"type": "text", "text": block.text})
        elif block.type == "tool_use":
            result.append({
                "type": "tool_use",
                "id": block.id,
                "name": block.name,
                "input": block.input,
            })
    return result


# ── Thread: Streaming (Sohbet Modu) ───────────────────────────────────────

class ClaudeAsistanThread(QThread):
    """Claude API streaming yanıt thread — Sohbet modu."""

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
            if not _ANTHROPIC_OK:
                raise ImportError(
                    "anthropic paketi kurulu değil.\n"
                    "Lütfen terminalde şunu çalıştırın:\n"
                    r'"E:\İNŞAAT METRAJ PRO\.venv\Scripts\pip.exe" install anthropic'
                )
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


# ── Thread: Tool Use (Hesap Asistanı + Analiz Modu) ───────────────────────

class ClaudeAracliThread(QThread):
    """
    Claude API araç kullanımı (tool use) destekli thread.

    Hesap Asistanı, Proje Analizi ve Gantt Planlama modları için kullanılır.
    Döngü: istek → araç çağrısı → Python fonksiyonu → sonuç → Claude → nihai yanıt
    """

    yanit_tamamlandi = pyqtSignal(str)    # Nihai tam yanıt metni
    arac_cagrildi = pyqtSignal(str, str)  # (arac_adi, sonuc) — UI'da gösterilir
    hata_olustu = pyqtSignal(str)
    islem_bitti = pyqtSignal()

    def __init__(self, api_key: str, mesajlar: list, model: str, arac_callback):
        super().__init__()
        self.api_key = api_key
        self.mesajlar = mesajlar
        self.model = model
        self.arac_callback = arac_callback  # callable(arac_adi: str, params: dict) -> str
        self._iptal = False

    def iptal_et(self):
        self._iptal = True

    def run(self):
        try:
            if not _ANTHROPIC_OK:
                raise ImportError(
                    "anthropic paketi kurulu değil.\n"
                    "Lütfen terminalde şunu çalıştırın:\n"
                    r'"E:\İNŞAAT METRAJ PRO\.venv\Scripts\pip.exe" install anthropic'
                )
            import anthropic
            client = anthropic.Anthropic(api_key=self.api_key)
            messages = list(self.mesajlar)

            max_dongu = 10  # sonsuz döngü koruması
            dongu = 0

            while dongu < max_dongu:
                if self._iptal:
                    break
                dongu += 1

                response = client.messages.create(
                    model=self.model,
                    max_tokens=3000,
                    system=SISTEM_PROMPT,
                    tools=ARACLAR,
                    messages=messages,
                )

                if response.stop_reason == "tool_use":
                    # 1. Asistan cevabını dict formatında messages'a ekle
                    messages.append({
                        "role": "assistant",
                        "content": _content_blocks_to_dict(response.content),
                    })

                    # 2. Her tool_use bloğunu işle
                    tool_results = []
                    for block in response.content:
                        if self._iptal:
                            break
                        if not hasattr(block, "type") or block.type != "tool_use":
                            continue
                        sonuc = self.arac_callback(block.name, block.input)
                        self.arac_cagrildi.emit(block.name, sonuc)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": sonuc,
                        })

                    if not tool_results:
                        break

                    # 3. Araç sonuçlarını messages'a ekle — döngü devam eder
                    messages.append({"role": "user", "content": tool_results})

                elif response.stop_reason == "end_turn":
                    final_text = ""
                    for block in response.content:
                        if hasattr(block, "text"):
                            final_text += block.text
                    self.yanit_tamamlandi.emit(final_text)
                    break

                else:
                    # Beklenmedik stop reason — mevcut metni gönder
                    final_text = ""
                    for block in response.content:
                        if hasattr(block, "text"):
                            final_text += block.text
                    if final_text:
                        self.yanit_tamamlandi.emit(final_text)
                    break

            self.islem_bitti.emit()

        except Exception as e:
            self.hata_olustu.emit(str(e))
            self.islem_bitti.emit()


# ── ClaudeEngine ───────────────────────────────────────────────────────────

class ClaudeEngine:
    """Claude API yönetim sınıfı — İnşaat asistanı motor."""

    DESTEKLENEN_MODELLER = [
        ("claude-sonnet-4-6",         "Claude Sonnet 4.6 (Önerilen)"),
        ("claude-opus-4-6",           "Claude Opus 4.6 (Güçlü)"),
        ("claude-haiku-4-5-20251001", "Claude Haiku 4.5 (Hızlı)"),
    ]

    def __init__(self):
        self.api_key: str = ""
        self.model: str = "claude-sonnet-4-6"
        self.gecmis: List[Dict[str, str]] = []
        self._active_thread = None

        # Bağlam referansları
        self._db = None
        self._proje_id: Optional[int] = None
        self._gantt_engine = None

        self._yukle_config()

    # ── Config ──────────────────────────────────────────────────────────────

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

    # ── Bağlam Yönetimi ─────────────────────────────────────────────────────

    def set_proje_baglam(self, db, proje_id: Optional[int]):
        """Veritabanı ve proje bağlamını ayarla."""
        self._db = db
        self._proje_id = proje_id

    def set_gantt_engine(self, gantt_engine):
        """Gantt engine referansını ayarla."""
        self._gantt_engine = gantt_engine

    # ── Sohbet Geçmişi ──────────────────────────────────────────────────────

    def gecmis_temizle(self):
        self.gecmis.clear()

    def mesaj_ekle_kullanici(self, icerik: str):
        self.gecmis.append({"role": "user", "content": icerik})
        self._gecmis_kisalt()

    def mesaj_ekle_asistan(self, icerik: str):
        self.gecmis.append({"role": "assistant", "content": icerik})
        self._gecmis_kisalt()

    def mesaj_ekle_dosyali(self, metin: str, dosya_yolu: str):
        """
        Excel (.xlsx/.xls) veya görsel (PNG/JPG/WEBP) dosyasıyla birlikte mesaj ekle.

        - Excel: pandas ile markdown tabloya çevrilir → metin bağlamı olarak eklenir
        - Görsel: base64 encode → Anthropic vision API formatında eklenir
        """
        uzanti = os.path.splitext(dosya_yolu)[1].lower()
        if uzanti in (".xlsx", ".xls"):
            tablo_metin = self._excel_to_markdown(dosya_yolu)
            dosya_adi = os.path.basename(dosya_yolu)
            icerik = (
                f"[EXCEL DOSYASI: {dosya_adi}]\n\n"
                f"{tablo_metin}\n\n"
                f"Kullanıcı sorusu: {metin}"
            )
            self.gecmis.append({"role": "user", "content": icerik})
        elif uzanti in (".png", ".jpg", ".jpeg", ".webp"):
            if not os.path.exists(dosya_yolu):
                raise FileNotFoundError(f"Dosya bulunamadı: {dosya_yolu}")
            with open(dosya_yolu, "rb") as f:
                gorsel_bytes = f.read()
            b64 = base64.b64encode(gorsel_bytes).decode("utf-8")
            media_type_map = {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".webp": "image/webp",
            }
            media_type = media_type_map.get(uzanti, "image/jpeg")
            content = [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": b64,
                    },
                },
                {"type": "text", "text": metin},
            ]
            self.gecmis.append({"role": "user", "content": content})
        else:
            # Desteklenmeyen format — düz metin olarak ekle
            self.gecmis.append({"role": "user", "content": metin})
        self._gecmis_kisalt()

    def _excel_to_markdown(self, dosya_yolu: str) -> str:
        """Excel dosyasını okunabilir markdown tabloya çevirir."""
        try:
            import pandas as pd
        except ImportError:
            return "[HATA: pandas kurulu değil — pip install pandas]"

        try:
            sheets: dict = pd.read_excel(
                dosya_yolu, sheet_name=None, engine="openpyxl"
            )
        except Exception as e:
            return f"[Excel okunamadı: {e}]"

        MAX_SATIR = 500
        parcalar = []
        for sheet_adi, df in sheets.items():
            if df.empty:
                continue
            # Çok büyük sheet'leri kes
            fazla = len(df) - MAX_SATIR
            df_goster = df.head(MAX_SATIR)
            try:
                tablo = df_goster.to_markdown(index=False)
            except Exception:
                tablo = df_goster.to_string(index=False)
            baslik = f"## Sheet: {sheet_adi}" if len(sheets) > 1 else ""
            blok = f"{baslik}\n\n{tablo}" if baslik else tablo
            if fazla > 0:
                blok += f"\n\n[+{fazla} satır daha gösterilmedi — toplam {len(df)} satır]"
            parcalar.append(blok.strip())

        return "\n\n---\n\n".join(parcalar) if parcalar else "[Excel boş veya okunamadı]"

    def _gecmis_kisalt(self):
        if len(self.gecmis) > 20:
            self.gecmis = self.gecmis[-20:]

    # ── Thread Oluşturma ────────────────────────────────────────────────────

    def sorgu_thread_olustur(self) -> Optional[ClaudeAsistanThread]:
        """Streaming sohbet thread'i oluştur."""
        if not self.api_key_gecerli():
            return None
        thread = ClaudeAsistanThread(self.api_key, list(self.gecmis), self.model)
        self._active_thread = thread
        return thread

    def sorgu_aracli_thread_olustur(self) -> Optional[ClaudeAracliThread]:
        """Araç kullanımı destekli thread oluştur (Hesap Asistanı + Analiz)."""
        if not self.api_key_gecerli():
            return None
        thread = ClaudeAracliThread(
            api_key=self.api_key,
            mesajlar=list(self.gecmis),
            model=self.model,
            arac_callback=self._arac_calistir,
        )
        self._active_thread = thread
        return thread

    def aktif_istegi_iptal_et(self):
        if self._active_thread and self._active_thread.isRunning():
            self._active_thread.iptal_et()

    def hizli_sor(self, soru: str, ekstra_baglam: str = "") -> Optional[ClaudeAsistanThread]:
        tam_soru = f"{ekstra_baglam}\n\n{soru}" if ekstra_baglam else soru
        self.mesaj_ekle_kullanici(tam_soru)
        return self.sorgu_thread_olustur()

    # ── Bağlam Üreticiler ───────────────────────────────────────────────────

    def proje_baglam_olustur(self, proje_data: Dict[str, Any]) -> str:
        """Proje verisinden Claude için bağlam metni oluşturur."""
        satirlar = ["=== AKTİF PROJE BİLGİLERİ ==="]
        if proje_data.get("ad"):
            satirlar.append(f"Proje Adı     : {proje_data['ad']}")
        if proje_data.get("toplam_maliyet"):
            satirlar.append(
                f"Toplam Maliyet: {proje_data['toplam_maliyet']:,.2f} ₺"
            )
        if proje_data.get("kalem_sayisi"):
            satirlar.append(f"Kalem Sayısı  : {proje_data['kalem_sayisi']}")
        if proje_data.get("durum"):
            satirlar.append(f"Durum         : {proje_data['durum']}")
        if proje_data.get("notlar"):
            satirlar.append(f"Notlar        : {proje_data['notlar']}")

        # Kategori dağılımı
        kategori_dagilimi = proje_data.get("kategori_dagilimi", {})
        if kategori_dagilimi:
            satirlar.append("\nKategori Dağılımı:")
            for kat, tutar in sorted(
                kategori_dagilimi.items(), key=lambda x: x[1], reverse=True
            ):
                satirlar.append(f"  {kat:<25}: {tutar:>12,.0f} ₺")

        # İlk 15 metraj kalemi
        kalemler = proje_data.get("kalemler", [])
        if kalemler:
            satirlar.append("\nÖnemli Kalemler (ilk 15):")
            for k in kalemler[:15]:
                satirlar.append(
                    f"  - {k.get('tanim', '?')}: "
                    f"{k.get('miktar', 0):.2f} {k.get('birim', '')} × "
                    f"{k.get('birim_fiyat', 0):,.2f} ₺"
                )

        return "\n".join(satirlar)

    # ── Araç Yürütücüsü ─────────────────────────────────────────────────────

    def _arac_calistir(self, arac_adi: str, parametreler: dict) -> str:
        """Claude'un çağırdığı araçları çalıştırır ve sonucu string olarak döndürür."""
        try:
            if arac_adi == "verimlilik_sure_hesapla":
                return self._arac_verimlilik_sure(parametreler)
            elif arac_adi == "kaba_yapi_maliyet":
                return self._arac_kaba_yapi_maliyet(parametreler)
            elif arac_adi == "proje_metraj_listesi":
                return self._arac_proje_metraj_listesi()
            elif arac_adi == "gantt_gorevleri_getir":
                return self._arac_gantt_gorevleri_getir()
            elif arac_adi == "metraj_kalem_ekle":
                return self._arac_metraj_kalem_ekle(parametreler)
            elif arac_adi == "metraj_toplu_ekle":
                return self._arac_metraj_toplu_ekle(parametreler)
            elif arac_adi == "gantt_gorev_ekle":
                return self._arac_gantt_gorev_ekle(parametreler)
            elif arac_adi == "gantt_toplu_ekle":
                return self._arac_gantt_toplu_ekle(parametreler)
            elif arac_adi == "gantt_dosya_iceri_aktar":
                return self._arac_gantt_dosya_iceri_aktar(parametreler)
            else:
                return f"Bilinmeyen araç: {arac_adi}"
        except Exception as e:
            logger.error(f"Araç çalıştırma hatası [{arac_adi}]: {e}")
            return f"Araç hatası [{arac_adi}]: {e}"

    # ── Araç Implementasyonları ─────────────────────────────────────────────

    def _arac_verimlilik_sure(self, parametreler: dict) -> str:
        """CŞB verimlilik tablosundan süre hesabı."""
        VERIMLILIK = {
            "Demir Bağlama/Bükme":      (333,  "kg"),
            "Nervürlü Soğuk Demir":     (250,  "kg"),
            "Kalıp Döşeme":             (4.0,  "m²"),
            "Kalıp Kiriş":              (2.86, "m²"),
            "Kalıp Kolon":              (1.82, "m²"),
            "Kalıp Sökme":              (8.0,  "m²"),
            "Kalıp (Karma)":            (3.33, "m²"),
            "Beton Dökme (Pompalı)":    (2.5,  "m³"),
            "Beton Dökme (Elle)":       (1.5,  "m³"),
            "İç Sıva":                  (25,   "m²"),
            "Dış Sıva":                 (20,   "m²"),
            "İç Boya":                  (45,   "m²"),
            "Dış Boya":                 (30,   "m²"),
            "Fayans/Seramik":           (8,    "m²"),
            "Mermer":                   (4,    "m²"),
            "Parke Laminat":            (25,   "m²"),
            "Parke Ahşap":              (15,   "m²"),
            "Mantolama":                (10,   "m²"),
            "Su Yalıtımı":              (8,    "m²"),
            "Tuğla":                    (4.5,  "m²"),
            "Gazbeton":                 (6,    "m²"),
            "Şap":                      (25,   "m²"),
            "Elektrik (m)":             (20,   "m"),
            "Su Tesisatı (m)":          (8,    "m"),
        }

        is_tipi = str(parametreler.get("is_tipi", ""))
        miktar = float(parametreler.get("miktar", 0))
        usta = max(1, int(parametreler.get("usta_sayisi", 1)))

        # Fuzzy match — büyük/küçük harf duyarsız
        eslesme = None
        is_tipi_lower = is_tipi.lower()
        for k in VERIMLILIK:
            if is_tipi_lower in k.lower() or k.lower() in is_tipi_lower:
                eslesme = k
                break

        if not eslesme:
            liste = "\n  ".join(VERIMLILIK.keys())
            return (
                f"'{is_tipi}' için verimlilik verisi bulunamadı.\n"
                f"Mevcut iş tipleri:\n  {liste}"
            )

        verimlilik, birim = VERIMLILIK[eslesme]
        sure = math.ceil(miktar / (verimlilik * usta))
        hafta, gun = divmod(sure, 5)
        if hafta:
            sure_metin = f"{hafta} hafta {gun} gün" if gun else f"{hafta} hafta"
        else:
            sure_metin = f"{gun} iş günü"

        return (
            f"Süre Hesabı — CŞB Birim Fiyat Analizleri:\n"
            f"  İş Tipi      : {eslesme}\n"
            f"  Miktar       : {miktar:,.2f} {birim}\n"
            f"  Verimlilik   : {verimlilik} {birim}/gün/usta\n"
            f"  Usta Sayısı  : {usta}\n"
            f"  Hesap        : ⌈{miktar:.1f} ÷ ({verimlilik} × {usta})⌉ = {sure} gün\n"
            f"  SONUÇ        : {sure} iş günü ({sure_metin})"
        )

    def _arac_kaba_yapi_maliyet(self, parametreler: dict) -> str:
        """Yapı sistemi katsayılarına göre kaba yapı maliyet tahmini."""
        KATSAYILAR = {
            "Betonarme Çerçeve": {
                "beton": 0.35, "kalip": 2.20, "demir": 95, "temel": 0.50,
            },
            "Betonarme Perde+Çerçeve": {
                "beton": 0.42, "kalip": 2.80, "demir": 120, "temel": 0.60,
            },
            "Yığma Tuğla": {
                "beton": 0.10, "kalip": 0.50, "demir": 20, "temel": 0.30,
            },
            "Çelik Konstrüksiyon": {
                "beton": 0.15, "kalip": 0.80, "demir": 50, "temel": 0.40,
            },
        }

        alan = float(parametreler.get("alan_m2", 0))
        sistem = str(parametreler.get("yapi_sistemi", ""))
        fiyat_beton = float(parametreler.get("birim_fiyat_beton", 4800))
        fiyat_demir = float(parametreler.get("birim_fiyat_demir", 38))
        fiyat_kalip = 180.0  # TL/m² (2026 Q1)

        # Fuzzy match
        eslesme = "Betonarme Çerçeve"
        for k in KATSAYILAR:
            if sistem.lower() in k.lower() or k.lower() in sistem.lower():
                eslesme = k
                break

        k = KATSAYILAR[eslesme]
        beton_hacim = alan * k["beton"]
        kalip_alani = alan * k["kalip"]
        demir_kg = alan * k["demir"]
        temel_m3 = alan * k["temel"]

        mal_beton = beton_hacim * fiyat_beton
        mal_kalip = kalip_alani * fiyat_kalip
        mal_demir = demir_kg * fiyat_demir
        mal_temel = temel_m3 * fiyat_beton
        toplam = mal_beton + mal_kalip + mal_demir + mal_temel
        birim_m2 = toplam / alan if alan > 0 else 0

        return (
            f"Kaba Yapı Maliyet Tahmini — {eslesme}:\n"
            f"  Alan           : {alan:,.0f} m²\n"
            f"  ─────────────────────────────────────\n"
            f"  Beton Dökme    : {beton_hacim:,.1f} m³ × {fiyat_beton:,.0f} ₺ = {mal_beton:,.0f} ₺\n"
            f"  Kalıp          : {kalip_alani:,.1f} m² × {fiyat_kalip:.0f} ₺    = {mal_kalip:,.0f} ₺\n"
            f"  Demir          : {demir_kg:,.0f} kg × {fiyat_demir:.0f} ₺      = {mal_demir:,.0f} ₺\n"
            f"  Temel Betonu   : {temel_m3:,.1f} m³ × {fiyat_beton:,.0f} ₺ = {mal_temel:,.0f} ₺\n"
            f"  ─────────────────────────────────────\n"
            f"  TOPLAM         : {toplam:,.0f} ₺\n"
            f"  Birim Maliyet  : {birim_m2:,.0f} ₺/m²\n"
            f"  Kaynak         : CŞB katsayıları, 2026 Q1 piyasa fiyatları\n"
            f"  Uyarı          : Bu tahmin ±%20 sapma içerebilir."
        )

    def _arac_proje_metraj_listesi(self) -> str:
        """Aktif projeden metraj kalemlerini DB'den çeker."""
        if not self._db or not self._proje_id:
            return "Aktif proje seçilmemiş veya veritabanı bağlantısı yok."
        try:
            kalemler = self._db.get_project_metraj(self._proje_id)
            if not kalemler:
                return "Aktif projede metraj kalemi bulunamadı."

            satirlar = [f"Proje Metraj Kalemleri ({len(kalemler)} kalem):"]
            toplam = 0.0
            for i, k in enumerate(kalemler[:30], 1):
                miktar = float(k.get("miktar") or 0)
                bf = float(k.get("birim_fiyat") or 0)
                tutar = miktar * bf
                toplam += tutar
                satirlar.append(
                    f"  {i:2d}. {str(k.get('tanim', 'Tanımsız'))[:45]:<45} "
                    f"{miktar:>8.2f} {str(k.get('birim', '')):5} × "
                    f"{bf:>10,.2f} ₺ = {tutar:>12,.2f} ₺"
                )

            if len(kalemler) > 30:
                satirlar.append(f"  ... ve {len(kalemler) - 30} kalem daha")

            satirlar.append(f"  {'─' * 70}")
            satirlar.append(f"  TOPLAM: {toplam:,.2f} ₺  ({len(kalemler)} kalem)")
            return "\n".join(satirlar)

        except Exception as e:
            return f"Metraj listesi alınamadı: {e}"

    def _arac_gantt_gorevleri_getir(self) -> str:
        """Aktif Gantt iş programındaki görevleri listeler."""
        if not self._gantt_engine:
            return (
                "Gantt iş programı bağlantısı yok.\n"
                "Ana pencereden Gantt sekmesine gidin ve ardından tekrar deneyin."
            )
        try:
            tasks = self._gantt_engine.tasks
            if not tasks:
                return "Gantt iş programında henüz görev yok."

            satirlar = [f"Mevcut Gantt Görevleri ({len(tasks)} adet):"]
            for task_id, task in list(tasks.items())[:25]:
                bas = (
                    task.baslangic_tarihi.strftime("%d.%m.%Y")
                    if task.baslangic_tarihi else "—"
                )
                bit = (
                    task.bitis_tarihi.strftime("%d.%m.%Y")
                    if task.bitis_tarihi else "—"
                )
                satirlar.append(
                    f"  [{task.wbs_kodu or task_id}] {task.ad} — "
                    f"{task.sure_gun} gün | "
                    f"%{task.ilerleme:.0f} tamamlandı | "
                    f"{bas} → {bit} | "
                    f"Kaynak: {task.kaynak or '—'}"
                )

            if len(tasks) > 25:
                satirlar.append(f"  ... ve {len(tasks) - 25} görev daha")

            return "\n".join(satirlar)

        except Exception as e:
            return f"Gantt görevleri alınamadı: {e}"

    # ── Veri Yazma Araçları ─────────────────────────────────────────────────

    # CŞB verimlilik tablosu (modül seviyesinde paylaşılan sabit)
    _VERIMLILIK_MAP = {
        "demir bağlama":     (333,  "kg"),
        "demir büküm":       (333,  "kg"),
        "nervürlü demir":    (250,  "kg"),
        "kalıp döşeme":      (4.0,  "m²"),
        "döşeme kalıbı":     (4.0,  "m²"),
        "kiriş kalıbı":      (2.86, "m²"),
        "kolon kalıbı":      (1.82, "m²"),
        "perde kalıbı":      (1.82, "m²"),
        "kalıp sökme":       (8.0,  "m²"),
        "kalıp karma":       (3.33, "m²"),
        "beton döküm":       (2.5,  "m³"),
        "beton pompalı":     (2.5,  "m³"),
        "beton elle":        (1.5,  "m³"),
        "iç sıva":           (25,   "m²"),
        "dış sıva":          (20,   "m²"),
        "iç boya":           (45,   "m²"),
        "dış boya":          (30,   "m²"),
        "fayans":            (8,    "m²"),
        "seramik":           (8,    "m²"),
        "mermer":            (4,    "m²"),
        "parke laminat":     (25,   "m²"),
        "parke ahşap":       (15,   "m²"),
        "mantolama":         (10,   "m²"),
        "su yalıtım":        (8,    "m²"),
        "tuğla":             (4.5,  "m²"),
        "gazbeton":          (6,    "m²"),
        "şap":               (25,   "m²"),
        "hafriyat":          (120,  "m³"),
        "grobeton":          (3.0,  "m³"),
        "dolgu":             (80,   "m³"),
    }

    def _csb_sure_hesapla(self, is_tipi: str, miktar: float, ekip: int = 3) -> int:
        """CŞB verimliliğinden iş günü hesaplar; eşleşme yoksa miktar/2 fallback."""
        if not is_tipi or miktar <= 0:
            return max(1, int(miktar / 2)) if miktar > 0 else 1
        is_lower = is_tipi.lower()
        for anahtar, (verim, _) in self._VERIMLILIK_MAP.items():
            if anahtar in is_lower or is_lower in anahtar:
                return max(1, math.ceil(miktar / (verim * max(1, ekip))))
        return max(1, int(miktar / 2))

    def _arac_metraj_kalem_ekle(self, parametreler: dict) -> str:
        """Tek metraj kalemi ekler — DB.add_metraj_kalem() çağırır."""
        if not self._db or not self._proje_id:
            return "HATA: Aktif proje seçilmemiş veya veritabanı bağlantısı yok."
        try:
            poz_no = str(parametreler.get("poz_no", ""))
            is_kalemi = str(parametreler.get("is_kalemi", ""))
            miktar = float(parametreler.get("miktar", 0))
            birim = str(parametreler.get("birim", ""))
            birim_fiyat = float(parametreler.get("birim_fiyat", 0))
            kategori = str(parametreler.get("kategori", "Genel"))

            if not is_kalemi:
                return "HATA: is_kalemi boş olamaz."

            kalem_id = self._db.add_metraj_kalem(
                proje_id=self._proje_id,
                poz_no=poz_no,
                tanim=is_kalemi,
                miktar=miktar,
                birim=birim,
                birim_fiyat=birim_fiyat,
                kategori=kategori,
            )
            toplam = miktar * birim_fiyat
            return (
                f"Metraj kalemi eklendi.\n"
                f"  ID         : {kalem_id}\n"
                f"  Poz No     : {poz_no}\n"
                f"  Tanım      : {is_kalemi}\n"
                f"  Miktar     : {miktar:,.2f} {birim}\n"
                f"  Birim Fiyat: {birim_fiyat:,.2f} ₺\n"
                f"  Toplam     : {toplam:,.2f} ₺\n"
                f"  Kategori   : {kategori}"
            )
        except Exception as e:
            return f"HATA — metraj_kalem_ekle: {e}"

    def _arac_metraj_toplu_ekle(self, parametreler: dict) -> str:
        """Birden fazla metraj kalemini toplu ekler."""
        if not self._db or not self._proje_id:
            return "HATA: Aktif proje seçilmemiş veya veritabanı bağlantısı yok."
        kalemler = parametreler.get("kalemler", [])
        if not kalemler:
            return "HATA: kalemler listesi boş."

        eklenen = 0
        hatalar = []
        toplam_tutar = 0.0

        for i, k in enumerate(kalemler):
            try:
                poz_no = str(k.get("poz_no", f"P{i+1:03d}"))
                is_kalemi = str(k.get("is_kalemi", ""))
                miktar = float(k.get("miktar", 0))
                birim = str(k.get("birim", ""))
                birim_fiyat = float(k.get("birim_fiyat", 0))
                kategori = str(k.get("kategori", "Genel"))

                if not is_kalemi:
                    hatalar.append(f"  Sıra {i+1}: is_kalemi boş — atlandı")
                    continue

                self._db.add_metraj_kalem(
                    proje_id=self._proje_id,
                    poz_no=poz_no,
                    tanim=is_kalemi,
                    miktar=miktar,
                    birim=birim,
                    birim_fiyat=birim_fiyat,
                    kategori=kategori,
                )
                toplam_tutar += miktar * birim_fiyat
                eklenen += 1
            except Exception as e:
                hatalar.append(f"  Sıra {i+1} ({k.get('is_kalemi', '?')}): {e}")

        satirlar = [
            f"Toplu metraj aktarımı tamamlandı.",
            f"  Eklenen  : {eklenen}/{len(kalemler)} kalem",
            f"  Toplam   : {toplam_tutar:,.2f} ₺",
        ]
        if hatalar:
            satirlar.append(f"  Hatalar  : {len(hatalar)} adet")
            satirlar.extend(hatalar[:5])
            if len(hatalar) > 5:
                satirlar.append(f"  ... ve {len(hatalar) - 5} hata daha")
        return "\n".join(satirlar)

    def _arac_gantt_gorev_ekle(self, parametreler: dict) -> str:
        """Gantt iş programına tek görev ekler; GanttEngine.tasks dict'ine yazar."""
        if not self._gantt_engine:
            return (
                "HATA: Gantt motoru bağlantısı yok.\n"
                "Ana pencereden Gantt sekmesini açık bırakarak tekrar deneyin."
            )
        try:
            import math as _math
            from datetime import datetime, timedelta

            ad = str(parametreler.get("ad", ""))
            if not ad:
                return "HATA: Görev adı (ad) boş olamaz."

            sure_gun = int(parametreler.get("sure_gun", 0))
            miktar = float(parametreler.get("miktar", 0))
            birim = str(parametreler.get("birim", ""))
            is_tipi = str(parametreler.get("is_tipi", ""))
            ekip = int(parametreler.get("ekip_sayisi", 3))
            oncul_str = str(parametreler.get("oncul", ""))
            kaynak = str(parametreler.get("kaynak", ""))
            baslangic_gun = int(parametreler.get("baslangic_gun", 0))

            # CŞB süre hesabı
            if sure_gun <= 0 and miktar > 0 and is_tipi:
                sure_gun = self._csb_sure_hesapla(is_tipi, miktar, ekip)

            if sure_gun <= 0:
                sure_gun = 1

            # Görev ID'si
            mevcut_ids = [
                int(k) for k in self._gantt_engine.tasks.keys()
                if str(k).isdigit()
            ]
            yeni_id = str(max(mevcut_ids) + 1) if mevcut_ids else "1"

            # Öncüller listesi
            oncul_listesi = []
            if oncul_str:
                for p in oncul_str.replace(";", ",").split(","):
                    p = p.strip()
                    if p:
                        oncul_listesi.append(p)

            # Başlangıç tarihi
            baslangic = datetime.today() + timedelta(days=baslangic_gun)

            # Task oluştur
            from app.core.gantt_engine import Task as GanttTask
            tid = int(yeni_id)
            yeni_task = GanttTask(
                task_id=tid,
                ad=ad,
                sure_gun=sure_gun,
                baslangic_tarihi=baslangic,
                bitis_tarihi=baslangic + timedelta(days=sure_gun),
                kaynak=kaynak or "",
                ilerleme=0.0,
            )
            for p in oncul_listesi:
                try:
                    yeni_task.predecessors.append((int(p), "FS", 0))
                except (ValueError, TypeError):
                    pass
            self._gantt_engine.tasks[tid] = yeni_task

            # Gantt sinyal — UI varsa yenile
            try:
                if hasattr(self._gantt_engine, "veri_degisti"):
                    self._gantt_engine.veri_degisti.emit()
            except Exception:
                pass

            return (
                f"Gantt görevi eklendi.\n"
                f"  ID         : {yeni_id}\n"
                f"  Ad         : {ad}\n"
                f"  Süre       : {sure_gun} iş günü\n"
                f"  Başlangıç  : {baslangic.strftime('%d.%m.%Y')}\n"
                f"  Öncüller   : {', '.join(oncul_listesi) if oncul_listesi else 'Yok'}\n"
                f"  Kaynak     : {kaynak or 'Atanmadı'}"
            )
        except Exception as e:
            return f"HATA — gantt_gorev_ekle: {e}"

    def _arac_gantt_toplu_ekle(self, parametreler: dict) -> str:
        """Gantt iş programına birden fazla görevi toplu ekler."""
        if not self._gantt_engine:
            return (
                "HATA: Gantt motoru bağlantısı yok.\n"
                "Ana pencereden Gantt sekmesini açık bırakarak tekrar deneyin."
            )
        gorevler = parametreler.get("gorevler", [])
        if not gorevler:
            return "HATA: gorevler listesi boş."

        from datetime import datetime, timedelta
        try:
            from app.core.gantt_engine import Task as GanttTask
            _gantt_task_cls = GanttTask
        except Exception:
            return "HATA: GanttTask sınıfı yüklenemedi."

        eklenen = 0
        hatalar = []

        # Mevcut max ID
        mevcut_ids = [
            int(k) for k in self._gantt_engine.tasks.keys()
            if str(k).isdigit()
        ]
        sonraki_id = (max(mevcut_ids) + 1) if mevcut_ids else 1

        # ID mapping: gorev index → yeni_id (öncül referansları için)
        id_map: dict = {}

        for i, g in enumerate(gorevler):
            try:
                ad = str(g.get("ad", ""))
                if not ad:
                    hatalar.append(f"  Sıra {i+1}: ad boş — atlandı")
                    continue

                sure_gun = int(g.get("sure_gun", 0))
                miktar = float(g.get("miktar", 0))
                birim = str(g.get("birim", ""))
                is_tipi = str(g.get("is_tipi", ""))
                ekip = int(g.get("ekip_sayisi", 3))
                oncul_str = str(g.get("oncul", ""))
                kaynak = str(g.get("kaynak", ""))
                baslangic_gun = int(g.get("baslangic_gun", 0))

                # CŞB süre hesabı
                if sure_gun <= 0 and miktar > 0 and is_tipi:
                    sure_gun = self._csb_sure_hesapla(is_tipi, miktar, ekip)
                if sure_gun <= 0:
                    sure_gun = 1

                yeni_id = str(sonraki_id)
                id_map[i] = yeni_id
                sonraki_id += 1

                # Öncül dönüşümü — index referansını gerçek ID'ye çevir
                oncul_listesi = []
                if oncul_str:
                    for p in oncul_str.replace(";", ",").split(","):
                        p = p.strip()
                        if not p:
                            continue
                        # Sayısal index mi, yoksa ID mi?
                        if p.isdigit() and int(p) < len(gorevler):
                            mapped = id_map.get(int(p))
                            if mapped:
                                oncul_listesi.append(mapped)
                            else:
                                oncul_listesi.append(p)
                        else:
                            oncul_listesi.append(p)

                baslangic = datetime.today() + timedelta(days=baslangic_gun)
                tid = int(yeni_id)
                yeni_task = _gantt_task_cls(
                    task_id=tid,
                    ad=ad,
                    sure_gun=sure_gun,
                    baslangic_tarihi=baslangic,
                    bitis_tarihi=baslangic + timedelta(days=sure_gun),
                    kaynak=kaynak or "",
                    ilerleme=0.0,
                )
                for p in oncul_listesi:
                    try:
                        yeni_task.predecessors.append((int(p), "FS", 0))
                    except (ValueError, TypeError):
                        pass
                self._gantt_engine.tasks[tid] = yeni_task
                eklenen += 1

            except Exception as e:
                hatalar.append(f"  Sıra {i+1} ({g.get('ad', '?')}): {e}")

        # UI sinyali
        try:
            if hasattr(self._gantt_engine, "veri_degisti"):
                self._gantt_engine.veri_degisti.emit()
        except Exception:
            pass

        satirlar = [
            f"Toplu Gantt aktarımı tamamlandı.",
            f"  Eklenen  : {eklenen}/{len(gorevler)} görev",
        ]
        if hatalar:
            satirlar.append(f"  Hatalar  : {len(hatalar)} adet")
            satirlar.extend(hatalar[:5])
            if len(hatalar) > 5:
                satirlar.append(f"  ... ve {len(hatalar) - 5} hata daha")
        return "\n".join(satirlar)

    def _arac_gantt_dosya_iceri_aktar(self, parametreler: dict) -> str:
        """Dosyadan (Excel/CSV/JSON) Gantt görevlerini içeri aktarır; GanttEngine.tasks'a yazar."""
        import csv as _csv

        dosya_yolu = str(parametreler.get("dosya_yolu", "")).strip()
        mod = str(parametreler.get("mod", "ekle")).strip().lower()

        if not dosya_yolu:
            return "HATA: dosya_yolu parametresi boş."
        if not os.path.isfile(dosya_yolu):
            return f"HATA: Dosya bulunamadı: {dosya_yolu}"

        uzanti = os.path.splitext(dosya_yolu)[1].lower()
        gorev_listesi = []

        try:
            # ── JSON ──────────────────────────────────────────────────
            if uzanti == ".json":
                with open(dosya_yolu, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    gorev_listesi = data
                elif isinstance(data, dict):
                    gorev_listesi = data.get("tasks", data.get("gorevler", []))

            # ── CSV ───────────────────────────────────────────────────
            elif uzanti in (".csv", ".txt"):
                with open(dosya_yolu, "r", encoding="utf-8-sig", newline="") as f:
                    reader = _csv.DictReader(f)
                    for row in reader:
                        row_lower = {k.lower().strip(): v for k, v in row.items()}
                        ad = row_lower.get("iş adı") or row_lower.get("ad") or row_lower.get("task name", "")
                        if not str(ad).strip():
                            continue
                        try:
                            sure = int(float(str(row_lower.get("süre (gün)") or row_lower.get("süre") or row_lower.get("duration") or 1)))
                        except (ValueError, TypeError):
                            sure = 1
                        gorev_listesi.append({
                            "ad": str(ad).strip(),
                            "sure": max(1, sure),
                            "baslangic": str(row_lower.get("başlangıç") or row_lower.get("start") or "").strip(),
                            "bitis": str(row_lower.get("bitiş") or row_lower.get("finish") or "").strip(),
                            "miktar": float(str(row_lower.get("miktar") or row_lower.get("quantity") or 0) or 0),
                            "miktar_birim": str(row_lower.get("birim") or row_lower.get("unit") or "m²").strip(),
                            "kaynak": str(row_lower.get("kaynak/ekip") or row_lower.get("kaynak") or row_lower.get("resource") or "").strip(),
                            "bagimliliklar": [],
                            "milestone": str(row_lower.get("milestone", "")).lower() in ("evet", "1", "true"),
                            "tamamlanma_yuzdesi": 0,
                            "butce": float(str(row_lower.get("bütçe (tl)") or row_lower.get("bütçe") or row_lower.get("budget") or 0) or 0),
                            "aciklama": str(row_lower.get("açıklama") or row_lower.get("description") or "").strip(),
                        })

            # ── Excel ─────────────────────────────────────────────────
            elif uzanti in (".xlsx", ".xls"):
                try:
                    import openpyxl as _opxl
                except ImportError:
                    return "HATA: openpyxl paketi yüklü değil. 'pip install openpyxl' çalıştırın."
                wb = _opxl.load_workbook(dosya_yolu, data_only=True)
                ws = wb.active
                basliklar = [str(c.value).lower().strip() if c.value else "" for c in ws[1]]

                def _kolon(adaylar):
                    for a in adaylar:
                        try:
                            return basliklar.index(a.lower())
                        except ValueError:
                            pass
                    return -1

                idx_ad  = _kolon(["iş adı", "ad", "task name", "name"])
                idx_sur = _kolon(["süre (gün)", "süre", "duration"])
                idx_bas = _kolon(["başlangıç", "başlangıç tarihi", "start"])
                idx_bit = _kolon(["bitiş", "bitiş tarihi", "finish", "end"])
                idx_mik = _kolon(["miktar", "quantity"])
                idx_bir = _kolon(["birim", "unit"])
                idx_kay = _kolon(["kaynak/ekip", "kaynak", "ekip", "resource"])
                idx_onc = _kolon(["öncüller (id)", "öncüller", "predecessors"])
                idx_mil = _kolon(["milestone (evet/hayır)", "milestone"])
                idx_tam = _kolon(["tamamlanma (%)", "tamamlanma", "progress"])
                idx_but = _kolon(["bütçe (tl)", "bütçe", "budget"])
                idx_ack = _kolon(["açıklama", "notlar", "description"])

                def _cell(row, idx):
                    return row[idx] if idx >= 0 and idx < len(row) else None

                for row in ws.iter_rows(min_row=2, values_only=True):
                    if all(v is None for v in row):
                        continue
                    ad_val = _cell(row, idx_ad)
                    if not ad_val:
                        continue
                    try:
                        sure = int(float(str(_cell(row, idx_sur) or 1)))
                    except (ValueError, TypeError):
                        sure = 1
                    oncul_str = str(_cell(row, idx_onc) or "")
                    bagimliliklar = []
                    for p in oncul_str.replace(";", ",").split(","):
                        p = p.strip()
                        if p.isdigit():
                            bagimliliklar.append(int(p))
                    gorev_listesi.append({
                        "ad": str(ad_val).strip(),
                        "sure": max(1, sure),
                        "baslangic": str(_cell(row, idx_bas) or "").strip(),
                        "bitis": str(_cell(row, idx_bit) or "").strip(),
                        "miktar": float(str(_cell(row, idx_mik) or 0) or 0),
                        "miktar_birim": str(_cell(row, idx_bir) or "m²").strip() or "m²",
                        "kaynak": str(_cell(row, idx_kay) or "").strip(),
                        "bagimliliklar": bagimliliklar,
                        "milestone": str(_cell(row, idx_mil) or "").lower() in ("evet", "1", "true"),
                        "tamamlanma_yuzdesi": int(float(str(_cell(row, idx_tam) or 0) or 0)),
                        "butce": float(str(_cell(row, idx_but) or 0) or 0),
                        "aciklama": str(_cell(row, idx_ack) or "").strip(),
                    })
            else:
                return f"HATA: Desteklenmeyen dosya formatı: {uzanti} (desteklenen: .xlsx, .csv, .json)"

        except Exception as e:
            return f"HATA — dosya okuma: {e}"

        # Geçerli görevleri filtrele
        gorevler = [g for g in gorev_listesi if isinstance(g, dict) and str(g.get("ad", "")).strip()]
        if not gorevler:
            return f"HATA: Dosyada geçerli görev bulunamadı. ({dosya_yolu})"

        if not self._gantt_engine:
            return (
                "HATA: Gantt motoru bağlantısı yok.\n"
                "Ana pencereden Gantt sekmesini açık bırakarak tekrar deneyin."
            )

        try:
            from app.core.gantt_engine import Task as GanttTask
        except Exception as e:
            return f"HATA: GanttTask sınıfı yüklenemedi: {e}"

        from datetime import datetime as _dt, timedelta, date as _date

        # ID offset
        mevcut_ids = [int(k) for k in self._gantt_engine.tasks.keys() if str(k).isdigit()]
        if mod == "yenile":
            self._gantt_engine.tasks.clear()
            id_offset = 0
        else:
            id_offset = max(mevcut_ids) if mevcut_ids else 0

        def _tarih_parse(s):
            if not s or str(s).strip() in ("", "None"):
                return _dt.today()
            for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%m/%d/%Y"):
                try:
                    return _dt.strptime(str(s).strip(), fmt)
                except ValueError:
                    pass
            return _dt.today()

        eklenen = 0
        hatalar = []
        for i, g in enumerate(gorevler):
            try:
                yeni_id = str(id_offset + i + 1)
                sure = max(1, int(g.get("sure", 1)))
                bas = _tarih_parse(g.get("baslangic", ""))
                bit = bas + timedelta(days=sure)
                oncul_listesi = [str(id_offset + b) for b in g.get("bagimliliklar", []) if b > 0]
                tid = int(id_offset + i + 1)
                task = GanttTask(
                    task_id=tid,
                    ad=str(g["ad"]),
                    sure_gun=sure,
                    baslangic_tarihi=bas,
                    bitis_tarihi=bit,
                    kaynak=g.get("kaynak") or "",
                    ilerleme=float(g.get("tamamlanma_yuzdesi", 0)),
                )
                for p in oncul_listesi:
                    try:
                        task.predecessors.append((int(p), "FS", 0))
                    except (ValueError, TypeError):
                        pass
                self._gantt_engine.tasks[tid] = task
                eklenen += 1
            except Exception as e:
                hatalar.append(f"  Sıra {i+1} ({g.get('ad', '?')}): {e}")

        try:
            if hasattr(self._gantt_engine, "veri_degisti"):
                self._gantt_engine.veri_degisti.emit()
        except Exception:
            pass

        satirlar = [
            f"Dosya içeri aktarıldı — {os.path.basename(dosya_yolu)}",
            f"  Format  : {uzanti.upper()}",
            f"  Mod     : {'Yenile (sıfırdan)' if mod == 'yenile' else 'Ekle (mevcut programa)'}",
            f"  Eklenen : {eklenen}/{len(gorevler)} görev",
        ]
        if hatalar:
            satirlar.append(f"  Hatalar : {len(hatalar)} adet")
            satirlar.extend(hatalar[:3])
        return "\n".join(satirlar)
