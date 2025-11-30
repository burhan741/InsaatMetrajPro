"""
Ana Pencere
PyQt6 ile modern kullanıcı arayüzü
"""

from typing import Optional, List, Dict, Any
from pathlib import Path
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QTableWidget, QTableWidgetItem, QTreeWidget, QTreeWidgetItem,
    QPushButton, QFileDialog, QMessageBox, QLabel, QLineEdit,
    QHeaderView, QSplitter, QGroupBox, QFormLayout, QDoubleSpinBox,
    QComboBox, QTextEdit, QDialog, QMenu
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QFont

from app.core.database import DatabaseManager
from app.core.cad_manager import CADManager
from app.core.calculator import Calculator
from app.core.material_calculator import MaterialCalculator
from app.utils.data_loader import (
    initialize_database_data, check_pozlar_loaded,
    initialize_material_data, check_malzemeler_loaded, check_formuller_loaded
)
from app.utils.export_manager import ExportManager
from app.ui.dialogs import MetrajItemDialog


class MainWindow(QMainWindow):
    """Ana uygulama penceresi"""
    
    def __init__(self) -> None:
        """Ana pencereyi başlat"""
        super().__init__()
        
        # Core modüller
        self.db = DatabaseManager()
        self.cad_manager = CADManager()
        self.calculator = Calculator()
        self.material_calculator = MaterialCalculator(self.db)
        self.export_manager = ExportManager()
        
        # UI durumu
        self.current_project_id: Optional[int] = None
        self.current_materials: List[Dict[str, Any]] = []  # Hesaplanan malzemeler
        
        # Arayüzü oluştur
        self.init_ui()
        self.load_projects()
        
        # İlk açılışta pozları kontrol et ve yükle
        self.check_and_load_pozlar()
        
    def init_ui(self) -> None:
        """Arayüzü başlat"""
        self.setWindowTitle("InsaatMetrajPro - İnşaat Metraj Uygulaması")
        self.setGeometry(100, 100, 1400, 900)
        
        # Merkezi widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Ana layout
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        
        # Splitter (bölünmüş pencere)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)
        
        # Sol panel - Proje Ağacı
        self.create_sidebar(splitter)
        
        # Sağ panel - Sekmeli yapı
        self.create_tabs(splitter)
        
        # Splitter oranları
        splitter.setSizes([250, 1150])
        
        # Menü çubuğu
        self.create_menu_bar()
        
        # Durum çubuğu
        self.statusBar().showMessage("Hazır")
        
    def create_sidebar(self, parent: QSplitter) -> None:
        """Sol sidebar'ı oluştur"""
        sidebar_widget = QWidget()
        sidebar_layout = QVBoxLayout(sidebar_widget)
        sidebar_layout.setContentsMargins(5, 5, 5, 5)
        
        # Başlık
        title = QLabel("Projeler")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        sidebar_layout.addWidget(title)
        
        # Proje ağacı
        self.project_tree = QTreeWidget()
        self.project_tree.setHeaderLabel("Projelerim")
        self.project_tree.setRootIsDecorated(True)
        self.project_tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        self.project_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        # Hem tek tıklama hem çift tıklama ile seçim
        self.project_tree.itemClicked.connect(self.on_project_selected)
        self.project_tree.itemDoubleClicked.connect(self.on_project_selected)
        self.project_tree.customContextMenuRequested.connect(self.show_project_context_menu)
        sidebar_layout.addWidget(self.project_tree)
        
        # Butonlar
        btn_layout = QVBoxLayout()
        
        btn_new = QPushButton("Yeni Proje")
        btn_new.clicked.connect(self.new_project)
        btn_layout.addWidget(btn_new)
        
        btn_delete = QPushButton("Proje Sil")
        btn_delete.clicked.connect(self.delete_selected_project)
        btn_delete.setStyleSheet("background-color: #c9184a;")
        btn_layout.addWidget(btn_delete)
        
        btn_refresh = QPushButton("Yenile")
        btn_refresh.clicked.connect(self.load_projects)
        btn_layout.addWidget(btn_refresh)
        
        sidebar_layout.addLayout(btn_layout)
        sidebar_layout.addStretch()
        
        parent.addWidget(sidebar_widget)
        
    def create_tabs(self, parent: QSplitter) -> None:
        """Sekmeli yapıyı oluştur"""
        self.tabs = QTabWidget()
        
        # Sekme 1: Metraj Cetveli
        self.create_metraj_tab()
        
        # Sekme 2: CAD Görüntüleyici/İşleyici
        self.create_cad_tab()
        
        # Sekme 3: Taşeron Analizi
        self.create_taseron_tab()
        
        # Sekme 4: Malzeme Listesi
        self.create_malzeme_tab()
        
        parent.addWidget(self.tabs)
        
    def create_metraj_tab(self) -> None:
        """Metraj Cetveli sekmesini oluştur"""
        tab = QWidget()
        main_layout = QVBoxLayout(tab)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Buton barı
        btn_layout = QHBoxLayout()
        
        btn_add = QPushButton("Kalem Ekle")
        btn_add.clicked.connect(self.add_metraj_item)
        btn_layout.addWidget(btn_add)
        
        btn_edit = QPushButton("Düzenle")
        btn_edit.clicked.connect(self.edit_metraj_item)
        btn_layout.addWidget(btn_edit)
        
        btn_delete = QPushButton("Sil")
        btn_delete.clicked.connect(self.delete_metraj_item)
        btn_layout.addWidget(btn_delete)
        
        btn_layout.addStretch()
        
        # Toplam etiketi
        self.total_label = QLabel("Toplam: 0.00 ₺")
        self.total_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        btn_layout.addWidget(self.total_label)
        
        main_layout.addLayout(btn_layout)
        
        # Splitter: Üstte metraj tablosu, altta malzeme detayları
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Üst panel: Metraj Tablosu
        metraj_widget = QWidget()
        metraj_layout = QVBoxLayout(metraj_widget)
        metraj_layout.setContentsMargins(0, 0, 0, 0)
        
        metraj_title = QLabel("📊 Metraj Cetveli")
        metraj_title.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        metraj_layout.addWidget(metraj_title)
        
        self.metraj_table = QTableWidget()
        self.metraj_table.setColumnCount(7)
        self.metraj_table.setHorizontalHeaderLabels([
            "ID", "Poz No", "Tanım", "Miktar", "Birim", "Birim Fiyat", "Toplam"
        ])
        self.metraj_table.setAlternatingRowColors(True)
        self.metraj_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.metraj_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.metraj_table.horizontalHeader().setStretchLastSection(True)
        self.metraj_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        # Satır seçildiğinde malzeme detaylarını göster
        self.metraj_table.itemSelectionChanged.connect(self.on_metraj_item_selected)
        metraj_layout.addWidget(self.metraj_table)
        
        splitter.addWidget(metraj_widget)
        
        # Alt panel: Malzeme Detayları
        malzeme_widget = QWidget()
        malzeme_layout = QVBoxLayout(malzeme_widget)
        malzeme_layout.setContentsMargins(0, 0, 0, 0)
        
        malzeme_title_layout = QHBoxLayout()
        malzeme_title = QLabel("📦 Seçili İş Kalemi İçin Gereken Malzemeler")
        malzeme_title.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        malzeme_title_layout.addWidget(malzeme_title)
        malzeme_title_layout.addStretch()
        
        # Fire oranı bilgisi
        self.metraj_fire_info = QLabel("")
        self.metraj_fire_info.setStyleSheet("color: #666; font-size: 9pt;")
        malzeme_title_layout.addWidget(self.metraj_fire_info)
        
        malzeme_layout.addLayout(malzeme_title_layout)
        
        self.metraj_malzeme_table = QTableWidget()
        self.metraj_malzeme_table.setColumnCount(5)
        self.metraj_malzeme_table.setHorizontalHeaderLabels([
            "Malzeme Adı", "Miktar", "Birim", "Birim Fiyat", "Toplam"
        ])
        self.metraj_malzeme_table.setAlternatingRowColors(True)
        self.metraj_malzeme_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        # Sadece birim fiyat sütunu düzenlenebilir
        self.metraj_malzeme_table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked | QTableWidget.EditTrigger.SelectedClicked)
        self.metraj_malzeme_table.horizontalHeader().setStretchLastSection(True)
        self.metraj_malzeme_table.setColumnWidth(0, 250)
        self.metraj_malzeme_table.setColumnWidth(1, 120)
        self.metraj_malzeme_table.setColumnWidth(2, 80)
        self.metraj_malzeme_table.setColumnWidth(3, 120)
        self.metraj_malzeme_table.setMinimumHeight(200)
        # Birim fiyat değiştiğinde toplamı güncelle
        self.metraj_malzeme_table.cellChanged.connect(self.on_malzeme_fiyat_changed)
        malzeme_layout.addWidget(self.metraj_malzeme_table)
        
        # Malzeme toplam etiketi
        self.metraj_malzeme_total = QLabel("Toplam: 0.00 ₺")
        self.metraj_malzeme_total.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        malzeme_layout.addWidget(self.metraj_malzeme_total)
        
        splitter.addWidget(malzeme_widget)
        
        # Splitter oranları (üst %60, alt %40)
        splitter.setSizes([400, 300])
        
        main_layout.addWidget(splitter)
        
        self.tabs.addTab(tab, "📊 Metraj Cetveli")
        
    def create_cad_tab(self) -> None:
        """CAD Görüntüleyici sekmesini oluştur"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Dosya seçme bölümü
        file_group = QGroupBox("CAD Dosyası")
        file_layout = QVBoxLayout()
        
        file_btn_layout = QHBoxLayout()
        self.cad_file_label = QLabel("Dosya seçilmedi")
        file_btn_layout.addWidget(self.cad_file_label)
        
        btn_select = QPushButton("Dosya Seç")
        btn_select.clicked.connect(self.select_cad_file)
        file_btn_layout.addWidget(btn_select)
        
        file_layout.addLayout(file_btn_layout)
        
        # Katman seçimi
        layer_layout = QFormLayout()
        self.layer_combo = QComboBox()
        self.layer_combo.setEditable(True)
        layer_layout.addRow("Katman:", self.layer_combo)
        
        btn_calculate = QPushButton("Uzunluk Hesapla")
        btn_calculate.clicked.connect(self.calculate_layer_length)
        layer_layout.addRow("", btn_calculate)
        
        file_layout.addLayout(layer_layout)
        file_group.setLayout(file_layout)
        layout.addWidget(file_group)
        
        # Analiz butonu
        btn_analyze = QPushButton("DXF Dosyasını Analiz Et")
        btn_analyze.clicked.connect(self.analyze_cad_file)
        layout.addWidget(btn_analyze)
        
        # Sonuç alanı
        result_group = QGroupBox("Hesaplama Sonuçları")
        result_layout = QVBoxLayout()
        
        self.cad_result_text = QTextEdit()
        self.cad_result_text.setReadOnly(True)
        self.cad_result_text.setMinimumHeight(300)
        result_layout.addWidget(self.cad_result_text)
        
        result_group.setLayout(result_layout)
        layout.addWidget(result_group)
        
        layout.addStretch()
        
        self.tabs.addTab(tab, "📐 CAD İşleyici")
        
    def create_taseron_tab(self) -> None:
        """Taşeron Analizi sekmesini oluştur"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Buton barı
        btn_layout = QHBoxLayout()
        
        btn_add = QPushButton("Teklif Ekle")
        btn_add.clicked.connect(self.add_taseron_offer)
        btn_layout.addWidget(btn_add)
        
        btn_compare = QPushButton("Karşılaştır")
        btn_compare.clicked.connect(self.compare_offers)
        btn_layout.addWidget(btn_compare)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        # Tablo
        self.taseron_table = QTableWidget()
        self.taseron_table.setColumnCount(6)
        self.taseron_table.setHorizontalHeaderLabels([
            "Firma", "Kalem", "Miktar", "Birim", "Fiyat", "Toplam"
        ])
        self.taseron_table.setAlternatingRowColors(True)
        self.taseron_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.taseron_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.taseron_table)
        
        # Karşılaştırma sonuçları
        self.comparison_label = QLabel("")
        self.comparison_label.setFont(QFont("Arial", 10))
        layout.addWidget(self.comparison_label)
        
        self.tabs.addTab(tab, "💼 Taşeron Analizi")
    
    def create_malzeme_tab(self) -> None:
        """Malzeme Listesi sekmesini oluştur"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Kontrol paneli
        control_group = QGroupBox("Hesaplama Ayarları")
        control_layout = QFormLayout()
        
        # Fire oranı modu
        self.fire_mode_combo = QComboBox()
        self.fire_mode_combo.addItems([
            "Otomatik (Poz Bazlı - Literatür Değerleri)",
            "Manuel (Tüm Pozlar İçin Aynı)"
        ])
        self.fire_mode_combo.currentIndexChanged.connect(self.on_fire_mode_changed)
        control_layout.addRow("Fire Oranı Modu:", self.fire_mode_combo)
        
        # Fire oranı (manuel mod için)
        self.fire_spin = QDoubleSpinBox()
        self.fire_spin.setMinimum(0.0)
        self.fire_spin.setMaximum(50.0)
        self.fire_spin.setValue(5.0)
        self.fire_spin.setSuffix(" %")
        self.fire_spin.setDecimals(2)
        self.fire_spin.setEnabled(False)  # Başlangıçta otomatik mod
        control_layout.addRow("Manuel Fire/Atık Oranı:", self.fire_spin)
        
        # Bilgi etiketi
        self.fire_info_label = QLabel("ℹ️ Otomatik mod: Her poz için Literatür/Kitap değerlerine göre fire oranı kullanılır.")
        self.fire_info_label.setWordWrap(True)
        self.fire_info_label.setStyleSheet("color: #666; font-size: 9pt;")
        control_layout.addRow("", self.fire_info_label)
        
        # Hesapla butonu
        btn_calculate = QPushButton("Malzemeleri Hesapla")
        btn_calculate.clicked.connect(self.calculate_materials)
        control_layout.addRow("", btn_calculate)
        
        control_group.setLayout(control_layout)
        layout.addWidget(control_group)
        
        # Export butonları
        export_group = QGroupBox("Export İşlemleri")
        export_layout = QHBoxLayout()
        
        btn_export_excel = QPushButton("Excel'e Aktar")
        btn_export_excel.clicked.connect(self.export_materials_excel)
        export_layout.addWidget(btn_export_excel)
        
        btn_export_pdf = QPushButton("PDF'e Aktar")
        btn_export_pdf.clicked.connect(self.export_materials_pdf)
        export_layout.addWidget(btn_export_pdf)
        
        btn_export_supplier = QPushButton("Tedarikçi Formatı")
        btn_export_supplier.clicked.connect(self.export_materials_supplier)
        export_layout.addWidget(btn_export_supplier)
        
        export_group.setLayout(export_layout)
        layout.addWidget(export_group)
        
        # Özet bilgiler
        self.material_summary_label = QLabel("Proje seçiniz ve 'Malzemeleri Hesapla' butonuna tıklayınız.")
        self.material_summary_label.setFont(QFont("Arial", 10))
        self.material_summary_label.setWordWrap(True)
        layout.addWidget(self.material_summary_label)
        
        # Malzeme tablosu
        self.material_table = QTableWidget()
        self.material_table.setColumnCount(4)
        self.material_table.setHorizontalHeaderLabels([
            "Malzeme Adı", "Miktar", "Birim", "Poz Bilgisi"
        ])
        self.material_table.setAlternatingRowColors(True)
        self.material_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.material_table.horizontalHeader().setStretchLastSection(True)
        self.material_table.setColumnWidth(0, 300)
        self.material_table.setColumnWidth(1, 150)
        self.material_table.setColumnWidth(2, 100)
        layout.addWidget(self.material_table)
        
        self.tabs.addTab(tab, "📦 Malzeme Listesi")
    
    def on_fire_mode_changed(self, index: int) -> None:
        """Fire oranı modu değiştiğinde"""
        if index == 0:  # Otomatik mod
            self.fire_spin.setEnabled(False)
            self.fire_info_label.setText(
                "ℹ️ Otomatik mod: Her poz için Literatür/Kitap değerlerine göre fire oranı kullanılır.\n"
                "Kaynak: İnşaat Metraj kitapları ve TBDY/TS standartlarına uygun genel kabul görmüş değerler."
            )
        else:  # Manuel mod
            self.fire_spin.setEnabled(True)
            self.fire_info_label.setText(
                "ℹ️ Manuel mod: Tüm pozlar için aynı fire oranı kullanılır.\n"
                "Bu değer poz bazlı otomatik fire oranlarını geçersiz kılar."
            )
    
    def calculate_materials(self) -> None:
        """Proje için malzeme listesini hesapla ve göster"""
        if not self.current_project_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce bir proje seçiniz.")
            return
        
        try:
            # Fire oranı modunu kontrol et
            fire_mode = self.fire_mode_combo.currentIndex()
            fire_orani_override = None
            
            if fire_mode == 1:  # Manuel mod
                fire_yuzde = self.fire_spin.value()
                fire_orani_override = fire_yuzde / 100.0
            
            # Malzemeleri hesapla (poz bazlı otomatik fire oranları kullanılır)
            materials = self.material_calculator.calculate_materials_for_project(
                self.current_project_id, fire_orani_override
            )
            
            if not materials:
                QMessageBox.information(
                    self, "Bilgi", 
                    "Bu proje için malzeme formülü bulunamadı.\n"
                    "Lütfen pozlar için malzeme formülleri tanımlayınız."
                )
                self.material_table.setRowCount(0)
                self.material_summary_label.setText("Malzeme bulunamadı.")
                return
            
            # Tabloyu doldur
            self.material_table.setRowCount(len(materials))
            
            for row, material in enumerate(materials):
                # Malzeme adı
                item = QTableWidgetItem(material.get('malzeme_adi', ''))
                self.material_table.setItem(row, 0, item)
                
                # Miktar
                miktar = material.get('miktar', 0)
                item = QTableWidgetItem(f"{miktar:,.2f}")
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.material_table.setItem(row, 1, item)
                
                # Birim
                item = QTableWidgetItem(material.get('birim', ''))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.material_table.setItem(row, 2, item)
                
                # Poz bilgisi (hangi pozlardan geldiği)
                poz_info = material.get('poz_no', '')
                if poz_info:
                    poz_tanim = material.get('poz_tanim', '')
                    poz_miktar = material.get('poz_miktar', 0)
                    poz_birim = material.get('poz_birim', '')
                    poz_info = f"{poz_info} ({poz_tanim[:30]}... - {poz_miktar} {poz_birim})"
                item = QTableWidgetItem(poz_info)
                self.material_table.setItem(row, 3, item)
            
            # Hesaplanan malzemeleri sakla (export için)
            self.current_materials = materials
            
            # Özet bilgi
            toplam_cesit = len(materials)
            toplam_miktar = sum(m.get('miktar', 0) for m in materials)
            
            if fire_mode == 0:
                # Otomatik mod - poz bazlı fire oranları kullanıldı
                summary = (
                    f"Toplam {toplam_cesit} farklı malzeme türü hesaplandı.\n"
                    f"Fire oranı: Otomatik (Poz bazlı - Literatür/Kitap değerleri)"
                )
            else:
                # Manuel mod
                summary = (
                    f"Toplam {toplam_cesit} farklı malzeme türü hesaplandı.\n"
                    f"Fire oranı: Manuel %{fire_orani_override*100:.2f} (Tüm pozlar için)"
                )
            self.material_summary_label.setText(summary)
            
            self.statusBar().showMessage(f"Malzeme listesi hesaplandı: {toplam_cesit} çeşit")
            
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Malzeme hesaplanırken bir hata oluştu:\n{str(e)}")
            print(f"Malzeme hesaplama hatası: {e}")
    
    def export_materials_excel(self) -> None:
        """Malzeme listesini Excel'e export et"""
        if not self.current_materials:
            QMessageBox.warning(self, "Uyarı", "Önce malzeme listesini hesaplayınız.")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Excel'e Kaydet", "", "Excel Dosyaları (*.xlsx)"
        )
        
        if file_path:
            proje = self.db.get_project(self.current_project_id) if self.current_project_id else None
            proje_adi = proje.get('ad', '') if proje else ''
            
            if self.export_manager.export_to_excel(self.current_materials, Path(file_path), proje_adi):
                QMessageBox.information(self, "Başarılı", f"Malzeme listesi Excel'e aktarıldı:\n{file_path}")
                self.statusBar().showMessage(f"Excel export tamamlandı: {file_path}")
            else:
                QMessageBox.critical(self, "Hata", "Excel export sırasında bir hata oluştu.")
    
    def export_materials_pdf(self) -> None:
        """Malzeme listesini PDF'e export et"""
        if not self.current_materials:
            QMessageBox.warning(self, "Uyarı", "Önce malzeme listesini hesaplayınız.")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "PDF'e Kaydet", "", "PDF Dosyaları (*.pdf)"
        )
        
        if file_path:
            proje = self.db.get_project(self.current_project_id) if self.current_project_id else None
            proje_adi = proje.get('ad', '') if proje else ''
            fire_orani = self.fire_spin.value() / 100.0
            
            if self.export_manager.export_to_pdf(self.current_materials, Path(file_path), proje_adi, fire_orani):
                QMessageBox.information(self, "Başarılı", f"Malzeme listesi PDF'e aktarıldı:\n{file_path}")
                self.statusBar().showMessage(f"PDF export tamamlandı: {file_path}")
            else:
                QMessageBox.critical(self, "Hata", "PDF export sırasında bir hata oluştu.")
    
    def export_materials_supplier(self) -> None:
        """Malzeme listesini tedarikçi formatında export et"""
        if not self.current_materials:
            QMessageBox.warning(self, "Uyarı", "Önce malzeme listesini hesaplayınız.")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Tedarikçi Formatına Kaydet", "", "Metin Dosyaları (*.txt)"
        )
        
        if file_path:
            if self.export_manager.export_supplier_format(self.current_materials, Path(file_path)):
                QMessageBox.information(self, "Başarılı", f"Malzeme listesi tedarikçi formatına aktarıldı:\n{file_path}")
                self.statusBar().showMessage(f"Tedarikçi format export tamamlandı: {file_path}")
            else:
                QMessageBox.critical(self, "Hata", "Export sırasında bir hata oluştu.")
        
    def create_menu_bar(self) -> None:
        """Menü çubuğunu oluştur"""
        menubar = self.menuBar()
        
        # Dosya menüsü
        file_menu = menubar.addMenu("Dosya")
        
        # Yeni proje
        new_action = file_menu.addAction("Yeni Proje")
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self.new_project)
        
        # Proje aç
        open_action = file_menu.addAction("Proje Aç")
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_project)
        
        file_menu.addSeparator()
        
        # Çıkış
        exit_action = file_menu.addAction("Çıkış")
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        
        # Veri menüsü
        data_menu = menubar.addMenu("Veri")
        load_pozlar_action = data_menu.addAction("Pozları Yükle")
        load_pozlar_action.triggered.connect(self.load_pozlar)
        data_menu.addSeparator()
        check_pozlar_action = data_menu.addAction("Poz Durumunu Kontrol Et")
        check_pozlar_action.triggered.connect(self.check_pozlar_status)
        
        # Yardım menüsü
        help_menu = menubar.addMenu("Yardım")
        about_action = help_menu.addAction("Hakkında")
        about_action.triggered.connect(self.show_about)
        
    # Proje İşlemleri
    def load_projects(self) -> None:
        """Projeleri yükle"""
        self.project_tree.clear()
        projects = self.db.get_all_projects()
        
        for project in projects:
            item = QTreeWidgetItem(self.project_tree)
            item.setText(0, project['ad'])
            item.setData(0, Qt.ItemDataRole.UserRole, project['id'])
            
    def on_project_selected(self, item: QTreeWidgetItem, column: int) -> None:
        """Proje seçildiğinde"""
        if not item:
            return
            
        project_id = item.data(0, Qt.ItemDataRole.UserRole)
        if project_id:
            self.current_project_id = project_id
            # Projeyi seçili olarak işaretle
            self.project_tree.setCurrentItem(item)
            # Verileri yükle
            self.load_metraj_data()
            self.load_taseron_data()
            self.statusBar().showMessage(f"Proje seçildi: {item.text(0)}")
        else:
            self.statusBar().showMessage("Geçersiz proje seçimi")
            
    def new_project(self) -> None:
        """Yeni proje oluştur"""
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(
            self, "Yeni Proje", "Proje Adı:"
        )
        if ok and name:
            project_id = self.db.create_project(name)
            if project_id:
                self.load_projects()
                # Yeni oluşturulan projeyi otomatik seç
                for i in range(self.project_tree.topLevelItemCount()):
                    item = self.project_tree.topLevelItem(i)
                    if item and item.data(0, Qt.ItemDataRole.UserRole) == project_id:
                        self.project_tree.setCurrentItem(item)
                        self.on_project_selected(item, 0)
                        break
                self.statusBar().showMessage(f"Yeni proje oluşturuldu ve seçildi: {name}")
                
    def open_project(self) -> None:
        """Proje aç (şimdilik bilgi mesajı)"""
        QMessageBox.information(
            self, "Bilgi", "Proje açma özelliği yakında eklenecek"
        )
        
    def show_project_context_menu(self, position) -> None:
        """Proje ağacında sağ tıklama menüsü"""
        item = self.project_tree.itemAt(position)
        if not item:
            return
            
        menu = QMenu(self)
        
        # Proje seç
        select_action = menu.addAction("Projeyi Seç")
        select_action.triggered.connect(lambda: self.on_project_selected(item, 0))
        
        menu.addSeparator()
        
        # Proje sil
        delete_action = menu.addAction("Projeyi Sil")
        delete_action.triggered.connect(lambda: self.delete_project(item))
        delete_action.setStyleSheet("color: #c9184a;")
        
        menu.exec(self.project_tree.mapToGlobal(position))
        
    def delete_selected_project(self) -> None:
        """Seçili projeyi sil"""
        current_item = self.project_tree.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Uyarı", "Lütfen silmek için bir proje seçin")
            return
            
        self.delete_project(current_item)
        
    def delete_project(self, item: QTreeWidgetItem) -> None:
        """Projeyi sil"""
        if not item:
            return
            
        project_id = item.data(0, Qt.ItemDataRole.UserRole)
        project_name = item.text(0)
        
        if not project_id:
            QMessageBox.warning(self, "Uyarı", "Geçersiz proje seçimi")
            return
            
        # Onay dialogu
        reply = QMessageBox.question(
            self, "Proje Silme Onayı",
            f"'{project_name}' projesini silmek istediğinize emin misiniz?\n\n"
            "⚠️ UYARI: Bu işlem geri alınamaz!\n"
            "Projeye ait tüm metraj kalemleri ve taşeron teklifleri de silinecektir.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                if self.db.delete_project(project_id):
                    # Eğer silinen proje seçiliyse, seçimi temizle
                    if self.current_project_id == project_id:
                        self.current_project_id = None
                        self.metraj_table.setRowCount(0)
                        self.taseron_table.setRowCount(0)
                        self.total_label.setText("Toplam: 0.00 ₺")
                        
                    # Proje listesini yenile
                    self.load_projects()
                    self.statusBar().showMessage(f"Proje silindi: {project_name}")
                else:
                    QMessageBox.warning(self, "Uyarı", "Proje silinirken bir hata oluştu")
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Proje silinirken hata oluştu:\n{str(e)}")
        
    # Metraj İşlemleri
    def load_metraj_data(self) -> None:
        """Metraj verilerini yükle"""
        if not self.current_project_id:
            return
            
        items = self.db.get_project_metraj(self.current_project_id)
        self.metraj_table.setRowCount(len(items))
        
        total = 0.0
        for row, item in enumerate(items):
            self.metraj_table.setItem(row, 0, QTableWidgetItem(str(item['id'])))
            self.metraj_table.setItem(row, 1, QTableWidgetItem(item.get('poz_no', '')))
            self.metraj_table.setItem(row, 2, QTableWidgetItem(item['tanim']))
            self.metraj_table.setItem(row, 3, QTableWidgetItem(str(item['miktar'])))
            self.metraj_table.setItem(row, 4, QTableWidgetItem(item['birim']))
            self.metraj_table.setItem(row, 5, QTableWidgetItem(f"{item['birim_fiyat']:.2f}"))
            self.metraj_table.setItem(row, 6, QTableWidgetItem(f"{item['toplam']:.2f}"))
            total += item['toplam']
            
        self.total_label.setText(f"Toplam: {total:.2f} ₺")
        
        # Seçili satır yoksa malzeme tablosunu temizle
        if self.metraj_table.currentRow() < 0:
            self.metraj_malzeme_table.setRowCount(0)
            self.metraj_malzeme_total.setText("Toplam: 0.00 ₺")
            self.metraj_fire_info.setText("")
    
    def on_metraj_item_selected(self) -> None:
        """Metraj tablosunda bir satır seçildiğinde malzeme detaylarını göster"""
        current_row = self.metraj_table.currentRow()
        
        if current_row < 0:
            self.metraj_malzeme_table.setRowCount(0)
            self.metraj_malzeme_total.setText("Toplam: 0.00 ₺")
            self.metraj_fire_info.setText("")
            return
        
        # Seçili satırdan poz bilgilerini al
        poz_no_item = self.metraj_table.item(current_row, 1)
        miktar_item = self.metraj_table.item(current_row, 3)
        
        if not poz_no_item or not miktar_item:
            self.metraj_malzeme_table.setRowCount(0)
            return
        
        poz_no = poz_no_item.text()
        miktar_text = miktar_item.text()
        
        if not poz_no or not miktar_text:
            self.metraj_malzeme_table.setRowCount(0)
            return
        
        try:
            miktar = float(miktar_text)
            
            # Poz bazlı fire oranını al
            poz = self.db.get_poz(poz_no)
            if not poz:
                self.metraj_malzeme_table.setRowCount(0)
                self.metraj_fire_info.setText("⚠️ Poz bulunamadı")
                return
            
            fire_orani = poz.get('fire_orani', 0.05)
            
            # Malzemeleri hesapla
            materials = self.material_calculator.calculate_materials_for_poz_no(
                poz_no, miktar, fire_orani_override=None  # Poz bazlı fire oranı kullan
            )
            
            if not materials:
                self.metraj_malzeme_table.setRowCount(0)
                self.metraj_fire_info.setText(
                    f"ℹ️ Bu poz için malzeme formülü tanımlanmamış. "
                    f"Fire oranı: %{fire_orani*100:.2f}"
                )
                self.metraj_malzeme_total.setText("Toplam: 0.00 ₺")
                return
            
            # Malzeme tablosunu doldur
            self.metraj_malzeme_table.setRowCount(len(materials))
            
            malzeme_total = 0.0
            
            for row, material in enumerate(materials):
                # Malzeme adı
                item = QTableWidgetItem(material.get('malzeme_adi', ''))
                self.metraj_malzeme_table.setItem(row, 0, item)
                
                # Miktar (fire dahil)
                miktar_val = material.get('miktar', 0)
                item = QTableWidgetItem(f"{miktar_val:,.2f}")
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.metraj_malzeme_table.setItem(row, 1, item)
                
                # Birim
                item = QTableWidgetItem(material.get('birim', ''))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.metraj_malzeme_table.setItem(row, 2, item)
                
                # Birim fiyat (veritabanından çek)
                malzeme_id = material.get('malzeme_id')
                birim_fiyat = 0.0
                if malzeme_id:
                    malzeme_info = self.db.get_malzeme(malzeme_id)
                    if malzeme_info:
                        birim_fiyat = malzeme_info.get('birim_fiyat', 0.0)
                
                # Birim fiyat düzenlenebilir olmalı
                item = QTableWidgetItem(f"{birim_fiyat:,.2f}")
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                item.setData(Qt.ItemDataRole.UserRole, malzeme_id)  # Malzeme ID'sini sakla
                item.setData(Qt.ItemDataRole.UserRole + 1, miktar_val)  # Miktarı sakla
                self.metraj_malzeme_table.setItem(row, 3, item)
                
                # Toplam (hesaplanmış)
                toplam = miktar_val * birim_fiyat
                malzeme_total += toplam
                item = QTableWidgetItem(f"{toplam:,.2f} ₺")
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)  # Toplam düzenlenemez
                self.metraj_malzeme_table.setItem(row, 4, item)
            
            # Toplam ve fire bilgisi
            self.metraj_malzeme_total.setText(f"Toplam: {malzeme_total:,.2f} ₺")
            self.metraj_fire_info.setText(
                f"ℹ️ Fire oranı: %{fire_orani*100:.2f} (Poz bazlı - Literatür değeri) | "
                f"İş miktarı: {miktar:,.2f} {poz.get('birim', '')}"
            )
            
        except Exception as e:
            print(f"Malzeme hesaplama hatası: {e}")
            self.metraj_malzeme_table.setRowCount(0)
            self.metraj_fire_info.setText(f"⚠️ Hata: {str(e)}")
    
    def on_malzeme_fiyat_changed(self, row: int, column: int) -> None:
        """Malzeme birim fiyatı değiştiğinde toplamı güncelle"""
        if column != 3:  # Sadece birim fiyat sütunu (3. sütun)
            return
        
        try:
            # Birim fiyatı al
            fiyat_item = self.metraj_malzeme_table.item(row, 3)
            if not fiyat_item:
                return
            
            # Fiyat metnini temizle (₺ işareti ve boşlukları kaldır)
            fiyat_text = fiyat_item.text().replace("₺", "").replace(",", ".").strip()
            birim_fiyat = float(fiyat_text) if fiyat_text else 0.0
            
            # Miktarı al (UserRole + 1'den)
            miktar = fiyat_item.data(Qt.ItemDataRole.UserRole + 1)
            if miktar is None:
                # Miktar sütunundan al
                miktar_item = self.metraj_malzeme_table.item(row, 1)
                if miktar_item:
                    miktar_text = miktar_item.text().replace(",", ".").strip()
                    miktar = float(miktar_text) if miktar_text else 0.0
                else:
                    miktar = 0.0
            
            # Toplamı hesapla
            toplam = miktar * birim_fiyat
            
            # Toplam sütununu güncelle
            toplam_item = QTableWidgetItem(f"{toplam:,.2f} ₺")
            toplam_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            toplam_item.setFlags(toplam_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.metraj_malzeme_table.setItem(row, 4, toplam_item)
            
            # Birim fiyatı formatla (₺ işareti olmadan)
            fiyat_item.setText(f"{birim_fiyat:,.2f}")
            
            # Genel toplamı güncelle
            self.update_malzeme_total()
            
        except (ValueError, TypeError) as e:
            print(f"Fiyat güncelleme hatası: {e}")
    
    def update_malzeme_total(self) -> None:
        """Malzeme tablosundaki toplam maliyeti güncelle"""
        total = 0.0
        for row in range(self.metraj_malzeme_table.rowCount()):
            toplam_item = self.metraj_malzeme_table.item(row, 4)
            if toplam_item:
                toplam_text = toplam_item.text().replace("₺", "").replace(",", ".").strip()
                try:
                    total += float(toplam_text) if toplam_text else 0.0
                except ValueError:
                    pass
        
        self.metraj_malzeme_total.setText(f"Toplam: {total:,.2f} ₺")
        
    def add_metraj_item(self) -> None:
        """Metraj kalemi ekle"""
        if not self.current_project_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce bir proje seçin")
            return
            
        # Dialog penceresini aç
        dialog = MetrajItemDialog(self.db, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            
            # Veritabanına ekle
            try:
                item_id = self.db.add_metraj_kalem(
                    proje_id=self.current_project_id,
                    tanim=data['tanim'],
                    miktar=data['miktar'],
                    birim=data['birim'],
                    birim_fiyat=data['birim_fiyat'],
                    poz_no=data['poz_no'] if data['poz_no'] else '',
                    kategori=data['kategori'] if data['kategori'] else ''
                )
                
                if item_id:
                    self.load_metraj_data()
                    # Yeni kalem eklendikten sonra seçili satırı güncelle
                    if self.metraj_table.rowCount() > 0:
                        self.metraj_table.selectRow(self.metraj_table.rowCount() - 1)
                    self.statusBar().showMessage("Kalem başarıyla eklendi")
                else:
                    QMessageBox.warning(self, "Uyarı", "Kalem eklenirken bir hata oluştu")
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Kalem eklenirken hata oluştu:\n{str(e)}")
        
    def edit_metraj_item(self) -> None:
        """Metraj kalemi düzenle"""
        current_row = self.metraj_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Uyarı", "Lütfen düzenlemek için bir satır seçin")
            return
            
        # Seçili kalemin ID'sini al
        item_id = int(self.metraj_table.item(current_row, 0).text())
        
        # Kalem verilerini getir
        try:
            items = self.db.get_project_metraj(self.current_project_id)
            item_data = next((item for item in items if item['id'] == item_id), None)
            
            if not item_data:
                QMessageBox.warning(self, "Uyarı", "Kalem bulunamadı")
                return
                
            # Dialog penceresini aç
            dialog = MetrajItemDialog(self.db, self, item_data)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                data = dialog.get_data()
                
                # Veritabanını güncelle
                if self.db.update_metraj_kalem(
                    item_id=item_id,
                    tanim=data['tanim'],
                    miktar=data['miktar'],
                    birim=data['birim'],
                    birim_fiyat=data['birim_fiyat'],
                    poz_no=data['poz_no'] if data['poz_no'] else '',
                    kategori=data['kategori'] if data['kategori'] else '',
                    notlar=data['notlar'] if data.get('notlar') else ''
                ):
                    self.load_metraj_data()
                    self.statusBar().showMessage("Kalem başarıyla güncellendi")
                else:
                    QMessageBox.warning(self, "Uyarı", "Kalem güncellenirken bir hata oluştu")
                    
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Kalem düzenlenirken hata oluştu:\n{str(e)}")
            
    def delete_metraj_item(self) -> None:
        """Metraj kalemi sil"""
        current_row = self.metraj_table.currentRow()
        if current_row >= 0:
            reply = QMessageBox.question(
                self, "Onay", "Bu kalemi silmek istediğinize emin misiniz?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                item_id = int(self.metraj_table.item(current_row, 0).text())
                if self.db.delete_item(item_id):
                    self.load_metraj_data()
                    self.statusBar().showMessage("Kalem silindi")
        else:
            QMessageBox.warning(self, "Uyarı", "Lütfen silmek için bir satır seçin")
            
    # CAD İşlemleri
    def select_cad_file(self) -> None:
        """CAD dosyası seç"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "CAD Dosyası Seç", "",
            "DXF Dosyaları (*.dxf);;Tüm Dosyalar (*.*)"
        )
        if file_path:
            self.cad_file_path = Path(file_path)
            self.cad_file_label.setText(self.cad_file_path.name)
            
            # Katmanları yükle
            try:
                layers = self.cad_manager.get_all_layers(self.cad_file_path)
                self.layer_combo.clear()
                self.layer_combo.addItems(layers)
            except Exception as e:
                QMessageBox.warning(self, "Uyarı", f"Katmanlar yüklenemedi: {e}")
                
    def calculate_layer_length(self) -> None:
        """Katman uzunluğunu hesapla"""
        if not hasattr(self, 'cad_file_path'):
            QMessageBox.warning(self, "Uyarı", "Lütfen önce bir CAD dosyası seçin")
            return
            
        layer_name = self.layer_combo.currentText()
        if not layer_name:
            QMessageBox.warning(self, "Uyarı", "Lütfen bir katman seçin")
            return
            
        try:
            length = self.cad_manager.calculate_layer_length(
                self.cad_file_path, layer_name
            )
            length_m = length / 1000.0  # mm'den m'ye
            
            result = f"Katman: {layer_name}\n"
            result += f"Toplam Uzunluk: {length:.2f} mm\n"
            result += f"Toplam Uzunluk: {length_m:.2f} m\n"
            
            self.cad_result_text.setText(result)
            self.statusBar().showMessage(f"Uzunluk hesaplandı: {length_m:.2f} m")
            
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Hesaplama hatası: {e}")
            
    def analyze_cad_file(self) -> None:
        """CAD dosyasını analiz et"""
        if not hasattr(self, 'cad_file_path'):
            QMessageBox.warning(self, "Uyarı", "Lütfen önce bir CAD dosyası seçin")
            return
            
        try:
            items = self.cad_manager.analyze_dxf_for_metraj(self.cad_file_path)
            
            result = "CAD Analiz Sonuçları:\n\n"
            result += f"Toplam {len(items)} kalem bulundu:\n\n"
            
            for item in items:
                result += f"- {item['tanim']}: {item['miktar']:.2f} {item['birim']} "
                result += f"({item['kategori']})\n"
                
            self.cad_result_text.setText(result)
            
            # Projeye ekleme seçeneği
            if self.current_project_id and items:
                reply = QMessageBox.question(
                    self, "Soru",
                    f"{len(items)} kalem bulundu. Projeye eklemek ister misiniz?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.Yes:
                    self.add_cad_items_to_project(items)
                    
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Analiz hatası: {e}")
            
    def add_cad_items_to_project(self, items: List[Dict[str, Any]]) -> None:
        """CAD kalemlerini projeye ekle"""
        for item in items:
            self.db.add_metraj_kalem(
                self.current_project_id,
                item['tanim'],
                item['miktar'],
                item['birim'],
                category=item.get('kategori', '')
            )
        self.load_metraj_data()
        self.statusBar().showMessage(f"{len(items)} kalem projeye eklendi")
        
    # Taşeron İşlemleri
    def load_taseron_data(self) -> None:
        """Taşeron verilerini yükle"""
        if not self.current_project_id:
            return
            
        offers = self.db.get_taseron_teklifleri(self.current_project_id)
        self.taseron_table.setRowCount(len(offers))
        
        for row, offer in enumerate(offers):
            self.taseron_table.setItem(row, 0, QTableWidgetItem(offer['firma_adi']))
            self.taseron_table.setItem(row, 1, QTableWidgetItem(offer.get('tanim', '')))
            self.taseron_table.setItem(row, 2, QTableWidgetItem(str(offer.get('miktar', 0))))
            self.taseron_table.setItem(row, 3, QTableWidgetItem(offer.get('birim', '')))
            self.taseron_table.setItem(row, 4, QTableWidgetItem(f"{offer['fiyat']:.2f}"))
            self.taseron_table.setItem(row, 5, QTableWidgetItem(f"{offer.get('toplam', 0):.2f}"))
            
    def add_taseron_offer(self) -> None:
        """Taşeron teklifi ekle"""
        if not self.current_project_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce bir proje seçin")
            return
            
        # TODO: Dialog penceresi eklenecek
        QMessageBox.information(
            self, "Bilgi", "Teklif ekleme dialogu yakında eklenecek"
        )
        
    def compare_offers(self) -> None:
        """Teklifleri karşılaştır"""
        if not self.current_project_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce bir proje seçin")
            return
            
        offers = self.db.get_taseron_teklifleri(self.current_project_id)
        if not offers:
            QMessageBox.information(self, "Bilgi", "Karşılaştırılacak teklif yok")
            return
            
        comparison = self.calculator.compare_taseron_offers(offers)
        
        result = "Teklif Karşılaştırması:\n\n"
        result += f"Firma Sayısı: {comparison['firma_sayisi']}\n"
        
        if comparison['en_dusuk']:
            result += f"En Düşük: {comparison['en_dusuk']['firma']} - "
            result += f"{comparison['en_dusuk']['tutar']:.2f} ₺\n"
            
        if comparison['en_yuksek']:
            result += f"En Yüksek: {comparison['en_yuksek']['firma']} - "
            result += f"{comparison['en_yuksek']['tutar']:.2f} ₺\n"
            
        result += f"Ortalama: {comparison['ortalama']:.2f} ₺"
        
        self.comparison_label.setText(result)
        
    def check_and_load_pozlar(self) -> None:
        """Uygulama açıldığında pozları kontrol et ve gerekirse yükle"""
        if not check_pozlar_loaded(self.db):
            reply = QMessageBox.question(
                self, "Veri Yükleme",
                "Pozlar henüz yüklenmemiş. Şimdi yüklemek ister misiniz?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.load_pozlar(silent=False)
        
        # Malzeme ve formülleri kontrol et ve yükle
        if not check_malzemeler_loaded(self.db) or not check_formuller_loaded(self.db):
            # Sessizce yükle (kullanıcıya sorma)
            try:
                result = initialize_material_data(self.db, force_reload=False)
                if result['malzemeler']['success'] > 0 or result['formuller']['success'] > 0:
                    self.statusBar().showMessage(
                        f"Malzeme verileri yüklendi: "
                        f"{result['malzemeler']['success']} malzeme, "
                        f"{result['formuller']['success']} formül"
                    )
            except Exception as e:
                print(f"Malzeme yükleme hatası: {e}")
                
    def load_pozlar(self, silent: bool = False) -> None:
        """Pozları veritabanına yükle"""
        try:
            # Mevcut pozlar var mı kontrol et
            if check_pozlar_loaded(self.db) and not silent:
                reply = QMessageBox.question(
                    self, "Onay",
                    "Pozlar zaten yüklü. Yeniden yüklemek istiyor musunuz?\n"
                    "(Mevcut pozlar silinmeyecek, sadece yeni olanlar eklenecek)",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return
            
            # Pozları yükle
            result = initialize_database_data(self.db, force_reload=False)
            
            if not silent:
                if result['pozlar']['success'] > 0:
                    QMessageBox.information(
                        self, "Başarılı",
                        f"✅ {result['pozlar']['success']} poz başarıyla yüklendi!\n\n"
                        f"{result['message']}"
                    )
                    self.statusBar().showMessage(f"{result['pozlar']['success']} poz yüklendi")
                else:
                    QMessageBox.warning(
                        self, "Uyarı",
                        "Pozlar yüklenemedi veya zaten yüklü.\n\n"
                        f"{result['message']}"
                    )
            else:
                self.statusBar().showMessage(result['message'])
                
        except Exception as e:
            QMessageBox.critical(
                self, "Hata",
                f"Pozlar yüklenirken hata oluştu:\n{str(e)}"
            )
            
    def check_pozlar_status(self) -> None:
        """Poz durumunu kontrol et ve göster"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) as count FROM pozlar")
                result = cursor.fetchone()
                count = result['count'] if result else 0
                
                # Kategori bazlı sayılar
                cursor.execute("""
                    SELECT kategori, COUNT(*) as count 
                    FROM pozlar 
                    GROUP BY kategori 
                    ORDER BY kategori
                """)
                categories = cursor.fetchall()
                
                message = f"📊 Poz Durumu:\n\n"
                message += f"Toplam Poz Sayısı: {count}\n\n"
                message += "Kategori Bazında:\n"
                for cat in categories:
                    message += f"  • {cat['kategori']}: {cat['count']} poz\n"
                
                QMessageBox.information(self, "Poz Durumu", message)
                self.statusBar().showMessage(f"Toplam {count} poz mevcut")
                
        except Exception as e:
            QMessageBox.critical(
                self, "Hata",
                f"Poz durumu kontrol edilirken hata oluştu:\n{str(e)}"
            )
            
    def show_about(self) -> None:
        """Hakkında dialogu"""
        QMessageBox.about(
            self, "Hakkında",
            "InsaatMetrajPro v1.0.0\n\n"
            "İnşaat sektörü için profesyonel metraj uygulaması\n"
            "Python ve PyQt6 ile geliştirilmiştir.\n\n"
            "Offline-First yaklaşım ile çalışır.\n\n"
            "Konut yapısı için 150+ iş kalemi içerir."
        )

