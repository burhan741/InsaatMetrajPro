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
from PyQt6.QtCore import Qt, pyqtSignal, QThread, pyqtSlot
from PyQt6.QtGui import QIcon, QFont

from app.core.database import DatabaseManager
from app.core.calculator import Calculator
from app.core.material_calculator import MaterialCalculator
from app.utils.data_loader import (
    initialize_database_data, check_pozlar_loaded,
    initialize_material_data, check_malzemeler_loaded, check_formuller_loaded
)
from app.utils.export_manager import ExportManager
from app.ui.dialogs import MetrajItemDialog, TaseronOfferDialog


class DataLoaderThread(QThread):
    """Arka planda veri yükleme thread'i"""
    data_loaded = pyqtSignal(dict)
    poz_question_needed = pyqtSignal()
    
    def __init__(self, db: DatabaseManager) -> None:
        super().__init__()
        self.db = db
    
    def run(self) -> None:
        """Thread çalıştığında"""
        result = {
            'malzemeler_loaded': False,
            'formuller_loaded': False,
            'malzeme_count': 0,
            'formul_count': 0
        }
        
        # Pozları kontrol et
        if not check_pozlar_loaded(self.db):
            # Poz yükleme sorusu için sinyal gönder
            self.poz_question_needed.emit()
        else:
            # Malzeme ve formülleri kontrol et ve yükle
            if not check_malzemeler_loaded(self.db) or not check_formuller_loaded(self.db):
                try:
                    material_result = initialize_material_data(self.db, force_reload=False)
                    result['malzemeler_loaded'] = material_result['malzemeler']['success'] > 0
                    result['formuller_loaded'] = material_result['formuller']['success'] > 0
                    result['malzeme_count'] = material_result['malzemeler']['success']
                    result['formul_count'] = material_result['formuller']['success']
                except Exception as e:
                    print(f"Malzeme yükleme hatası: {e}")
            else:
                # Zaten yüklü, sayıları al
                try:
                    with self.db.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT COUNT(*) as count FROM malzemeler")
                        result['malzeme_count'] = cursor.fetchone()['count']
                        cursor.execute("SELECT COUNT(*) as count FROM malzeme_formulleri")
                        result['formul_count'] = cursor.fetchone()['count']
                except Exception as e:
                    print(f"Sayım hatası: {e}")
        
        # Sonucu gönder
        self.data_loaded.emit(result)


class MainWindow(QMainWindow):
    """Ana uygulama penceresi"""
    
    def __init__(self) -> None:
        """Ana pencereyi başlat"""
        super().__init__()
        
        # Core modüller (hafif olanlar hemen yükle)
        self.db = DatabaseManager()
        self.calculator = Calculator()
        self.export_manager = ExportManager()
        
        # Ağır modüller lazy loading ile (sadece gerektiğinde yüklenecek)
        self._material_calculator: Optional[MaterialCalculator] = None
        
        # UI durumu
        self.current_project_id: Optional[int] = None
        self.current_materials: List[Dict[str, Any]] = []  # Hesaplanan malzemeler
        
        # Arayüzü oluştur
        self.init_ui()
        self.load_projects()
        
        # İlk açılışta pozları kontrol et ve yükle (async - arka planda)
        self.check_and_load_pozlar_async()
    
    @property
    def material_calculator(self) -> MaterialCalculator:
        """MaterialCalculator'ı lazy loading ile yükle"""
        if self._material_calculator is None:
            self._material_calculator = MaterialCalculator(self.db)
        return self._material_calculator
        
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
        # Sekme değiştiğinde özeti güncelle
        self.tabs.currentChanged.connect(self.on_tab_changed)
        
        # Sekme 1: Metraj Cetveli
        self.create_metraj_tab()
        
        # Sekme 2: Proje Özeti
        self.create_proje_ozet_tab()
        
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
    
    def create_proje_ozet_tab(self) -> None:
        """Proje Özeti/Rapor sekmesini oluştur"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        
        # Üst panel: Özet kartları
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(10)
        
        # Kart 1: Toplam Kalem
        self.ozet_kalem_card = QGroupBox("Toplam Kalem")
        kalem_layout = QVBoxLayout()
        self.ozet_kalem_label = QLabel("0")
        self.ozet_kalem_label.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        self.ozet_kalem_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ozet_kalem_label.setStyleSheet("color: #c9184a;")
        kalem_layout.addWidget(self.ozet_kalem_label)
        self.ozet_kalem_card.setLayout(kalem_layout)
        self.ozet_kalem_card.setMinimumHeight(100)
        cards_layout.addWidget(self.ozet_kalem_card)
        
        # Kart 2: Toplam Maliyet
        self.ozet_maliyet_card = QGroupBox("Toplam Maliyet (KDV Hariç)")
        maliyet_layout = QVBoxLayout()
        self.ozet_maliyet_label = QLabel("0.00 ₺")
        self.ozet_maliyet_label.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        self.ozet_maliyet_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ozet_maliyet_label.setStyleSheet("color: #4CAF50;")
        maliyet_layout.addWidget(self.ozet_maliyet_label)
        self.ozet_maliyet_card.setLayout(maliyet_layout)
        self.ozet_maliyet_card.setMinimumHeight(100)
        cards_layout.addWidget(self.ozet_maliyet_card)
        
        # Kart 3: KDV Dahil
        self.ozet_kdv_card = QGroupBox("KDV Dahil Toplam")
        kdv_layout = QVBoxLayout()
        self.ozet_kdv_label = QLabel("0.00 ₺")
        self.ozet_kdv_label.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        self.ozet_kdv_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ozet_kdv_label.setStyleSheet("color: #16213e;")
        kdv_layout.addWidget(self.ozet_kdv_label)
        # KDV oranı seçimi
        kdv_rate_layout = QHBoxLayout()
        kdv_rate_layout.addWidget(QLabel("KDV Oranı:"))
        self.ozet_kdv_rate = QComboBox()
        self.ozet_kdv_rate.addItems(["%1", "%10", "%20"])
        self.ozet_kdv_rate.setCurrentText("%20")
        self.ozet_kdv_rate.currentTextChanged.connect(self.update_proje_ozet)
        kdv_rate_layout.addWidget(self.ozet_kdv_rate)
        kdv_rate_layout.addStretch()
        kdv_layout.addLayout(kdv_rate_layout)
        self.ozet_kdv_card.setLayout(kdv_layout)
        self.ozet_kdv_card.setMinimumHeight(100)
        cards_layout.addWidget(self.ozet_kdv_card)
        
        # Kart 4: Taşeron Teklif Sayısı
        self.ozet_taseron_card = QGroupBox("Taşeron Teklifleri")
        taseron_layout = QVBoxLayout()
        self.ozet_taseron_label = QLabel("0")
        self.ozet_taseron_label.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        self.ozet_taseron_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ozet_taseron_label.setStyleSheet("color: #ff9800;")
        taseron_layout.addWidget(self.ozet_taseron_label)
        self.ozet_taseron_card.setLayout(taseron_layout)
        self.ozet_taseron_card.setMinimumHeight(100)
        cards_layout.addWidget(self.ozet_taseron_card)
        
        layout.addLayout(cards_layout)
        
        # Orta panel: Splitter (Kategori dağılımı ve En pahalı kalemler)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Sol: Kategori Dağılımı
        kategori_widget = QWidget()
        kategori_layout = QVBoxLayout(kategori_widget)
        kategori_layout.setContentsMargins(0, 0, 0, 0)
        
        kategori_title = QLabel("📋 Kategori Bazında Dağılım")
        kategori_title.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        kategori_layout.addWidget(kategori_title)
        
        self.ozet_kategori_table = QTableWidget()
        self.ozet_kategori_table.setColumnCount(3)
        self.ozet_kategori_table.setHorizontalHeaderLabels([
            "Kategori", "Kalem Sayısı", "Toplam Maliyet"
        ])
        self.ozet_kategori_table.setAlternatingRowColors(True)
        self.ozet_kategori_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.ozet_kategori_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.ozet_kategori_table.horizontalHeader().setStretchLastSection(True)
        self.ozet_kategori_table.setColumnWidth(0, 200)
        self.ozet_kategori_table.setColumnWidth(1, 120)
        kategori_layout.addWidget(self.ozet_kategori_table)
        
        splitter.addWidget(kategori_widget)
        
        # Sağ: En Pahalı Kalemler
        pahali_widget = QWidget()
        pahali_layout = QVBoxLayout(pahali_widget)
        pahali_layout.setContentsMargins(0, 0, 0, 0)
        
        pahali_title = QLabel("💰 En Pahalı 5 Kalem")
        pahali_title.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        pahali_layout.addWidget(pahali_title)
        
        self.ozet_pahali_table = QTableWidget()
        self.ozet_pahali_table.setColumnCount(3)
        self.ozet_pahali_table.setHorizontalHeaderLabels([
            "Kalem", "Miktar", "Toplam"
        ])
        self.ozet_pahali_table.setAlternatingRowColors(True)
        self.ozet_pahali_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.ozet_pahali_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.ozet_pahali_table.horizontalHeader().setStretchLastSection(True)
        self.ozet_pahali_table.setColumnWidth(0, 250)
        self.ozet_pahali_table.setColumnWidth(1, 100)
        pahali_layout.addWidget(self.ozet_pahali_table)
        
        splitter.addWidget(pahali_widget)
        
        splitter.setSizes([400, 400])
        layout.addWidget(splitter)
        
        # Alt panel: Malzeme ve Taşeron Özeti
        alt_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Malzeme Özeti
        malzeme_ozet_widget = QWidget()
        malzeme_ozet_layout = QVBoxLayout(malzeme_ozet_widget)
        malzeme_ozet_layout.setContentsMargins(0, 0, 0, 0)
        
        malzeme_ozet_title = QLabel("📦 Malzeme Özeti")
        malzeme_ozet_title.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        malzeme_ozet_layout.addWidget(malzeme_ozet_title)
        
        self.ozet_malzeme_label = QLabel("Malzeme listesi hesaplanmadı.\n'Malzeme Listesi' sekmesinden hesaplayınız.")
        self.ozet_malzeme_label.setWordWrap(True)
        self.ozet_malzeme_label.setStyleSheet("color: #666; padding: 10px;")
        malzeme_ozet_layout.addWidget(self.ozet_malzeme_label)
        
        alt_splitter.addWidget(malzeme_ozet_widget)
        
        # Taşeron Özeti
        taseron_ozet_widget = QWidget()
        taseron_ozet_layout = QVBoxLayout(taseron_ozet_widget)
        taseron_ozet_layout.setContentsMargins(0, 0, 0, 0)
        
        taseron_ozet_title = QLabel("💼 Taşeron Özeti")
        taseron_ozet_title.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        taseron_ozet_layout.addWidget(taseron_ozet_title)
        
        self.ozet_taseron_detay_label = QLabel("Taşeron teklif bilgisi yok.")
        self.ozet_taseron_detay_label.setWordWrap(True)
        self.ozet_taseron_detay_label.setStyleSheet("color: #666; padding: 10px;")
        taseron_ozet_layout.addWidget(self.ozet_taseron_detay_label)
        
        alt_splitter.addWidget(taseron_ozet_widget)
        
        alt_splitter.setSizes([400, 400])
        layout.addWidget(alt_splitter)
        
        # Export butonları
        export_layout = QHBoxLayout()
        export_layout.addStretch()
        
        btn_export_pdf = QPushButton("PDF Rapor Oluştur")
        btn_export_pdf.clicked.connect(self.export_proje_ozet_pdf)
        export_layout.addWidget(btn_export_pdf)
        
        btn_export_excel = QPushButton("Excel Rapor Oluştur")
        btn_export_excel.clicked.connect(self.export_proje_ozet_excel)
        export_layout.addWidget(btn_export_excel)
        
        layout.addLayout(export_layout)
        
        self.tabs.addTab(tab, "📈 Proje Özeti")
        
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
        
        btn_edit = QPushButton("Düzenle")
        btn_edit.clicked.connect(self.edit_taseron_offer)
        btn_layout.addWidget(btn_edit)
        
        btn_delete = QPushButton("Sil")
        btn_delete.clicked.connect(self.delete_taseron_offer)
        btn_delete.setStyleSheet("background-color: #c9184a;")
        btn_layout.addWidget(btn_delete)
        
        btn_layout.addStretch()
        
        btn_compare = QPushButton("Karşılaştır")
        btn_compare.clicked.connect(self.compare_offers)
        btn_layout.addWidget(btn_compare)
        
        # Export butonları
        btn_export_excel = QPushButton("Excel'e Aktar")
        btn_export_excel.clicked.connect(self.export_taseron_excel)
        btn_layout.addWidget(btn_export_excel)
        
        btn_export_pdf = QPushButton("PDF'e Aktar")
        btn_export_pdf.clicked.connect(self.export_taseron_pdf)
        btn_layout.addWidget(btn_export_pdf)
        
        layout.addLayout(btn_layout)
        
        # Tablo
        self.taseron_table = QTableWidget()
        self.taseron_table.setColumnCount(7)
        self.taseron_table.setHorizontalHeaderLabels([
            "ID", "Firma", "Kalem", "Miktar", "Birim", "Fiyat", "Toplam"
        ])
        self.taseron_table.setAlternatingRowColors(True)
        self.taseron_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.taseron_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.taseron_table.horizontalHeader().setStretchLastSection(True)
        self.taseron_table.setColumnHidden(0, True)  # ID sütununu gizle
        layout.addWidget(self.taseron_table)
        
        # Karşılaştırma sonuçları (tablo olarak)
        comparison_group = QGroupBox("Teklif Karşılaştırması")
        comparison_layout = QVBoxLayout()
        
        self.comparison_table = QTableWidget()
        self.comparison_table.setColumnCount(4)
        self.comparison_table.setHorizontalHeaderLabels([
            "Firma", "Toplam Tutar", "Durum", "Fark (Ortalamadan)"
        ])
        self.comparison_table.setAlternatingRowColors(True)
        self.comparison_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.comparison_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.comparison_table.horizontalHeader().setStretchLastSection(True)
        self.comparison_table.setMaximumHeight(200)
        comparison_layout.addWidget(self.comparison_table)
        
        self.comparison_summary_label = QLabel("")
        self.comparison_summary_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        comparison_layout.addWidget(self.comparison_summary_label)
        
        comparison_group.setLayout(comparison_layout)
        layout.addWidget(comparison_group)
        
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
            self.update_proje_ozet()  # Özeti güncelle (malzeme bilgisi için)
            
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
            self.update_proje_ozet()
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
                    self.update_proje_ozet()  # Özeti güncelle
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
                    self.update_proje_ozet()  # Özeti güncelle
                    self.statusBar().showMessage("Kalem silindi")
        else:
            QMessageBox.warning(self, "Uyarı", "Lütfen silmek için bir satır seçin")
            
    # Taşeron İşlemleri
    def load_taseron_data(self) -> None:
        """Taşeron verilerini yükle"""
        if not self.current_project_id:
            return
            
        offers = self.db.get_taseron_teklifleri(self.current_project_id)
        self.taseron_table.setRowCount(len(offers))
        
        for row, offer in enumerate(offers):
            # ID (gizli)
            self.taseron_table.setItem(row, 0, QTableWidgetItem(str(offer['id'])))
            # Firma
            self.taseron_table.setItem(row, 1, QTableWidgetItem(offer['firma_adi']))
            # Kalem/Tanım
            tanim = offer.get('tanim', '')
            if not tanim:
                tanim = f"Poz: {offer.get('poz_no', 'N/A')}"
            self.taseron_table.setItem(row, 2, QTableWidgetItem(tanim))
            # Miktar
            miktar = offer.get('miktar', 0)
            miktar_item = QTableWidgetItem(f"{miktar:.2f}" if miktar > 0 else "-")
            miktar_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.taseron_table.setItem(row, 3, miktar_item)
            # Birim
            self.taseron_table.setItem(row, 4, QTableWidgetItem(offer.get('birim', '')))
            # Fiyat
            fiyat_item = QTableWidgetItem(f"{offer['fiyat']:.2f} ₺")
            fiyat_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.taseron_table.setItem(row, 5, fiyat_item)
            # Toplam
            toplam_item = QTableWidgetItem(f"{offer.get('toplam', 0):,.2f} ₺")
            toplam_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.taseron_table.setItem(row, 6, toplam_item)
            
    def add_taseron_offer(self) -> None:
        """Taşeron teklifi ekle"""
        if not self.current_project_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce bir proje seçin")
            return
            
        # Dialog penceresini aç
        dialog = TaseronOfferDialog(self.db, self, proje_id=self.current_project_id)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            
            # Veritabanına ekle
            try:
                offer_id = self.db.add_taseron_teklif(
                    proje_id=self.current_project_id,
                    firma_adi=data['firma_adi'],
                    kalem_id=data['kalem_id'],
                    fiyat=data['fiyat'],
                    poz_no=data['poz_no'] if data['poz_no'] else '',
                    tanim=data['tanim'],
                    miktar=data['miktar'],
                    birim=data['birim']
                )
                
                if offer_id:
                    # Durum ve notları güncelle
                    self.db.update_taseron_teklif(offer_id, durum=data['durum'], notlar=data['notlar'])
                    
                    self.load_taseron_data()
                    self.update_proje_ozet()  # Özeti güncelle
                    self.statusBar().showMessage("Teklif başarıyla eklendi")
                else:
                    QMessageBox.warning(self, "Uyarı", "Teklif eklenirken bir hata oluştu")
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Teklif eklenirken hata oluştu:\n{str(e)}")
        
    def edit_taseron_offer(self) -> None:
        """Taşeron teklifi düzenle"""
        current_row = self.taseron_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Uyarı", "Lütfen düzenlemek için bir satır seçin")
            return
            
        # Seçili teklifin ID'sini al
        offer_id = int(self.taseron_table.item(current_row, 0).text())
        
        # Teklif verilerini getir
        try:
            offers = self.db.get_taseron_teklifleri(self.current_project_id)
            offer_data = next((offer for offer in offers if offer['id'] == offer_id), None)
            
            if not offer_data:
                QMessageBox.warning(self, "Uyarı", "Teklif bulunamadı")
                return
                
            # Dialog penceresini aç
            dialog = TaseronOfferDialog(self.db, self, offer_data, proje_id=self.current_project_id)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                data = dialog.get_data()
                
                # Veritabanını güncelle
                if self.db.update_taseron_teklif(
                    offer_id=offer_id,
                    firma_adi=data['firma_adi'],
                    kalem_id=data['kalem_id'],
                    fiyat=data['fiyat'],
                    poz_no=data['poz_no'] if data['poz_no'] else '',
                    tanim=data['tanim'],
                    miktar=data['miktar'],
                    birim=data['birim'],
                    durum=data['durum'],
                    notlar=data['notlar']
                ):
                    self.load_taseron_data()
                    self.update_proje_ozet()  # Özeti güncelle
                    self.statusBar().showMessage("Teklif başarıyla güncellendi")
                else:
                    QMessageBox.warning(self, "Uyarı", "Teklif güncellenirken bir hata oluştu")
                    
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Teklif düzenlenirken hata oluştu:\n{str(e)}")
            
    def delete_taseron_offer(self) -> None:
        """Taşeron teklifi sil"""
        current_row = self.taseron_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Uyarı", "Lütfen silmek için bir satır seçin")
            return
            
        reply = QMessageBox.question(
            self, "Onay", "Bu teklifi silmek istediğinize emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            offer_id = int(self.taseron_table.item(current_row, 0).text())
            if self.db.delete_taseron_teklif(offer_id):
                self.load_taseron_data()
                self.update_proje_ozet()  # Özeti güncelle
                self.statusBar().showMessage("Teklif silindi")
            else:
                QMessageBox.warning(self, "Uyarı", "Teklif silinirken bir hata oluştu")
    
    def compare_offers(self) -> None:
        """Teklifleri karşılaştır"""
        if not self.current_project_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce bir proje seçin")
            return
            
        offers = self.db.get_taseron_teklifleri(self.current_project_id)
        if not offers:
            QMessageBox.information(self, "Bilgi", "Karşılaştırılacak teklif yok")
            self.comparison_table.setRowCount(0)
            self.comparison_summary_label.setText("")
            return
            
        comparison = self.calculator.compare_taseron_offers(offers)
        
        # Firma bazında toplamları hesapla
        firma_totals = {}
        for offer in offers:
            firma = offer['firma_adi']
            toplam = offer.get('toplam', 0)
            durum = offer.get('durum', 'beklemede')
            
            if firma not in firma_totals:
                firma_totals[firma] = {
                    'toplam': 0.0,
                    'durum': durum,
                    'teklif_sayisi': 0
                }
            
            firma_totals[firma]['toplam'] += toplam
            firma_totals[firma]['teklif_sayisi'] += 1
        
        # Karşılaştırma tablosunu doldur
        self.comparison_table.setRowCount(len(firma_totals))
        
        ortalama = comparison.get('ortalama', 0.0)
        row = 0
        for firma, data in sorted(firma_totals.items(), key=lambda x: x[1]['toplam']):
            # Firma
            self.comparison_table.setItem(row, 0, QTableWidgetItem(firma))
            
            # Toplam Tutar
            toplam_item = QTableWidgetItem(f"{data['toplam']:,.2f} ₺")
            toplam_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.comparison_table.setItem(row, 1, toplam_item)
            
            # Durum
            durum_item = QTableWidgetItem(data['durum'].title())
            durum_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.comparison_table.setItem(row, 2, durum_item)
            
            # Fark (Ortalamadan)
            fark = data['toplam'] - ortalama
            fark_text = f"{fark:+,.2f} ₺"
            fark_item = QTableWidgetItem(fark_text)
            fark_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            
            # Fark pozitifse yeşil, negatifse kırmızı
            if fark < 0:
                fark_item.setForeground(Qt.GlobalColor.darkGreen)
            elif fark > 0:
                fark_item.setForeground(Qt.GlobalColor.red)
            
            self.comparison_table.setItem(row, 3, fark_item)
            
            row += 1
        
        # Özet bilgi
        summary = f"📊 Toplam {len(firma_totals)} firma, {len(offers)} teklif | "
        if comparison['en_dusuk']:
            summary += f"En Düşük: {comparison['en_dusuk']['firma']} ({comparison['en_dusuk']['tutar']:,.2f} ₺) | "
        summary += f"Ortalama: {ortalama:,.2f} ₺"
        
        self.comparison_summary_label.setText(summary)
    
    def export_taseron_excel(self) -> None:
        """Taşeron tekliflerini Excel'e export et"""
        if not self.current_project_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce bir proje seçin")
            return
            
        offers = self.db.get_taseron_teklifleri(self.current_project_id)
        if not offers:
            QMessageBox.warning(self, "Uyarı", "Export edilecek teklif bulunamadı")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Excel'e Kaydet", "", "Excel Dosyaları (*.xlsx)"
        )
        
        if file_path:
            proje = self.db.get_project(self.current_project_id) if self.current_project_id else None
            proje_adi = proje.get('ad', '') if proje else ''
            
            if self.export_manager.export_taseron_offers_to_excel(offers, Path(file_path), proje_adi):
                QMessageBox.information(self, "Başarılı", f"Taşeron teklifleri Excel'e aktarıldı:\n{file_path}")
                self.statusBar().showMessage(f"Excel export tamamlandı: {file_path}")
            else:
                QMessageBox.critical(self, "Hata", "Excel export sırasında bir hata oluştu.")
    
    def export_taseron_pdf(self) -> None:
        """Taşeron tekliflerini PDF'e export et"""
        if not self.current_project_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce bir proje seçin")
            return
            
        offers = self.db.get_taseron_teklifleri(self.current_project_id)
        if not offers:
            QMessageBox.warning(self, "Uyarı", "Export edilecek teklif bulunamadı")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "PDF'e Kaydet", "", "PDF Dosyaları (*.pdf)"
        )
        
        if file_path:
            proje = self.db.get_project(self.current_project_id) if self.current_project_id else None
            proje_adi = proje.get('ad', '') if proje else ''
            
            if self.export_manager.export_taseron_offers_to_pdf(offers, Path(file_path), proje_adi):
                QMessageBox.information(self, "Başarılı", f"Taşeron teklifleri PDF'e aktarıldı:\n{file_path}")
                self.statusBar().showMessage(f"PDF export tamamlandı: {file_path}")
            else:
                QMessageBox.critical(self, "Hata", "PDF export sırasında bir hata oluştu.")
        
    def check_and_load_pozlar_async(self) -> None:
        """Uygulama açıldığında pozları kontrol et ve gerekirse yükle (async)"""
        # Arka planda yükleme için thread oluştur
        self.data_loader_thread = DataLoaderThread(self.db)
        self.data_loader_thread.data_loaded.connect(self.on_data_loaded)
        self.data_loader_thread.poz_question_needed.connect(self.show_poz_question)
        self.data_loader_thread.start()
        
        # Durum çubuğunda bilgi göster
        self.statusBar().showMessage("Veriler kontrol ediliyor...")
    
    @pyqtSlot(dict)
    def on_data_loaded(self, result: Dict[str, Any]) -> None:
        """Veri yükleme tamamlandığında çağrılır"""
        if result.get('malzemeler_loaded', False) or result.get('formuller_loaded', False):
            self.statusBar().showMessage(
                f"Veriler hazır: {result.get('malzeme_count', 0)} malzeme, "
                f"{result.get('formul_count', 0)} formül"
            )
        else:
            self.statusBar().showMessage("Hazır")
    
    @pyqtSlot()
    def show_poz_question(self) -> None:
        """Poz yükleme sorusu göster"""
        reply = QMessageBox.question(
            self, "Veri Yükleme",
            "Pozlar henüz yüklenmemiş. Şimdi yüklemek ister misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        if reply == QMessageBox.StandardButton.Yes:
            # Pozları yükle (yine async olabilir ama şimdilik sync)
            self.load_pozlar(silent=False)
    
    def check_and_load_pozlar(self) -> None:
        """Uygulama açıldığında pozları kontrol et ve gerekirse yükle (sync versiyon - eski)"""
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
    
    def on_tab_changed(self, index: int) -> None:
        """Sekme değiştiğinde çağrılır"""
        # Proje Özeti sekmesine geçildiğinde güncelle
        if index == 1:  # Proje Özeti sekmesi (2. sekme, 0-indexed)
            self.update_proje_ozet()
            
    def update_proje_ozet(self) -> None:
        """Proje özeti sekmesini güncelle"""
        if not self.current_project_id:
            # Proje seçili değilse temizle
            self.ozet_kalem_label.setText("0")
            self.ozet_maliyet_label.setText("0.00 ₺")
            self.ozet_kdv_label.setText("0.00 ₺")
            self.ozet_taseron_label.setText("0")
            self.ozet_kategori_table.setRowCount(0)
            self.ozet_pahali_table.setRowCount(0)
            self.ozet_malzeme_label.setText("Malzeme listesi hesaplanmadı.\n'Malzeme Listesi' sekmesinden hesaplayınız.")
            self.ozet_taseron_detay_label.setText("Taşeron teklif bilgisi yok.")
            return
        
        try:
            # Proje bilgilerini al
            proje = self.db.get_project(self.current_project_id)
            metraj_items = self.db.get_project_metraj(self.current_project_id)
            taseron_offers = self.db.get_taseron_teklifleri(self.current_project_id)
            
            # Toplam kalem sayısı
            toplam_kalem = len(metraj_items)
            self.ozet_kalem_label.setText(str(toplam_kalem))
            
            # Toplam maliyet
            toplam_maliyet = sum(item.get('toplam', 0) for item in metraj_items)
            self.ozet_maliyet_label.setText(f"{toplam_maliyet:,.2f} ₺")
            
            # KDV hesaplama
            kdv_rate_text = self.ozet_kdv_rate.currentText().replace("%", "")
            kdv_rate = float(kdv_rate_text)
            kdv_hesap = self.calculator.calculate_with_kdv(toplam_maliyet, kdv_rate)
            self.ozet_kdv_label.setText(f"{kdv_hesap['kdv_dahil']:,.2f} ₺")
            
            # Taşeron teklif sayısı
            toplam_taseron = len(taseron_offers)
            self.ozet_taseron_label.setText(str(toplam_taseron))
            
            # Kategori bazında dağılım
            kategori_dict = {}
            for item in metraj_items:
                kategori = item.get('kategori', 'Kategori Yok')
                if kategori not in kategori_dict:
                    kategori_dict[kategori] = {'sayi': 0, 'toplam': 0.0}
                kategori_dict[kategori]['sayi'] += 1
                kategori_dict[kategori]['toplam'] += item.get('toplam', 0)
            
            self.ozet_kategori_table.setRowCount(len(kategori_dict))
            for row, (kategori, data) in enumerate(sorted(kategori_dict.items(), key=lambda x: x[1]['toplam'], reverse=True)):
                self.ozet_kategori_table.setItem(row, 0, QTableWidgetItem(kategori))
                self.ozet_kategori_table.setItem(row, 1, QTableWidgetItem(str(data['sayi'])))
                toplam_item = QTableWidgetItem(f"{data['toplam']:,.2f} ₺")
                toplam_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.ozet_kategori_table.setItem(row, 2, toplam_item)
            
            # En pahalı 5 kalem
            sorted_items = sorted(metraj_items, key=lambda x: x.get('toplam', 0), reverse=True)[:5]
            self.ozet_pahali_table.setRowCount(len(sorted_items))
            for row, item in enumerate(sorted_items):
                tanim = item.get('tanim', '')[:40] + ('...' if len(item.get('tanim', '')) > 40 else '')
                self.ozet_pahali_table.setItem(row, 0, QTableWidgetItem(tanim))
                miktar_text = f"{item.get('miktar', 0):,.2f} {item.get('birim', '')}"
                miktar_item = QTableWidgetItem(miktar_text)
                miktar_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.ozet_pahali_table.setItem(row, 1, miktar_item)
                toplam_item = QTableWidgetItem(f"{item.get('toplam', 0):,.2f} ₺")
                toplam_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.ozet_pahali_table.setItem(row, 2, toplam_item)
            
            # Malzeme özeti
            if self.current_materials:
                toplam_malzeme_cesit = len(self.current_materials)
                toplam_malzeme_miktar = sum(m.get('miktar', 0) for m in self.current_materials)
                self.ozet_malzeme_label.setText(
                    f"📦 Toplam {toplam_malzeme_cesit} farklı malzeme türü\n"
                    f"📊 Toplam malzeme miktarı: {toplam_malzeme_miktar:,.2f}"
                )
            else:
                self.ozet_malzeme_label.setText(
                    "Malzeme listesi hesaplanmadı.\n"
                    "'Malzeme Listesi' sekmesinden 'Malzemeleri Hesapla' butonuna tıklayınız."
                )
            
            # Taşeron özeti
            if taseron_offers:
                firma_dict = {}
                for offer in taseron_offers:
                    firma = offer.get('firma_adi', '')
                    toplam = offer.get('toplam', 0)
                    if firma not in firma_dict:
                        firma_dict[firma] = 0.0
                    firma_dict[firma] += toplam
                
                if firma_dict:
                    en_dusuk = min(firma_dict.items(), key=lambda x: x[1])
                    en_yuksek = max(firma_dict.items(), key=lambda x: x[1])
                    ortalama = sum(firma_dict.values()) / len(firma_dict)
                    
                    self.ozet_taseron_detay_label.setText(
                        f"📊 Toplam {len(firma_dict)} firma\n"
                        f"💰 En Düşük: {en_dusuk[0]} ({en_dusuk[1]:,.2f} ₺)\n"
                        f"💰 En Yüksek: {en_yuksek[0]} ({en_yuksek[1]:,.2f} ₺)\n"
                        f"📈 Ortalama: {ortalama:,.2f} ₺"
                    )
                else:
                    self.ozet_taseron_detay_label.setText("Taşeron teklif bilgisi yok.")
            else:
                self.ozet_taseron_detay_label.setText("Taşeron teklif bilgisi yok.")
                
        except Exception as e:
            print(f"Proje özeti güncelleme hatası: {e}")
            import traceback
            traceback.print_exc()
    
    def export_proje_ozet_pdf(self) -> None:
        """Proje özetini PDF olarak export et"""
        if not self.current_project_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce bir proje seçin")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "PDF Rapor Oluştur", "", "PDF Dosyaları (*.pdf)"
        )
        
        if file_path:
            try:
                proje = self.db.get_project(self.current_project_id)
                metraj_items = self.db.get_project_metraj(self.current_project_id)
                taseron_offers = self.db.get_taseron_teklifleri(self.current_project_id)
                
                # KDV hesaplama
                kdv_rate_text = self.ozet_kdv_rate.currentText().replace("%", "")
                kdv_rate = float(kdv_rate_text)
                toplam_maliyet = sum(item.get('toplam', 0) for item in metraj_items)
                kdv_hesap = self.calculator.calculate_with_kdv(toplam_maliyet, kdv_rate)
                
                # PDF oluştur
                from reportlab.lib.pagesizes import A4
                from reportlab.lib import colors
                from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                from reportlab.lib.units import cm
                from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
                from datetime import datetime
                
                doc = SimpleDocTemplate(str(file_path), pagesize=A4)
                story = []
                styles = getSampleStyleSheet()
                
                # Başlık
                title_style = ParagraphStyle(
                    'CustomTitle',
                    parent=styles['Heading1'],
                    fontSize=18,
                    textColor=colors.HexColor('#1a1a2e'),
                    spaceAfter=30,
                    alignment=1
                )
                story.append(Paragraph(f"Proje Özet Raporu - {proje.get('ad', '')}", title_style))
                story.append(Spacer(1, 0.5*cm))
                
                # Özet bilgiler
                info_data = [
                    ['Proje Adı', proje.get('ad', '')],
                    ['Oluşturulma Tarihi', proje.get('olusturma_tarihi', '')[:10] if proje.get('olusturma_tarihi') else ''],
                    ['Toplam Kalem Sayısı', str(len(metraj_items))],
                    ['Toplam Maliyet (KDV Hariç)', f"{toplam_maliyet:,.2f} ₺"],
                    ['KDV (%' + kdv_rate_text + ')', f"{kdv_hesap['kdv']:,.2f} ₺"],
                    ['Toplam Maliyet (KDV Dahil)', f"{kdv_hesap['kdv_dahil']:,.2f} ₺"],
                    ['Taşeron Teklif Sayısı', str(len(taseron_offers))],
                ]
                
                info_table = Table(info_data, colWidths=[6*cm, 6*cm])
                info_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#16213e')),
                    ('TEXTCOLOR', (0, 0), (0, -1), colors.whitesmoke),
                    ('BACKGROUND', (1, 0), (1, -1), colors.white),
                    ('TEXTCOLOR', (1, 0), (1, -1), colors.black),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                    ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ]))
                story.append(info_table)
                story.append(Spacer(1, 0.5*cm))
                
                # Kategori dağılımı
                kategori_dict = {}
                for item in metraj_items:
                    kategori = item.get('kategori', 'Kategori Yok')
                    if kategori not in kategori_dict:
                        kategori_dict[kategori] = {'sayi': 0, 'toplam': 0.0}
                    kategori_dict[kategori]['sayi'] += 1
                    kategori_dict[kategori]['toplam'] += item.get('toplam', 0)
                
                if kategori_dict:
                    story.append(Paragraph("Kategori Bazında Dağılım", styles['Heading2']))
                    kategori_data = [['Kategori', 'Kalem Sayısı', 'Toplam Maliyet']]
                    for kategori, data in sorted(kategori_dict.items(), key=lambda x: x[1]['toplam'], reverse=True):
                        kategori_data.append([
                            kategori,
                            str(data['sayi']),
                            f"{data['toplam']:,.2f} ₺"
                        ])
                    
                    kategori_table = Table(kategori_data, colWidths=[6*cm, 3*cm, 3*cm])
                    kategori_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#16213e')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 10),
                        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
                    ]))
                    story.append(kategori_table)
                
                # PDF oluştur
                doc.build(story)
                QMessageBox.information(self, "Başarılı", f"Proje özet raporu PDF'e aktarıldı:\n{file_path}")
                self.statusBar().showMessage(f"PDF rapor oluşturuldu: {file_path}")
                
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"PDF oluşturulurken hata oluştu:\n{str(e)}")
                print(f"PDF export hatası: {e}")
    
    def export_proje_ozet_excel(self) -> None:
        """Proje özetini Excel olarak export et"""
        if not self.current_project_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce bir proje seçin")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Excel Rapor Oluştur", "", "Excel Dosyaları (*.xlsx)"
        )
        
        if file_path:
            try:
                import pandas as pd
                from openpyxl import load_workbook
                from openpyxl.styles import Font, Alignment, PatternFill
                
                proje = self.db.get_project(self.current_project_id)
                metraj_items = self.db.get_project_metraj(self.current_project_id)
                taseron_offers = self.db.get_taseron_teklifleri(self.current_project_id)
                
                # KDV hesaplama
                kdv_rate_text = self.ozet_kdv_rate.currentText().replace("%", "")
                kdv_rate = float(kdv_rate_text)
                toplam_maliyet = sum(item.get('toplam', 0) for item in metraj_items)
                kdv_hesap = self.calculator.calculate_with_kdv(toplam_maliyet, kdv_rate)
                
                # Excel writer
                with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                    # Özet bilgiler
                    ozet_data = {
                        'Bilgi': [
                            'Proje Adı',
                            'Oluşturulma Tarihi',
                            'Toplam Kalem Sayısı',
                            'Toplam Maliyet (KDV Hariç)',
                            f'KDV (%{kdv_rate_text})',
                            'Toplam Maliyet (KDV Dahil)',
                            'Taşeron Teklif Sayısı'
                        ],
                        'Değer': [
                            proje.get('ad', ''),
                            proje.get('olusturma_tarihi', '')[:10] if proje.get('olusturma_tarihi') else '',
                            str(len(metraj_items)),
                            f"{toplam_maliyet:,.2f} ₺",
                            f"{kdv_hesap['kdv']:,.2f} ₺",
                            f"{kdv_hesap['kdv_dahil']:,.2f} ₺",
                            str(len(taseron_offers))
                        ]
                    }
                    df_ozet = pd.DataFrame(ozet_data)
                    df_ozet.to_excel(writer, sheet_name='Proje Özeti', index=False)
                    
                    # Kategori dağılımı
                    kategori_dict = {}
                    for item in metraj_items:
                        kategori = item.get('kategori', 'Kategori Yok')
                        if kategori not in kategori_dict:
                            kategori_dict[kategori] = {'sayi': 0, 'toplam': 0.0}
                        kategori_dict[kategori]['sayi'] += 1
                        kategori_dict[kategori]['toplam'] += item.get('toplam', 0)
                    
                    if kategori_dict:
                        kategori_data = {
                            'Kategori': [],
                            'Kalem Sayısı': [],
                            'Toplam Maliyet': []
                        }
                        for kategori, data in sorted(kategori_dict.items(), key=lambda x: x[1]['toplam'], reverse=True):
                            kategori_data['Kategori'].append(kategori)
                            kategori_data['Kalem Sayısı'].append(data['sayi'])
                            kategori_data['Toplam Maliyet'].append(f"{data['toplam']:,.2f} ₺")
                        
                        df_kategori = pd.DataFrame(kategori_data)
                        df_kategori.to_excel(writer, sheet_name='Kategori Dağılımı', index=False)
                    
                    # En pahalı kalemler
                    sorted_items = sorted(metraj_items, key=lambda x: x.get('toplam', 0), reverse=True)[:10]
                    pahali_data = {
                        'Kalem': [item.get('tanim', '') for item in sorted_items],
                        'Miktar': [f"{item.get('miktar', 0):,.2f} {item.get('birim', '')}" for item in sorted_items],
                        'Toplam': [f"{item.get('toplam', 0):,.2f} ₺" for item in sorted_items]
                    }
                    df_pahali = pd.DataFrame(pahali_data)
                    df_pahali.to_excel(writer, sheet_name='En Pahalı Kalemler', index=False)
                
                # Stil ayarları
                wb = load_workbook(file_path)
                for sheet_name in wb.sheetnames:
                    ws = wb[sheet_name]
                    # Başlık satırını kalın yap
                    header_fill = PatternFill(start_color='16213e', end_color='16213e', fill_type='solid')
                    for cell in ws[1]:
                        cell.font = Font(bold=True, color='FFFFFF')
                        cell.fill = header_fill
                        cell.alignment = Alignment(horizontal='center', vertical='center')
                wb.save(file_path)
                
                QMessageBox.information(self, "Başarılı", f"Proje özet raporu Excel'e aktarıldı:\n{file_path}")
                self.statusBar().showMessage(f"Excel rapor oluşturuldu: {file_path}")
                
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Excel oluşturulurken hata oluştu:\n{str(e)}")
                print(f"Excel export hatası: {e}")
    
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

