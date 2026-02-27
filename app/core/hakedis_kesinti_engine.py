"""
Hakediş Kesinti ve Mahsup Hesabı — Engine
==========================================
4734 Kamu İhale Kanunu + 4735 Kamu İhale Sözleşmeleri Kanunu

Kesinti kalemleri:
1. Avans mahsubu — sözleşme/hakediş avans oranı × brüt hakediş
2. Kesin teminat kesintisi — %6 (sözleşme bedelinin tamamlanana dek)
3. Damga vergisi — %0.948 (488 sayılı DVK IV/1 Cetvel)
4. Gelir vergisi stopajı — %3 (GVK Geçici md.67 kapsam dışı yapım işi)
5. SGK prim kesintisi — %1 (5510 md.85 — asgari işçilik fark primi)
6. Gecikme cezası mahsubu — sözleşme bedeli × ‰5 (%0.5) × gün sayısı
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
from datetime import date


# ---------------------------------------------------------------------------
# Sabitler (mevzuat kaynakları)
# ---------------------------------------------------------------------------

KESIN_TEMINAT_ORANI = Decimal("0.06") # 4735 md.13
DAMGA_VERGISI_ORANI = Decimal("0.00948") # 488 sayılı DVK — yapım işi
GELIR_VERGISI_STOPAJ = Decimal("0.03") # GVK Geçici md.67
SGK_PRIM_KESINTI_ORANI = Decimal("0.01") # 5510 md.85 — asgari işçilik
GUNLUK_GECIKME_ORANI = Decimal("0.005") # 4735 md.20 — binde beş (%0.5) günlük
FESIH_ESIGI_ORANI = Decimal("0.30") # toplam ceza sözleşme bedelinin %30'unu aşarsa fesih


# ---------------------------------------------------------------------------
# Veri sınıfları
# ---------------------------------------------------------------------------

@dataclass
class HakedisKesintiBilgisi:
    """Tekil bir hakediş dönemine ait tüm bilgiler"""

    # Genel bilgiler
    sozlesme_bedeli: Decimal = Decimal("0")
    hakedis_no: int = 1
    hakedis_tarihi: Optional[date] = None

    # Brüt hakediş (imalat bedeli)
    brut_hakedis: Decimal = Decimal("0")

    # Önceki dönemlere ait birikimli hakediş
    onceki_hakedis_toplami: Decimal = Decimal("0")

    # Avans bilgileri
    avans_orani: Decimal = Decimal("0.30") # sözleşme bedelinin %30'u tipik
    verilen_avans: Decimal = Decimal("0") # nakit ödenen avans tutarı
    onceki_avans_mahsubu: Decimal = Decimal("0") # önceki hakedişlerde kesilen avans

    # Kesin teminat — sözleşme bedelinin %6'sı tamamlanana kadar kesilir
    kesin_teminat_tamamlandi: bool = False # limit dolmuşsa daha fazla kesilmez

    # Gecikme
    gecikme_gun: int = 0

    # SGK prim kesintisi aktif mi?
    sgk_kesinti_aktif: bool = True

    # GV stopaj aktif mi? (bazı kamu yapım işlerinde muafiyet var)
    gv_stopaj_aktif: bool = True


@dataclass
class HakedisKesintleri:
    """Hesaplama sonucu — her kalem ayrıştırılmış"""

    brut_hakedis: Decimal = Decimal("0")

    avans_mahsubu: Decimal = Decimal("0")
    kesin_teminat: Decimal = Decimal("0")
    damga_vergisi: Decimal = Decimal("0")
    gelir_vergisi: Decimal = Decimal("0")
    sgk_prim: Decimal = Decimal("0")
    gecikme_cezasi: Decimal = Decimal("0")

    toplam_kesinti: Decimal = Decimal("0")
    net_odeme: Decimal = Decimal("0")

    # Uyarı mesajları
    uyarilar: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Ana engine
# ---------------------------------------------------------------------------

class HakedisKesintEngine:
    """
    Kamu yapım işi hakediş kesintilerini hesaplar.

    Kullanım:
    engine = HakedisKesintEngine()
    bilgi = HakedisKesintiBilgisi(
    sozlesme_bedeli = Decimal("10_000_000"),
    brut_hakedis = Decimal("1_500_000"),
    verilen_avans = Decimal("3_000_000"),
    gecikme_gun = 0)
    sonuc = engine.hesapla(bilgi)
    print(sonuc.net_odeme)
    """

    def _round2(self, val: Decimal) -> Decimal:
        """2 ondalık basamağa yuvarla (banker yuvarlama yerine ROUND_HALF_UP)"""
        return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # ------------------------------------------------------------------
        # Ana hesap
        # ------------------------------------------------------------------

        def hesapla(self, bilgi: HakedisKesintiBilgisi) -> HakedisKesintleri:
            sonuc = HakedisKesintleri(brut_hakedis=bilgi.brut_hakedis)

            brut = bilgi.brut_hakedis

            # 1. Avans mahsubu
            avans_mahsubu = self._hesapla_avans_mahsubu(bilgi)
            sonuc.avans_mahsubu = avans_mahsubu

            # 2. Kesin teminat
            kt = self._hesapla_kesin_teminat(bilgi)
            sonuc.kesin_teminat = kt

            # 3. Damga vergisi (brüt hakediş üzerinden)
            dv = self._round2(brut * DAMGA_VERGISI_ORANI)
            sonuc.damga_vergisi = dv

            # 4. Gelir vergisi stopajı
            if bilgi.gv_stopaj_aktif:
                gv = self._round2(brut * GELIR_VERGISI_STOPAJ)
            else:
                gv = Decimal("0")
                sonuc.uyarilar.append("Gelir vergisi stopajı muafiyet kapsamında uygulanmadı.")
                sonuc.gelir_vergisi = gv

                # 5. SGK prim kesintisi
                if bilgi.sgk_kesinti_aktif:
                    sgk = self._round2(brut * SGK_PRIM_KESINTI_ORANI)
                else:
                    sgk = Decimal("0")
                    sonuc.sgk_prim = sgk

                    # 6. Gecikme cezası
                    gecikme = self._hesapla_gecikme(bilgi)
                    sonuc.gecikme_cezasi = gecikme

                    # Toplam ve net
                    toplam = avans_mahsubu + kt + dv + gv + sgk + gecikme
                    sonuc.toplam_kesinti = self._round2(toplam)
                    sonuc.net_odeme = self._round2(brut - toplam)

                    # Uyarılar
                    self._ekle_uyarilar(bilgi, sonuc)

                    return sonuc

                    # ------------------------------------------------------------------
                    # Alt hesaplar
                    # ------------------------------------------------------------------

                    def _hesapla_avans_mahsubu(self, bilgi: HakedisKesintiBilgisi) -> Decimal:
                        """
                        Avans mahsup oranı = (verilen avans) / (sözleşme bedeli)
                        Her hakediş döneminde bu oran × brüt hakediş kadar mahsup edilir.
                        Kalan avans = verilen avans − önceki mahsuplar
                        """
                        if bilgi.verilen_avans <= 0:
                            return Decimal("0")

                            kalan_avans = bilgi.verilen_avans - bilgi.onceki_avans_mahsubu
                            if kalan_avans <= 0:
                                return Decimal("0")

                                # Oran bazlı mahsup
                                mahsup = self._round2(bilgi.brut_hakedis * bilgi.avans_orani)

                                # Kalan avansı aşamaz
                                mahsup = min(mahsup, kalan_avans)
                                return mahsup

                                def _hesapla_kesin_teminat(self, bilgi: HakedisKesintiBilgisi) -> Decimal:
                                    """
                                    4735 md.13: Her hakediş döneminde %6 oranında kesin teminat kesilir.
                                    Toplam kesilen kesin teminat, sözleşme bedelinin %6'sına ulaşınca
                                    daha fazla kesilmez.
                                    """
                                    if bilgi.kesin_teminat_tamamlandi:
                                        return Decimal("0")

                                        kt_tutari = self._round2(bilgi.brut_hakedis * KESIN_TEMINAT_ORANI)
                                        return kt_tutari

                                        def _hesapla_gecikme(self, bilgi: HakedisKesintiBilgisi) -> Decimal:
                                            """4735 md.20: günlük ‰5 (%0.5, binde beş) gecikme cezası"""
                                            if bilgi.gecikme_gun <= 0:
                                                return Decimal("0")
                                                ceza = self._round2(
                                                bilgi.sozlesme_bedeli * GUNLUK_GECIKME_ORANI * Decimal(bilgi.gecikme_gun)
                                                )
                                                return ceza

                                                def _ekle_uyarilar(
                                                self, bilgi: HakedisKesintiBilgisi, sonuc: HakedisKesintleri
                                                ) -> None:
                                                # Net ödeme negatifse uyar
                                                    if sonuc.net_odeme < 0:
                                                        sonuc.uyarilar.append(
                                                    f" Net ödeme negatif ({sonuc.net_odeme:,.2f} TL). "
                                                    "Kesintiler brüt hakediş tutarını aşıyor."
                                                    )

                                                    # Gecikme cezası sözleşme bedelinin %30'una yaklaşıyorsa uyar
                                                    if bilgi.gecikme_gun > 0:
                                                        gecikme_toplam_oran = (
                                                        GUNLUK_GECIKME_ORANI * Decimal(bilgi.gecikme_gun)
                                                        )
                                                        if gecikme_toplam_oran >= FESIH_ESIGI_ORANI * Decimal("0.80"):
                                                            sonuc.uyarilar.append(
                                                            f" Gecikme cezası sözleşme bedelinin %30 fesih eşiğine "
                                                            f"yaklaşıyor ({float(gecikme_toplam_oran * 100):.1f}%)."
                                                            )

                                                            # ------------------------------------------------------------------
                                                            # Raporlama yardımcıları
                                                            # ------------------------------------------------------------------

                                                            def ozet_dict(
                                                            self, bilgi: HakedisKesintiBilgisi, sonuc: HakedisKesintleri
                                                            ) -> dict:
                                                                """Excel/PDF için düz sözlük (satır listesi dahil)"""
                                                            return {
                                                            "hakedis_no": bilgi.hakedis_no,
                                                            "tarih": str(bilgi.hakedis_tarihi or ""),
                                                            "sozlesme_bedeli": float(bilgi.sozlesme_bedeli),
                                                            "brut_hakedis": float(sonuc.brut_hakedis),
                                                            "avans_mahsubu": float(sonuc.avans_mahsubu),
                                                            "kesin_teminat": float(sonuc.kesin_teminat),
                                                            "damga_vergisi": float(sonuc.damga_vergisi),
                                                            "gelir_vergisi": float(sonuc.gelir_vergisi),
                                                            "sgk_prim": float(sonuc.sgk_prim),
                                                            "gecikme_cezasi": float(sonuc.gecikme_cezasi),
                                                            "toplam_kesinti": float(sonuc.toplam_kesinti),
                                                            "net_odeme": float(sonuc.net_odeme),
                                                            "uyarilar": sonuc.uyarilar,
                                                            "satirlar": [
                                                            ("Brüt Hakediş Tutarı", float(sonuc.brut_hakedis), ""),
                                                            ("(–) Avans Mahsubu", -float(sonuc.avans_mahsubu), ""),
                                                            ("(–) Kesin Teminat Kesintisi", -float(sonuc.kesin_teminat), "%6"),
                                                            ("(–) Damga Vergisi", -float(sonuc.damga_vergisi), "%0.948"),
                                                            ("(–) Gelir Vergisi Stopajı", -float(sonuc.gelir_vergisi), "%3"),
                                                            ("(–) SGK Prim Kesintisi", -float(sonuc.sgk_prim), "%1"),
                                                            ("(–) Gecikme Cezası", -float(sonuc.gecikme_cezasi), f"{bilgi.gecikme_gun} gün"),
                                                            ("NET ÖDENECEKlER MİKTAR", float(sonuc.net_odeme), ""),
                                                            ],
                                                            }

                                                            def to_excel_rows(
                                                            self, bilgi: HakedisKesintiBilgisi, sonuc: HakedisKesintleri
                                                            ) -> list[tuple]:
                                                                """Excel tablosu için satır listesi"""
                                                            return self.ozet_dict(bilgi, sonuc)["satirlar"]

                                                            # ------------------------------------------------------------------
                                                            # Kesin teminat limit kontrolü (harici çağrı)
                                                            # ------------------------------------------------------------------

                                                            def kesin_teminat_limit_doldu_mu(
                                                            self, sozlesme_bedeli: Decimal, toplam_kesilen_kt: Decimal
                                                            ) -> bool:
                                                                """
                                                            Önceki hakedişlerde kesilen toplam kesin teminat,
                                                            sözleşme bedelinin %6'sına ulaştıysa True döner.
                                                            """
                                                            limit = self._round2(sozlesme_bedeli * KESIN_TEMINAT_ORANI)
                                                            return toplam_kesilen_kt >= limit
