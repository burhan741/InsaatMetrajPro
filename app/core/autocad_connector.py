# -*- coding: utf-8 -*-
"""
AutoCAD Canlı Bağlantı Modülü (COM Automation)
==============================================
Profesyonel metraj yazılımları gibi AutoCAD ile canlı bağlantı kurar.
win32com.client kullanarak ActiveX/COM üzerinden iletişim sağlar.

Yazar: İNŞAAT METRAJ PRO
Tarih: 2026
"""

import logging
import re
import time
import math
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import IntEnum

logger = logging.getLogger(__name__)

# win32com opsiyonel import
try:
 import win32com.client
 import pythoncom
 from pywintypes import com_error
 WIN32COM_AVAILABLE = True
except ImportError:
 WIN32COM_AVAILABLE = False
 logger.warning("win32com.client bulunamadı. 'pip install pywin32' ile yükleyin.")

# win32gui opsiyonel import (pencere yönetimi için)
try:
 import win32gui
 import win32con
 WIN32GUI_AVAILABLE = True
except ImportError:
 WIN32GUI_AVAILABLE = False


class AcadColor(IntEnum):
 """AutoCAD renk sabitleri (ACI - AutoCAD Color Index)"""
 RED = 1 # acRed
 YELLOW = 2 # acYellow
 GREEN = 3 # acGreen
 CYAN = 4 # acCyan
 BLUE = 5 # acBlue
 MAGENTA = 6 # acMagenta
 WHITE = 7 # acWhite
 GRAY = 8 # Gri
 BYLAYER = 256 # Katmana göre


class AcadEntityType:
 """AutoCAD entity tip isimleri"""
 LINE = "AcDbLine"
 POLYLINE = "AcDbPolyline"
 LWPOLYLINE = "AcDbPolyline"
 POLYLINE_2D = "AcDb2dPolyline"
 POLYLINE_3D = "AcDb3dPolyline"
 CIRCLE = "AcDbCircle"
 ARC = "AcDbArc"
 TEXT = "AcDbText"
 MTEXT = "AcDbMText"
 BLOCK_REF = "AcDbBlockReference"
 HATCH = "AcDbHatch"
 DIMENSION = "AcDbDimension"
 SPLINE = "AcDbSpline"


@dataclass
class MetrajObjesi:
 """Metrajı alınan obje bilgisi"""
 entity_type: str
 layer: str
 handle: str
 # Geometrik veriler
 uzunluk: float = 0.0
 alan: float = 0.0
 cevre: float = 0.0
 # Özel veriler
 blok_adi: str = ""
 text_icerigi: str = ""
 koordinatlar: List[Tuple[float, float]] = field(default_factory=list)
 # Orijinal renk (geri almak için)
 orijinal_renk: int = 256
 # Ek özellikler
 ozellikler: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DemirBilgisi:
 """Demir metraj bilgisi (AutoCAD'den okunan)"""
 handle: str # AutoCAD handle (referans için)
 orijinal_metin: str # Orijinal metin içeriği
 adet: int = 0 # Demir adedi
 cap: int = 0 # Çap (mm) - Ø değeri
 boy: float = 0.0 # Boy (cm veya m) - L değeri
 toplam_boy: float = 0.0 # adet x boy
 agirlik_birim: float = 0.0 # kg/m (çapa göre)
 toplam_agirlik: float = 0.0 # Toplam ağırlık (kg)
 katman: str = "" # AutoCAD katmanı
 gecerli: bool = False # Regex ile eşleşti mi?
 hata_mesaji: str = "" # Eşleşmediyse neden


# Demir çap -> kg/m tablosu (nervürlü)
DEMIR_AGIRLIK_TABLOSU = {
 6: 0.222,
 8: 0.395,
 10: 0.617,
 12: 0.888,
 14: 1.208,
 16: 1.578,
 18: 1.998,
 20: 2.466,
 22: 2.984,
 24: 3.551,
 25: 3.853,
 26: 4.168,
 28: 4.834,
 30: 5.549,
 32: 6.313,
 36: 7.990,
 40: 9.865,
}


class AutoCADConnector:
 """
 AutoCAD Canlı Bağlantı Sınıfı
 =============================

 Bilgisayarda açık olan AutoCAD uygulamasına COM üzerinden bağlanır.
 Kullanıcı seçimlerini alır, veri okur ve görsel geri bildirim verir.

 Kullanım:
 ---------
 >>> connector = AutoCADConnector()
 >>> if connector.baglan():
 ... objeler = connector.kullanici_secimi_al()
 ... for obj in objeler:
 ... print(f"{obj.entity_type}: {obj.uzunluk}m")
 ... connector.secimi_temizle()
 """

 def __init__(self):
 """AutoCADConnector başlatıcısı"""
 self.acad_app = None
 self.aktif_cizim = None
 self.model_space = None
 self.selection_set = None
 self._bagli = False
 self._metraj_alinan_objeler: List[Any] = []
 self._orijinal_renkler: Dict[str, int] = {}

 if not WIN32COM_AVAILABLE:
 raise ImportError(
 "win32com.client modülü bulunamadı.\n"
 "Yüklemek için: pip install pywin32"
 )

 @property
 def bagli(self) -> bool:
 """AutoCAD'e bağlı mı?"""
 return self._bagli and self.acad_app is not None

 def baglan(self) -> bool:
 """
 Çalışan AutoCAD uygulamasına bağlan.

 Returns:
 bool: Bağlantı başarılı ise True

 Raises:
 ConnectionError: AutoCAD bulunamazsa veya bağlantı hatasında
 """
 try:
 # Farklı AutoCAD sürümlerini dene
 prog_ids = [
 "AutoCAD.Application.24", # AutoCAD 2024
 "AutoCAD.Application.25", # AutoCAD 2025
 "AutoCAD.Application.23", # AutoCAD 2023
 "AutoCAD.Application.26", # AutoCAD 2026
 "AutoCAD.Application", # Genel
 ]

 acad_found = False
 for prog_id in prog_ids:
 try:
 self.acad_app = win32com.client.GetActiveObject(prog_id)
 logger.info(f"AutoCAD bulundu: {prog_id}")
 acad_found = True
 break
 except com_error:
 continue

 if not acad_found:
 # Dispatch ile yeni instance dene
 try:
 self.acad_app = win32com.client.Dispatch("AutoCAD.Application")
 logger.info("AutoCAD Dispatch ile bağlandı")
 acad_found = True
 except com_error:
 pass

 if not acad_found:
 logger.warning("Açık AutoCAD uygulaması bulunamadı!")
 raise ConnectionError(
 "AutoCAD açık değil veya bağlantı kurulamadı!\n\n"
 "Çözüm önerileri:\n"
 "1. AutoCAD'i kapatıp yeniden açın\n"
 "2. AutoCAD'i YÖNETİCİ OLARAK çalıştırmayın\n"
 "3. Bu programı YÖNETİCİ OLARAK çalıştırın\n"
 "4. Bir DWG dosyası açık olduğundan emin olun"
 )

 # Uygulama görünür olsun
 try:
 self.acad_app.Visible = True
 except com_error:
 pass

 # Aktif çizimi al (retry ile - AutoCAD hazır olmayabilir)
 self.aktif_cizim = None
 for deneme in range(5):
 try:
 self.aktif_cizim = self.acad_app.ActiveDocument
 if self.aktif_cizim is not None:
 break
 except com_error:
 time.sleep(0.5)

 if self.aktif_cizim is None:
 raise ConnectionError(
 "AutoCAD'de açık bir çizim yok!\n"
 "Lütfen bir DWG dosyası açın."
 )

 # Model Space'i al (retry ile - COM bazen gecikmeli yanıt verir)
 self.model_space = None
 for deneme in range(5):
 try:
 self.model_space = self.aktif_cizim.ModelSpace
 if self.model_space is not None:
 break
 except com_error:
 time.sleep(0.5)
 # Late-binding sorunu olabilir, Dispatch ile tekrar dene
 try:
 self.aktif_cizim = win32com.client.Dispatch(
 self.acad_app.ActiveDocument
 )
 self.model_space = self.aktif_cizim.ModelSpace
 if self.model_space is not None:
 break
 except com_error:
 pass

 if self.model_space is None:
 raise ConnectionError(
 "AutoCAD ModelSpace'e erişilemiyor!\n\n"
 "Çözüm önerileri:\n"
 "1. AutoCAD'de bir DWG dosyası açık olduğundan emin olun\n"
 "2. AutoCAD'i kapatıp yeniden açın\n"
 "3. Bu programı ve AutoCAD'i aynı yetki seviyesinde çalıştırın"
 )

 # Bağlantı bilgilerini logla
 cizim_adi = self.aktif_cizim.Name
 cizim_yolu = self.aktif_cizim.FullName

 logger.info(f"AutoCAD bağlantısı başarılı!")
 logger.info(f" Çizim Adı: {cizim_adi}")
 logger.info(f" Tam Yol: {cizim_yolu}")

 print(f"\n{'='*50}")
 print(f" AutoCAD BAĞLANTISI BAŞARILI")
 print(f"{'='*50}")
 print(f" Çizim: {cizim_adi}")
 print(f" Yol: {cizim_yolu}")
 print(f"{'='*50}\n")

 self._bagli = True
 return True

 except com_error as e:
 logger.error(f"AutoCAD COM hatası: {e}")
 self._bagli = False
 raise ConnectionError(f"AutoCAD ile iletişim hatası: {e}")
 except Exception as e:
 logger.error(f"Bağlantı hatası: {e}")
 self._bagli = False
 raise

 def _autocad_one_getir(self):
 """AutoCAD penceresini görünür yap ve öne getir."""
 if not self.bagli:
 return

 max_deneme = 3
 for deneme in range(max_deneme):
 try:
 # 1. COM üzerinden görünür yap
 self.acad_app.Visible = True
 time.sleep(0.3)

 # 2. Pencere durumunu ayarla
 try:
 self.acad_app.WindowState = 1 # acNorm
 time.sleep(0.2)
 self.acad_app.WindowState = 3 # acMax
 except:
 pass

 time.sleep(0.3)

 # 3. Aktif çizimi aktifleştir
 if self.aktif_cizim:
 try:
 self.aktif_cizim.Activate()
 except:
 pass

 # 4. win32gui ile pencereyi öne getir
 if WIN32GUI_AVAILABLE:
 self._win32_pencere_one_getir()

 # 5. Görünürlüğü doğrula
 time.sleep(0.3)
 try:
 gorunur = self.acad_app.Visible
 if gorunur:
 logger.debug(f"AutoCAD penceresi öne getirildi (deneme {deneme + 1})")
 return
 except:
 pass

 # Görünür değilse - SendCommand ile REGEN dene
 if deneme < max_deneme - 1:
 logger.debug(f"AutoCAD hâlâ görünür değil, tekrar deneniyor ({deneme + 1}/{max_deneme})")
 try:
 self.aktif_cizim.SendCommand("(command \"REGEN\") ")
 except:
 pass
 time.sleep(0.5)

 except Exception as e:
 if deneme < max_deneme - 1:
 logger.debug(f"AutoCAD öne getirme denemesi {deneme + 1} başarısız: {e}")
 time.sleep(0.5)
 else:
 logger.warning(f"AutoCAD öne getirilemedi ({max_deneme} deneme): {e}")

 def _win32_pencere_one_getir(self):
 """win32gui ile AutoCAD penceresini bulup öne getirir."""
 def callback(hwnd, windows):
 try:
 title = win32gui.GetWindowText(hwnd)
 if "AutoCAD" in title and win32gui.IsWindow(hwnd):
 windows.append(hwnd)
 except:
 pass
 return True

 windows = []
 try:
 win32gui.EnumWindows(callback, windows)
 except:
 return

 for hwnd in windows:
 try:
 # Minimize durumunu kontrol et
 if win32gui.IsIconic(hwnd):
 win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
 time.sleep(0.3)
 else:
 win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
 time.sleep(0.1)

 # Öne getir - AllowSetForegroundWindow trick
 try:
 import ctypes
 ctypes.windll.user32.AllowSetForegroundWindow(-1) # ASFW_ANY
 except:
 pass

 try:
 win32gui.SetForegroundWindow(hwnd)
 except:
 try:
 win32gui.BringWindowToTop(hwnd)
 except:
 pass
 break
 except:
 pass

 def _com_retry(self, func, max_deneme=5, bekleme=0.1):
 """COM çağrısını RPC_E_CALL_REJECTED hatasına karşı korumalı çağırır.

 AutoCAD meşgulken (özellikle büyük seçimlerde) COM çağrıları
 reddedilebilir. Bu metot otomatik retry ile bu sorunu aşar.
 """
 for deneme in range(max_deneme):
 try:
 return func()
 except com_error as e:
 # -2147418111 = 0x80010001 = RPC_E_CALL_REJECTED
 if e.hresult == -2147418111 and deneme < max_deneme - 1:
 time.sleep(bekleme * (deneme + 1))
 else:
 raise

 def _guvenli_select_on_screen(self, selection_set, max_deneme=2):
 """SelectOnScreen'i 'invisible' hatasına karşı korumalı çağırır.

 AutoCAD penceresi görünür değilse tekrar öne getirmeyi dener.
 """
 for deneme in range(max_deneme):
 try:
 selection_set.SelectOnScreen()
 return # Başarılı
 except com_error as e:
 hata_str = str(e).lower()
 if "invisible" in hata_str and deneme < max_deneme - 1:
 logger.warning(f"AutoCAD penceresi görünür değil, tekrar öne getiriliyor (deneme {deneme + 1})")
 print(">>> AutoCAD penceresi görünür değil, öne getiriliyor...")
 time.sleep(0.5)
 self._autocad_one_getir()
 time.sleep(0.5)
 else:
 raise # invisible değilse veya son denemeyse hatayı fırlat

 def baglantıyi_kes(self):
 """AutoCAD bağlantısını sonlandır ve kaynakları temizle."""
 try:
 # Renkleri geri al
 self.renkleri_geri_al()

 # Selection set'i temizle
 if self.selection_set:
 try:
 self.selection_set.Delete()
 except:
 pass
 self.selection_set = None

 self.acad_app = None
 self.aktif_cizim = None
 self.model_space = None
 self._bagli = False

 logger.info("AutoCAD bağlantısı sonlandırıldı.")

 except Exception as e:
 logger.warning(f"Bağlantı kapatılırken hata: {e}")

 def kullanici_secimi_al(self, mesaj: str = "Metraj alınacak objeleri seçin") -> List[MetrajObjesi]:
 """
 AutoCAD ekranında kullanıcıdan obje seçimi iste.

 Args:
 mesaj: Kullanıcıya gösterilecek bilgi mesajı

 Returns:
 List[MetrajObjesi]: Seçilen objelerin metraj bilgileri
 """
 if not self.bagli:
 raise ConnectionError("AutoCAD'e bağlı değil! Önce baglan() çağırın.")

 try:
 # AutoCAD penceresini görünür yap ve öne getir
 self._autocad_one_getir()

 # Önceki selection set'i temizle
 self._selection_set_temizle()

 # Yeni selection set oluştur
 ss_adi = f"MetrajSecim_{id(self)}"

 # Var olan aynı isimli set'i sil
 try:
 existing = self.aktif_cizim.SelectionSets.Item(ss_adi)
 existing.Delete()
 except:
 pass

 self.selection_set = self.aktif_cizim.SelectionSets.Add(ss_adi)

 # Kullanıcıya bilgi ver
 print(f"\n>>> {mesaj}")
 print(">>> AutoCAD penceresine geçin ve objeleri seçin...")
 print(">>> Seçimi tamamlamak için ENTER tuşuna basın.\n")

 # Kullanıcı seçimi (SelectOnScreen) - invisible hatasına karşı korumalı
 # Not: Bu çağrı, kullanıcı ENTER'a basana kadar bekler
 self._guvenli_select_on_screen(self.selection_set)

 # Seçilen objeleri işle
 secilen_objeler = []
 secim_sayisi = self.selection_set.Count

 if secim_sayisi == 0:
 print(">>> Hiç obje seçilmedi.")
 return []

 print(f"\n>>> {secim_sayisi} obje seçildi. İşleniyor...")

 for i in range(secim_sayisi):
 entity = self.selection_set.Item(i)
 metraj_obj = self._obje_verisi_oku(entity)
 if metraj_obj:
 secilen_objeler.append(metraj_obj)
 # Görsel teyit: Yeşile boya
 self._objeyi_renklendir(entity, AcadColor.GREEN)

 # Ekranı güncelle
 self.aktif_cizim.Regen(1) # acActiveViewport = 1

 print(f">>> {len(secilen_objeler)} objenin metrajı alındı ve YEŞİL ile işaretlendi.\n")

 return secilen_objeler

 except com_error as e:
 if "canceled" in str(e).lower() or "esc" in str(e).lower():
 print(">>> Seçim iptal edildi (ESC).")
 return []
 logger.error(f"Seçim hatası: {e}")
 raise
 except Exception as e:
 logger.error(f"Kullanıcı seçimi alınırken hata: {e}")
 raise

 def _obje_verisi_oku(self, entity) -> Optional[MetrajObjesi]:
 """
 Tek bir AutoCAD objesinin verilerini oku.

 Args:
 entity: AutoCAD entity objesi

 Returns:
 MetrajObjesi veya None
 """
 try:
 entity_type = entity.ObjectName
 layer = entity.Layer
 handle = entity.Handle

 metraj = MetrajObjesi(
 entity_type=entity_type,
 layer=layer,
 handle=handle,
 orijinal_renk=entity.Color
 )

 # Entity tipine göre özel verileri oku

 # LINE
 if entity_type == AcadEntityType.LINE:
 metraj.uzunluk = entity.Length
 start = entity.StartPoint
 end = entity.EndPoint
 metraj.koordinatlar = [
 (start[0], start[1]),
 (end[0], end[1])
 ]
 metraj.ozellikler["start"] = start
 metraj.ozellikler["end"] = end

 # POLYLINE / LWPOLYLINE
 elif entity_type in [AcadEntityType.POLYLINE, AcadEntityType.LWPOLYLINE,
 AcadEntityType.POLYLINE_2D, AcadEntityType.POLYLINE_3D,
 "AcDbPolyline"]:
 metraj.uzunluk = entity.Length
 try:
 metraj.alan = entity.Area
 except:
 metraj.alan = 0.0
 metraj.cevre = entity.Length
 try:
 metraj.ozellikler["closed"] = entity.Closed
 except:
 pass
 # Koordinatları al
 try:
 coords = entity.Coordinates
 # Koordinatlar düz liste olarak gelir: [x1, y1, x2, y2, ...]
 points = []
 for j in range(0, len(coords), 2):
 points.append((coords[j], coords[j+1]))
 metraj.koordinatlar = points
 except:
 pass

 # CIRCLE
 elif entity_type == AcadEntityType.CIRCLE:
 import math
 radius = entity.Radius
 metraj.alan = math.pi * radius ** 2
 metraj.cevre = 2 * math.pi * radius
 metraj.ozellikler["radius"] = radius
 center = entity.Center
 metraj.koordinatlar = [(center[0], center[1])]

 # ARC
 elif entity_type == AcadEntityType.ARC:
 metraj.uzunluk = entity.ArcLength
 metraj.ozellikler["radius"] = entity.Radius
 metraj.ozellikler["start_angle"] = entity.StartAngle
 metraj.ozellikler["end_angle"] = entity.EndAngle

 # TEXT
 elif entity_type == AcadEntityType.TEXT:
 metraj.text_icerigi = entity.TextString
 pos = entity.InsertionPoint
 metraj.koordinatlar = [(pos[0], pos[1])]
 metraj.ozellikler["height"] = entity.Height
 metraj.ozellikler["rotation"] = entity.Rotation

 # MTEXT
 elif entity_type == AcadEntityType.MTEXT:
 metraj.text_icerigi = entity.TextString
 pos = entity.InsertionPoint
 metraj.koordinatlar = [(pos[0], pos[1])]
 try:
 metraj.ozellikler["width"] = entity.Width
 metraj.ozellikler["height"] = entity.Height
 except:
 pass

 # BLOCK REFERENCE (INSERT)
 elif entity_type == AcadEntityType.BLOCK_REF:
 try:
 metraj.blok_adi = entity.EffectiveName
 except:
 metraj.blok_adi = entity.Name
 pos = entity.InsertionPoint
 metraj.koordinatlar = [(pos[0], pos[1])]
 metraj.ozellikler["rotation"] = entity.Rotation
 metraj.ozellikler["x_scale"] = entity.XScaleFactor
 metraj.ozellikler["y_scale"] = entity.YScaleFactor
 # Blok attribute'larını oku
 try:
 if entity.HasAttributes:
 attrs = {}
 for attr in entity.GetAttributes():
 attrs[attr.TagString] = attr.TextString
 metraj.ozellikler["attributes"] = attrs
 except:
 pass

 # HATCH
 elif entity_type == AcadEntityType.HATCH:
 try:
 metraj.alan = entity.Area
 except:
 pass
 metraj.ozellikler["pattern_name"] = entity.PatternName

 # SPLINE
 elif entity_type == AcadEntityType.SPLINE:
 try:
 # Spline uzunluğu için yaklaşık hesap
 metraj.uzunluk = entity.Length if hasattr(entity, 'Length') else 0.0
 except:
 pass

 # Diğer tipler için temel bilgiler
 else:
 logger.debug(f"Bilinmeyen entity tipi: {entity_type}")

 return metraj

 except Exception as e:
 logger.warning(f"Obje verisi okunurken hata (Handle: {entity.Handle}): {e}")
 return None

 def _guvenli_text_oku(self, entity) -> Optional[str]:
 """
 COM objesinden TextString'i güvenli şekilde oku.

 Bazı objeler (dimension alt-objeleri, proxy, bayat referans)
 TextString özelliğine erişim vermeyebilir.

 Returns:
 str veya None (okunamazsa)
 """
 # Yöntem 1: Doğrudan TextString
 try:
 text = entity.TextString
 if text is not None:
 return str(text)
 except Exception:
 pass

 # Yöntem 2: Objeyi handle ile yeniden al ve dene
 try:
 handle = entity.Handle
 yeni_entity = self.aktif_cizim.HandleToObject(handle)
 text = yeni_entity.TextString
 if text is not None:
 return str(text)
 except Exception:
 pass

 return None

 def _read_entity_props(self, entity) -> Optional[Dict[str, Any]]:
 """
 Bir entity'den tüm gerekli özellikleri TEK SEFERDE okur ve cache'ler.
 Böylece aynı özellik tekrar COM'dan çekilmez.
 RPC_E_CALL_REJECTED hatalarına karşı retry mekanizması içerir.

 Returns:
 Dict veya None (ObjectName okunamazsa)
 """
 try:
 obj_name = self._com_retry(lambda: entity.ObjectName)
 except Exception:
 return None

 handle = None
 try:
 handle = self._com_retry(lambda: entity.Handle)
 except Exception:
 pass

 text = None
 if obj_name in ["AcDbText", "AcDbMText"]:
 try:
 t = self._com_retry(lambda: entity.TextString)
 if t is not None:
 text = str(t)
 except Exception:
 text = self._guvenli_text_oku(entity)

 layer = ""
 try:
 layer = self._com_retry(lambda: entity.Layer)
 except Exception:
 pass

 color = 256
 try:
 color = self._com_retry(lambda: entity.Color)
 except Exception:
 pass

 return {
 'entity': entity,
 'object_name': obj_name,
 'handle': handle,
 'text': text,
 'layer': layer,
 'color': color,
 }

 def _read_entity_with_coords(self, entity) -> Optional[Dict[str, Any]]:
 """
 Entity özelliklerini koordinatlarıyla birlikte oku.
 Tablo yapılarını parse etmek için X,Y pozisyonu gerekli.

 Koordinat okuma stratejisi:
 1. GetBoundingBox (en güvenilir - her zaman görsel pozisyonu verir)
 2. TextAlignmentPoint (ortalı/sağa yaslı TEXT'ler için)
 3. InsertionPoint (sola yaslı TEXT'ler için)
 """
 props = self._read_entity_props(entity)
 if props is not None and props['object_name'] in ["AcDbText", "AcDbMText"]:
 x, y = None, None

 # Yöntem 1: GetBoundingBox (en güvenilir)
 try:
 result = self._com_retry(lambda: entity.GetBoundingBox())
 if result and len(result) == 2:
 min_pt, max_pt = result
 x = (min_pt[0] + max_pt[0]) / 2.0 # merkez X
 y = (min_pt[1] + max_pt[1]) / 2.0 # merkez Y
 except Exception:
 pass

 # Yöntem 2: TextAlignmentPoint (ortalı/sağa yaslı metinler)
 if x is None:
 try:
 pos = self._com_retry(lambda: entity.TextAlignmentPoint)
 if pos and (abs(pos[0]) > 0.01 or abs(pos[1]) > 0.01):
 x, y = pos[0], pos[1]
 except Exception:
 pass

 # Yöntem 3: InsertionPoint (fallback)
 if x is None:
 try:
 pos = self._com_retry(lambda: entity.InsertionPoint)
 x, y = pos[0], pos[1]
 except Exception:
 logger.debug(f"Koordinat okunamadı, obje atlanıyor: {props.get('text', '?')}")
 return None

 props['x'] = x
 props['y'] = y
 return props

 def _objeyi_renklendir(self, entity, renk: AcadColor):
 """
 Bir objenin rengini değiştir ve orijinal rengi kaydet.

 Args:
 entity: AutoCAD entity objesi
 renk: Yeni renk (AcadColor enum değeri)
 """
 try:
 # Handle alınabiliyorsa orijinal rengi kaydet
 try:
 handle = entity.Handle
 if handle not in self._orijinal_renkler:
 self._orijinal_renkler[handle] = entity.Color
 except Exception:
 pass # Handle alınamasa da renklendirmeye devam et

 # Katman kilidini kontrol et ve geçici olarak aç
 layer_obj = None
 layer_was_locked = False
 try:
 layer_obj = self.aktif_cizim.Layers.Item(entity.Layer)
 if layer_obj.Lock:
 layer_was_locked = True
 layer_obj.Lock = False
 except Exception:
 pass

 try:
 # Yeni rengi uygula
 entity.Color = int(renk)
 finally:
 # Katman kilidini geri yükle
 if layer_was_locked and layer_obj is not None:
 try:
 layer_obj.Lock = True
 except Exception:
 pass

 # Metrajı alınan objeler listesine ekle
 self._metraj_alinan_objeler.append(entity)

 except Exception as e:
 logger.debug(f"Obje renklendirilemedi (atlanıyor): {e}")

 def _objeyi_renklendir_cached(self, entity, renk: AcadColor,
 handle: str = None,
 original_color: int = None):
 """
 Optimizeli renklendirme - önceden okunan handle/color değerlerini kullanır.
 Optimistik yaklaşım: önce Color yaz, başarısız olursa layer kilidi çöz.
 """
 try:
 # Orijinal rengi kaydet (cache'ten, COM çağrısı yok)
 if handle is not None:
 if handle not in self._orijinal_renkler:
 self._orijinal_renkler[handle] = original_color if original_color is not None else 256
 else:
 try:
 h = entity.Handle
 if h not in self._orijinal_renkler:
 self._orijinal_renkler[h] = entity.Color
 except Exception:
 pass

 # Optimistik: Doğrudan renk yaz (1 COM çağrısı, retry korumalı)
 try:
 self._com_retry(lambda: setattr(entity, 'Color', int(renk)))
 except Exception:
 # Başarısız → muhtemelen kilitli katman, şimdi çöz
 try:
 layer_name = self._com_retry(lambda: entity.Layer)
 layer_obj = self._com_retry(lambda: self.aktif_cizim.Layers.Item(layer_name))
 if layer_obj.Lock:
 layer_obj.Lock = False
 try:
 self._com_retry(lambda: setattr(entity, 'Color', int(renk)))
 finally:
 try:
 layer_obj.Lock = True
 except Exception:
 pass
 except Exception:
 pass

 self._metraj_alinan_objeler.append(entity)

 except Exception as e:
 logger.debug(f"Obje renklendirilemedi (atlanıyor): {e}")

 def objeleri_hatali_isaretle(self, handle_listesi: List[str]):
 """
 Belirtilen handle'lara sahip objeleri KIRMIZI ile işaretle.

 Args:
 handle_listesi: İşaretlenecek objelerin handle değerleri
 """
 if not self.bagli:
 return

 try:
 for handle in handle_listesi:
 try:
 entity = self.aktif_cizim.HandleToObject(handle)
 self._objeyi_renklendir(entity, AcadColor.RED)
 except:
 pass

 self.aktif_cizim.Regen(1)

 except Exception as e:
 logger.warning(f"Hatalı işaretleme sırasında hata: {e}")

 def renkleri_geri_al(self):
 """Tüm değiştirilen renkleri orijinal hallerine döndür."""
 if not self.bagli or not self._orijinal_renkler:
 return

 try:
 for handle, orijinal_renk in self._orijinal_renkler.items():
 try:
 entity = self.aktif_cizim.HandleToObject(handle)
 entity.Color = orijinal_renk
 except:
 pass

 self._orijinal_renkler.clear()
 self._metraj_alinan_objeler.clear()

 self.aktif_cizim.Regen(1)
 logger.info("Tüm obje renkleri geri alındı.")

 except Exception as e:
 logger.warning(f"Renkler geri alınırken hata: {e}")

 def _selection_set_temizle(self):
 """Mevcut selection set'i temizle."""
 if self.selection_set:
 try:
 self.selection_set.Clear()
 except:
 pass

 def katman_listesi_al(self) -> List[str]:
 """Çizimdeki tüm katman isimlerini döndür."""
 if not self.bagli:
 return []

 try:
 katmanlar = []
 for layer in self.aktif_cizim.Layers:
 katmanlar.append(layer.Name)
 return sorted(katmanlar)
 except Exception as e:
 logger.warning(f"Katman listesi alınamadı: {e}")
 return []

 def blok_listesi_al(self) -> List[str]:
 """Çizimdeki tüm blok isimlerini döndür."""
 if not self.bagli:
 return []

 try:
 bloklar = []
 for block in self.aktif_cizim.Blocks:
 name = block.Name
 # Sistem bloklarını atla
 if not name.startswith("*"):
 bloklar.append(name)
 return sorted(bloklar)
 except Exception as e:
 logger.warning(f"Blok listesi alınamadı: {e}")
 return []

 def polyline_cizdir(self, mesaj: str = "Polyline çizin", kapat: bool = True) -> Dict[str, Any]:
 """
 AutoCAD'in yerleşik PLINE komutunu başlatarak kullanıcıya polyline çizdirir.
 AutoCAD'deki gibi tam çizim deneyimi sunar (rubber-band çizgi, snap, ortho vb.).

 Args:
 mesaj: Kullanıcıya gösterilecek bilgi mesajı
 kapat: True → polyline kapatılır (alan hesabı için)
 False → açık kalır (duvar uzunluk ölçümü için)

 Returns:
 Dict:
 uzunluk: float (çizilen polyline'ın AÇIK uzunluğu - kapatma segmenti hariç)
 alan: float (kapalı polyline alanı, kapat=False ise 0)
 cevre: float (kapalı polyline çevresi, kapat=False ise = uzunluk)
 nokta_sayisi: int (tıklanan nokta adedi)
 handle: str (oluşturulan polyline'ın handle'ı)
 iptal: bool (True ise kullanıcı iptal etti)
 """
 if not self.bagli:
 raise ConnectionError("AutoCAD'e bağlı değil!")

 self._autocad_one_getir()

 doc = self.aktif_cizim
 ms = doc.ModelSpace

 # ── 1) Mevcut obje sayısını kaydet ──
 count_before = ms.Count

 # ── 2) Aktif komut varsa iptal et ──
 try:
 doc.SendCommand("\x1b\x1b") # ESC ESC
 time.sleep(0.2)
 except Exception:
 pass

 # ── 3) AutoCAD'in yerleşik PLINE komutunu başlat ──
 # _PLINE = dil-bağımsız komut adı (İngilizce, Türkçe fark etmez)
 # SendCommand senkron çalışır → kullanıcı çizimi bitirene kadar bekler
 _iptal_sonuc = {
 "uzunluk": 0.0, "alan": 0.0, "cevre": 0.0,
 "nokta_sayisi": 0, "handle": "", "iptal": True
 }

 try:
 logger.info(f"PLINE komutu başlatılıyor: {mesaj}")
 doc.SendCommand("_PLINE\n")
 except Exception as e:
 logger.error(f"PLINE komutu başlatılamadı: {e}")
 return _iptal_sonuc

 # ── 4) Komut bitti → yeni obje var mı kontrol et ──
 time.sleep(0.1)
 count_after = ms.Count

 if count_after <= count_before:
 logger.info("PLINE: Kullanıcı iptal etti, yeni obje yok")
 return _iptal_sonuc

 # ── 5) Son eklenen objeyi al ──
 try:
 pline = ms.Item(count_after - 1)
 obj_name = pline.ObjectName

 if "Polyline" not in obj_name:
 logger.warning(f"PLINE: Son obje polyline değil: {obj_name}")
 return _iptal_sonuc
 except Exception as e:
 logger.error(f"PLINE: Son obje alınamadı: {e}")
 return _iptal_sonuc

 # ── 6) Önce AÇIK uzunluğu ölç (kapatma segmenti hariç) ──
 uzunluk = pline.Length

 # ── 7) Gerekirse kapat ──
 if kapat:
 try:
 pline.Closed = True
 except Exception:
 pass # Zaten kapalı olabilir (kullanıcı C ile kapatmışsa)

 # Yeşile boya
 pline.Color = int(AcadColor.GREEN)
 pline.Update()

 handle = pline.Handle
 self._orijinal_renkler[handle] = 256 # ByLayer

 # Nokta sayısını hesapla
 try:
 coords = pline.Coordinates
 nokta_sayisi = len(coords) // 2
 except Exception:
 nokta_sayisi = 0

 # Alan ve çevre (kapatıldıysa)
 if kapat:
 alan = pline.Area
 cevre = pline.Length # kapalı çevre
 else:
 alan = 0.0
 cevre = uzunluk # açık uzunluk

 doc.Regen(1)

 logger.info(
 f"PLINE tamamlandı: {nokta_sayisi} nokta, kapat={kapat}, "
 f"Uzunluk={uzunluk:.4f}, Alan={alan:.4f}, Çevre={cevre:.4f}"
 )

 return {
 "uzunluk": uzunluk,
 "alan": alan,
 "cevre": cevre,
 "nokta_sayisi": nokta_sayisi,
 "handle": handle,
 "iptal": False,
 }

 def blok_sayimi_al(self, mesaj: str = "Sayılacak blokları seçin") -> Dict[str, Any]:
 """
 Kullanıcıdan blok seçimi al ve blok isimlerine göre adet say.

 Returns:
 Dict: bloklar (isim->adet), toplam_adet, obje_sayisi
 """
 if not self.bagli:
 raise ConnectionError("AutoCAD'e bağlı değil!")

 objeler = self.kullanici_secimi_al(mesaj)

 blok_sayilari: Dict[str, int] = {}
 toplam_adet = 0

 for obj in objeler:
 if obj.entity_type == AcadEntityType.BLOCK_REF and obj.blok_adi:
 blok_sayilari[obj.blok_adi] = blok_sayilari.get(obj.blok_adi, 0) + 1
 toplam_adet += 1

 return {
 "bloklar": blok_sayilari,
 "toplam_adet": toplam_adet,
 "obje_sayisi": len(objeler),
 }

 def katmana_gore_sec(self, katman_adi: str) -> List[MetrajObjesi]:
 """
 Belirtilen katmandaki tüm objeleri seç ve metrajını al.

 Args:
 katman_adi: Seçilecek katman adı

 Returns:
 List[MetrajObjesi]: Katmandaki objelerin metraj bilgileri
 """
 if not self.bagli:
 raise ConnectionError("AutoCAD'e bağlı değil!")

 try:
 self._selection_set_temizle()

 ss_adi = f"KatmanSecim_{id(self)}"
 try:
 existing = self.aktif_cizim.SelectionSets.Item(ss_adi)
 existing.Delete()
 except:
 pass

 self.selection_set = self.aktif_cizim.SelectionSets.Add(ss_adi)

 # Filtre: Katman adı (DXF code 8 = Layer)
 import array
 filter_type = array.array('h', [8]) # signed short array
 filter_data = [katman_adi]

 # Tüm model space'i tara (5 = acSelectionSetAll)
 self.selection_set.Select(5, None, None, filter_type, filter_data)

 secilen_objeler = []
 for i in range(self.selection_set.Count):
 entity = self.selection_set.Item(i)
 metraj_obj = self._obje_verisi_oku(entity)
 if metraj_obj:
 secilen_objeler.append(metraj_obj)
 self._objeyi_renklendir(entity, AcadColor.GREEN)

 self.aktif_cizim.Regen(1)

 print(f">>> '{katman_adi}' katmanından {len(secilen_objeler)} obje seçildi.")

 return secilen_objeler

 except Exception as e:
 logger.error(f"Katmana göre seçim hatası: {e}")
 raise

 def zoom_secim(self):
 """Seçili objelere zoom yap."""
 if not self.bagli:
 return

 try:
 self.acad_app.ZoomExtents()
 except:
 pass

 def cizimi_kaydet(self):
 """Aktif çizimi kaydet."""
 if not self.bagli:
 return

 try:
 self.aktif_cizim.Save()
 logger.info("Çizim kaydedildi.")
 except Exception as e:
 logger.error(f"Kaydetme hatası: {e}")
 raise

 def komut_calistir(self, komut: str):
 """
 AutoCAD komut satırına komut gönder.

 Args:
 komut: Çalıştırılacak AutoCAD komutu
 """
 if not self.bagli:
 return

 try:
 self.aktif_cizim.SendCommand(komut + "\n")
 except Exception as e:
 logger.warning(f"Komut çalıştırılamadı: {e}")

 # ========================================================================
 # DEMİR METRAJ FONKSİYONLARI
 # ========================================================================

 def get_rebar_report_from_selection(self,
 birim: str = "cm",
 mesaj: str = "Demir yazılarını seçin") -> Dict[str, Any]:
 """
 AutoCAD'den seçilen TEXT/MTEXT objelerinden demir metrajı çıkar.

 Kullanıcı tek tek tıklayarak veya kutu çizerek obje seçer.
 ENTER'a basınca Python devreye girer ve:
 1. Sadece TEXT/MTEXT objelerini filtreler
 2. Demir regex analizi yapar: (\d+)[Øø](\d+).*?[Ll]=(\d+)
 3. Başarılı olanları YEŞİL, başarısızları KIRMIZI boyar
 4. Detaylı rapor döndürür

 Args:
 birim: Boy birimi ("cm" veya "m"), varsayılan "cm"
 mesaj: Kullanıcıya gösterilecek mesaj

 Returns:
 Dict: {
 "basarili": List[DemirBilgisi], # Geçerli demir yazıları
 "basarisiz": List[DemirBilgisi], # Format dışı metinler
 "toplam_adet": int, # Toplam demir adedi
 "toplam_boy_m": float, # Toplam boy (metre)
 "toplam_agirlik_kg": float, # Toplam ağırlık (kg)
 "cap_ozeti": Dict[int, Dict], # Çap bazlı özet
 "secim_sayisi": int, # Toplam seçilen obje
 "metin_sayisi": int, # TEXT/MTEXT sayısı
 }

 Örnek Demir Yazıları:
 "10Ø12 L=250" -> 10 adet, Ø12, 250cm
 "5ø16 l=180" -> 5 adet, Ø16, 180cm
 "8Ø10 L=320 cm" -> 8 adet, Ø10, 320cm
 "12 Ø 14 L = 150" -> 12 adet, Ø14, 150cm (boşluklu)
 """
 if not self.bagli:
 raise ConnectionError("AutoCAD'e bağlı değil! Önce baglan() çağırın.")

 # Sonuç yapısı
 sonuc = {
 "basarili": [],
 "basarisiz": [],
 "toplam_adet": 0,
 "toplam_boy_m": 0.0,
 "toplam_agirlik_kg": 0.0,
 "cap_ozeti": {},
 "secim_sayisi": 0,
 "metin_sayisi": 0,
 }

 try:
 # AutoCAD penceresini görünür yap ve öne getir
 self._autocad_one_getir()

 # Önceki selection set'i temizle
 self._selection_set_temizle()

 # Yeni selection set oluştur
 ss_adi = f"DemirSecim_{id(self)}"
 try:
 existing = self.aktif_cizim.SelectionSets.Item(ss_adi)
 existing.Delete()
 except:
 pass

 self.selection_set = self.aktif_cizim.SelectionSets.Add(ss_adi)

 # Kullanıcıya bilgi ver
 print(f"\n{'='*50}")
 print(f" DEMİR METRAJİ - AutoCAD Seçimi")
 print(f"{'='*50}")
 print(f">>> {mesaj}")
 print(">>> Tek tek tıklayın veya kutu çizin.")
 print(">>> Seçimi tamamlamak için ENTER tuşuna basın.")
 print(">>> İptal için ESC tuşuna basın.\n")

 # SelectOnScreen - Kullanıcı seçimi (ENTER'a kadar bekler)
 self._guvenli_select_on_screen(self.selection_set)

 secim_sayisi = self.selection_set.Count
 sonuc["secim_sayisi"] = secim_sayisi

 if secim_sayisi == 0:
 print(">>> Hiç obje seçilmedi.")
 return sonuc

 print(f"\n>>> {secim_sayisi} obje seçildi. Filtreleniyor...")

 # ================================================================
 # TEK GEÇİŞ: FİLTRELE + ÖZELLİKLERİ CACHE'LE
 # ================================================================
 metin_props_listesi = [] # Cache'lenmiş özellikler

 for i in range(secim_sayisi):
 # Her 100 objede bir AutoCAD'e nefes aldır
 if i > 0 and i % 100 == 0:
 time.sleep(0.05)

 try:
 entity = self._com_retry(lambda idx=i: self.selection_set.Item(idx))
 except Exception as e:
 logger.debug(f"Obje {i} okunamadı, atlanıyor: {e}")
 continue

 props = self._read_entity_props(entity)
 if props is None:
 continue

 if props['object_name'] in ["AcDbText", "AcDbMText"]:
 if props['text'] is not None:
 metin_props_listesi.append(props)
 else:
 logger.debug(f"Metin objesi okunamadı, atlanıyor (index: {i})")

 sonuc["metin_sayisi"] = len(metin_props_listesi)

 if not metin_props_listesi:
 print(f">>> Seçilen {secim_sayisi} objeden hiçbiri metin değil!")
 print(f">>> Lütfen demir yazılarını (TEXT/MTEXT) seçin.")
 return sonuc

 print(f">>> {len(metin_props_listesi)} metin objesi bulundu. Analiz ediliyor...")

 # Debug: Seçilen metinleri göster (cache'ten, 0 COM çağrısı)
 print(f"\n>>> SEÇİLEN METİNLER (DEBUG):")
 for idx, props in enumerate(metin_props_listesi[:10], 1):
 print(f" {idx}. \"{props['text']}\"")
 if len(metin_props_listesi) > 10:
 print(f" ... ve {len(metin_props_listesi)-10} metin daha")
 print()

 # ================================================================
 # DEMİR REGEX ANALİZİ (cache'lenmiş verilerle)
 # ================================================================
 # Pattern: ADET Ø/ƒ/φ ÇAP ... L = BOY
 # Desteklenen formatlar:
 # "10Ø12 L=250" -> 10 adet, Ø12, 250cm
 # "P05 2ƒ12 ila. l=233" -> 2 adet, Ø12, 233cm (poz numaralı)
 # "5φ16 l=180" -> 5 adet, Ø16, 180cm
 # "%%c" = AutoCAD'in Ø kodu
 # Çap karakterleri: Ø ø ƒ φ Φ ∅ T (T bazen font sorunu)
 demir_pattern = re.compile(
 r'(?:P\d+\s+)?(\d+)\s*[ØøƒφΦ∅TtΤ]\s*(\d+).*?[Ll]\s*=\s*(\d+(?:[.,]\d+)?)',
 re.IGNORECASE
 )

 # AutoCAD %%c kodu için alternatif pattern
 demir_pattern_autocad = re.compile(
 r'(?:P\d+\s+)?(\d+)\s*%%[cC]\s*(\d+).*?[Ll]\s*=\s*(\d+(?:[.,]\d+)?)',
 re.IGNORECASE
 )

 # Qt event loop'u rahatlatmak için import
 try:
 from PyQt6.QtWidgets import QApplication
 _qt_available = True
 except ImportError:
 _qt_available = False

 for idx, props in enumerate(metin_props_listesi):
 # Her 5 objede bir Qt mesaj kuyruğunu boşalt
 if _qt_available and idx % 5 == 0:
 QApplication.processEvents()

 try:
 # Cache'ten oku (0 COM çağrısı)
 handle = props['handle'] or str(id(props['entity']))
 text_content = props['text']
 layer = props['layer'] or ""

 # Demir bilgisi oluştur
 demir = DemirBilgisi(
 handle=handle,
 orijinal_metin=text_content,
 katman=layer
 )

 # Debug: Metin içeriğini logla
 logger.debug(f"Metin kontrol ediliyor: '{text_content}' (hex: {text_content.encode('utf-8').hex()})")

 # Regex ile eşleştir (iki pattern dene)
 match = demir_pattern.search(text_content)
 if not match:
 match = demir_pattern_autocad.search(text_content)

 if match:
 # Başarılı eşleşme
 adet = int(match.group(1))
 cap = int(match.group(2))
 boy_str = match.group(3).replace(',', '.')
 boy = float(boy_str)

 # Birim dönüşümü (cm -> m)
 if birim.lower() == "cm":
 boy_m = boy / 100.0
 else:
 boy_m = boy

 # Ağırlık hesabı
 agirlik_birim = DEMIR_AGIRLIK_TABLOSU.get(cap, 0.0)
 toplam_boy = adet * boy_m
 toplam_agirlik = toplam_boy * agirlik_birim

 # Demir bilgisini güncelle
 demir.adet = adet
 demir.cap = cap
 demir.boy = boy
 demir.toplam_boy = toplam_boy
 demir.agirlik_birim = agirlik_birim
 demir.toplam_agirlik = toplam_agirlik
 demir.gecerli = True

 # Başarılı listeye ekle
 sonuc["basarili"].append(demir)

 # Toplamları güncelle
 sonuc["toplam_adet"] += adet
 sonuc["toplam_boy_m"] += toplam_boy
 sonuc["toplam_agirlik_kg"] += toplam_agirlik

 # Çap özeti
 if cap not in sonuc["cap_ozeti"]:
 sonuc["cap_ozeti"][cap] = {
 "adet": 0,
 "boy_m": 0.0,
 "agirlik_kg": 0.0,
 "birim_agirlik": agirlik_birim
 }
 sonuc["cap_ozeti"][cap]["adet"] += adet
 sonuc["cap_ozeti"][cap]["boy_m"] += toplam_boy
 sonuc["cap_ozeti"][cap]["agirlik_kg"] += toplam_agirlik

 # YEŞİL boya (cache'li, 1 COM çağrısı)
 self._objeyi_renklendir_cached(
 props['entity'], AcadColor.GREEN,
 handle=props['handle'],
 original_color=props['color']
 )

 logger.debug(f"Demir bulundu: {adet}Ø{cap} L={boy}{birim} -> {toplam_agirlik:.2f}kg")

 else:
 # Eşleşmedi - format dışı
 demir.gecerli = False
 demir.hata_mesaji = "Demir formatına uymuyor"
 sonuc["basarisiz"].append(demir)

 # KIRMIZI boya (cache'li, 1 COM çağrısı)
 self._objeyi_renklendir_cached(
 props['entity'], AcadColor.RED,
 handle=props['handle'],
 original_color=props['color']
 )

 logger.debug(f"Format dışı metin: '{text_content}'")

 except Exception as e:
 logger.warning(f"Metin işlenirken hata: {type(e).__name__}: {e}")
 try:
 hata_demir = DemirBilgisi(
 handle=str(id(props.get('entity', None))),
 orijinal_metin=f"(Okunamadı: {e})",
 katman=""
 )
 hata_demir.gecerli = False
 hata_demir.hata_mesaji = f"COM hatası: {e}"
 sonuc["basarisiz"].append(hata_demir)
 self._objeyi_renklendir_cached(
 props['entity'], AcadColor.RED,
 handle=props.get('handle'),
 original_color=props.get('color')
 )
 except Exception:
 pass

 # Ekranı güncelle
 self.aktif_cizim.Regen(1)

 # ================================================================
 # SONUÇ RAPORU
 # ================================================================
 print(f"\n{'='*50}")
 print(f" DEMİR METRAJ RAPORU")
 print(f"{'='*50}")
 print(f" Toplam seçim : {secim_sayisi} obje")
 print(f" Metin objesi : {len(metin_props_listesi)} adet")
 print(f" Geçerli demir : {len(sonuc['basarili'])} adet")
 print(f" Format dışı : {len(sonuc['basarisiz'])} adet")
 print(f"{'='*50}")

 if sonuc["basarili"]:
 # Çubuk adedi hesapla (1 çubuk = 12 metre) - yukarı yuvarla
 CUBUK_BOYU = 12.0 # metre
 toplam_cubuk = math.ceil(sonuc['toplam_boy_m'] / CUBUK_BOYU)
 sonuc["toplam_cubuk"] = toplam_cubuk

 # Çap bazlı çubuk hesabı - yukarı yuvarla
 for cap in sonuc["cap_ozeti"]:
 sonuc["cap_ozeti"][cap]["cubuk_adet"] = math.ceil(sonuc["cap_ozeti"][cap]["boy_m"] / CUBUK_BOYU)

 print(f"\n ÖZET:")
 print(f" ─────────────────────────────────")
 print(f" Toplam Demir Adedi : {sonuc['toplam_adet']:,}")
 print(f" Toplam Boy : {sonuc['toplam_boy_m']:,.2f} m")
 print(f" Toplam Ağırlık : {sonuc['toplam_agirlik_kg']:,.2f} kg")
 print(f" : {sonuc['toplam_agirlik_kg']/1000:,.3f} ton")
 print(f" ─────────────────────────────────")
 print(f" ÇUBUK ADEDİ (12m) : {toplam_cubuk:,} çubuk")

 print(f"\n ÇAP BAZLI DAĞILIM:")
 print(f" {'Çap':<6} {'Adet':>8} {'Boy(m)':>10} {'Ağırlık(kg)':>12} {'Çubuk':>8}")
 print(f" {'-'*50}")
 for cap in sorted(sonuc["cap_ozeti"].keys()):
 ozet = sonuc["cap_ozeti"][cap]
 print(f" Ø{cap:<4} {ozet['adet']:>8,} {ozet['boy_m']:>10,.2f} {ozet['agirlik_kg']:>12,.2f} {ozet['cubuk_adet']:>8,}")

 if sonuc["basarisiz"]:
 print(f"\n FORMAT DIŞI METİNLER (KIRMIZI):")
 for d in sonuc["basarisiz"][:5]: # İlk 5'i göster
 print(f" • \"{d.orijinal_metin[:40]}...\"" if len(d.orijinal_metin) > 40 else f" • \"{d.orijinal_metin}\"")
 if len(sonuc["basarisiz"]) > 5:
 print(f" ... ve {len(sonuc['basarisiz'])-5} metin daha")

 print(f"\n{'='*50}\n")

 return sonuc

 except com_error as e:
 if "canceled" in str(e).lower() or "esc" in str(e).lower():
 print(">>> Seçim iptal edildi (ESC).")
 return sonuc
 logger.error(f"Demir seçim hatası: {e}")
 raise
 except Exception as e:
 logger.error(f"Demir raporu alınırken hata: {e}")
 raise

 def get_kolon_filizi_from_table(self,
 birim: str = "cm",
 mesaj: str = "Kolon filizi tablosunu seçin") -> Dict[str, Any]:
 """
 AutoCAD'deki kolon filizi tablosunu otomatik okur.

 Kullanıcı tüm tabloyu kutu çizerek seçer.
 Program Y koordinatına göre satırları, X koordinatına göre sütunları belirler.
 Başlık satırını (KOLON, DONATI, BOY) otomatik tanır.

 Tablo formatı:
 KOLON | DONATI | BOY
 SB01 | P84-28Ø14 | 135
 SB02 | P84-14Ø14 | 135

 Returns:
 get_rebar_report_from_selection() ile aynı dict formatı
 """
 if not self.bagli:
 raise ConnectionError("AutoCAD'e bağlı değil! Önce baglan() çağırın.")

 sonuc = {
 "basarili": [],
 "basarisiz": [],
 "toplam_adet": 0,
 "toplam_boy_m": 0.0,
 "toplam_agirlik_kg": 0.0,
 "cap_ozeti": {},
 "secim_sayisi": 0,
 "metin_sayisi": 0,
 }

 try:
 self._autocad_one_getir()
 self._selection_set_temizle()

 ss_adi = f"FilizSecim_{id(self)}"
 try:
 existing = self.aktif_cizim.SelectionSets.Item(ss_adi)
 existing.Delete()
 except:
 pass

 self.selection_set = self.aktif_cizim.SelectionSets.Add(ss_adi)

 print(f"\n{'='*50}")
 print(f" KOLON FİLİZİ - Tablo Okuma")
 print(f"{'='*50}")
 print(f">>> {mesaj}")
 print(">>> Tüm tabloyu kutu çizerek seçin.")
 print(">>> Seçimi tamamlamak için ENTER tuşuna basın.\n")

 self._guvenli_select_on_screen(self.selection_set)

 secim_sayisi = self.selection_set.Count
 sonuc["secim_sayisi"] = secim_sayisi

 if secim_sayisi == 0:
 print(">>> Hiç obje seçilmedi.")
 return sonuc

 print(f"\n>>> {secim_sayisi} obje seçildi. Tablo analiz ediliyor...")

 # ================================================================
 # 1. TÜM METİN OBJELERİNİ OKU
 # ================================================================
 metin_listesi = []

 for i in range(secim_sayisi):
 if i > 0 and i % 100 == 0:
 time.sleep(0.05)
 try:
 entity = self._com_retry(lambda idx=i: self.selection_set.Item(idx))
 except Exception:
 continue
 props = self._read_entity_props(entity)
 if props is None:
 continue
 if props['object_name'] not in ["AcDbText", "AcDbMText"]:
 continue
 if props['text'] is None:
 continue
 metin_listesi.append(props)

 sonuc["metin_sayisi"] = len(metin_listesi)

 if len(metin_listesi) < 3:
 print(">>> Yeterli metin objesi bulunamadı.")
 return sonuc

 # ================================================================
 # 2. İÇERİK BAZLI AKILLI PARSE (koordinat gerekmez)
 # ================================================================
 # Metin sınıflandırma kalıpları
 donati_pattern = re.compile(
 r'(?:P\d+[-.])?(\d+)\s*[ØøƒφΦ∅]\s*(\d+)',
 re.IGNORECASE
 )
 donati_pattern_autocad = re.compile(
 r'(?:P\d+[-.])?(\d+)\s*%%[cC]\s*(\d+)',
 re.IGNORECASE
 )
 boy_pattern = re.compile(r'^(\d+(?:[.,]\d+)?)$')
 baslik_kelimeleri = {"KOLON", "DONATI", "DONAT", "BOY", "FİLİZ", "FILIZ", "FILIZI", "FİLİZİ", "KOLON FILIZI", "KOLON FİLİZİ"}

 # Tüm metinleri sınıflandır
 donati_listesi = [] # [(props, match)]
 boy_listesi = [] # [(props, değer)]
 kolon_listesi = [] # [props]
 atlanan = 0

 for props in metin_listesi:
 text = props['text'].strip()
 text_upper = text.upper().strip()

 # Başlık metinleri → atla
 if text_upper in baslik_kelimeleri:
 atlanan += 1
 continue

 # Donatı mı? (P84-28ƒ14, 28Ø14, vb.)
 match = donati_pattern.search(text)
 if not match:
 match = donati_pattern_autocad.search(text)
 if match:
 donati_listesi.append((props, match))
 continue

 # Sayı mı? (boy değeri: 135, 150, 200 vb.)
 boy_match = boy_pattern.match(text)
 if boy_match:
 try:
 val = float(boy_match.group(1).replace(',', '.'))
 if val > 0:
 boy_listesi.append((props, val))
 continue
 except ValueError:
 pass

 # Geriye kalan → kolon adı (SB01, K1, S03 vb.)
 if len(text) <= 20 and text_upper not in baslik_kelimeleri:
 kolon_listesi.append(props)

 print(f">>> Sınıflandırma: {len(donati_listesi)} donatı, {len(boy_listesi)} boy, {len(kolon_listesi)} kolon, {atlanan} başlık")

 # Eşleştirme: donatı ve boy aynı sayıda olmalı
 if len(donati_listesi) == 0:
 print(">>> Hiç donatı metni bulunamadı!")
 print(">>> Beklenen format: P84-28Ø14 veya 28Ø14")
 return sonuc

 # Boy listesi donatıdan az/çoksa uyar
 if len(boy_listesi) != len(donati_listesi):
 print(f">>> UYARI: {len(donati_listesi)} donatı ama {len(boy_listesi)} boy değeri bulundu.")
 # Eğer tek boy değeri varsa hepsine uygula
 if len(boy_listesi) == 1:
 tek_boy = boy_listesi[0][1]
 print(f">>> Tek boy değeri ({tek_boy}) tüm donatılara uygulanıyor.")
 boy_listesi = [(boy_listesi[0][0], tek_boy)] * len(donati_listesi)
 elif len(set(b[1] for b in boy_listesi)) == 1:
 # Hepsi aynı boy
 tek_boy = boy_listesi[0][1]
 print(f">>> Tüm boy değerleri aynı ({tek_boy}), donatı sayısına tamamlanıyor.")
 boy_listesi = [(boy_listesi[0][0], tek_boy)] * len(donati_listesi)

 # Satır sayısını belirle
 satir_sayisi = min(len(donati_listesi), len(boy_listesi))
 print(f">>> {satir_sayisi} veri satırı işleniyor...\n")

 for idx in range(satir_sayisi):
 d_props, d_match = donati_listesi[idx]
 b_props, boy = boy_listesi[idx]
 kolon_text = kolon_listesi[idx]['text'].strip() if idx < len(kolon_listesi) else f"Satır{idx+1}"

 donati_text = d_props['text'].strip()
 satir_entityleri = [d_props, b_props]
 if idx < len(kolon_listesi):
 satir_entityleri.append(kolon_listesi[idx])

 if not donati_text or boy <= 0:
 continue

 # Handle bilgisi
 handle = satir_entityleri[0]['handle'] if satir_entityleri else f"row_{idx}"
 orijinal = f"{kolon_text}: {donati_text} L={boy}" if kolon_text else f"{donati_text} L={boy}"

 # Birleşik donatıları yakala (ör: 8ƒ16+6ƒ14 → 2 ayrı demir)
 all_matches = list(donati_pattern.finditer(donati_text))
 if not all_matches:
 all_matches = list(donati_pattern_autocad.finditer(donati_text))

 if not all_matches:
 demir = DemirBilgisi(
 handle=handle,
 orijinal_metin=orijinal,
 katman=kolon_text
 )
 demir.gecerli = False
 demir.hata_mesaji = "Donatı parse edilemedi"
 sonuc["basarisiz"].append(demir)

 for p in satir_entityleri:
 self._objeyi_renklendir_cached(
 p['entity'], AcadColor.RED,
 handle=p['handle'], original_color=p['color']
 )
 continue

 if birim.lower() == "cm":
 boy_m = boy / 100.0
 else:
 boy_m = boy

 for mi, match in enumerate(all_matches):
 adet = int(match.group(1))
 cap = int(match.group(2))

 agirlik_birim = DEMIR_AGIRLIK_TABLOSU.get(cap, 0.0)
 toplam_boy = adet * boy_m
 toplam_agirlik = toplam_boy * agirlik_birim

 demir = DemirBilgisi(
 handle=f"{handle}_{mi}" if mi > 0 else handle,
 orijinal_metin=orijinal if mi == 0 else f" +{adet}Ø{cap}",
 katman=kolon_text
 )
 demir.adet = adet
 demir.cap = cap
 demir.boy = boy
 demir.toplam_boy = toplam_boy
 demir.agirlik_birim = agirlik_birim
 demir.toplam_agirlik = toplam_agirlik
 demir.gecerli = True

 sonuc["basarili"].append(demir)
 sonuc["toplam_adet"] += adet
 sonuc["toplam_boy_m"] += toplam_boy
 sonuc["toplam_agirlik_kg"] += toplam_agirlik

 if cap not in sonuc["cap_ozeti"]:
 sonuc["cap_ozeti"][cap] = {
 "adet": 0, "boy_m": 0.0, "agirlik_kg": 0.0,
 "birim_agirlik": agirlik_birim
 }
 sonuc["cap_ozeti"][cap]["adet"] += adet
 sonuc["cap_ozeti"][cap]["boy_m"] += toplam_boy
 sonuc["cap_ozeti"][cap]["agirlik_kg"] += toplam_agirlik

 logger.debug(f"Filiz: {kolon_text} {adet}Ø{cap} L={boy} -> {toplam_agirlik:.2f}kg")

 # YEŞİL boya (satırdaki tüm donatılar başarılı)
 for p in satir_entityleri:
 self._objeyi_renklendir_cached(
 p['entity'], AcadColor.GREEN,
 handle=p['handle'], original_color=p['color']
 )

 # Ekranı güncelle
 self.aktif_cizim.Regen(1)

 # ================================================================
 # SONUÇ RAPORU
 # ================================================================
 print(f"\n{'='*50}")
 print(f" KOLON FİLİZİ RAPORU")
 print(f"{'='*50}")
 print(f" Toplam seçim : {secim_sayisi} obje")
 print(f" Metin objesi : {sonuc['metin_sayisi']} adet")
 print(f" Satır sayısı : {satir_sayisi} adet")
 print(f" Geçerli demir : {len(sonuc['basarili'])} adet")
 print(f" Format dışı : {len(sonuc['basarisiz'])} adet")

 if sonuc["basarili"]:
 CUBUK_BOYU = 12.0
 toplam_cubuk = math.ceil(sonuc['toplam_boy_m'] / CUBUK_BOYU)
 sonuc["toplam_cubuk"] = toplam_cubuk

 for cap in sonuc["cap_ozeti"]:
 sonuc["cap_ozeti"][cap]["cubuk_adet"] = math.ceil(
 sonuc["cap_ozeti"][cap]["boy_m"] / CUBUK_BOYU
 )

 print(f"\n ÖZET:")
 print(f" Toplam Demir : {sonuc['toplam_adet']:,} adet")
 print(f" Toplam Boy : {sonuc['toplam_boy_m']:,.2f} m")
 print(f" Toplam Ağırlık : {sonuc['toplam_agirlik_kg']:,.2f} kg")
 print(f" : {sonuc['toplam_agirlik_kg']/1000:,.3f} ton")
 print(f" Çubuk (12m) : {toplam_cubuk:,} çubuk")

 print(f"\n ÇAP BAZLI DAĞILIM:")
 print(f" {'Çap':<6} {'Adet':>8} {'Boy(m)':>10} {'Ağırlık(kg)':>12}")
 print(f" {'-'*40}")
 for cap in sorted(sonuc["cap_ozeti"].keys()):
 ozet = sonuc["cap_ozeti"][cap]
 print(f" Ø{cap:<4} {ozet['adet']:>8,} {ozet['boy_m']:>10,.2f} {ozet['agirlik_kg']:>12,.2f}")

 print(f"\n{'='*50}\n")
 return sonuc

 except com_error as e:
 if "canceled" in str(e).lower() or "esc" in str(e).lower():
 print(">>> Seçim iptal edildi (ESC).")
 return sonuc
 logger.error(f"Kolon filizi seçim hatası: {e}")
 raise
 except Exception as e:
 logger.error(f"Kolon filizi raporu alınırken hata: {e}")
 raise

 def get_beton_kalip_boyutlar(
 self,
 eleman_turu: str,
 birim: str = "cm"
 ) -> Dict[str, Any]:
 """
 Seçilen AutoCAD objesi üzerinden beton elemanı boyutlarını oku.

 Eleman türüne göre beklenen obje tipi ve döndürülen boyutlar:
 Kolon / Kiriş : Kapalı POLYLINE (kesit) → BoundingBox → dim1=boy, dim2=en (m)
 Döşeme / Temel : Kapalı POLYLINE veya HATCH → BoundingBox → dim1=uzunluk, dim2=genişlik (m)
 Perde Duvar : LINE veya POLYLINE (eksen) → Length → dim1=uzunluk (m), dim2=0

 Neyi çözüyoruz?
 Kullanıcının boyutları elle girmek yerine doğrudan AutoCAD kesitini
 veya eksen çizgisini tıklayarak form alanlarını otomatik doldurması.

 Nasıl test ederiz?
 Connector bağlı durumdayken eleman_turu="Kolon", birim="cm" ile çağır,
 AutoCAD'de 50×60 cm boyutlarında bir dikdörtgen seçince
 dim1=0.50, dim2=0.60 dönmeli.

 Args:
 eleman_turu : "Kolon", "Kiriş", "Döşeme", "Temel", "Perde Duvar"
 birim : AutoCAD çizim birimi — "mm", "cm" veya "m"

 Returns:
 Dict:
 dim1 (float) — Boyut 1 (m cinsinden)
 dim2 (float) — Boyut 2 (m cinsinden); Perde Duvar = 0.0
 entity_type (str) — Seçilen AutoCAD obje tipi
 katman (str) — Objenin bulunduğu katman
 iptal (bool) — ESC ile iptal edildiyse True
 hata (str) — Hata açıklaması (varsa)
 """
 if not self.bagli:
 raise ConnectionError("AutoCAD'e bağlı değil! Önce baglan() çağırın.")

 # Birim → metre dönüşüm katsayısı
 birim_katsayi = {"mm": 1000.0, "cm": 100.0, "m": 1.0}.get(birim, 100.0)

 _bos = {
 "dim1": 0.0, "dim2": 0.0,
 "entity_type": "", "katman": "",
 "iptal": True, "hata": ""
 }

 # Eleman türüne göre kullanıcı yönlendirme mesajları
 mesaj_haritasi = {
 "Kolon": "Kolon KESİT çizgisini (kapalı dikdörtgen) seçin → ENTER",
 "Kiriş": "Kiriş KESİT çizgisini (kapalı dikdörtgen) seçin → ENTER",
 "Döşeme": "Döşeme ALANINI (kapalı polyline veya hatch) seçin → ENTER",
 "Temel": "Temel ALANINI (kapalı polyline) seçin → ENTER",
 "Perde Duvar": "Perde duvar EKSEN çizgisini (line/polyline) seçin → ENTER",
 }
 mesaj = mesaj_haritasi.get(eleman_turu, "Elemanı seçin → ENTER")

 try:
 self._autocad_one_getir()
 self._selection_set_temizle()

 ss_adi = f"BetonKalipSecim_{id(self)}"
 try:
 self.aktif_cizim.SelectionSets.Item(ss_adi).Delete()
 except Exception:
 pass

 self.selection_set = self.aktif_cizim.SelectionSets.Add(ss_adi)

 print(f"\n{'='*55}")
 print(f" BETON & KALIP — {eleman_turu.upper()} Boyut Okuma")
 print(f"{'='*55}")
 print(f">>> {mesaj}")
 print(f">>> Çizim birimi: {birim} (dönüşüm: 1 {birim} = {1/birim_katsayi:.4f} m)")
 print(f">>> İptal için ESC tuşuna basın.\n")

 self._guvenli_select_on_screen(self.selection_set)

 if self.selection_set.Count == 0:
 print(">>> Hiç obje seçilmedi (ESC veya boş seçim).")
 return _bos

 # Sadece ilk objeyi al (tek eleman boyutu bekleniyor)
 entity = self._com_retry(lambda: self.selection_set.Item(0))
 entity_type = entity.ObjectName
 katman = entity.Layer

 print(f">>> Seçilen obje: {entity_type} | Katman: {katman}")

 dim1 = 0.0
 dim2 = 0.0
 hata = ""

 # ── Strateji A: GetBoundingBox (Kolon/Kiriş/Döşeme/Temel için) ──
 if eleman_turu in ("Kolon", "Kiriş", "Döşeme", "Temel"):
 try:
 result = self._com_retry(lambda: entity.GetBoundingBox())
 if result and len(result) == 2:
 min_pt, max_pt = result
 dx = abs(max_pt[0] - min_pt[0]) / birim_katsayi
 dy = abs(max_pt[1] - min_pt[1]) / birim_katsayi
 # dim1 = uzun kenar, dim2 = kısa kenar (büyük→küçük sırala)
 dim1 = round(max(dx, dy), 4)
 dim2 = round(min(dx, dy), 4)
 print(
 f">>> BoundingBox: {dx*birim_katsayi:.1f}×{dy*birim_katsayi:.1f} {birim}"
 f" → {dim1:.4f}×{dim2:.4f} m"
 )
 else:
 hata = "GetBoundingBox geçerli değer döndürmedi."
 except Exception as e:
 # Fallback: entity.Area üzerinden kare tahmin
 try:
 alan_ham = entity.Area
 kenar = math.sqrt(alan_ham) / birim_katsayi
 dim1 = round(kenar, 4)
 dim2 = round(kenar, 4)
 hata = f"BoundingBox hatası ({e}), Alan'dan tahmin edildi."
 print(f">>> [Fallback] Area={alan_ham:.2f} → {dim1:.4f}×{dim2:.4f} m")
 except Exception as e2:
 hata = f"Boyut okunamadı: {e2}"

 # ── Strateji B: Length (Perde Duvar için) ──
 elif eleman_turu == "Perde Duvar":
 try:
 uzunluk_ham = entity.Length
 dim1 = round(uzunluk_ham / birim_katsayi, 4)
 dim2 = 0.0
 print(f">>> Uzunluk: {uzunluk_ham:.2f} {birim} → {dim1:.4f} m")
 except Exception as e:
 hata = f"Uzunluk okunamadı: {e}"

 # Yeşile boya (başarılı okuma)
 if not hata:
 self._objeyi_renklendir(entity, AcadColor.GREEN)
 else:
 self._objeyi_renklendir(entity, AcadColor.YELLOW)

 try:
 self.aktif_cizim.Regen(1)
 except Exception:
 pass

 if dim1 == 0.0 and not hata:
 hata = "Boyut sıfır döndü — obje tipi uygun olmayabilir."

 return {
 "dim1": dim1,
 "dim2": dim2,
 "entity_type": entity_type,
 "katman": katman,
 "iptal": False,
 "hata": hata,
 }

 except Exception as e:
 logger.error(f"Beton & Kalıp boyut okuma hatası: {e}")
 sonuc = dict(_bos)
 sonuc["hata"] = str(e)
 return sonuc

 def get_rebar_summary_dataframe(self, rapor: Dict[str, Any]):
 """
 Demir raporunu pandas DataFrame'e çevir.

 Args:
 rapor: get_rebar_report_from_selection() çıktısı

 Returns:
 Tuple[DataFrame, DataFrame]: (detay_df, ozet_df)
 """
 try:
 import pandas as pd
 except ImportError:
 logger.warning("pandas yüklü değil, DataFrame oluşturulamadı")
 return None, None

 # Detay DataFrame
 detay_rows = []
 for d in rapor["basarili"]:
 detay_rows.append({
 "Metin": d.orijinal_metin,
 "Adet": d.adet,
 "Çap (mm)": d.cap,
 "Boy (cm)": d.boy,
 "Toplam Boy (m)": d.toplam_boy,
 "Birim Ağırlık (kg/m)": d.agirlik_birim,
 "Toplam Ağırlık (kg)": d.toplam_agirlik,
 "Katman": d.katman,
 })

 detay_df = pd.DataFrame(detay_rows) if detay_rows else pd.DataFrame()

 # Özet DataFrame
 ozet_rows = []
 for cap, ozet in sorted(rapor["cap_ozeti"].items()):
 ozet_rows.append({
 "Çap (Ø)": f"Ø{cap}",
 "Adet": ozet["adet"],
 "Toplam Boy (m)": ozet["boy_m"],
 "Birim Ağırlık (kg/m)": ozet["birim_agirlik"],
 "Toplam Ağırlık (kg)": ozet["agirlik_kg"],
 })

 # Genel toplam satırı
 if ozet_rows:
 ozet_rows.append({
 "Çap (Ø)": "TOPLAM",
 "Adet": rapor["toplam_adet"],
 "Toplam Boy (m)": rapor["toplam_boy_m"],
 "Birim Ağırlık (kg/m)": "-",
 "Toplam Ağırlık (kg)": rapor["toplam_agirlik_kg"],
 })

 ozet_df = pd.DataFrame(ozet_rows) if ozet_rows else pd.DataFrame()

 return detay_df, ozet_df

 def calculate_vertical_rebar_unified(self, birim: str = "cm") -> Dict[str, Any]:
 """
 Birleşik Düşey Eleman (Kolon/Perde) Demir Hesaplama.

 Akıllı Tekil/Grup Ayrımı ve Perde "2x" formatı desteği ile çalışır.
 Program seçilen verilere bakarak modu otomatik belirler.

 Metin Sınıflandırma:
 - BAŞLIK: "SB17", "PB055", "KOLON DETAY", "PERDE DETAY" gibi
 - LİSTE: Virgülle ayrılmış benzerler ("SB24,SB31,SB39...")
 - VERİ: Demir bilgisi ("28Ø14 L=442" veya "2x8Ø12 L=420")

 Mod Belirleme:
 - LİSTE varsa → GRUP modu (Başlık + Liste elemanları)
 - LİSTE yoksa, BAŞLIK varsa → TEKİL modu (Tek perde/kolon)

 Perde "2x" Matematiği:
 - "2x8Ø12 L=420" → 2 * 8 = 16 adet Ø12 demir

 Args:
 birim: Boy birimi ("cm" veya "m")

 Returns:
 Dict: Hesaplama sonuçları, mod bilgisi ve DemirBilgisi listesi
 """
 import re

 sonuc = {
 "basarili": False,
 "hata": None,
 "mod": None, # "GRUP" veya "TEKİL"
 "tip": None, # "KOLON" veya "PERDE"
 "baslik": None,
 "elemanlar": [],
 "donatilar": [], # Birden fazla donatı satırı olabilir
 "demirler": [], # DemirBilgisi listesi (UI'a aktarılacak)
 "ozet": {}
 }

 try:
 import pandas as pd
 except ImportError:
 sonuc["hata"] = "pandas yüklü değil"
 return sonuc

 # Bağlantı kontrolü
 if not self.bagli:
 self.baglan()

 print("\n" + "="*60)
 print(" DÜŞEY ELEMAN DEMİR HESAPLAMA (Kolon/Perde)")
 print("="*60)
 print("\n AutoCAD'de metinleri seçin:")
 print(" • BAŞLIK: Eleman adı (SB17, PB055, vb.)")
 print(" • LİSTE (opsiyonel): Benzerler (SB24,SB31,...)")
 print(" • DONATI: Demir bilgisi (28Ø14 L=442 veya 2x8Ø12 L=420)")
 print("-"*60)

 # AutoCAD'i aktif hale getir
 try:
 # 1. Visible ayarla
 self.acad_app.Visible = True
 time.sleep(0.2)

 # 2. WindowState ayarla
 try:
 self.acad_app.WindowState = 3 # Maximize
 except:
 pass
 time.sleep(0.2)

 # 3. Çizimi aktifleştir
 try:
 self.aktif_cizim.Activate()
 except:
 pass
 time.sleep(0.2)

 # 4. REGEN komutu gönder (AutoCAD'i zorla aktifleştirir)
 try:
 self.aktif_cizim.SendCommand("REGEN\n")
 except:
 pass
 time.sleep(0.5)

 # 5. win32gui ile öne getir
 self._autocad_one_getir()
 time.sleep(0.3)

 except Exception as e:
 logger.warning(f"AutoCAD aktifleştirme hatası: {e}")

 print(" AutoCAD'e geçiliyor...")
 time.sleep(0.5) # _autocad_one_getir() zaten ~1.3sn bekliyor

 # Selection Set oluştur
 ss_name = f"DuseyEleman_{int(time.time())}"
 try:
 ss = self.aktif_cizim.SelectionSets.Add(ss_name)
 except:
 try:
 ss = self.aktif_cizim.SelectionSets.Item(ss_name)
 ss.Clear()
 except:
 ss = self.aktif_cizim.SelectionSets.Add(f"DuseyEleman_{id(self)}")

 try:
 # Kullanıcı seçimi - invisible hatasına karşı korumalı
 self._guvenli_select_on_screen(ss)
 secim_sayisi = ss.Count
 print(f"\n>>> {secim_sayisi} obje seçildi")

 if secim_sayisi == 0:
 sonuc["hata"] = "Hiç obje seçilmedi"
 return sonuc

 # Metin objelerini SEÇİM SIRASINA göre topla + entity ref kaydet
 metinler = []
 metin_entityleri = [] # Renklendirme için entity referansları
 for i in range(ss.Count):
 entity = ss.Item(i)
 props = self._read_entity_props(entity)
 if props is None:
 continue
 if props['object_name'] in ["AcDbText", "AcDbMText"]:
 text = props['text']
 if text is None:
 logger.debug(f"Metin okunamadı (index: {i}), atlanıyor")
 continue
 text = text.strip()
 # MText özel karakterlerini temizle
 temiz = re.sub(r'\\[A-Za-z];?|\\P|[{}]', '', text).strip()
 if temiz:
 metinler.append(temiz)
 metin_entityleri.append(props['entity'])

 if len(metinler) == 0:
 sonuc["hata"] = "Seçimde metin objesi bulunamadı"
 return sonuc

 print(f"\n Seçilen metinler (SIRASINA GÖRE):")
 for i, m in enumerate(metinler, 1):
 print(f" {i}. \"{m}\"")

 # ════════════════════════════════════════════════════════════
 # 1. SEÇİM SIRASINA GÖRE GRUPLAMA
 # ════════════════════════════════════════════════════════════
 # Mantık: Kullanıcı sırayla seçer:
 # 1. Eleman adı (PB055, SB01, veya "SB15 KOLON DETAYI")
 # 2. [Opsiyonel] Benzerler listesi (SB16,SB18,SB19...)
 # 3. Donatı(lar) (28Ø14 L=442)
 # 4. Sonraki eleman adı... (döngü devam eder)

 # === REGEX KALIPLARI ===
 eleman_pattern = re.compile(r'(S[BK]|P[BK])\s*(\d+)', re.IGNORECASE)
 detayi_pattern = re.compile(r'(KOLON|PERDE)\s*DETAYI', re.IGNORECASE)
 veri_pattern = re.compile(
 r'(?:(\d+)\s*[xX*]\s*)?(\d+)\s*[ØøƒφΦ∅]\s*(\d+).*?[Ll]\s*=\s*(\d+(?:[.,]\d+)?)',
 re.IGNORECASE
 )
 veri_pattern_autocad = re.compile(
 r'(?:(\d+)\s*[xX*]\s*)?(\d+)\s*%%[cC]\s*(\d+).*?[Ll]\s*=\s*(\d+(?:[.,]\d+)?)',
 re.IGNORECASE
 )

 # === GRUPLARI OLUŞTUR ===
 gruplar = [] # Her grup: {"lider": str, "benzerler": [], "donatilar": [], "tip": str, "mod": str}
 aktif_grup = None

 print(f"\n SEÇİM SIRASINA GÖRE GRUPLAMA:")
 print(f" ─────────────────────────────────")

 for i, metin in enumerate(metinler, 1):
 # Metin tipi belirleme
 is_donati = veri_pattern.search(metin) or veri_pattern_autocad.search(metin)
 is_detayi = detayi_pattern.search(metin)
 is_liste = ',' in metin and eleman_pattern.search(metin)
 is_eleman = eleman_pattern.search(metin) and not is_liste

 if is_donati:
 # DONATI → Aktif gruba ekle
 if aktif_grup:
 aktif_grup["donatilar"].append(metin)
 print(f" {i}. DONATI → {aktif_grup['lider']}'e eklendi: \"{metin[:35]}...\"")
 else:
 print(f" {i}. DONATI (grup yok, atlandı): \"{metin[:35]}\"")

 elif is_detayi or is_eleman:
 # YENİ ELEMAN ADI → Yeni grup başlat
 match = eleman_pattern.search(metin)
 if match:
 eleman_adi = f"{match.group(1).upper()}{match.group(2)}"

 # Tip belirleme
 if eleman_adi.startswith('PB') or eleman_adi.startswith('PK') or 'PERDE' in metin.upper():
 tip = "PERDE"
 else:
 tip = "KOLON"

 # Mod belirleme
 mod = "GRUP" if is_detayi else "TEKİL"

 # Yeni grup oluştur
 aktif_grup = {
 "lider": eleman_adi,
 "benzerler": [],
 "donatilar": [],
 "tip": tip,
 "mod": mod
 }
 gruplar.append(aktif_grup)

 if is_detayi:
 print(f" {i}. YENİ GRUP: {eleman_adi} ({tip} - DETAYI var)")
 else:
 print(f" {i}. YENİ TEKİL: {eleman_adi} ({tip})")

 elif is_liste:
 # LİSTE → Aktif gruba benzerler ekle
 if aktif_grup:
 parcalar = metin.split(',')
 eklenen = 0
 for parca in parcalar:
 match = eleman_pattern.search(parca.strip())
 if match:
 eleman_adi = f"{match.group(1).upper()}{match.group(2)}"
 if eleman_adi != aktif_grup["lider"] and eleman_adi not in aktif_grup["benzerler"]:
 aktif_grup["benzerler"].append(eleman_adi)
 eklenen += 1
 aktif_grup["mod"] = "GRUP" # Liste varsa grup moduna geç
 print(f" {i}. LİSTE → {aktif_grup['lider']}'e {eklenen} benzer eklendi")
 else:
 print(f" {i}. LİSTE (grup yok, atlandı)")

 else:
 print(f" {i}. TANINAMADI: \"{metin[:40]}\"")

 # === GRUP KONTROLÜ ===
 if not gruplar:
 sonuc["hata"] = "Hiç eleman grubu oluşturulamadı!\nLütfen önce eleman adı (SB15, PB055) seçin."
 return sonuc

 # Donatısız grupları kontrol et
 bos_gruplar = [g["lider"] for g in gruplar if not g["donatilar"]]
 if bos_gruplar:
 print(f"\n Donatısız elemanlar: {bos_gruplar}")

 print(f"\n TOPLAM: {len(gruplar)} eleman/grup oluşturuldu")

 # ════════════════════════════════════════════════════════════
 # 2. SONUÇ YAPISI GÜNCELLE
 # ════════════════════════════════════════════════════════════
 sonuc["gruplar"] = gruplar
 sonuc["mod"] = "ÇOKLU" if len(gruplar) > 1 else gruplar[0]["mod"]

 # İlk grup bilgilerini ana sonuca yaz (geriye uyumluluk)
 ilk_grup = gruplar[0]
 tum_elemanlar = [ilk_grup["lider"]] + ilk_grup["benzerler"]
 eleman_tipi = ilk_grup["tip"]

 # ════════════════════════════════════════════════════════════
 # 3. HER GRUP İÇİN DONATI PARSE VE HESAPLAMA
 # ════════════════════════════════════════════════════════════
 print(f"\n HESAPLAMA:")
 print(f" ─────────────────────────────────")

 demir_listesi = [] # DemirBilgisi nesneleri (tüm gruplardan)
 genel_toplam_adet = 0
 genel_toplam_boy = 0.0
 genel_toplam_agirlik = 0.0
 cap_ozeti = {} # Çap bazlı özet
 toplam_eleman_sayisi = 0

 for grup in gruplar:
 lider = grup["lider"]
 benzerler = grup["benzerler"]
 donatilar_raw = grup["donatilar"]
 tip = grup["tip"]

 # Gruptaki tüm elemanlar
 grup_elemanlari = [lider] + benzerler
 toplam_eleman_sayisi += len(grup_elemanlari)

 if not donatilar_raw:
 print(f" {lider}: Donatı yok, atlandı!")
 continue

 # Donatıları parse et
 grup_donatilari = []
 for veri in donatilar_raw:
 match = veri_pattern.search(veri)
 if not match:
 match = veri_pattern_autocad.search(veri)

 if match:
 carpan = int(match.group(1)) if match.group(1) else 1
 taban_adet = int(match.group(2))
 cap = int(match.group(3))
 boy_str = match.group(4).replace(',', '.')
 boy = float(boy_str)

 gercek_adet = carpan * taban_adet

 if birim.lower() == "cm":
 boy_m = boy / 100.0
 else:
 boy_m = boy

 agirlik_birim = DEMIR_AGIRLIK_TABLOSU.get(cap, 0.0)

 grup_donatilari.append({
 "orijinal": veri,
 "gercek_adet": gercek_adet,
 "cap": cap,
 "boy": boy,
 "boy_m": boy_m,
 "agirlik_birim": agirlik_birim
 })

 if not grup_donatilari:
 print(f" {lider}: Donatı parse edilemedi!")
 continue

 # Her eleman için her donatıyı hesapla
 for eleman_adi in grup_elemanlari:
 for donati in grup_donatilari:
 toplam_boy = donati["gercek_adet"] * donati["boy_m"]
 toplam_agirlik = toplam_boy * donati["agirlik_birim"]

 demir = DemirBilgisi(
 handle=f"{eleman_adi}_{donati['cap']}",
 orijinal_metin=f"{eleman_adi}: {donati['orijinal']}",
 adet=donati["gercek_adet"],
 cap=donati["cap"],
 boy=donati["boy"],
 toplam_boy=toplam_boy,
 agirlik_birim=donati["agirlik_birim"],
 toplam_agirlik=toplam_agirlik,
 katman=f"{tip}_{eleman_adi}",
 gecerli=True
 )
 demir_listesi.append(demir)

 genel_toplam_adet += donati["gercek_adet"]
 genel_toplam_boy += toplam_boy
 genel_toplam_agirlik += toplam_agirlik

 cap = donati["cap"]
 if cap not in cap_ozeti:
 cap_ozeti[cap] = {"adet": 0, "boy_m": 0.0, "agirlik_kg": 0.0}
 cap_ozeti[cap]["adet"] += donati["gercek_adet"]
 cap_ozeti[cap]["boy_m"] += toplam_boy
 cap_ozeti[cap]["agirlik_kg"] += toplam_agirlik

 print(f" {lider}: {len(grup_elemanlari)} eleman × {len(grup_donatilari)} donatı")

 if not demir_listesi:
 sonuc["hata"] = "Hiç demir hesaplanamadı! Donatı bilgisi eksik olabilir."
 return sonuc

 sonuc["demirler"] = demir_listesi
 sonuc["baslik"] = gruplar[0]["lider"]
 sonuc["tip"] = gruplar[0]["tip"]
 sonuc["elemanlar"] = [g["lider"] for g in gruplar]

 # Çubuk adetleri
 for cap in cap_ozeti:
 cap_ozeti[cap]["cubuk_adet"] = math.ceil(cap_ozeti[cap]["boy_m"] / 12.0)

 genel_cubuk = math.ceil(genel_toplam_boy / 12.0)

 sonuc["ozet"] = {
 "mod": sonuc["mod"],
 "grup_sayisi": len(gruplar),
 "eleman_sayisi": toplam_eleman_sayisi,
 "toplam_adet": genel_toplam_adet,
 "toplam_boy_m": genel_toplam_boy,
 "toplam_agirlik_kg": genel_toplam_agirlik,
 "toplam_agirlik_ton": genel_toplam_agirlik / 1000,
 "cubuk_adet": genel_cubuk,
 "cap_ozeti": cap_ozeti
 }

 sonuc["basarili"] = True

 # ════════════════════════════════════════════════════════════
 # SONUÇ RAPORU
 # ════════════════════════════════════════════════════════════
 print(f"\n{'='*60}")
 print(f" DEMİR METRAJ RAPORU ({sonuc['mod']} MOD)")
 print(f"{'='*60}")
 print(f" Grup Sayısı : {len(gruplar)}")
 print(f" Toplam Eleman : {toplam_eleman_sayisi} adet")

 # Grup detayları
 print(f"\n GRUP DETAYLARI:")
 for i, grup in enumerate(gruplar, 1):
 eleman_sayisi = 1 + len(grup["benzerler"])
 donati_sayisi = len(grup["donatilar"])
 mod_str = "GRUP" if grup["benzerler"] else "TEKİL"
 print(f" {i}. {grup['lider']} ({grup['tip']}) - {mod_str}")
 print(f" Eleman: {eleman_sayisi}, Donatı: {donati_sayisi}")

 print(f"\n ─────────────────────────────────")
 print(f" Toplam Demir Adedi : {genel_toplam_adet:,}")
 print(f" Toplam Boy : {genel_toplam_boy:,.2f} m")
 print(f" Toplam Ağırlık : {genel_toplam_agirlik:,.2f} kg")
 print(f" : {genel_toplam_agirlik/1000:,.3f} ton")
 print(f" ─────────────────────────────────")

 # Çap bazlı dağılım
 print(f"\n ÇAP BAZLI DAĞILIM:")
 print(f" {'Çap':<6} {'Adet':>8} {'Boy(m)':>10} {'Ağırlık(kg)':>12} {'Çubuk':>8}")
 print(f" {'-'*50}")
 for cap in sorted(cap_ozeti.keys()):
 ozet = cap_ozeti[cap]
 print(f" Ø{cap:<4} {ozet['adet']:>8,} {ozet['boy_m']:>10,.2f} {ozet['agirlik_kg']:>12,.2f} {ozet['cubuk_adet']:>8,}")

 print(f"\n TOPLAM ÇUBUK : {genel_cubuk:,} çubuk")
 print(f"{'='*60}\n")

 # Kayıtlı metin entity'lerini yeşile boya (tekrar tarama yok)
 for entity in metin_entityleri:
 try:
 self._objeyi_renklendir(entity, AcadColor.GREEN)
 except Exception:
 pass

 self.aktif_cizim.Regen(1)

 return sonuc

 except com_error as e:
 if "canceled" in str(e).lower() or "esc" in str(e).lower():
 print(">>> Seçim iptal edildi (ESC).")
 sonuc["hata"] = "Seçim iptal edildi"
 return sonuc
 logger.error(f"Düşey eleman seçim hatası: {e}")
 sonuc["hata"] = str(e)
 return sonuc
 except Exception as e:
 logger.error(f"Düşey eleman hesaplama hatası: {e}")
 sonuc["hata"] = str(e)
 return sonuc
 finally:
 # Selection set temizle
 try:
 ss.Delete()
 except:
 pass

 # Geriye uyumluluk için eski fonksiyon adını koru
 def calculate_all_grouped_columns(self, birim: str = "cm") -> Dict[str, Any]:
 """Geriye uyumluluk için - yeni fonksiyona yönlendir."""
 return self.calculate_vertical_rebar_unified(birim=birim)

 # ========================================================================
 # LISP MOTOR METODLARI
 # ========================================================================

 def lisp_calistir(self, lsp_dosya_adi: str, bekle: float = 0.5) -> bool:
 """
 Bir LISP dosyasını AutoCAD'e yükler ve komutunu çalıştırır.

 Akış:
 1. APPLOAD komutuyla .lsp dosyasını yükle
 2. LISP komut adını (dosya adından türet) çalıştır
 3. bekle sn sonra lisp_sonuc_oku() ile sonucu al

 Args:
 lsp_dosya_adi: .lsp dosyasının tam yolu (örn. "C:/...duvar_alan.lsp")
 bekle: Komut sonrası bekleme süresi (saniye)

 Returns:
 True: komut gönderildi, False: bağlantı yok
 """
 if not self.bagli:
 logger.warning("AutoCAD bağlantısı yok — LISP çalıştırılamadı.")
 return False

 try:
 # LISP komut adını dosya adından çıkar: "duvar_alan.lsp" → "DUVAR-ALAN"
 import os
 base = os.path.splitext(os.path.basename(lsp_dosya_adi))[0]
 komut_adi = "c:" + base.replace("_", "-").upper()

 # Yolu AutoCAD için düzelt (ters eğik çizgi + tırnak)
 lsp_yolu_acad = lsp_dosya_adi.replace("\\", "/")

 # 1) APPLOAD ile yükle
 appload_cmd = f'(load "{lsp_yolu_acad}")\n'
 self.aktif_cizim.SendCommand(appload_cmd)
 time.sleep(0.2)

 # 2) Komutu çalıştır
 self.aktif_cizim.SendCommand(komut_adi + "\n")
 time.sleep(bekle)

 logger.info(f"LISP çalıştırıldı: {komut_adi}")
 return True

 except Exception as e:
 logger.error(f"LISP çalıştırma hatası: {e}")
 return False

 def lisp_sonuc_oku(self) -> Dict[str, Any]:
 """
 %TEMP%\\imp_metraj.txt dosyasından LISP sonucunu okur.

 LISP rutinleri bu dosyaya JSON yazar.
 Python burada okur, parse eder ve döndürür.

 Returns:
 dict: Parse edilmiş sonuç (hata durumunda {"hata": "..."})
 """
 import os
 import json as _json

 sonuc_yolu = os.path.join(os.environ.get("TEMP", ""), "imp_metraj.txt")
 if not os.path.exists(sonuc_yolu):
 return {"hata": "Sonuç dosyası bulunamadı — LISP henüz çalışmadı mı?"}

 try:
 with open(sonuc_yolu, "r", encoding="utf-8") as f:
 icerik = f.read().strip()
 return self._parse_lisp_sonuc(icerik)
 except Exception as e:
 logger.error(f"LISP sonuç okuma hatası: {e}")
 return {"hata": str(e)}

 def _parse_lisp_sonuc(self, json_str: str) -> Dict[str, Any]:
 """
 LISP'in yazdığı JSON string'ini parse eder.
 AutoLISP'in rtos() fonksiyonu ondalık ayracı olarak nokta kullanır,
 bu yüzden direkt json.loads() çalışır.

 Args:
 json_str: LISP'ten gelen JSON string

 Returns:
 dict: Parse edilmiş veri
 """
 import json as _json
 try:
 return _json.loads(json_str)
 except _json.JSONDecodeError as e:
 logger.warning(f"JSON parse hatası: {e} | İçerik: {json_str[:200]}")
 return {"hata": f"JSON parse hatası: {e}", "ham": json_str}

 def katman_degisken_set(self, katman_dict: Dict[str, str]) -> None:
 """
 LISP global katman değişkenlerini AutoCAD'de ayarlar.

 Katman adları Python'dan LISP'e geçirilir, böylece LISP
 kendi varsayılanları yerine projeye özel isimleri kullanır.

 Örnek kullanım:
 connector.katman_degisken_set({
 "*IMP_KATMAN_DUVAR*": "DUVAR-BETON",
 "*IMP_KATMAN_KAPI*": "A-DOOR",
 })

 Args:
 katman_dict: {lisp_değişken_adı: katman_adı} sözlüğü
 """
 if not self.bagli:
 return

 for degisken, deger in katman_dict.items():
 try:
 # AutoLISP: (setq *IMP_KATMAN_DUVAR* "DUVAR")
 lisp_expr = f'(setq {degisken} "{deger}")\n'
 self.aktif_cizim.SendCommand(lisp_expr)
 logger.debug(f"Katman değişkeni ayarlandı: {degisken} = {deger}")
 except Exception as e:
 logger.warning(f"Katman değişkeni ayarlanamadı ({degisken}): {e}")

 def lisp_tam_calistir(
 self,
 lsp_dosya_adi: str,
 katman_dict: Optional[Dict[str, str]] = None,
 bekle: float = 1.0,
 ) -> Dict[str, Any]:
 """
 Katman değişkenlerini set et → LISP yükle/çalıştır → sonucu oku.
 Tek adımda tüm akışı yönetir.

 Args:
 lsp_dosya_adi: .lsp dosyasının tam yolu
 katman_dict: Opsiyonel katman override dict'i
 bekle: LISP tamamlanması için bekleme süresi (sn)

 Returns:
 dict: LISP sonucu veya hata dict'i
 """
 if not self.bagli:
 return {"hata": "AutoCAD bağlantısı yok"}

 if katman_dict:
 self.katman_degisken_set(katman_dict)
 time.sleep(0.1)

 basarili = self.lisp_calistir(lsp_dosya_adi, bekle=bekle)
 if not basarili:
 return {"hata": "LISP çalıştırılamadı"}

 return self.lisp_sonuc_oku()


# ============================================================================
# TEST / DEMO FONKSIYONU
# ============================================================================

def demo_autocad_baglantisi():
 """AutoCAD bağlantısını test et ve demo çalıştır."""

 print("\n" + "="*60)
 print(" AutoCAD Canlı Bağlantı Demo")
 print("="*60 + "\n")

 try:
 # Connector oluştur
 connector = AutoCADConnector()

 # Bağlan
 connector.baglan()

 # Katman listesi
 katmanlar = connector.katman_listesi_al()
 print(f"Katmanlar ({len(katmanlar)} adet):")
 for k in katmanlar[:10]: # İlk 10 katman
 print(f" - {k}")
 if len(katmanlar) > 10:
 print(f" ... ve {len(katmanlar) - 10} katman daha")

 # Blok listesi
 bloklar = connector.blok_listesi_al()
 print(f"\nBloklar ({len(bloklar)} adet):")
 for b in bloklar[:10]:
 print(f" - {b}")
 if len(bloklar) > 10:
 print(f" ... ve {len(bloklar) - 10} blok daha")

 # Kullanıcı seçimi
 print("\n" + "-"*40)
 objeler = connector.kullanici_secimi_al("Demo için obje seçin")

 # Sonuçları göster
 if objeler:
 print("\nSeçilen Objeler:")
 print("-"*40)
 for i, obj in enumerate(objeler, 1):
 print(f"\n{i}. {obj.entity_type}")
 print(f" Katman: {obj.layer}")
 if obj.uzunluk > 0:
 print(f" Uzunluk: {obj.uzunluk:.2f}")
 if obj.alan > 0:
 print(f" Alan: {obj.alan:.2f}")
 if obj.blok_adi:
 print(f" Blok Adı: {obj.blok_adi}")
 if obj.text_icerigi:
 print(f" Metin: {obj.text_icerigi}")

 # Renkleri geri al
 input("\n>>> Renkleri geri almak için ENTER'a basın...")
 connector.renkleri_geri_al()

 # Bağlantıyı kes
 connector.baglantıyi_kes()

 print("\nDemo tamamlandı!")

 except ImportError as e:
 print(f"HATA: {e}")
 except ConnectionError as e:
 print(f"BAĞLANTI HATASI: {e}")
 except Exception as e:
 print(f"HATA: {e}")
 import traceback
 traceback.print_exc()


if __name__ == "__main__":
 demo_autocad_baglantisi()
