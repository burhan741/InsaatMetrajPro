"""COM mesaj filtresi (IMessageFilter) — AutoCAD "meşgul" reddini COM katmanında yeniden dener.

Neyi çözüyoruz?
AutoCAD kullanıcı girdisi (GetPoint vb.) bittikten hemen sonra ya da ekranı
yeniden çizerken gelen çağrıları RPC_E_CALL_REJECTED (0x80010001, "Arama aranan
tarafından kabul edilmedi") ile reddeder. Mesaj filtresi kayıtlı değilse COM
bu hatayı doğrudan çağırana fırlatır. Filtre kayıtlıysa COM, RetryRejectedCall'ın
döndürdüğü süre kadar bekleyip çağrıyı KENDİSİ tekrarlar.

pywin32 CoRegisterMessageFilter'ı sunmadığı için (pythoncom'da yok — 2026-09-27
iki Python ortamında da doğrulandı) arayüz ctypes ile, elle kurulmuş bir vtable
üzerinden ole32.CoRegisterMessageFilter'a verilir.

KURAL: Filtre, COM çağrılarının yapıldığı AYNI thread'de (STA) kaydedilmelidir.
Kayıt thread başına bir kez yapılır; tekrar çağrı zararsızdır.

Nasıl test ederiz? scratchpad/test_com_filtre.py (programsız) — kayıt HRESULT'u,
QueryInterface, RetryRejectedCall dönüş değerleri ve log satırı doğrudan
vtable üzerinden çağrılarak doğrulanır.
"""

import ctypes
import logging
import threading
from contextlib import contextmanager
from ctypes import POINTER, WINFUNCTYPE, Structure, byref, c_long, c_ubyte, c_ulong, c_ushort, c_void_p

logger = logging.getLogger(__name__)

SERVERCALL_ISHANDLED = 0
SERVERCALL_RETRYLATER = 2
PENDINGMSG_WAITDEFPROCESS = 2
YENIDEN_DENEME_MS = 150           # reddedilen çağrıyı bu kadar sonra tekrar dene
AZAMI_BEKLEME_MS = 30000          # bu süreden sonra vazgeç (çağıran hatayı alır)
VAZGEC = 0xFFFFFFFF               # RetryRejectedCall: -1 = iptal et
S_OK = 0
E_NOINTERFACE = -2147467262


class GUID(Structure):
    _fields_ = [("Data1", c_ulong), ("Data2", c_ushort), ("Data3", c_ushort), ("Data4", c_ubyte * 8)]


def _guid(d1: int, d4_son: int = 0x46) -> GUID:
    """{d1-0000-0000-C000-000000000046} biçimindeki standart OLE arayüz kimlikleri."""
    return GUID(d1, 0, 0, (c_ubyte * 8)(0xC0, 0, 0, 0, 0, 0, 0, d4_son))


IID_IUnknown = _guid(0x00000000)
IID_IMessageFilter = _guid(0x00000016)

_QI = WINFUNCTYPE(c_long, c_void_p, POINTER(GUID), POINTER(c_void_p))
_REF = WINFUNCTYPE(c_ulong, c_void_p)
_HANDLE_IN = WINFUNCTYPE(c_ulong, c_void_p, c_ulong, c_void_p, c_ulong, c_void_p)
_RETRY = WINFUNCTYPE(c_ulong, c_void_p, c_void_p, c_ulong, c_ulong)
_PENDING = WINFUNCTYPE(c_ulong, c_void_p, c_void_p, c_ulong, c_ulong)


class _VTBL(Structure):
    _fields_ = [("QueryInterface", _QI), ("AddRef", _REF), ("Release", _REF),
                ("HandleInComingCall", _HANDLE_IN), ("RetryRejectedCall", _RETRY),
                ("MessagePending", _PENDING)]


class _NESNE(Structure):
    _fields_ = [("lpVtbl", POINTER(_VTBL))]


def _ayni_guid(a: GUID, b: GUID) -> bool:
    return bytes(a) == bytes(b)


def _query_interface(this, riid, ppv):
    try:
        if _ayni_guid(riid.contents, IID_IUnknown) or _ayni_guid(riid.contents, IID_IMessageFilter):
            ppv[0] = this
            return S_OK
        ppv[0] = None
    except Exception:
        pass
    return E_NOINTERFACE


def _add_ref(this):
    return 1  # nesne modül ömrü boyunca yaşar (global referans), sayım gerekmez


def _handle_in_coming_call(this, call_type, htask, tick, info):
    return SERVERCALL_ISHANDLED


# Rev-156: azami bekleme geçici olarak kısaltılabilir (bağlanırken 3 sn — AutoCAD'de açık
# iletişim kutusu varsa 30 sn × retry döngüleri programı dakikalarca donduruyordu).
_azami_ms = AZAMI_BEKLEME_MS
_vazgecme_sayaci = 0


def vazgecme_sayisi() -> int:
    """Filtrenin bugüne kadar kaç çağrıdan vazgeçtiği — çağıran 'meşgul yüzünden mi düştü' anlar
    (pywin32 reddi AttributeError'a çevirebildiği için hata tipinden anlaşılamaz)."""
    return _vazgecme_sayaci


@contextmanager
def kisa_bekleme(azami_ms: int):
    """Blok içinde meşgul reddi en fazla azami_ms denenir."""
    global _azami_ms
    eski = _azami_ms
    _azami_ms = azami_ms
    try:
        yield
    finally:
        _azami_ms = eski


def retry_kararı(reddetme_tipi: int, gecen_ms: int) -> int:
    """Saf karar: meşgul (RETRYLATER) ise ve süre dolmadıysa bekleme ms, değilse vazgeç."""
    if reddetme_tipi == SERVERCALL_RETRYLATER and gecen_ms < _azami_ms:
        return YENIDEN_DENEME_MS
    return VAZGEC


def _retry_rejected_call(this, htask, tick, reject_type):
    global _vazgecme_sayaci
    try:
        karar = retry_kararı(int(reject_type), int(tick))
        if karar == VAZGEC:
            _vazgecme_sayaci += 1
            logger.warning(f"[COM_FILTRE] reddedildi, VAZGEÇİLDİ (tip={reject_type}, geçen={tick} ms)")
        else:
            logger.warning(f"[COM_FILTRE] reddedildi, yeniden deneniyor (tip={reject_type}, geçen={tick} ms)")
        return karar
    except Exception:
        return VAZGEC


def _message_pending(this, htask, tick, pending_type):
    return PENDINGMSG_WAITDEFPROCESS


# Geri çağrılar ve nesne modül seviyesinde tutulur — GC toplarsa COM çöken
# bir işaretçiye atlar.
_VTABLE = _VTBL(_QI(_query_interface), _REF(_add_ref), _REF(_add_ref),
                _HANDLE_IN(_handle_in_coming_call), _RETRY(_retry_rejected_call),
                _PENDING(_message_pending))
_FILTRE = _NESNE(ctypes.pointer(_VTABLE))
_KAYITLI_THREADLER = set()
_KILIT = threading.Lock()


def mesaj_filtresi_kaydet() -> bool:
    """Çağıran thread için filtreyi kaydeder (thread başına bir kez). True = kayıtlı."""
    tid = threading.get_ident()
    with _KILIT:
        if tid in _KAYITLI_THREADLER:
            return True
        try:
            eski = c_void_p()
            hr = ctypes.windll.ole32.CoRegisterMessageFilter(byref(_FILTRE), byref(eski))
        except Exception as e:
            logger.error(f"[COM_FILTRE] kaydedilemedi: {e}", exc_info=True)
            return False
        ad = threading.current_thread().name
        if hr != S_OK:
            # CO_E_NOT_SUPPORTED vb.: thread STA değil — filtre çalışmaz
            logger.error(f"[COM_FILTRE] kaydedilemedi HRESULT=0x{hr & 0xFFFFFFFF:08X} (thread {ad}, {tid}) "
                         "— thread STA olmayabilir")
            return False
        _KAYITLI_THREADLER.add(tid)
        logger.info(f"[COM_FILTRE] kaydedildi (thread {ad}, {tid})")
        return True


def vtable_nesnesi():
    """Test için: kayıtlı filtre nesnesinin işaretçisi."""
    return ctypes.addressof(_FILTRE), _VTABLE
