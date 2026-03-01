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


# ── Gantt Undo Stack Yardımcıları ──────────────────────────────────────────

import copy as _copy


def _gantt_push_undo(gantt):
    """Mevcut engine.tasks durumunu undo stack'e kaydet (maks 20 adım)."""
    snapshot = {
        'tasks': _copy.deepcopy(gantt.engine.tasks),
        'next_task_id': gantt.next_task_id,
    }
    gantt._undo_stack.append(snapshot)
    if len(gantt._undo_stack) > 20:
        gantt._undo_stack.pop(0)
    if hasattr(gantt, '_undo_btn') and gantt._undo_btn is not None:
        gantt._undo_btn.setEnabled(True)
        gantt._undo_btn.setText(f"↩ Geri Al ({len(gantt._undo_stack)})")


def _gantt_undo(gantt):
    """Son işlemi geri al."""
    if not gantt._undo_stack:
        return
    snapshot = gantt._undo_stack.pop()
    gantt.engine.tasks = snapshot['tasks']
    gantt.next_task_id = snapshot['next_task_id']
    gantt.yukle_is_listesi()
    remaining = len(gantt._undo_stack)
    if hasattr(gantt, '_undo_btn') and gantt._undo_btn is not None:
        gantt._undo_btn.setEnabled(remaining > 0)
        if remaining > 0:
            gantt._undo_btn.setText(f"↩ Geri Al ({remaining})")
        else:
            gantt._undo_btn.setText("↩ Geri Al")


def _gantt_setup_undo(gantt):
    """Undo altyapısını kur: stack, wrapped metodlar, kısayol, buton."""
    from PyQt6.QtGui import QKeySequence
    from PyQt6.QtWidgets import QShortcut, QPushButton

    gantt._undo_stack = []
    gantt._undo_btn = None

    # 1) Mevcut bound metodları sarmalamak için closure'lar
    _orig_ekle = gantt.ekle_is
    _orig_duzenle = gantt.duzenle_is
    _orig_sil = gantt.sil_is
    _orig_bag = gantt.ekle_bagimliluk

    def _w_ekle():
        _gantt_push_undo(gantt)
        _orig_ekle()

    def _w_duzenle():
        _gantt_push_undo(gantt)
        _orig_duzenle()

    def _w_sil():
        _gantt_push_undo(gantt)
        _orig_sil()

    def _w_bag():
        _gantt_push_undo(gantt)
        _orig_bag()

    gantt.ekle_is = _w_ekle
    gantt.duzenle_is = _w_duzenle
    gantt.sil_is = _w_sil
    gantt.ekle_bagimliluk = _w_bag

    # 2) Ctrl+Z kısayolu
    sc = QShortcut(QKeySequence("Ctrl+Z"), gantt)
    sc.activated.connect(lambda: _gantt_undo(gantt))

    # 3) "↩ Geri Al" butonunu btn_layout'a ekle
    #    is_table'ın parent'ı QGroupBox "İş Kalemleri",
    #    onun layout'unun 0. item'ı QHBoxLayout (btn_layout)
    try:
        from PyQt6.QtWidgets import QHBoxLayout
        if not hasattr(gantt, 'is_table'):
            return
        grp = gantt.is_table.parent()       # QGroupBox
        grp_layout = grp.layout()           # QVBoxLayout
        item0 = grp_layout.itemAt(0)        # btn_layout item
        btn_layout = item0.layout() if item0 else None
        if not isinstance(btn_layout, QHBoxLayout):
            return

        undo_btn = QPushButton("↩ Geri Al")
        undo_btn.setEnabled(False)
        undo_btn.setToolTip("Son işlemi geri al  (Ctrl+Z)")
        undo_btn.setStyleSheet(
            "background-color: #6c3483; color: white; "
            "padding: 4px 10px; border-radius: 3px;"
        )
        undo_btn.clicked.connect(lambda: _gantt_undo(gantt))

        # Stretch varsa ondan önce ekle
        stretch_idx = -1
        for i in range(btn_layout.count()):
            item = btn_layout.itemAt(i)
            if item and item.spacerItem() is not None:
                stretch_idx = i
                break
        if stretch_idx >= 0:
            btn_layout.insertWidget(stretch_idx, undo_btn)
        else:
            btn_layout.addWidget(undo_btn)

        gantt._undo_btn = undo_btn
    except Exception:
        pass   # buton eklenemezse sessizce geç (Ctrl+Z yine çalışır)


def _patched_gantt_init(self, *args, **kwargs):
    _orig_gantt_init(self, *args, **kwargs)
    # Koyu tema
    if hasattr(self, "tab_widget"):
        self.tab_widget.setStyleSheet(_GANTT_TAB_STYLE)
    # Undo sistemi
    _gantt_setup_undo(self)


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
