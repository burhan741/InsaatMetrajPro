"""
Kazanılmış Değer Yönetimi (EVM — Earned Value Management)
===========================================================
Neyi çözer?
"Yüzde 60 bitti" diyen müteahhidin parasının bitip bitmediğini
matematiksel olarak ölçer. Proje sonunda kaç TL ile biteceğini
bugünden tahmin eder. Şantiye şefine trafik ışığı ile bilgi verir.

Formüller (PMBOK 7. Baskı uyumlu):
PV (BCWS) = Planned Value → Bugüne kadar yapılması planlanan
EV (BCWP) = Earned Value → Gerçekte tamamlanan işin değeri
AC (ACWP) = Actual Cost → Gerçekte harcanan para
BAC = Budget at Completion → Toplam proje bütçesi
CPI = EV / AC → Maliyet Performans Endeksi
SPI = EV / PV → Zaman Performans Endeksi
CV = EV - AC → Maliyet Farkı
SV = EV - PV → Zaman Farkı
EAC = BAC / CPI → Proje sonunda toplam maliyet tahmini
ETC = EAC - AC → Kalan maliyet tahmini
VAC = BAC - EAC → Bitişteki fark (+ tasarruf, - zarar)
TCPI = (BAC - EV) / (BAC - AC) → Hedefte kalmak için gereken CPI

Test:
python -c "
from app.core.evm_engine import EVMEngine, GorevEVM
from decimal import Decimal
g = [GorevEVM(1,'Test',Decimal('100000'),80,Decimal('95000'),90)]
r = EVMEngine().hesapla(g)
assert r.cpi < 1.0 # Para aşımı
assert r.spi < 1.0 # Geride
print('EVM OK')
"
"""

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional, Dict
from datetime import datetime, date, timedelta
import logging

logger = logging.getLogger(__name__)

# Trafik ışığı eşik değerleri (PMBOK önerisi)
CPI_ESIK_YESIL = Decimal("0.95") # >= yeşil
CPI_ESIK_SARI = Decimal("0.85") # >= sarı, < yeşil
# < sarı → kırmızı

SPI_ESIK_YESIL = Decimal("0.90")
SPI_ESIK_SARI = Decimal("0.80")


@dataclass
class GorevEVM:
    """
    EVM hesabı için tek görev verisi.
    GanttEngine.Task sınıfından bağımsız tutuldu (bağımlılık azaltma).
    """
    id: int
    ad: str
    butce_tl: Decimal # BAC — göreve ayrılan toplam bütçe
    ilerleme_yuzde: float # 0-100 — fiili tamamlanma yüzdesi
    gercek_maliyet_tl: Decimal # AC — bugüne kadar gerçekten harcanan
    planlanan_ilerleme: float # 0-100 — bugün itibarıyla olması gereken %
    kaynak: str = ""
    wbs_kodu: str = ""
    kritik: bool = False

    def earned_value(self) -> Decimal:
        """EV = BAC × Fiili Tamamlanma %"""
        return (self.butce_tl * Decimal(str(self.ilerleme_yuzde / 100))
        ).quantize(Decimal("0.01"), ROUND_HALF_UP)

        def planned_value(self) -> Decimal:
            """PV = BAC × Planlanan Tamamlanma %"""
            return (self.butce_tl * Decimal(str(self.planlanan_ilerleme / 100))
            ).quantize(Decimal("0.01"), ROUND_HALF_UP)


@dataclass
class EVMSonucu:
    """EVM hesap çıktısı — UI'ye hazır."""
    # ── Temel Değerler ──────────────────────────────────────────
    bac_tl: Decimal # Budget at Completion
    pv_tl: Decimal # Planned Value (BCWS)
    ev_tl: Decimal # Earned Value (BCWP)
    ac_tl: Decimal # Actual Cost (ACWP)

    # ── Performans Endeksleri ────────────────────────────────────
    cpi: float # Cost Performance Index (1.0 = ideal)
    spi: float # Schedule Performance Index(1.0 = ideal)
    tcpi: float # To-Complete Performance Index

    # ── Farklar ─────────────────────────────────────────────────
    cv_tl: Decimal # Cost Variance (+ tasarruf, - aşım)
    sv_tl: Decimal # Schedule Variance (+ ileride, - geride)

    # ── Tahminler ───────────────────────────────────────────────
    eac_tl: Decimal # Estimate at Completion
    etc_tl: Decimal # Estimate to Complete
    vac_tl: Decimal # Variance at Completion

    # ── Yüzdeler ────────────────────────────────────────────────
    pct_complete: float # Mali tamamlanma %
    pct_spent: float # Bütçe harcama %
    pct_planned: float # Planlanan tamamlanma %

    # ── Trafik Işığı ────────────────────────────────────────────
    butce_durumu: str # "yesil" | "sari" | "kirmizi"
    takvim_durumu: str # "yesil" | "sari" | "kirmizi"

    # ── Görev Bazlı Detay ────────────────────────────────────────
    gorev_detaylari: List[Dict] = field(default_factory=list)

    # ── Otomatik Yorum ───────────────────────────────────────────
    yorum: str = ""
    kritik_uyari: str = ""

    # ── Meta ─────────────────────────────────────────────────────
    hesap_tarihi: datetime = field(default_factory=datetime.now)


class EVMEngine:
    """
    Proje ve görev düzeyinde EVM hesaplama motoru.

    Kullanım — GanttWindow'dan:
    engine = EVMEngine()
    gorevler = [
    GorevEVM(
    id=1, ad="Hafriyat",
    butce_tl=Decimal("50000"),
    ilerleme_yuzde=100,
    gercek_maliyet_tl=Decimal("58000"), # %16 aşım
    planlanan_ilerleme=100
    ),
    GorevEVM(
    id=2, ad="Temel Beton",
    butce_tl=Decimal("120000"),
    ilerleme_yuzde=60,
    gercek_maliyet_tl=Decimal("85000"),
    planlanan_ilerleme=80 # Gerideyiz
    ),
    ]
    sonuc = engine.hesapla(gorevler)
    # → sonuc.cpi, sonuc.spi, sonuc.eac_tl, sonuc.yorum
    """

    def hesapla(self, gorevler: List[GorevEVM]) -> EVMSonucu:
        """Ana hesaplama metodu — proje geneli EVM."""
        if not gorevler:
            return self._bos_sonuc()

            # ── Toplam değerleri hesapla ──────────────────────────────
            bac = sum(g.butce_tl for g in gorevler)
            pv = sum(g.planned_value() for g in gorevler)
            ev = sum(g.earned_value() for g in gorevler)
            ac = sum(g.gercek_maliyet_tl for g in gorevler)

            # ── Endeksler (sıfıra bölme koruması) ────────────────────
            cpi = float(ev / ac) if ac > 0 else 1.0
            spi = float(ev / pv) if pv > 0 else 1.0
            # TCPI: Hedefe ulaşmak için gereken maliyet performansı
            tcpi = (float((bac - ev) / (bac - ac))
            if (bac - ac) != 0 else 1.0)

            # ── Farklar ──────────────────────────────────────────────
            cv = ev - ac # Maliyet farkı
            sv = ev - pv # Zaman farkı

            # ── Tahminler ─────────────────────────────────────────────
            # EAC: Performans trendi devam ederse proje toplam maliyeti
            eac = (bac / Decimal(str(cpi))
            if cpi > 0 else bac)
            etc = eac - ac
            vac = bac - eac

            # ── Yüzdeler ─────────────────────────────────────────────
            pct_complete = float(ev / bac * 100) if bac > 0 else 0.0
            pct_spent = float(ac / bac * 100) if bac > 0 else 0.0
            pct_planned = float(pv / bac * 100) if bac > 0 else 0.0

            # ── Trafik ışığı ─────────────────────────────────────────
            butce_durumu = self._trafik(Decimal(str(cpi)),
            CPI_ESIK_YESIL, CPI_ESIK_SARI)
            takvim_durumu = self._trafik(Decimal(str(spi)),
            SPI_ESIK_YESIL, SPI_ESIK_SARI)

            # ── Görev detayları ──────────────────────────────────────
            gorev_detay = self._gorev_detaylari(gorevler)

            # ── Yorumlar ─────────────────────────────────────────────
            yorum = self._yorum_uret(cpi, spi, vac, bac)
            kritik_uyari = self._kritik_uyari(cpi, spi, tcpi, gorevler)

            # ── Yuvarlama ─────────────────────────────────────────────
            _q = lambda x: x.quantize(Decimal("0.01"), ROUND_HALF_UP)

            return EVMSonucu(
            bac_tl=_q(bac), pv_tl=_q(pv), ev_tl=_q(ev), ac_tl=_q(ac),
            cpi=round(cpi, 3), spi=round(spi, 3), tcpi=round(tcpi, 3),
            cv_tl=_q(cv), sv_tl=_q(sv),
            eac_tl=_q(eac), etc_tl=_q(etc), vac_tl=_q(vac),
            pct_complete=round(pct_complete, 1),
            pct_spent=round(pct_spent, 1),
            pct_planned=round(pct_planned, 1),
            butce_durumu=butce_durumu,
            takvim_durumu=takvim_durumu,
            gorev_detaylari=gorev_detay,
            yorum=yorum,
            kritik_uyari=kritik_uyari,
            )

            def gorev_bazli_hesapla(self, gorev: GorevEVM) -> Dict:
                """Tek görev için EVM hesapla (tablo satırı için)."""
                ev = gorev.earned_value()
                pv = gorev.planned_value()
                ac = gorev.gercek_maliyet_tl
                bac = gorev.butce_tl

                cpi = float(ev / ac) if ac > 0 else 1.0
                spi = float(ev / pv) if pv > 0 else 1.0
                cv = ev - ac
                sv = ev - pv

                return {
                "id": gorev.id,
                "ad": gorev.ad,
                "wbs": gorev.wbs_kodu,
                "kaynak": gorev.kaynak,
                "bac": float(bac),
                "pv": float(pv),
                "ev": float(ev),
                "ac": float(ac),
                "cpi": round(cpi, 2),
                "spi": round(spi, 2),
                "cv": float(cv),
                "sv": float(sv),
                "cpi_renk": self._renk(cpi, 0.95, 0.85),
                "spi_renk": self._renk(spi, 0.90, 0.80),
                "kritik": gorev.kritik,
                }

                # ── Yardımcı metodlar ─────────────────────────────────────────

                def _gorev_detaylari(self, gorevler: List[GorevEVM]) -> List[Dict]:
                    return [self.gorev_bazli_hesapla(g) for g in gorevler]

                    @staticmethod
                    def _trafik(deger: Decimal, esik_yesil: Decimal, esik_sari: Decimal) -> str:
                        if deger >= esik_yesil:
                            return "yesil"
                        elif deger >= esik_sari:
                            return "sari"
                            return "kirmizi"

                            @staticmethod
                            def _renk(deger: float, esik_yesil: float, esik_sari: float) -> str:
                                if deger >= esik_yesil:
                                    return "#27ae60" # Yeşil
                                elif deger >= esik_sari:
                                    return "#e67e22" # Turuncu
                                    return "#e74c3c" # Kırmızı

                                    @staticmethod
                                    def _yorum_uret(cpi: float, spi: float,
                                    vac: Decimal, bac: Decimal) -> str:
                                        """Şantiye şefinin anlayacağı sade Türkçe yorum."""
                                    yorumlar = []

                                    if cpi >= 1.0:
                                        yorumlar.append(
                                        f" Bütçe kontrolde — "
                                        f"her 100 TL'ye {100/cpi:.0f} TL harcanıyor."
                                        )
                                    elif cpi >= 0.85:
                                        asim = round((1 - cpi) * 100, 1)
                                        yorumlar.append(
                                        f" Bütçe %{asim} geride — "
                                        f"her 100 TL'lik işe {100/cpi:.0f} TL gidiyor."
                                        )
                                    else:
                                        asim = round((1 - cpi) * 100, 1)
                                        yorumlar.append(
                                        f" KRİTİK: Bütçe %{asim} aşımda! "
                                        f"Acil maliyet revizyonu gerekiyor."
                                        )

                                        if spi >= 1.0:
                                            yorumlar.append(" Program önde.")
                                        elif spi >= 0.80:
                                            geri = round((1 - spi) * 100, 1)
                                            yorumlar.append(f" Program %{geri} geride.")
                                        else:
                                            geri = round((1 - spi) * 100, 1)
                                            yorumlar.append(
                                            f" KRİTİK: Program %{geri} geride! "
                                            f"Ek kaynak veya mesai planla."
                                            )

                                            if bac > 0:
                                                if vac < 0:
                                                    zarar_yuzde = abs(float(vac / bac) * 100)
                                                    yorumlar.append(
                                                    f" Tahmini bitiş maliyeti: bütçeyi "
                                                    f"%{zarar_yuzde:.1f} aşacak "
                                                    f"({abs(vac):,.0f} TL zarar)."
                                                    )
                                                else:
                                                    tasarruf_yuzde = float(vac / bac * 100)
                                                    yorumlar.append(
                                                    f" Tahmini tasarruf: {float(vac):,.0f} TL "
                                                    f"(bütçenin %{tasarruf_yuzde:.1f}'i)."
                                                    )

                                                    return " | ".join(yorumlar)

                                                    @staticmethod
                                                    def _kritik_uyari(cpi: float, spi: float, tcpi: float,
                                                    gorevler: List[GorevEVM]) -> str:
                                                        """Kritik durumlar için özel uyarı metni."""
                                                    uyarilar = []

                                                    # CPI kritik eşiği
                                                    if cpi < 0.80:
                                                        uyarilar.append(
                                                        f" CPI = {cpi:.2f} — "
                                                        "Bu performansta proje ciddi zararda bitecek. "
                                                        "Taşeron/malzeme maliyetlerini gözden geçir."
                                                        )

                                                        # SPI kritik eşiği
                                                        if spi < 0.70:
                                                            uyarilar.append(
                                                            f" SPI = {spi:.2f} — "
                                                            "Proje takvimden çok geride. "
                                                            "Kritik yolu yeniden hesapla, kaynak ekle."
                                                            )

                                                            # TCPI > 1.2 → hedefte kalmak artık çok zor
                                                            if tcpi > 1.20:
                                                                uyarilar.append(
                                                                f" TCPI = {tcpi:.2f} — "
                                                                "Bütçede kalmak için kalan işleri {:.0f}% daha verimli "
                                                                "yapmak gerekiyor. Hedef revize edilmeli.".format(
                                                                (tcpi - 1) * 100
                                                                )
                                                                )

                                                                # Kritik görevlerde aşım var mı?
                                                                kritik_asim = [
                                                                g for g in gorevler
                                                                if g.kritik
                                                                and g.gercek_maliyet_tl > g.butce_tl * Decimal("1.1")
                                                                ]
                                                                if kritik_asim:
                                                                    isimler = ", ".join(g.ad for g in kritik_asim[:3])
                                                                    uyarilar.append(
                                                                    f" Kritik görevlerde bütçe aşımı: {isimler}"
                                                                    )

                                                                    return "\n".join(uyarilar) if uyarilar else ""

                                                                    @staticmethod
                                                                    def _bos_sonuc() -> "EVMSonucu":
                                                                        """Boş / sıfır değerli sonuç döndür."""
                                                                        z = Decimal("0")
                                                                        return EVMSonucu(
                                                                        bac_tl=z, pv_tl=z, ev_tl=z, ac_tl=z,
                                                                        cpi=1.0, spi=1.0, tcpi=1.0,
                                                                        cv_tl=z, sv_tl=z,
                                                                        eac_tl=z, etc_tl=z, vac_tl=z,
                                                                        pct_complete=0.0, pct_spent=0.0, pct_planned=0.0,
                                                                        butce_durumu="yesil", takvim_durumu="yesil",
                                                                        yorum="Görev verisi girilmedi.",
                                                                        )

                                                                        def s_egrisi_verisi(self, gorevler: List[GorevEVM],
                                                                        proje_baslangic: datetime,
                                                                        proje_bitis: datetime) -> Dict[str, List]:
                                                                            """
                                                                        S-Eğrisi için PV / EV / AC kümülatif veri seti üret.
                                                                        Gantt eksenini (tarih) x ekseni olarak kullanır.
                                                                        """
                                                                        if not gorevler:
                                                                            return {"tarihler": [], "pv_list": [], "ev_list": [], "ac_list": []}

                                                                            gun_sayisi = (proje_bitis - proje_baslangic).days + 1
                                                                            tarihler = []
                                                                            pv_list = []
                                                                            ev_list = []
                                                                            ac_list = []

                                                                            toplam_bac = float(sum(g.butce_tl for g in gorevler))

                                                                            for gun in range(0, gun_sayisi, max(1, gun_sayisi // 50)):
                                                                                tarih = proje_baslangic + timedelta(days=gun)
                                                                                oran = gun / max(1, gun_sayisi - 1)

                                                                                # S-eğrisi şekli için sigmoid benzeri dağılım
                                                                                # (gerçek proje verisi yoksa planlanan ilerleme varsayılır)
                                                                                sigmoid = 1 / (1 + 2.71828 ** (-10 * (oran - 0.5)))
                                                                                pv_kumulatif = toplam_bac * sigmoid

                                                                                # EV = fiili × planlanan oran
                                                                                ev_kumulatif = sum(
                                                                                float(g.butce_tl) * (g.ilerleme_yuzde / 100) * min(oran / max(0.01, g.planlanan_ilerleme / 100), 1.0)
                                                                                for g in gorevler
                                                                                )
                                                                                ac_kumulatif = sum(
                                                                                float(g.gercek_maliyet_tl) * min(oran * 2, 1.0)
                                                                                for g in gorevler
                                                                                )

                                                                                tarihler.append(tarih.strftime("%d.%m.%Y"))
                                                                                pv_list.append(round(pv_kumulatif, 0))
                                                                                ev_list.append(round(ev_kumulatif, 0))
                                                                                ac_list.append(round(ac_kumulatif, 0))

                                                                                return {
                                                                                "tarihler": tarihler,
                                                                                "pv_list": pv_list,
                                                                                "ev_list": ev_list,
                                                                                "ac_list": ac_list,
                                                                                }
