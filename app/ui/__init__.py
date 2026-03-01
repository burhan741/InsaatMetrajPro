"""
UI Package
Kullanıcı arayüzü modülleri
"""

import copy as _copy
import math as _math


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


# ── GanttWindow Tab Arka Plan: Koyu Tema ──────────────────────────────────
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


def _gantt_snapshot(gantt):
    """Şu anki engine durumunun anlık görüntüsünü (deepcopy) al."""
    return {
        'tasks': _copy.deepcopy(gantt.engine.tasks),
        'next_task_id': gantt.next_task_id,
    }


def _gantt_commit_undo(gantt, snap):
    """Önceden alınmış snapshot'ı undo stack'e ekle ve butonu güncelle."""
    if not hasattr(gantt, '_undo_stack'):
        return
    gantt._undo_stack.append(snap)
    if len(gantt._undo_stack) > 20:
        gantt._undo_stack.pop(0)
    if hasattr(gantt, '_undo_btn') and gantt._undo_btn is not None:
        gantt._undo_btn.setEnabled(True)
        gantt._undo_btn.setText(f"↩ Geri Al ({len(gantt._undo_stack)})")


def _gantt_setup_undo(gantt):
    """Undo altyapısını kur: stack, Ctrl+Z kısayolu, '↩ Geri Al' butonu.

    NOT: İş ekleme/düzenleme/silme undo mantığı artık sınıf seviyesi
    patch'lerde (_patched_ekle_is_cls vb.) barındırılmaktadır.
    """
    from PyQt6.QtGui import QKeySequence, QShortcut
    from PyQt6.QtWidgets import QPushButton

    gantt._undo_stack = []
    gantt._undo_btn = None

    # Ctrl+Z kısayolu
    sc = QShortcut(QKeySequence("Ctrl+Z"), gantt)
    sc.activated.connect(lambda: _gantt_undo(gantt))

    # "↩ Geri Al" butonunu btn_layout'a ekle
    try:
        from PyQt6.QtWidgets import QHBoxLayout
        if not hasattr(gantt, 'is_table'):
            return
        grp = gantt.is_table.parent()        # QGroupBox
        grp_layout = grp.layout()            # QVBoxLayout
        item0 = grp_layout.itemAt(0)         # btn_layout item
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


# ── Miktar & Ekip Sistemi ───────────────────────────────────────────────────

# Patch'lar arası veri köprüsü: get_task_data() → ekle_is / duzenle_is
_LAST_TASK_DIALOG_EXTRA = {}

# Verimlilik tablosu: (iş tipi adı, verimlilik değeri, miktar birimi)
# Kaynak: Çevre, Şehircilik ve İklim Değişikliği Bakanlığı Birim Fiyat Analizleri
# Verimlilik = 1 / (usta.gün/birim)  →  birim/gün/usta
# Birim, preset seçildiğinde Miktar birim combo'suna otomatik yazılır.
_VERIMLILIK_TABLOSU = [
    # ── KALIP İŞLERİ ────────────────────────────────────────────────────
    # Analiz: ~0.45 usta.gün/m² (kolon/kiriş/döşeme ortalama)
    ("Kalıp Çakma (Ahşap)",   2.22,  'm²'),  # 1/0.45 ≈ 2.22 m²/gün/usta
    # Analiz: ~0.20 usta.gün/m² (sökme çakmanın yarısı)
    ("Kalıp Sökme",           5.0,   'm²'),  # 1/0.20 = 5 m²/gün/usta
    # ── DEMİR İŞLERİ ────────────────────────────────────────────────────
    # Analiz: ~0.015 usta.gün/kg → bükme+kesme+bağlama dahil
    ("Demir Bağlama/Bükme",  66.7,   'kg'),  # 1/0.015 ≈ 67 kg/gün/usta
    # ── BETON İŞLERİ ────────────────────────────────────────────────────
    # Analiz: ~0.5 usta.gün/m³ (hazır beton + vibrasyon)
    ("Beton Dökme",           2.0,   'm³'),  # 1/0.5 = 2 m³/gün/usta
    # ── SIVAIŞLER ────────────────────────────────────────────────────────
    # Analiz: ~0.04 usta.gün/m² iç sıva
    ("İç Sıva",              25.0,   'm²'),  # 1/0.04 = 25 m²/gün/usta
    # Analiz: ~0.05 usta.gün/m² dış sıva (iskele gecikmesi dahil)
    ("Dış Sıva",             20.0,   'm²'),  # 1/0.05 = 20 m²/gün/usta
    # ── BOYA ─────────────────────────────────────────────────────────────
    # Analiz: ~0.022 usta.gün/m² (2 kat iç boya)
    ("Boya (İç, 2 kat)",     45.0,   'm²'),  # 1/0.022 ≈ 45 m²/gün/usta
    ("Boya (Dış, Cephe)",    30.0,   'm²'),  # iskele+hazırlık dahil
    # ── KAPLAMA ──────────────────────────────────────────────────────────
    # Analiz: ~0.12 usta.gün/m²
    ("Fayans/Seramik",        8.0,   'm²'),  # 1/0.12 ≈ 8 m²/gün/usta
    ("Mermer/Granit",         4.0,   'm²'),  # ağır plaka, detaylı kesim
    ("Parke (Laminat)",      25.0,   'm²'),  # hızlı döşeme
    ("Parke (Ahşap)",        15.0,   'm²'),  # zımpara+cila dahil
    # ── YALITIM ──────────────────────────────────────────────────────────
    # Analiz: ~0.10 usta.gün/m²
    ("Mantolama (XPS/EPS)",  10.0,   'm²'),  # 1/0.10 = 10 m²/gün/usta
    ("Su Yalıtımı",           8.0,   'm²'),  # membran+şap dahil
    # ── KAGİR / DUVAR ────────────────────────────────────────────────────
    ("Tuğla Duvar",           4.5,   'm²'),  # 1/0.22 ≈ 4.5 m²/gün/usta
    ("Gazbeton Duvar",        6.0,   'm²'),  # hafif blok, hızlı
    ("Alçıpan",              15.0,   'm²'),  # profil+panel
    # ── DOĞRAMA ──────────────────────────────────────────────────────────
    ("Kapı Montajı",          2.0,   'adet'),# 2 kapı/gün/usta
    ("Pencere Montajı",       3.0,   'adet'),# 3 pencere/gün/usta
    # ── TESİSAT ──────────────────────────────────────────────────────────
    ("Su Tesisatı (PPR)",     8.0,   'm'),   # kaynaklı boru
    ("Elektrik (Kablo)",     20.0,   'm'),   # döşeme+bağlama
    # ── KAZI/TOPRAK ──────────────────────────────────────────────────────
    ("Kazı (Elle)",           3.0,   'm³'),  # 1/0.33 ≈ 3 m³/gün/usta
    ("Kazı (Makine/Kepçe)", 200.0,   'm³'),  # operatör başına
]


def _add_miktar_ekip_section(dlg):
    """TaskDialog'a Miktar & Ekip bölümü ekle (monkey-patch yardımcısı)."""
    from PyQt6.QtWidgets import (
        QGroupBox, QFormLayout, QDoubleSpinBox, QComboBox,
        QSpinBox, QPushButton, QLabel, QHBoxLayout,
    )

    grp = QGroupBox("Miktar & Ekip  —  Otomatik Süre Hesabı")
    grp.setStyleSheet(
        "QGroupBox {"
        "  color: #00BFFF; font-weight: bold;"
        "  border: 1px solid #00BFFF; border-radius: 5px; margin-top: 8px;"
        "}"
        "QGroupBox::title { subcontrol-origin: margin; left: 8px; color: #00BFFF; }"
    )
    f = QFormLayout()
    f.setSpacing(6)

    # ── Miktar ──────────────────────────────────────────
    dlg._miktar_spin = QDoubleSpinBox()
    dlg._miktar_spin.setRange(0.0, 999999.0)
    dlg._miktar_spin.setDecimals(2)
    dlg._miktar_spin.setValue(0.0)

    dlg._miktar_birim_combo = QComboBox()
    for b in ['m²', 'm³', 'm', 'adet', 'kg', 'ton']:
        dlg._miktar_birim_combo.addItem(b)

    mik_row = QHBoxLayout()
    mik_row.addWidget(dlg._miktar_spin, 3)
    mik_row.addWidget(dlg._miktar_birim_combo, 1)
    f.addRow("Miktar:", mik_row)

    # ── Ekip ────────────────────────────────────────────
    dlg._usta_spin = QSpinBox()
    dlg._usta_spin.setRange(1, 50)
    dlg._usta_spin.setValue(1)

    dlg._yardimci_spin = QSpinBox()
    dlg._yardimci_spin.setRange(0, 50)
    dlg._yardimci_spin.setValue(0)

    ekip_row = QHBoxLayout()
    ekip_row.addWidget(QLabel("Usta:"))
    ekip_row.addWidget(dlg._usta_spin)
    ekip_row.addSpacing(12)
    ekip_row.addWidget(QLabel("Yardımcı:"))
    ekip_row.addWidget(dlg._yardimci_spin)
    ekip_row.addStretch()
    f.addRow("Ekip:", ekip_row)

    # ── Verimlilik ──────────────────────────────────────
    dlg._verim_preset_combo = QComboBox()
    dlg._verim_preset_combo.addItem("-- İş Tipi Seç (Opsiyonel) --", None)
    for name, val, birim in _VERIMLILIK_TABLOSU:
        dlg._verim_preset_combo.addItem(
            f"{name}  —  {val} {birim}/gün/usta", (val, birim)
        )

    dlg._verim_spin = QDoubleSpinBox()
    dlg._verim_spin.setRange(0.0, 99999.0)
    dlg._verim_spin.setDecimals(2)
    dlg._verim_spin.setValue(0.0)
    dlg._verim_spin.setSuffix("  birim/gün/usta")

    def _on_preset_changed(_idx):
        data = dlg._verim_preset_combo.currentData()
        if data:
            val, birim = data
            dlg._verim_spin.setValue(float(val))
            dlg._verim_spin.setSuffix(f"  {birim}/gün/usta")
            # Miktar birimini otomatik eşleştir
            birim_idx = dlg._miktar_birim_combo.findText(birim)
            if birim_idx >= 0:
                dlg._miktar_birim_combo.setCurrentIndex(birim_idx)

    dlg._verim_preset_combo.currentIndexChanged.connect(_on_preset_changed)
    f.addRow("İş Tipi:", dlg._verim_preset_combo)
    f.addRow("Verimlilik:", dlg._verim_spin)

    # ── Otomatik Hesapla butonu ──────────────────────────
    dlg._sure_sonuc_label = QLabel("—")
    dlg._sure_sonuc_label.setStyleSheet(
        "color: #2ecc71; font-weight: bold; font-size: 10pt;"
    )

    hesapla_btn = QPushButton("🔄  Süreyi Otomatik Hesapla")
    hesapla_btn.setStyleSheet(
        "background-color: #1a6e3c; color: white; "
        "padding: 4px 10px; border-radius: 3px; font-weight: bold;"
    )

    def _on_hesapla():
        miktar = dlg._miktar_spin.value()
        verim = dlg._verim_spin.value()
        usta = dlg._usta_spin.value()
        if miktar > 0 and verim > 0 and usta > 0:
            sure = int(_math.ceil(miktar / (verim * usta)))
            sure = max(1, sure)
            if hasattr(dlg, 'sure_input'):
                dlg.sure_input.setValue(sure)
            birim = dlg._miktar_birim_combo.currentText()
            dlg._sure_sonuc_label.setText(
                f"✓  {miktar:.1f} {birim} ÷ ({verim}×{usta}) = {sure} gün"
            )
        else:
            dlg._sure_sonuc_label.setText("Miktar ve Verimlilik giriniz")

    hesapla_btn.clicked.connect(_on_hesapla)

    btn_row = QHBoxLayout()
    btn_row.addWidget(hesapla_btn)
    btn_row.addWidget(dlg._sure_sonuc_label)
    btn_row.addStretch()
    f.addRow("", btn_row)

    grp.setLayout(f)

    # Ana layout'a button box'tan hemen önce ekle
    main_layout = dlg.layout()
    if main_layout:
        pos = max(0, main_layout.count() - 1)
        main_layout.insertWidget(pos, grp)

    # Dialog yüksekliğini genişlet
    dlg.resize(dlg.width(), dlg.height() + 240)


def _patched_task_dialog_init(self, parent=None, task=None, db=None, parent_tasks=None):
    """TaskDialog.__init__ patch: Miktar & Ekip bölümünü ekle."""
    _orig_task_dialog_init(self, parent=parent, task=task, db=db, parent_tasks=parent_tasks)
    try:
        _add_miktar_ekip_section(self)
    except Exception:
        pass


def _patched_get_task_data(self):
    """TaskDialog.get_task_data patch: ekstra alanları _LAST_TASK_DIALOG_EXTRA'ya yaz."""
    data = _orig_get_task_data(self)
    _LAST_TASK_DIALOG_EXTRA.clear()
    if hasattr(self, '_miktar_spin'):
        _LAST_TASK_DIALOG_EXTRA['miktar'] = self._miktar_spin.value()
        _LAST_TASK_DIALOG_EXTRA['miktar_birim'] = self._miktar_birim_combo.currentText()
        _LAST_TASK_DIALOG_EXTRA['usta_sayisi'] = self._usta_spin.value()
        _LAST_TASK_DIALOG_EXTRA['yardimci_sayisi'] = self._yardimci_spin.value()
        _LAST_TASK_DIALOG_EXTRA['verimlilik'] = self._verim_spin.value()
    return data


def _patched_load_task_data(self):
    """TaskDialog.load_task_data patch: ekstra alanları forma yükle."""
    _orig_load_task_data(self)
    if not self.task or not hasattr(self, '_miktar_spin'):
        return
    self._miktar_spin.setValue(getattr(self.task, 'miktar', 0.0))
    birim = getattr(self.task, 'miktar_birim', 'm²')
    idx = self._miktar_birim_combo.findText(birim)
    if idx >= 0:
        self._miktar_birim_combo.setCurrentIndex(idx)
    self._usta_spin.setValue(getattr(self.task, 'usta_sayisi', 1))
    self._yardimci_spin.setValue(getattr(self.task, 'yardimci_sayisi', 0))
    self._verim_spin.setValue(getattr(self.task, 'verimlilik', 0.0))


# ── GanttWindow Sınıf Seviyesi Patch'leri ──────────────────────────────────

def _patched_ekle_is_cls(self):
    """GanttWindow.ekle_is: undo destekli, Miktar+Ekip alanlarıyla."""
    from PyQt6.QtWidgets import QDialog, QMessageBox
    try:
        from app.ui.gantt_window import TaskDialog
        from app.core.gantt_engine import Task
    except Exception:
        return

    dialog = TaskDialog(self, db=self.db)
    # Snapshot'ı dialogdan önce al; kullanıcı kabul ederse commit ederiz
    snap = _gantt_snapshot(self)

    if dialog.exec() != QDialog.DialogCode.Accepted:
        return  # İptal — snapshot'ı atmıyoruz (commit edilmedi)

    data = dialog.get_task_data()   # _LAST_TASK_DIALOG_EXTRA'yı doldurur

    task = Task(
        task_id=self.next_task_id,
        ad=data['ad'],
        sure_gun=data['sure_gun'],
        kaynak=data['kaynak'],
        milestone=data['milestone'],
        aciklama=data['aciklama'],
        metraj_kalem_id=data['metraj_kalem_id'],
    )

    # Miktar & Ekip alanlarını task nesnesine ekle
    task.miktar = _LAST_TASK_DIALOG_EXTRA.get('miktar', 0.0)
    task.miktar_birim = _LAST_TASK_DIALOG_EXTRA.get('miktar_birim', 'm²')
    task.usta_sayisi = _LAST_TASK_DIALOG_EXTRA.get('usta_sayisi', 1)
    task.yardimci_sayisi = _LAST_TASK_DIALOG_EXTRA.get('yardimci_sayisi', 0)
    task.verimlilik = _LAST_TASK_DIALOG_EXTRA.get('verimlilik', 0.0)

    _gantt_commit_undo(self, snap)
    self.engine.add_task(task)
    self.next_task_id += 1
    self.yukle_is_listesi()
    QMessageBox.information(self, "Başarılı", f"İş eklendi: {task.ad}")


def _patched_duzenle_is_cls(self):
    """GanttWindow.duzenle_is: undo destekli, Miktar+Ekip güncellemesiyle."""
    from PyQt6.QtWidgets import QDialog, QMessageBox
    try:
        from app.ui.gantt_window import TaskDialog
    except Exception:
        return

    selected = self.is_table.selectedItems()
    if not selected:
        QMessageBox.warning(self, "Uyarı", "Lütfen düzenlemek için bir iş seçin")
        return

    row = selected[0].row()
    task_id = int(self.is_table.item(row, 0).text())

    if task_id not in self.engine.tasks:
        QMessageBox.warning(self, "Hata", "İş bulunamadı")
        return

    task = self.engine.tasks[task_id]
    snap = _gantt_snapshot(self)
    dialog = TaskDialog(self, task=task, db=self.db)

    if dialog.exec() != QDialog.DialogCode.Accepted:
        return  # İptal

    data = dialog.get_task_data()   # _LAST_TASK_DIALOG_EXTRA doldurulur

    task.ad = data['ad']
    task.sure_gun = data['sure_gun']
    task.kaynak = data['kaynak']
    task.milestone = data['milestone']
    task.aciklama = data['aciklama']
    task.metraj_kalem_id = data['metraj_kalem_id']

    # Miktar & Ekip güncelle (mevcut değer fallback olarak kullan)
    task.miktar = _LAST_TASK_DIALOG_EXTRA.get(
        'miktar', getattr(task, 'miktar', 0.0))
    task.miktar_birim = _LAST_TASK_DIALOG_EXTRA.get(
        'miktar_birim', getattr(task, 'miktar_birim', 'm²'))
    task.usta_sayisi = _LAST_TASK_DIALOG_EXTRA.get(
        'usta_sayisi', getattr(task, 'usta_sayisi', 1))
    task.yardimci_sayisi = _LAST_TASK_DIALOG_EXTRA.get(
        'yardimci_sayisi', getattr(task, 'yardimci_sayisi', 0))
    task.verimlilik = _LAST_TASK_DIALOG_EXTRA.get(
        'verimlilik', getattr(task, 'verimlilik', 0.0))

    _gantt_commit_undo(self, snap)
    self.yukle_is_listesi()
    QMessageBox.information(self, "Başarılı", "İş güncellendi")


def _patched_sil_is_cls(self):
    """GanttWindow.sil_is: undo destekli."""
    from PyQt6.QtWidgets import QMessageBox

    selected = self.is_table.selectedItems()
    if not selected:
        QMessageBox.warning(self, "Uyarı", "Lütfen silmek için bir iş seçin")
        return

    row = selected[0].row()
    task_id = int(self.is_table.item(row, 0).text())

    if task_id not in self.engine.tasks:
        return

    reply = QMessageBox.question(
        self, "Onay",
        f"'{self.engine.tasks[task_id].ad}' işini silmek istediğinizden emin misiniz?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    )

    if reply == QMessageBox.StandardButton.Yes:
        snap = _gantt_snapshot(self)
        del self.engine.tasks[task_id]
        _gantt_commit_undo(self, snap)
        self.yukle_is_listesi()
        QMessageBox.information(self, "Başarılı", "İş silindi")


def _patched_ekle_bagimliluk_cls(self):
    """GanttWindow.ekle_bagimliluk: undo destekli."""
    from PyQt6.QtWidgets import QDialog, QMessageBox
    try:
        from app.ui.gantt_window import DependencyDialog
    except Exception:
        return

    if len(self.engine.tasks) < 2:
        QMessageBox.warning(
            self, "Uyarı", "Bağımlılık eklemek için en az 2 iş gerekli"
        )
        return

    snap = _gantt_snapshot(self)
    dialog = DependencyDialog(self, self.engine.tasks)

    if dialog.exec() != QDialog.DialogCode.Accepted:
        return

    data = dialog.get_dependency_data()
    success = self.engine.add_dependency(
        data['onceki_id'], data['sonraki_id'], data['tip'], data['lag']
    )

    if success:
        _gantt_commit_undo(self, snap)
        self.yukle_is_listesi()
        QMessageBox.information(self, "Başarılı", "Bağımlılık eklendi")
    else:
        QMessageBox.warning(
            self, "Hata",
            "Bağımlılık eklenemedi (döngüsel bağımlılık olabilir)"
        )


def _patched_yukle_is_listesi_cls(self):
    """GanttWindow.yukle_is_listesi: 8 sütunlu (Miktar + Ekip dahil)."""
    from PyQt6.QtWidgets import QTableWidgetItem

    self.is_table.setRowCount(0)

    for task_id, task in self.engine.tasks.items():
        row = self.is_table.rowCount()
        self.is_table.insertRow(row)

        # 0: ID
        self.is_table.setItem(row, 0, QTableWidgetItem(str(task_id)))
        # 1: İş Adı
        self.is_table.setItem(row, 1, QTableWidgetItem(task.ad))
        # 2: Süre (Gün)
        self.is_table.setItem(row, 2, QTableWidgetItem(str(task.sure_gun)))
        # 3: Miktar
        miktar = getattr(task, 'miktar', 0.0)
        birim = getattr(task, 'miktar_birim', 'm²')
        miktar_str = f"{miktar:.1f} {birim}" if miktar > 0 else "—"
        self.is_table.setItem(row, 3, QTableWidgetItem(miktar_str))
        # 4: Ekip
        usta = getattr(task, 'usta_sayisi', 1)
        yrd = getattr(task, 'yardimci_sayisi', 0)
        ekip_str = f"{usta}U + {yrd}Y" if yrd > 0 else f"{usta} Usta"
        self.is_table.setItem(row, 4, QTableWidgetItem(ekip_str))
        # 5: Kaynak
        self.is_table.setItem(row, 5, QTableWidgetItem(task.kaynak))
        # 6: Milestone
        self.is_table.setItem(row, 6, QTableWidgetItem("✓" if task.milestone else ""))
        # 7: Bağımlılıklar
        deps = []
        for pred_id, dep_type, _lag in task.predecessors:
            pred_name = (
                self.engine.tasks[pred_id].ad
                if pred_id in self.engine.tasks else f"#{pred_id}"
            )
            deps.append(f"{pred_name} ({dep_type})")
        self.is_table.setItem(row, 7, QTableWidgetItem(
            ", ".join(deps) if deps else "—"
        ))


def _patched_gantt_init(self, *args, **kwargs):
    """GanttWindow.__init__ patch: koyu tema + 8-sütun is_table + undo."""
    _orig_gantt_init(self, *args, **kwargs)

    # Sekme koyu tema
    if hasattr(self, "tab_widget"):
        self.tab_widget.setStyleSheet(_GANTT_TAB_STYLE)

    # ── İş Kalemleri tablosu: 8 sütun + genişlikler ─────────────────────
    if hasattr(self, 'is_table'):
        t = self.is_table
        t.setColumnCount(8)
        t.setHorizontalHeaderLabels([
            "ID", "İş Adı", "Süre (Gün)", "Miktar", "Ekip",
            "Kaynak", "Milestone", "Bağımlılıklar",
        ])
        # Sütun genişlikleri (son sütun stretch ile kalan alanı alır)
        for col, w in enumerate([40, 165, 80, 95, 85, 115, 65]):
            t.setColumnWidth(col, w)
        # Satır yüksekliği + dikey başlığı gizle
        t.verticalHeader().setDefaultSectionSize(28)
        t.verticalHeader().hide()
        # Yatay başlık: tıklanabilir, minimum yükseklik
        t.horizontalHeader().setMinimumSectionSize(40)

    # ── Gantt Chart tablosu: sütun genişlikleri ──────────────────────────
    if hasattr(self, 'gantt_table'):
        g = self.gantt_table
        # "İş Adı", "Başlangıç", "Bitiş", "Süre", "İlerleme", "Float", "Durum", "Kritik"
        for col, w in enumerate([165, 90, 90, 60, 75, 55, 95]):
            g.setColumnWidth(col, w)
        g.verticalHeader().setDefaultSectionSize(28)
        g.verticalHeader().hide()
        g.horizontalHeader().setMinimumSectionSize(40)

    # Undo altyapısı (stack + Ctrl+Z + buton)
    _gantt_setup_undo(self)


# ── TemplateDialog Koyu Tema ─────────────────────────────────────────────────

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
    """TemplateDialog.__init__ patch: koyu tema uygula."""
    _orig_template_dialog_init(self, parent)
    self.setStyleSheet(_TEMPLATE_DIALOG_QSS)
    if hasattr(self, "template_list"):
        self.template_list.setStyleSheet(_TEMPLATE_LIST_QSS)
    if hasattr(self, "info_label"):
        self.info_label.setStyleSheet("color: #b0c4de;")


# ── Tüm Patch'leri Uygula ───────────────────────────────────────────────────

try:
    from app.ui.gantt_window import (
        GanttWindow as _GW,
        TaskDialog as _TskD,
        TemplateDialog as _TmpD,
    )

    # GanttWindow patch'leri
    _orig_gantt_init = _GW.__init__
    _GW.__init__ = _patched_gantt_init
    _GW.ekle_is = _patched_ekle_is_cls
    _GW.duzenle_is = _patched_duzenle_is_cls
    _GW.sil_is = _patched_sil_is_cls
    _GW.ekle_bagimliluk = _patched_ekle_bagimliluk_cls
    _GW.yukle_is_listesi = _patched_yukle_is_listesi_cls

    # TaskDialog patch'leri
    _orig_task_dialog_init = _TskD.__init__
    _orig_get_task_data = _TskD.get_task_data
    _orig_load_task_data = _TskD.load_task_data
    _TskD.__init__ = _patched_task_dialog_init
    _TskD.get_task_data = _patched_get_task_data
    _TskD.load_task_data = _patched_load_task_data

    # TemplateDialog patch'leri
    _orig_template_dialog_init = _TmpD.__init__
    _TmpD.__init__ = _patched_template_dialog_init

except Exception:
    pass  # Modül yüklenemezse tüm patch'ler atlanır
