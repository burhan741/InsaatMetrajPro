"""
UI Package
Kullanıcı arayüzü modülleri
"""


# ── Demir Kat Listesi: Ton Gösterimi Patch ─────────────────────────────────
# Kat listesindeki "23373.4 kg" yerine "23.4 ton" göstermek için
# MetrajAnalizWindow._demir_kat_listesini_guncelle() monkey-patch ile düzeltildi.
# ─────────────────────────────────────────────────────────────────────────────

def _patched_demir_kat_listesini_guncelle(self):
    """Kat listesini ton gösterimiyle güncelle."""
    self.demir_kat_listesi.clear()
    for kat_data in self.demir_kat_verileri:
        demir_sayisi = len(kat_data["demirler"])
        toplam_agirlik = (
            sum(d.toplam_agirlik for d in kat_data["demirler"])
            if kat_data["demirler"] else 0
        )
        ton = toplam_agirlik / 1000.0
        self.demir_kat_listesi.addItem(
            f" {kat_data['kat_adi']} ({demir_sayisi} demir, {ton:.3f} ton)"
        )


try:
    from app.ui.metraj_analiz_window import MetrajAnalizWindow as _MAW
    _MAW._demir_kat_listesini_guncelle = _patched_demir_kat_listesini_guncelle
except Exception:
    pass  # Modül yüklenemezse patch atlanır


# ── GanttWindow Tab Arka Plan: Koyu Tema Patch ─────────────────────────────
# Sekmeler'deki beyaz (#ecf0f1 ve white) arka planı koyu temaya uygun hale getirir.
# GanttWindow.__init__ çalıştıktan sonra tab_widget stili override edilir.
# ─────────────────────────────────────────────────────────────────────────────

_GANTT_TAB_STYLE = """
QTabWidget::pane {
    border: 1px solid #00BFFF;
    border-radius: 5px;
    background-color: #1a1a2e;
}
QTabBar::tab {
    background-color: #16213e;
    color: #b0c4de;
    padding: 8px 14px;
    margin-right: 2px;
    border-top-left-radius: 5px;
    border-top-right-radius: 5px;
}
QTabBar::tab:selected {
    background-color: #00BFFF;
    color: #0d0d1a;
    font-weight: bold;
}
QTabBar::tab:hover:!selected {
    background-color: #0f3460;
    color: #ffffff;
}
"""


def _patched_gantt_init(self, *args, **kwargs):
    _orig_gantt_init(self, *args, **kwargs)
    if hasattr(self, "tab_widget"):
        self.tab_widget.setStyleSheet(_GANTT_TAB_STYLE)


try:
    from app.ui.gantt_window import GanttWindow as _GW
    _orig_gantt_init = _GW.__init__
    _GW.__init__ = _patched_gantt_init
except Exception:
    pass  # Modül yüklenemezse patch atlanır


# ── TemplateDialog Koyu Tema Patch ──────────────────────────────────────────
# Şablon seçim dialogundaki beyaz liste/arka planı koyu temaya çevirir.
# ─────────────────────────────────────────────────────────────────────────────

_TEMPLATE_DIALOG_QSS = """
QDialog {
    background-color: #1a1a2e;
    color: #e0e0e0;
}
QLabel {
    color: #b0c4de;
}
QGroupBox {
    color: #00BFFF;
    border: 1px solid #00BFFF;
    border-radius: 5px;
    margin-top: 8px;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    color: #00BFFF;
}
QDateEdit {
    background-color: #16213e;
    color: #e0e0e0;
    border: 1px solid #00BFFF;
    border-radius: 3px;
    padding: 3px 6px;
}
QDateEdit::drop-down {
    border: none;
}
QPushButton {
    background-color: #0f3460;
    color: #e0e0e0;
    border: 1px solid #00BFFF;
    border-radius: 4px;
    padding: 5px 14px;
}
QPushButton:hover {
    background-color: #00BFFF;
    color: #0d0d1a;
}
"""

_TEMPLATE_LIST_QSS = """
QListWidget {
    border: 1px solid #00BFFF;
    border-radius: 5px;
    background-color: #16213e;
    color: #b0c4de;
}
QListWidget::item {
    padding: 10px;
    border-bottom: 1px solid #0f3460;
    color: #b0c4de;
}
QListWidget::item:selected {
    background-color: #00BFFF;
    color: #0d0d1a;
    font-weight: bold;
}
QListWidget::item:hover:!selected {
    background-color: #0f3460;
    color: #ffffff;
}
"""


def _patched_template_dialog_init(self, parent=None):
    _orig_template_dialog_init(self, parent)
    self.setStyleSheet(_TEMPLATE_DIALOG_QSS)
    if hasattr(self, "template_list"):
        self.template_list.setStyleSheet(_TEMPLATE_LIST_QSS)
    if hasattr(self, "info_label"):
        self.info_label.setStyleSheet("color: #b0c4de;")


try:
    from app.ui.gantt_window import TemplateDialog as _TD
    _orig_template_dialog_init = _TD.__init__
    _TD.__init__ = _patched_template_dialog_init
except Exception:
    pass  # Modül yüklenemezse patch atlanır
