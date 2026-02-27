"""
Kaynak Dengeleme (Resource Leveling) Motoru
=============================================
Neyi çözer?
Aynı ekibin (kalıpçı, demirci vb.) birden fazla göreve aynı anda
atanması durumunu tespit eder ve bolluk payını kullanarak otomatik çözer.
MS Project'in "Level Resources" özelliğinin inşaat sektörüne özel versiyonu.

Algoritma:
1. Kaynak bazında görevleri grupla
2. Her gün için atanmış görev sayısını say
3. Kapasite aşımında: daha fazla bolluğu olan görevi kaydır
4. Bolluk yetmezse kritik yolu uzatma uyarısı ver

Test:
python -c "
from app.core.kaynak_dengeleme_engine import KaynakDengeleme, AtamaKayit
from datetime import datetime
d = KaynakDengeleme()
d.kapasite_tanimla('Kalıpçı Ekibi', 1, 3500)
d.atama_ekle(AtamaKayit(1,'T1','Kalıpçı Ekibi',datetime(2026,3,1),datetime(2026,3,8),5,2,False))
d.atama_ekle(AtamaKayit(2,'T2','Kalıpçı Ekibi',datetime(2026,3,3),datetime(2026,3,10),5,5,False))
c = d.cakismalari_bul()
assert len(c) > 0
r = d.otomatik_dengele()
print(f'Çakışma: {len(c)}, Çözüm: {len(r)} kaydırma')
"
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class AtamaKayit:
    """Tek görev-kaynak ataması."""
    gorev_id: int
    gorev_ad: str
    kaynak_ad: str
    baslangic: datetime
    bitis: datetime
    sure_gun: int
    bolluk_gun: int # CPM'den gelen toplam bolluk
    kritik: bool
    maliyet_gun_tl: float = 0.0


@dataclass
class CakismaKaydi:
    """Tespit edilen çakışma kaydı."""
    tarih: datetime
    kaynak_ad: str
    gorev_ids: List[int]
    gorev_adlar: List[str]
    kapasite_asim: int # Kaç birim fazla?
    cozum_onerildi: bool = False


@dataclass
class KaydirmaKaydi:
    """Otomatik kaydırma sonucu."""
    gorev_id: int
    gorev_ad: str
    kaynak_ad: str
    kaydi_gun: int
    eski_baslangic: datetime
    yeni_baslangic: datetime
    eski_bitis: datetime
    yeni_bitis: datetime
    sebep: str
    kritik_etki: bool = False # Proje süresi uzuyor mu?


@dataclass
class DengelemeRaporu:
    """Otomatik dengeleme özet raporu."""
    toplam_cakisma: int
    cozulen_cakisma: int
    cozulemeyen: int
    kaydirmalar: List[KaydirmaKaydi]
    kritik_uzama_gun: int # Proje süresi ne kadar uzadı?
    uyarilar: List[str]
    ozet_metin: str


class KaynakDengeleme:
    """
    Kaynak dengeleme motoru.

    Kullanım (GanttWindow içinden):
    dengele = KaynakDengeleme()

    # Kapasite tanımla
    dengele.kapasite_tanimla("Kalıpçı Ekibi", kapasite=1, maliyet_gun=3500)
    dengele.kapasite_tanimla("Demirci Ekibi", kapasite=1, maliyet_gun=4000)

    # GanttEngine.tasks'dan besle
    for task in engine.tasks.values():
    if task.early_start and task.early_finish:
    dengele.atama_ekle(AtamaKayit(
    gorev_id=task.task_id,
    gorev_ad=task.ad,
    kaynak_ad=task.kaynak,
    baslangic=task.early_start,
    bitis=task.early_finish,
    sure_gun=task.sure_gun,
    bolluk_gun=task.float_gun,
    kritik=task.kritik,
    ))

    # Çakışmaları bul ve çöz
    rapor = dengele.tam_dengele()
    print(rapor.ozet_metin)

    # GanttEngine'e geri besle
    for k in rapor.kaydirmalar:
    engine.tasks[k.gorev_id].early_start = k.yeni_baslangic
    engine.tasks[k.gorev_id].early_finish = k.yeni_bitis
    """

    def __init__(self):
        self.atamalar: List[AtamaKayit] = []
        self.kapasiteler: Dict[str, Dict] = {} # kaynak_ad → {kapasite, maliyet_gun}

        def kapasite_tanimla(
        self,
        kaynak_ad: str,
        kapasite: int = 1,
        maliyet_gun_tl: float = 0.0,
        ) -> None:
            """Kaynak kapasitesi tanımla (aynı anda kaç iş yapabilir)."""
        self.kapasiteler[kaynak_ad] = {
        "kapasite": kapasite,
        "maliyet_gun_tl": maliyet_gun_tl,
        }

        def atama_ekle(self, atama: AtamaKayit) -> None:
            """Görev ataması ekle."""
            if atama.kaynak_ad:
                self.atamalar.append(atama)
                # Henüz tanımlanmamışsa default kapasite 1
                if atama.kaynak_ad not in self.kapasiteler:
                    self.kapasiteler[atama.kaynak_ad] = {
                    "kapasite": 1, "maliyet_gun_tl": 0.0
                    }

                    def atamalari_temizle(self) -> None:
                        """GanttEngine yeniden hesaplandığında atamaları sıfırla."""
                        self.atamalar.clear()

                        # ── Ana metodlar ──────────────────────────────────────────────────────────

                        def cakismalari_bul(self) -> List[CakismaKaydi]:
                            """
                            Tüm çakışmaları tespit et.
                            Her çakışma: aynı kaynağın aynı günde kapasitenin üzerinde kullanımı.
                            """
                            cakismalar: List[CakismaKaydi] = []

                            # Kaynak bazında grupla
                            kaynak_gruplari: Dict[str, List[AtamaKayit]] = defaultdict(list)
                            for atama in self.atamalar:
                                kaynak_gruplari[atama.kaynak_ad].append(atama)

                                for kaynak_ad, grup in kaynak_gruplari.items():
                                    kapasite = self.kapasiteler.get(
                                    kaynak_ad, {"kapasite": 1}
                                    )["kapasite"]

                                    # Her gün için bu kaynağa atanmış görevleri say
                                    tarih_gorevler: Dict[str, List[AtamaKayit]] = defaultdict(list)
                                    for atama in grup:
                                        tarih = atama.baslangic
                                        while tarih <= atama.bitis:
                                            if tarih.weekday() < 5: # hafta içi
                                                tarih_gorevler[tarih.strftime("%Y-%m-%d")].append(atama)
                                            tarih += timedelta(days=1)

                                            # Kapasite aşımı olan günleri topla (ardışık günleri birleştirme)
                                            bildirildi = set()
                                            for tarih_str, gorevler in tarih_gorevler.items():
                                                if len(gorevler) > kapasite:
                                                    # Aynı çakışma grubunu tekrar bildirme
                                                    anahtar = frozenset(a.gorev_id for a in gorevler)
                                                    if anahtar not in bildirildi:
                                                        bildirildi.add(anahtar)
                                                        cakismalar.append(CakismaKaydi(
                                                        tarih=datetime.strptime(tarih_str, "%Y-%m-%d"),
                                                        kaynak_ad=kaynak_ad,
                                                        gorev_ids=[a.gorev_id for a in gorevler],
                                                        gorev_adlar=[a.gorev_ad for a in gorevler],
                                                        kapasite_asim=len(gorevler) - kapasite,
                                                        ))

                                                        return cakismalar

                                                        def otomatik_dengele(self) -> List[KaydirmaKaydi]:
                                                            """
                                                            Minimum gecikme prensibiyle çakışmaları çöz.
                                                            Öncelik: Kritik görevler kaydırılmaz; önce bolluğu yüksek olanı kaydır.
                                                            """
                                                            kaydirmalar: List[KaydirmaKaydi] = []

                                                            # Kaynak bazında işle
                                                            kaynak_gruplari: Dict[str, List[AtamaKayit]] = defaultdict(list)
                                                            for atama in self.atamalar:
                                                                kaynak_gruplari[atama.kaynak_ad].append(atama)

                                                                for kaynak_ad, grup in kaynak_gruplari.items():
                                                                    kapasite = self.kapasiteler.get(
                                                                    kaynak_ad, {"kapasite": 1}
                                                                    )["kapasite"]

                                                                    # Birden fazla geçişte tüm çakışmaları çöz
                                                                    max_iter = 50 # Sonsuz döngü önlemi
                                                                    iterasyon = 0
                                                                    while iterasyon < max_iter:
                                                                        iterasyon += 1
                                                                        cakisma_var, kaydi = self._tek_iterasyon(grup, kapasite)
                                                                        if kaydi:
                                                                            kaydirmalar.append(kaydi)
                                                                            if not cakisma_var:
                                                                                break

                                                                                return kaydirmalar

                                                                                def tam_dengele(self) -> DengelemeRaporu:
                                                                                    """
                                                                                    Çakışma tespiti + otomatik düzeltme + rapor üret.
                                                                                    En üst seviye API — GanttWindow bu metodu çağırır.
                                                                                    """
                                                                                    # Önce çakışmaları bul (orijinal durumu kaydet)
                                                                                    onceki_cakismalar = self.cakismalari_bul()
                                                                                    toplam_cakisma = len(onceki_cakismalar)

                                                                                    # Otomatik dengele
                                                                                    kaydirmalar = self.otomatik_dengele()

                                                                                    # Sonra çakışmaları tekrar kontrol et
                                                                                    kalan_cakismalar = self.cakismalari_bul()
                                                                                    cozulen = toplam_cakisma - len(kalan_cakismalar)
                                                                                    cozulemeyen = len(kalan_cakismalar)

                                                                                    # Kritik uzama
                                                                                    kritik_uzama = sum(
                                                                                    k.kaydi_gun for k in kaydirmalar if k.kritik_etki
                                                                                    )

                                                                                    # Uyarılar
                                                                                    uyarilar = []
                                                                                    for k in kaydirmalar:
                                                                                        if k.kritik_etki:
                                                                                            uyarilar.append(
                                                                                            f" '{k.gorev_ad}' kaydırıldı → "
                                                                                            f"proje süresi +{k.kaydi_gun} gün uzayabilir!"
                                                                                            )
                                                                                            for c in kalan_cakismalar:
                                                                                                uyarilar.append(
                                                                                                f" Çözülemeyen çakışma: '{c.kaynak_ad}' — "
                                                                                                f"Görevler: {', '.join(c.gorev_adlar)}"
                                                                                                )

                                                                                                # Özet metin
                                                                                                if toplam_cakisma == 0:
                                                                                                    ozet = " Kaynak çakışması bulunamadı. Tüm ekipler düzenli."
                                                                                                elif cozulemeyen == 0:
                                                                                                    ozet = (
                                                                                                    f" {toplam_cakisma} çakışma tespit edildi, "
                                                                                                    f"tamamı otomatik çözüldü. "
                                                                                                    f"{len(kaydirmalar)} görev kaydırıldı."
                                                                                                    )
                                                                                                else:
                                                                                                    ozet = (
                                                                                                    f" {toplam_cakisma} çakışmadan {cozulen} çözüldü, "
                                                                                                    f"{cozulemeyen} tanesi el ile düzenleme gerektiriyor. "
                                                                                                    f"Proje süresi +" + str(kritik_uzama) + " gün uzayabilir."
                                                                                                    )

                                                                                                    return DengelemeRaporu(
                                                                                                    toplam_cakisma=toplam_cakisma,
                                                                                                    cozulen_cakisma=cozulen,
                                                                                                    cozulemeyen=cozulemeyen,
                                                                                                    kaydirmalar=kaydirmalar,
                                                                                                    kritik_uzama_gun=kritik_uzama,
                                                                                                    uyarilar=uyarilar,
                                                                                                    ozet_metin=ozet,
                                                                                                    )

                                                                                                    def kaynak_histogrami(
                                                                                                    self,
                                                                                                    baslangic: datetime,
                                                                                                    bitis: datetime,
                                                                                                    ) -> Dict[str, Dict[str, int]]:
                                                                                                        """
                                                                                                    Kaynak histogram verisi üret.
                                                                                                    Returns: {"Kalıpçı Ekibi": {"2026-03-01": 2, "2026-03-02": 1, ...}, ...}
                                                                                                    UI'da matplotlib bar chart olarak gösterilir.
                                                                                                    """
                                                                                                    histogram: Dict[str, Dict[str, int]] = defaultdict(dict)

                                                                                                    tarih = baslangic
                                                                                                    while tarih <= bitis:
                                                                                                        if tarih.weekday() < 5:
                                                                                                            tarih_str = tarih.strftime("%Y-%m-%d")
                                                                                                            for kaynak_ad in self.kapasiteler:
                                                                                                                histogram[kaynak_ad][tarih_str] = 0

                                                                                                                for atama in self.atamalar:
                                                                                                                    if atama.baslangic <= tarih <= atama.bitis:
                                                                                                                        if tarih.weekday() < 5:
                                                                                                                            tarih_str = tarih.strftime("%Y-%m-%d")
                                                                                                                    histogram[atama.kaynak_ad][tarih_str] = (
                                                                                                                    histogram[atama.kaynak_ad].get(tarih_str, 0) + 1
                                                                                                                    )
                                                                                                                    tarih += timedelta(days=1)

                                                                                                                    return dict(histogram)

                                                                                                                    # ── Yardımcı metodlar ─────────────────────────────────────────────────────

                                                                                                                    def _tek_iterasyon(
                                                                                                                    self,
                                                                                                                    grup: List[AtamaKayit],
                                                                                                                    kapasite: int,
                                                                                                                    ) -> Tuple[bool, Optional[KaydirmaKaydi]]:
                                                                                                                        """
                                                                                                                    Bir çakışma bul ve kaydır.
                                                                                                                    Returns: (çakışma_var_mi, kaydırma_kaydı_veya_None)
                                                                                                                    """
                                                                                                                    # Günlük kullanım haritası oluştur
                                                                                                                    tarih_gorevler: Dict[str, List[AtamaKayit]] = defaultdict(list)
                                                                                                                    for atama in grup:
                                                                                                                        tarih = atama.baslangic
                                                                                                                    while tarih <= atama.bitis:
                                                                                                                        if tarih.weekday() < 5:
                                                                                                                            tarih_gorevler[tarih.strftime("%Y-%m-%d")].append(atama)
                                                                                                                    tarih += timedelta(days=1)

                                                                                                                    # İlk çakışmayı bul
                                                                                                                    for tarih_str in sorted(tarih_gorevler.keys()):
                                                                                                                        gorevler = tarih_gorevler[tarih_str]
                                                                                                                    if len(gorevler) <= kapasite:
                                                                                                                        continue

                                                                                                                    # Çakışan görevleri bolluk payına göre sırala (en yüksek bolluk → kaydır)
                                                                                                                    # Kritik görevleri koru
                                                                                                                    kaydirilebilir = sorted(
                                                                                                                    [a for a in gorevler if not a.kritik],
                                                                                                                    key=lambda a: a.bolluk_gun,
                                                                                                                    reverse=True, # En yüksek bolluk önce
                                                                                                                    )

                                                                                                                    if not kaydirilebilir:
                                                                                                                    # Tüm görevler kritik — çözüm yok
                                                                                                                        return True, None

                                                                                                                    kaydirilan = kaydirilebilir[0]

                                                                                                                    # Çakışma bitiş tarihini bul (kaç gün kaydırmak gerekiyor?)
                                                                                                                    # → Çakışan en büyük aralığın bitişine git
                                                                                                                    oncelikli_bitisler = [
                                                                                                                    a.bitis for a in gorevler
                                                                                                                    if a.gorev_id != kaydirilan.gorev_id
                                                                                                                    ]
                                                                                                                    if not oncelikli_bitisler:
                                                                                                                        return False, None

                                                                                                                    yeni_baslangic = max(oncelikli_bitisler) + timedelta(days=1)
                                                                                                                    # Pazartesiye denk getir
                                                                                                                    while yeni_baslangic.weekday() >= 5:
                                                                                                                        yeni_baslangic += timedelta(days=1)

                                                                                                                    kaydi_gun = max(0, (yeni_baslangic - kaydirilan.baslangic).days)

                                                                                                                    # Bolluk yeterli mi?
                                                                                                                    kritik_etki = kaydi_gun > kaydirilan.bolluk_gun

                                                                                                                    yeni_bitis = kaydirilan.bitis + timedelta(days=kaydi_gun)

                                                                                                                    kaydi = KaydirmaKaydi(
                                                                                                                    gorev_id=kaydirilan.gorev_id,
                                                                                                                    gorev_ad=kaydirilan.gorev_ad,
                                                                                                                    kaynak_ad=kaydirilan.kaynak_ad,
                                                                                                                    kaydi_gun=kaydi_gun,
                                                                                                                    eski_baslangic=kaydirilan.baslangic,
                                                                                                                    yeni_baslangic=yeni_baslangic,
                                                                                                                    eski_bitis=kaydirilan.bitis,
                                                                                                                    yeni_bitis=yeni_bitis,
                                                                                                                    sebep=f"Kaynak çakışması: '{kaydirilan.kaynak_ad}'",
                                                                                                                    kritik_etki=kritik_etki,
                                                                                                                    )

                                                                                                                    # Atamayı güncelle
                                                                                                                    kaydirilan.baslangic = yeni_baslangic
                                                                                                                    kaydirilan.bitis = yeni_bitis
                                                                                                                    kaydirilan.bolluk_gun = max(0, kaydirilan.bolluk_gun - kaydi_gun)

                                                                                                                    return True, kaydi

                                                                                                                    return False, None
