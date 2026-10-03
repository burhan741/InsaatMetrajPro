"""
Core Package
Veritabanı, CAD ve hesaplama modülleri
"""

# Rev-140 (2026-09-27): Buradaki "2x/3x perde çarpanı" monkey-patch'i
# (_apply_carpan_fix) KALDIRILDI. Çarpan artık autocad_connector.py
# get_rebar_report_from_selection içinde regex grup 1 ile uygulanıyor
# (adet = carpan * adet); patch aynı çarpanı İKİNCİ kez uygulayıp
# "2x8Ø12" için 16 yerine 32 adet üretiyordu.
# Test: scratchpad/test_genel_demir_secim.py
