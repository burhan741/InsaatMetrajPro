"""Akıllı Metraj Analizi — proje kayıt / açma (Rev-168).

Neyi çözüyoruz?
    Kaba İnşaat ve demir metrajı kayıtları (kolon, perde, döşeme + saçak, kiriş,
    merdiven, SBH, radye, kat listesi, demirler, aralıklı donatı, elle Beton & Kalıp
    satırları, kat ayarları) sadece bellekteydi: program kapanınca / PC çökünce
    kayboluyordu ve hiçbir yedeğe giremiyordu. Bu modül o durumu JSON dosyasına
    yazar / geri okur. Dosyalar veri klasöründe (data/metraj_projeleri/) durur →
    yedekle.ps1 onları OneDrive zip'ine otomatik katar.

    JSON'un taşıyamadığı yapılar kayıpsız çevrilir:
      tuple anahtarlı / int anahtarlı sözlük -> {"__dk__": [[anahtar, değer], ...]}
      tuple                                   -> {"__t__": [...]}
      dataclass (DemirBilgisi, KatYukseklikAyari) -> {"__dc__": ad, "v": {...}}
    Yazma ATOMİKTİR (geçici dosya + os.replace): yazarken elektrik kesilse bile
    eski dosya bozulmaz; bir önceki sürüm ayrıca ".onceki.json" olarak tutulur.

Nasıl test ederiz?
    scratchpad/test_metraj_proje_kayit.py — gidiş-dönüş (serileştir -> çöz) birebir
    aynı nesneleri vermeli; pencere üzerinde kaydet -> yeni pencere -> aç sonrası
    tablolar ve Kat Özeti aynı olmalı.
"""
import dataclasses
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional

SURUM = 1
OTOMATIK_AD = "_otomatik_kayit"


def metraj_kayit_klasoru() -> Path:
    """data/metraj_projeleri — EXE modunda QUANTIX_DATA_DIR (AppData) altında."""
    kok = os.environ.get("QUANTIX_DATA_DIR") or str(Path(__file__).resolve().parents[2] / "data")
    yol = Path(kok) / "metraj_projeleri"
    yol.mkdir(parents=True, exist_ok=True)
    return yol


def guvenli_dosya_adi(ad: str) -> str:
    """Proje adından Windows'ta geçerli dosya adı ("Yurt / A Blok" -> "Yurt - A Blok")."""
    temiz = re.sub(r'[\\/:*?"<>|]+', " - ", (ad or "").strip())
    temiz = re.sub(r"\s+", " ", temiz).strip(" .-")
    return temiz[:80] or "Isimsiz Proje"


def proje_dosyasi(proje_adi: str) -> Path:
    return metraj_kayit_klasoru() / f"{guvenli_dosya_adi(proje_adi)}.json"


# ── kayıpsız JSON çevirimi ──
def serilestir(o: Any) -> Any:
    if dataclasses.is_dataclass(o) and not isinstance(o, type):
        return {"__dc__": type(o).__name__,
                "v": {f.name: serilestir(getattr(o, f.name)) for f in dataclasses.fields(o)}}
    if isinstance(o, dict):
        if all(isinstance(k, str) for k in o):
            return {k: serilestir(v) for k, v in o.items()}
        return {"__dk__": [[serilestir(k), serilestir(v)] for k, v in o.items()]}
    if isinstance(o, tuple):
        return {"__t__": [serilestir(x) for x in o]}
    if isinstance(o, (list, set)):
        return [serilestir(x) for x in o]
    if isinstance(o, (str, int, float, bool)) or o is None:
        return o
    return str(o)   # bilinmeyen nesne (ör. COM) — metin olarak, kayıt bozulmasın


def coz(o: Any, siniflar: Optional[Dict[str, Callable]] = None) -> Any:
    siniflar = siniflar or {}
    if isinstance(o, list):
        return [coz(x, siniflar) for x in o]
    if isinstance(o, dict):
        if "__t__" in o and len(o) == 1:
            return tuple(coz(x, siniflar) for x in o["__t__"])
        if "__dk__" in o and len(o) == 1:
            return {_anahtar(coz(k, siniflar)): coz(v, siniflar) for k, v in o["__dk__"]}
        if "__dc__" in o and "v" in o:
            alanlar = {k: coz(v, siniflar) for k, v in o["v"].items()}
            sinif = siniflar.get(o["__dc__"])
            if sinif is None:
                return alanlar
            gecerli = {f.name for f in dataclasses.fields(sinif)}
            return sinif(**{k: v for k, v in alanlar.items() if k in gecerli})
        return {k: coz(v, siniflar) for k, v in o.items()}
    return o


def _anahtar(k):
    return tuple(k) if isinstance(k, list) else k


def kaydet(yol: Path, durum: Dict[str, Any], proje_adi: str = "") -> Path:
    """Durumu atomik yazar; varsa eski dosya .onceki.json olur."""
    yol = Path(yol)
    yol.parent.mkdir(parents=True, exist_ok=True)
    veri = {"surum": SURUM, "proje_adi": proje_adi, "kayit_zamani": datetime.now().isoformat(timespec="seconds"),
            "durum": serilestir(durum)}
    gecici = yol.with_suffix(".tmp")
    with open(gecici, "w", encoding="utf-8") as f:
        json.dump(veri, f, ensure_ascii=False, indent=1)
        f.flush()
        os.fsync(f.fileno())
    if yol.exists():
        try:
            os.replace(yol, yol.with_name(yol.stem + ".onceki.json"))
        except OSError:
            pass
    os.replace(gecici, yol)
    return yol


def yukle(yol: Path, siniflar: Optional[Dict[str, Callable]] = None) -> Dict[str, Any]:
    """{"proje_adi", "kayit_zamani", "durum"} döner. Bozuksa .onceki.json denenir."""
    yol = Path(yol)
    for aday in (yol, yol.with_name(yol.stem + ".onceki.json")):
        try:
            with open(aday, encoding="utf-8") as f:
                veri = json.load(f)
            veri["durum"] = coz(veri.get("durum") or {}, siniflar)
            veri["yuklenen_dosya"] = str(aday)
            return veri
        except FileNotFoundError:
            continue
        except (ValueError, OSError):
            continue
    raise FileNotFoundError(f"Okunabilir kayıt yok: {yol}")


def durum_ozeti(durum: Dict[str, Any]) -> str:
    """Kullanıcıya: 'Kat: 3 | kolon 24, perde 6, döşeme 12 ...'"""
    def say(anahtar, ic=False):
        v = durum.get(anahtar) or {}
        if ic:
            return sum(len(x) for x in v.values())
        return len(v)
    parcalar = [f"Kat: {len(durum.get('demir_kat_verileri') or [])}"]
    for ad, anahtar, ic in (("kolon/perde", "beton_kalip_kolon_kayitlari", False), ("perde", "perde_kayitlari", False),
                            ("döşeme/saçak", "_doseme_kat_kayitlari", True), ("kiriş", "_kiris_kat_kayitlari", True),
                            ("merdiven", "_merdiven_kat_kayitlari", True), ("SBH", "temel_kirisi_kayitlari", False),
                            ("radye", "radye_kayitlari", False)):
        n = say(anahtar, ic)
        if n:
            parcalar.append(f"{ad} {n}")
    demir = sum(len(k.get("demirler") or []) for k in durum.get("demir_kat_verileri") or [])
    if demir:
        parcalar.append(f"demir {demir}")
    return " | ".join(parcalar)
