"""
Core Package
Veritabanı, CAD ve hesaplama modülleri
"""

import re as _re

# ── 2x/3x Perde Çarpanı Düzeltme Patch ────────────────────────────────────
# Sorun: Eski autocad_connector regex "2x8Ø12 L=420" içinde yalnızca "8"
#        ile eşleşiyor; "2x" çarpanını atlıyor → adet=8 yerine 16 olmalı.
# Çözüm: get_rebar_report_from_selection() çıktısını post-process edip
#        orijinal metin üzerinden çarpanı uyguluyoruz.
# ─────────────────────────────────────────────────────────────────────────

_CARPAN_PREFIX = _re.compile(
    r'^(?:P\d+\s+)?(\d+)\s*[xX*]\s*\d+',
    _re.IGNORECASE
)


def _apply_carpan_fix(rapor):
    """2x/3x çarpanı eksik uygulanmış demirleri düzelt."""
    delta_adet = 0
    delta_boy = 0.0
    delta_agirlik = 0.0

    for demir in rapor.get("basarili", []):
        m = _CARPAN_PREFIX.search(demir.orijinal_metin)
        if m:
            carpan = int(m.group(1))
            if carpan > 1:
                eski_adet = demir.adet
                eski_boy = demir.toplam_boy
                eski_agirlik = demir.toplam_agirlik

                demir.adet = carpan * eski_adet
                demir.toplam_boy = carpan * eski_boy
                demir.toplam_agirlik = demir.toplam_boy * demir.agirlik_birim

                delta_adet += demir.adet - eski_adet
                delta_boy += demir.toplam_boy - eski_boy
                delta_agirlik += demir.toplam_agirlik - eski_agirlik

                cap = demir.cap
                cap_ozeti = rapor.get("cap_ozeti", {})
                if cap in cap_ozeti:
                    cap_ozeti[cap]["adet"] += demir.adet - eski_adet
                    cap_ozeti[cap]["boy_m"] += demir.toplam_boy - eski_boy
                    cap_ozeti[cap]["agirlik_kg"] += (
                        demir.toplam_agirlik - eski_agirlik
                    )

    rapor["toplam_adet"] += delta_adet
    rapor["toplam_boy_m"] += delta_boy
    rapor["toplam_agirlik_kg"] += delta_agirlik
    return rapor


try:
    from app.core.autocad_connector import AutoCADConnector as _AC
    _orig_get_rebar = _AC.get_rebar_report_from_selection

    def _patched_get_rebar(self, birim="cm", mesaj="Demir yazılarını seçin"):
        rapor = _orig_get_rebar(self, birim=birim, mesaj=mesaj)
        return _apply_carpan_fix(rapor)

    _AC.get_rebar_report_from_selection = _patched_get_rebar
except Exception:
    pass  # AutoCAD connector yüklenemezse patch atlanır
