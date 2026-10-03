# -*- coding: utf-8 -*-
"""
Merkezi ReportLab Font Yöneticisi
Türkçe karakter desteği için Arial/Calibri kaydeder.
Tüm PDF üreten modüller bu modülü kullanmalıdır.
"""

import os

_KAYITLI = False
_ANA_FONT = "Helvetica"
_KALIN_FONT = "Helvetica-Bold"

# Windows sistem font yolları (öncelik sırasıyla)
_FONT_ADAYLARI = [
    ("Arial",      r"C:\Windows\Fonts\arial.ttf",    r"C:\Windows\Fonts\arialbd.ttf"),
    ("Calibri",    r"C:\Windows\Fonts\calibri.ttf",  r"C:\Windows\Fonts\calibrib.ttf"),
    ("Tahoma",     r"C:\Windows\Fonts\tahoma.ttf",   r"C:\Windows\Fonts\tahomabd.ttf"),
    ("Verdana",    r"C:\Windows\Fonts\verdana.ttf",  r"C:\Windows\Fonts\verdanab.ttf"),
]


def get_fonts():
    """
    Türkçe destekli font adlarını döndürür.
    İlk çağrıda kaydeder; sonraki çağrılarda cache'den döner.

    Returns:
        tuple: (ana_font_adi, kalin_font_adi)
    """
    global _KAYITLI, _ANA_FONT, _KALIN_FONT
    if _KAYITLI:
        return _ANA_FONT, _KALIN_FONT

    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        for ad, normal_yol, kalin_yol in _FONT_ADAYLARI:
            if not os.path.exists(normal_yol):
                continue
            try:
                pdfmetrics.registerFont(TTFont(ad, normal_yol))
                _ANA_FONT = ad
                if os.path.exists(kalin_yol):
                    kalin_ad = ad + "-Bold"
                    pdfmetrics.registerFont(TTFont(kalin_ad, kalin_yol))
                    _KALIN_FONT = kalin_ad
                else:
                    _KALIN_FONT = ad  # Kalın yoksa aynı fontu kullan
                _KAYITLI = True
                break
            except Exception:
                continue
    except Exception:
        pass  # reportlab yoksa Helvetica fallback

    _KAYITLI = True
    return _ANA_FONT, _KALIN_FONT


def ana_font():
    """Normal ağırlık font adı"""
    return get_fonts()[0]


def kalin_font():
    """Kalın font adı"""
    return get_fonts()[1]
