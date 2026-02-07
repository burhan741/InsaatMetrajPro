"""
Ana Pencere
PyQt6 ile modern kullanıcı arayüzü
"""
from __future__ import annotations

from typing import Optional, List, Dict, Any
from pathlib import Path
from datetime import datetime
import logging
import importlib
import sys
import sqlite3
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QTableWidget, QTableWidgetItem, QTreeWidget, QTreeWidgetItem,
    QPushButton, QFileDialog, QMessageBox, QLabel, QLineEdit,
    QHeaderView, QSplitter, QGroupBox, QFormLayout, QDoubleSpinBox,
    QComboBox, QTextEdit, QDialog, QMenu, QCheckBox, QScrollArea,
    QInputDialog, QListWidget, QAbstractItemView
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, pyqtSlot
from PyQt6.QtGui import QIcon, QFont, QColor

from app.core.database import DatabaseManager
from app.core.calculator import Calculator
from app.utils.data_loader import (
    initialize_database_data, check_pozlar_loaded,
    initialize_material_data, check_malzemeler_loaded, check_formuller_loaded
)
from app.ui.dialogs import MetrajItemDialog, TaseronOfferDialog

# Ağır modüller lazy import ile yüklenir (başlangıç hızı için)
# MaterialCalculator, DXFAnaliz, DemirEngine, ExportManager, PDFBirimFiyatImporter
# ve tüm UI pencere modülleri sadece kullanıldığında import edilir

logger = logging.getLogger(__name__)
# Logger seviyesini açıkça DEBUG'a ayarla (modül import edilirken logging konfigürasyonu aktif olmalı)
logger.setLevel(logging.DEBUG)


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


class InitialDataLoaderThread(QThread):
    """İlk açılışta proje ve diğer verileri yükleyen thread"""
    projects_loaded = pyqtSignal(list)
    
    def __init__(self, db: DatabaseManager) -> None:
        super().__init__()
        self.db = db
    
    def run(self) -> None:
        """Thread çalıştığında"""
        try:
            # Projeleri yükle
            projects = self.db.get_all_projects()
            self.projects_loaded.emit(projects)
        except Exception as e:
            print(f"Proje yükleme hatası: {e}")
            self.projects_loaded.emit([])


class MainWindow(QMainWindow):
    """Ana uygulama penceresi"""
    
    def __init__(self, db: Optional[DatabaseManager] = None, splash: Optional[Any] = None, user_type: str = 'muteahhit') -> None:
        """Ana pencereyi başlat"""
        super().__init__()
        
        self.splash = splash
        self.user_type = user_type  # 'muteahhit' veya 'taseron'
        
        # Core modüller (hafif olanlar hemen yükle)
        # Eğer dışarıdan bir DatabaseManager verildiyse kullan, yoksa yenisini oluştur
        self.db = db if db is not None else DatabaseManager()
        self.calculator = Calculator()

        # Ağır modüller lazy loading ile (sadece gerektiğinde yüklenecek)
        self._material_calculator = None
        self._export_manager = None
        
        # UI durumu
        self.current_project_id: Optional[int] = None
        self.current_materials: List[Dict[str, Any]] = []  # Hesaplanan malzemeler
        
        # Sekme lazy loading için
        self._tabs_created = {
            'metraj': False,
            'ozet': False,
            'taseron': False,
            'malzeme': False,
            'sablonlar': False,
            'birim_fiyat': False,
            'ihale': False
        }
        
        # Arayüzü oluştur
        if self.splash:
            self.splash.showMessage(
                "Arayüz oluşturuluyor...",
                Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignBottom,
                Qt.GlobalColor.white
            )
            from PyQt6.QtWidgets import QApplication
            QApplication.processEvents()
        
        # Kullanıcı tipine göre arayüz oluştur
        if self.user_type == 'taseron':
            from app.ui.taseron_window import TaseronWindow
            # Alt Yüklenici penceresini göster, Yüklenici penceresini gizle
            self.taseron_window = TaseronWindow(self.db, self.splash)
            self.taseron_window.show()
            self.taseron_window.showMaximized()  # Tam ekran aç
            self.hide()  # Yüklenici penceresini gizle
        else:
            self.init_ui()
        
        # Veritabanı yüklemelerini async yap (UI'ı bloklamadan)
        self.load_data_async()
        
        # İlk açılışta pozları kontrol et ve yükle (async - arka planda)
        self.check_and_load_pozlar_async()
        
        if self.splash:
            self.splash.showMessage(
                "Hazırlanıyor...",
                Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignBottom,
                Qt.GlobalColor.white
            )
            from PyQt6.QtWidgets import QApplication
            QApplication.processEvents()
    
    @property
    def material_calculator(self):
        """MaterialCalculator'ı lazy loading ile yükle"""
        if self._material_calculator is None:
            from app.core.material_calculator import MaterialCalculator
            self._material_calculator = MaterialCalculator(self.db)
        return self._material_calculator

    @property
    def export_manager(self):
        """ExportManager'ı lazy loading ile yükle"""
        if self._export_manager is None:
            from app.utils.export_manager import ExportManager
            self._export_manager = ExportManager()
        return self._export_manager

    def init_ui(self) -> None:
        """Arayüzü başlat"""
        self.setWindowTitle("InsaatMetrajPro - İnşaat Metraj Uygulaması")

        # Ekran boyutuna göre pencere boyutunu ayarla
        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen()
        if screen:
            screen_size = screen.availableGeometry()
            # Ekranın %85'i kadar genişlik ve yükseklik
            width = min(1400, int(screen_size.width() * 0.85))
            height = min(900, int(screen_size.height() * 0.85))
            x = (screen_size.width() - width) // 2
            y = (screen_size.height() - height) // 2
            self.setGeometry(x, y, width, height)
        else:
            self.setGeometry(100, 100, 1400, 900)
        
        # Uygulama ikonunu ayarla
        icon_path = Path(__file__).parent.parent.parent / "assets" / "app_icon.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        
        # Merkezi widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Arka plan görseli ayarla (ana pencere için - wireframe şehir)
        bg_path = Path(__file__).parent.parent.parent / "assets" / "wireframe_background.jpg"
        if bg_path.exists():
            try:
                # QLabel ile arka plan görseli ekle (daha güvenilir yöntem)
                from PyQt6.QtWidgets import QLabel
                from PyQt6.QtGui import QPixmap
                
                bg_label = QLabel(central_widget)
                bg_pixmap = QPixmap(str(bg_path))
                if not bg_pixmap.isNull():
                    bg_label.setPixmap(bg_pixmap)
                    bg_label.setScaledContents(True)
                    bg_label.lower()  # En alta gönder (arka planda kalsın)
                    self._bg_label = bg_label  # Referansı sakla
                else:
                    print("Arka plan görseli yüklenemedi: QPixmap null")
            except Exception as e:
                print(f"Arka plan görseli yükleme hatası: {e}")
                import traceback
                traceback.print_exc()
        
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
        
        # Hızlı Arama
        search_group = QGroupBox("🔍 Hızlı Arama")
        search_layout = QVBoxLayout()
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Proje, kalem, poz ara...")
        self.search_input.textChanged.connect(self.on_search_text_changed)
        search_layout.addWidget(self.search_input)
        
        self.search_type_combo = QComboBox()
        self.search_type_combo.addItems(["Tümü", "Projeler", "Kalemler", "Pozlar"])
        self.search_type_combo.currentTextChanged.connect(self.on_search_text_changed)
        search_layout.addWidget(self.search_type_combo)
        
        search_group.setLayout(search_layout)
        sidebar_layout.addWidget(search_group)
        
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
        
        # Proje Notları bölümü
        notes_group = QGroupBox("📝 Proje Notları")
        notes_layout = QVBoxLayout()
        
        self.project_notes_text = QTextEdit()
        self.project_notes_text.setPlaceholderText("Proje notlarınızı buraya yazın...")
        self.project_notes_text.setMaximumHeight(150)
        notes_layout.addWidget(self.project_notes_text)
        
        btn_save_notes = QPushButton("Notları Kaydet")
        btn_save_notes.clicked.connect(self.save_project_notes)
        notes_layout.addWidget(btn_save_notes)
        
        notes_group.setLayout(notes_layout)
        sidebar_layout.addWidget(notes_group)
        
        sidebar_layout.addStretch()
        
        parent.addWidget(sidebar_widget)
        
    def create_tabs(self, parent: QSplitter) -> None:
        """Sekmeli yapıyı oluştur (lazy loading ile)"""
        self.tabs = QTabWidget()
        # Sekme değiştiğinde lazy loading ve özeti güncelle
        self.tabs.currentChanged.connect(self.on_tab_changed)
        
        # Sadece ilk sekmeyi hemen oluştur, diğerleri lazy loading ile
        # Sekme 1: Metraj Cetveli (ilk sekme, hemen yükle)
        self.create_metraj_tab()
        self._tabs_created['metraj'] = True
        
        # Diğer sekmeler placeholder olarak ekle, lazy loading ile yüklenecek
        self.tabs.addTab(QWidget(), "Proje Özeti")
        self.tabs.addTab(QWidget(), "Alt Yüklenici Analizi")
        self.tabs.addTab(QWidget(), "Malzeme Listesi")
        self.tabs.addTab(QWidget(), "Şablonlar")
        self.tabs.addTab(QWidget(), "Birim Fiyat Yönetimi")
        self.tabs.addTab(QWidget(), "İhale Dosyası Hazırlama")
        self.tabs.addTab(QWidget(), "Enflasyon ve Fiyat Farkı")
        self.tabs.addTab(QWidget(), "Tedarikçi Fiyat Karşılaştırma")
        self.tabs.addTab(QWidget(), "BI Dashboard")
        self.tabs.addTab(QWidget(), "Çevre ve Sürdürülebilirlik")
        self.tabs.addTab(QWidget(), "Gantt Chart ve İş Programı")

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
        
        # KDV oranı seçimi
        kdv_label = QLabel("KDV:")
        btn_layout.addWidget(kdv_label)
        self.metraj_kdv_rate = QComboBox()
        self.metraj_kdv_rate.addItems(["%1", "%10", "%20"])
        self.metraj_kdv_rate.setCurrentText("%20")
        self.metraj_kdv_rate.currentTextChanged.connect(self.update_malzeme_total)
        btn_layout.addWidget(self.metraj_kdv_rate)
        
        # Toplam etiketi (KDV hariç)
        self.total_label = QLabel("Toplam (KDV Hariç): 0.00 ₺")
        self.total_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        btn_layout.addWidget(self.total_label)
        
        # KDV dahil toplam
        self.total_kdv_label = QLabel("Toplam (KDV Dahil): 0.00 ₺")
        self.total_kdv_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        self.total_kdv_label.setStyleSheet("color: #00BFFF;")
        btn_layout.addWidget(self.total_kdv_label)
        
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
    
    def create_proje_ozet_tab(self, add_to_tabs: bool = True) -> None:
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
        
        # Kart 4: Alt Yüklenici Teklif Sayısı
        self.ozet_taseron_card = QGroupBox("Alt Yüklenici Teklifleri")
        taseron_layout = QVBoxLayout()
        self.ozet_taseron_label = QLabel("0")
        self.ozet_taseron_label.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        self.ozet_taseron_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ozet_taseron_label.setStyleSheet("color: #00BFFF;")
        taseron_layout.addWidget(self.ozet_taseron_label)
        self.ozet_taseron_card.setLayout(taseron_layout)
        self.ozet_taseron_card.setMinimumHeight(100)
        cards_layout.addWidget(self.ozet_taseron_card)
        
        layout.addLayout(cards_layout)
        
        # Orta panel: Splitter (Grafikler ve Tablolar)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Sol: Kategori Dağılımı (Grafik + Tablo)
        kategori_widget = QWidget()
        kategori_layout = QVBoxLayout(kategori_widget)
        kategori_layout.setContentsMargins(0, 0, 0, 0)
        
        kategori_title = QLabel("📋 Kategori Bazında Dağılım")
        kategori_title.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        kategori_layout.addWidget(kategori_title)
        
        # Pie Chart için matplotlib widget
        try:
            from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
            from matplotlib.figure import Figure
            import matplotlib.pyplot as plt
            
            self.kategori_figure = Figure(figsize=(5, 4))
            self.kategori_canvas = FigureCanvasQTAgg(self.kategori_figure)
            self.kategori_ax = self.kategori_figure.add_subplot(111)
            self.kategori_canvas.setMinimumHeight(250)
            kategori_layout.addWidget(self.kategori_canvas)
        except ImportError:
            # Matplotlib yoksa placeholder
            placeholder = QLabel("Matplotlib yüklenmedi. Grafik gösterilemiyor.")
            placeholder.setStyleSheet("color: #666; padding: 20px;")
            kategori_layout.addWidget(placeholder)
            self.kategori_canvas = None
        
        # Kategori tablosu
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
        self.ozet_kategori_table.setMaximumHeight(150)
        kategori_layout.addWidget(self.ozet_kategori_table)
        
        splitter.addWidget(kategori_widget)
        
        # Sağ: En Pahalı Kalemler (Bar Chart + Tablo)
        pahali_widget = QWidget()
        pahali_layout = QVBoxLayout(pahali_widget)
        pahali_layout.setContentsMargins(0, 0, 0, 0)
        
        pahali_title = QLabel("💰 En Pahalı 5 Kalem")
        pahali_title.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        pahali_layout.addWidget(pahali_title)
        
        # Bar Chart için matplotlib widget
        try:
            from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
            from matplotlib.figure import Figure
            
            self.pahali_figure = Figure(figsize=(5, 4))
            self.pahali_canvas = FigureCanvasQTAgg(self.pahali_figure)
            self.pahali_ax = self.pahali_figure.add_subplot(111)
            self.pahali_canvas.setMinimumHeight(250)
            pahali_layout.addWidget(self.pahali_canvas)
        except ImportError:
            placeholder = QLabel("Matplotlib yüklenmedi. Grafik gösterilemiyor.")
            placeholder.setStyleSheet("color: #666; padding: 20px;")
            pahali_layout.addWidget(placeholder)
            self.pahali_canvas = None
        
        # En pahalı kalemler tablosu
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
        self.ozet_pahali_table.setMaximumHeight(150)
        pahali_layout.addWidget(self.ozet_pahali_table)
        
        splitter.addWidget(pahali_widget)
        
        splitter.setSizes([400, 400])
        layout.addWidget(splitter)
        
        # Alt panel: İstatistikler ve Detaylı Analiz
        stats_group = QGroupBox("📊 Detaylı İstatistikler ve Analiz")
        stats_layout = QVBoxLayout()
        
        # İstatistik tablosu
        self.stats_table = QTableWidget()
        self.stats_table.setColumnCount(2)
        self.stats_table.setHorizontalHeaderLabels(["İstatistik", "Değer"])
        self.stats_table.setAlternatingRowColors(True)
        self.stats_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.stats_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.stats_table.horizontalHeader().setStretchLastSection(True)
        self.stats_table.setColumnWidth(0, 300)
        self.stats_table.setMaximumHeight(200)
        stats_layout.addWidget(self.stats_table)
        
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)
        
        # Alt panel: Malzeme ve Alt Yüklenici Özeti
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
        
        self.ozet_widget = tab
        if add_to_tabs:
            self.tabs.addTab(tab, "📈 Proje Özeti")
        
    def create_taseron_tab(self, add_to_tabs: bool = True) -> None:
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
        
        # KDV oranı seçimi
        kdv_label = QLabel("KDV:")
        btn_layout.addWidget(kdv_label)
        self.taseron_kdv_rate = QComboBox()
        self.taseron_kdv_rate.addItems(["%1", "%10", "%20"])
        self.taseron_kdv_rate.setCurrentText("%20")
        self.taseron_kdv_rate.currentTextChanged.connect(self.load_taseron_data)
        btn_layout.addWidget(self.taseron_kdv_rate)
        
        # Toplam etiketleri
        self.taseron_total_label = QLabel("Toplam (KDV Hariç): 0.00 ₺")
        self.taseron_total_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        btn_layout.addWidget(self.taseron_total_label)
        
        self.taseron_total_kdv_label = QLabel("Toplam (KDV Dahil): 0.00 ₺")
        self.taseron_total_kdv_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        self.taseron_total_kdv_label.setStyleSheet("color: #00BFFF;")
        btn_layout.addWidget(self.taseron_total_kdv_label)
        
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
        
        self.taseron_widget = tab
        if add_to_tabs:
            self.tabs.addTab(tab, "💼 Taşeron Analizi")
    
    def create_malzeme_tab(self, add_to_tabs: bool = True) -> None:
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
        
        self.malzeme_widget = tab
        if add_to_tabs:
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
        
    def create_sablonlar_tab(self, add_to_tabs: bool = True) -> None:
        """Şablonlar sekmesini oluştur"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Buton barı
        btn_layout = QHBoxLayout()
        
        # Şablon oluşturma butonları
        btn_create_empty = QPushButton("➕ Boş Şablon Oluştur")
        btn_create_empty.clicked.connect(self.create_empty_template)
        btn_layout.addWidget(btn_create_empty)
        
        btn_create_from_project = QPushButton("📋 Projeden Şablon Oluştur")
        btn_create_from_project.clicked.connect(self.create_template_from_project)
        btn_layout.addWidget(btn_create_from_project)
        
        btn_create_from_category = QPushButton("📂 Kategori Bazlı Şablon Oluştur")
        btn_create_from_category.clicked.connect(self.create_template_from_categories)
        btn_layout.addWidget(btn_create_from_category)
        
        btn_create_from_preset = QPushButton("⭐ Hazır Şablonlardan Oluştur")
        btn_create_from_preset.clicked.connect(self.create_template_from_preset)
        btn_layout.addWidget(btn_create_from_preset)
        
        btn_layout.addStretch()
        
        # Şablon işlem butonları
        btn_create_project = QPushButton("🚀 Şablondan Proje Oluştur")
        btn_create_project.clicked.connect(self.create_project_from_template)
        btn_layout.addWidget(btn_create_project)
        
        btn_edit_template = QPushButton("✏️ Şablon Düzenle")
        btn_edit_template.clicked.connect(self.edit_template)
        btn_layout.addWidget(btn_edit_template)
        
        btn_copy_template = QPushButton("📋 Şablon Kopyala")
        btn_copy_template.clicked.connect(self.copy_template)
        btn_layout.addWidget(btn_copy_template)
        
        btn_refresh = QPushButton("🔄 Yenile")
        btn_refresh.clicked.connect(self.load_templates)
        btn_layout.addWidget(btn_refresh)
        
        btn_delete = QPushButton("🗑️ Şablon Sil")
        btn_delete.clicked.connect(self.delete_template)
        btn_delete.setStyleSheet("background-color: #c9184a;")
        btn_layout.addWidget(btn_delete)
        
        layout.addLayout(btn_layout)
        
        # Şablon listesi
        self.template_table = QTableWidget()
        self.template_table.setColumnCount(4)
        self.template_table.setHorizontalHeaderLabels([
            "Şablon Adı", "Açıklama", "Oluşturulma Tarihi", "Kalem Sayısı"
        ])
        self.template_table.setAlternatingRowColors(True)
        self.template_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.template_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.template_table.horizontalHeader().setStretchLastSection(True)
        self.template_table.setColumnWidth(0, 250)
        self.template_table.setColumnWidth(1, 300)
        self.template_table.setColumnWidth(2, 150)
        self.template_table.itemDoubleClicked.connect(self.view_template_items)
        self.template_table.itemClicked.connect(self.view_template_items)
        layout.addWidget(self.template_table)
        
        # Şablon kalemleri (seçili şablon için)
        items_group = QGroupBox("Şablon Kalemleri")
        items_layout = QVBoxLayout()
        
        # Kalem işlem butonları
        items_btn_layout = QHBoxLayout()
        btn_add_item = QPushButton("➕ Kalem Ekle")
        btn_add_item.clicked.connect(self.add_template_item)
        items_btn_layout.addWidget(btn_add_item)
        
        btn_edit_item = QPushButton("✏️ Kalem Düzenle")
        btn_edit_item.clicked.connect(self.edit_template_item)
        items_btn_layout.addWidget(btn_edit_item)
        
        btn_delete_item = QPushButton("🗑️ Kalem Sil")
        btn_delete_item.clicked.connect(self.delete_template_item)
        btn_delete_item.setStyleSheet("background-color: #c9184a;")
        items_btn_layout.addWidget(btn_delete_item)
        
        items_btn_layout.addStretch()
        items_layout.addLayout(items_btn_layout)
        
        self.template_items_table = QTableWidget()
        self.template_items_table.setColumnCount(8)
        self.template_items_table.setHorizontalHeaderLabels([
            "ID", "Poz No", "Tanım", "Kategori", "Miktar", "Birim", "Birim Fiyat", "Toplam"
        ])
        self.template_items_table.setAlternatingRowColors(True)
        self.template_items_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.template_items_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.template_items_table.horizontalHeader().setStretchLastSection(True)
        self.template_items_table.setColumnHidden(0, True)  # ID kolonunu gizle
        items_layout.addWidget(self.template_items_table)
        
        items_group.setLayout(items_layout)
        layout.addWidget(items_group)
        
        # Seçili şablon ID'sini sakla
        self.current_template_id: Optional[int] = None
        
        self.sablonlar_widget = tab
        if add_to_tabs:
            self.tabs.addTab(tab, "📋 Şablonlar")
    
    def create_birim_fiyat_tab(self, add_to_tabs: bool = True) -> None:
        """Birim Fiyat Yönetimi sekmesini oluştur"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Üst panel: Butonlar ve arama
        top_layout = QHBoxLayout()
        
        btn_add = QPushButton("Fiyat Ekle")
        btn_add.clicked.connect(self.add_birim_fiyat)
        top_layout.addWidget(btn_add)
        
        btn_refresh = QPushButton("Yenile")
        btn_refresh.clicked.connect(self.load_birim_fiyatlar)
        top_layout.addWidget(btn_refresh)
        
        btn_edit_fiyat = QPushButton("✏️ Fiyatı Düzelt")
        btn_edit_fiyat.clicked.connect(self.edit_birim_fiyat)
        top_layout.addWidget(btn_edit_fiyat)
        
        top_layout.addStretch()
        
        # Filtre
        filter_label = QLabel("Filtre:")
        top_layout.addWidget(filter_label)
        
        self.fiyat_filter_combo = QComboBox()
        self.fiyat_filter_combo.addItems(["Tümü", "Sadece Aktif"])
        self.fiyat_filter_combo.setCurrentText("Sadece Aktif")
        self.fiyat_filter_combo.currentTextChanged.connect(self.load_birim_fiyatlar)
        top_layout.addWidget(self.fiyat_filter_combo)
        
        layout.addLayout(top_layout)
        
        # Splitter: Sol tarafta fiyat listesi, sağ tarafta detaylar
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Sol: Birim fiyat listesi
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        list_title = QLabel("💰 Birim Fiyat Listesi")
        list_title.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        left_layout.addWidget(list_title)
        
        self.birim_fiyat_table = QTableWidget()
        self.birim_fiyat_table.setColumnCount(6)
        self.birim_fiyat_table.setHorizontalHeaderLabels([
            "Poz No", "Poz Tanımı", "Birim Fiyat", "Tarih", "Kaynak", "Aktif"
        ])
        self.birim_fiyat_table.setAlternatingRowColors(True)
        self.birim_fiyat_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.birim_fiyat_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.birim_fiyat_table.horizontalHeader().setStretchLastSection(True)
        self.birim_fiyat_table.setColumnWidth(0, 120)
        self.birim_fiyat_table.setColumnWidth(1, 300)
        self.birim_fiyat_table.setColumnWidth(2, 120)
        self.birim_fiyat_table.setColumnWidth(3, 120)
        self.birim_fiyat_table.itemDoubleClicked.connect(self.view_fiyat_gecmisi)
        left_layout.addWidget(self.birim_fiyat_table)
        
        splitter.addWidget(left_widget)
        
        # Sağ: Fiyat geçmişi ve karşılaştırma
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        detail_title = QLabel("📊 Fiyat Geçmişi ve Karşılaştırma")
        detail_title.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        right_layout.addWidget(detail_title)
        
        # Fiyat geçmişi tablosu
        self.fiyat_gecmisi_table = QTableWidget()
        self.fiyat_gecmisi_table.setColumnCount(5)
        self.fiyat_gecmisi_table.setHorizontalHeaderLabels([
            "Tarih", "Birim Fiyat", "Kaynak", "Açıklama", "Aktif"
        ])
        self.fiyat_gecmisi_table.setAlternatingRowColors(True)
        self.fiyat_gecmisi_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.fiyat_gecmisi_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.fiyat_gecmisi_table.horizontalHeader().setStretchLastSection(True)
        right_layout.addWidget(self.fiyat_gecmisi_table)
        
        # Karşılaştırma özeti
        self.fiyat_karsilastirma_label = QLabel("Bir fiyat seçin veya çift tıklayın")
        self.fiyat_karsilastirma_label.setWordWrap(True)
        self.fiyat_karsilastirma_label.setStyleSheet("padding: 10px; background-color: #f5f5f5; border: 1px solid #ddd;")
        right_layout.addWidget(self.fiyat_karsilastirma_label)
        
        splitter.addWidget(right_widget)
        
        splitter.setSizes([500, 500])
        layout.addWidget(splitter)
        
        self.birim_fiyat_widget = tab
        if add_to_tabs:
            self.tabs.addTab(tab, "💰 Birim Fiyatlar")
    
    def load_birim_fiyatlar(self) -> None:
        """Birim fiyatları yükle"""
        # Sekme henüz oluşturulmamışsa (lazy loading) yükleme yapma
        if not hasattr(self, 'fiyat_filter_combo') or not self._tabs_created.get('birim_fiyat', False):
            return
        
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()  # UI'ı güncelle
        
        aktif_only = self.fiyat_filter_combo.currentText() == "Sadece Aktif"
        fiyatlar = self.db.get_all_birim_fiyatlar(aktif_only=aktif_only)
        
        self.birim_fiyat_table.setRowCount(len(fiyatlar))
        
        for row, fiyat in enumerate(fiyatlar):
            self.birim_fiyat_table.setItem(row, 0, QTableWidgetItem(fiyat.get('poz_no', '')))
            self.birim_fiyat_table.setItem(row, 1, QTableWidgetItem(fiyat.get('poz_tanim', '')))
            self.birim_fiyat_table.setItem(row, 2, QTableWidgetItem(f"{fiyat.get('birim_fiyat', 0):,.2f} ₺"))
            tarih = fiyat.get('tarih', '')[:10] if fiyat.get('tarih') else ''
            self.birim_fiyat_table.setItem(row, 3, QTableWidgetItem(tarih))
            self.birim_fiyat_table.setItem(row, 4, QTableWidgetItem(fiyat.get('kaynak', '')))
            aktif_text = "Evet" if fiyat.get('aktif', 0) == 1 else "Hayır"
            self.birim_fiyat_table.setItem(row, 5, QTableWidgetItem(aktif_text))
            
            # ID'yi sakla
            item = self.birim_fiyat_table.item(row, 0)
            if item:
                item.setData(Qt.ItemDataRole.UserRole, fiyat.get('poz_no', ''))
            
            # Her 50 satırda bir UI'ı güncelle
            if row % 50 == 0:
                QApplication.processEvents()
    
    def view_fiyat_gecmisi(self, item: QTableWidgetItem) -> None:
        """Fiyat geçmişini ve karşılaştırmayı göster"""
        row = item.row()
        poz_no_item = self.birim_fiyat_table.item(row, 0)
        if not poz_no_item:
            return
        
        poz_no = poz_no_item.data(Qt.ItemDataRole.UserRole)
        if not poz_no:
            poz_no = poz_no_item.text()
        
        # Fiyat geçmişini yükle
        gecmis = self.db.get_birim_fiyat_gecmisi(poz_no=poz_no)
        self.fiyat_gecmisi_table.setRowCount(len(gecmis))
        
        for row_idx, fiyat in enumerate(gecmis):
            tarih = fiyat.get('tarih', '')[:10] if fiyat.get('tarih') else ''
            self.fiyat_gecmisi_table.setItem(row_idx, 0, QTableWidgetItem(tarih))
            self.fiyat_gecmisi_table.setItem(row_idx, 1, QTableWidgetItem(f"{fiyat.get('birim_fiyat', 0):,.2f} ₺"))
            self.fiyat_gecmisi_table.setItem(row_idx, 2, QTableWidgetItem(fiyat.get('kaynak', '')))
            self.fiyat_gecmisi_table.setItem(row_idx, 3, QTableWidgetItem(fiyat.get('aciklama', '')))
            aktif_text = "Evet" if fiyat.get('aktif', 0) == 1 else "Hayır"
            self.fiyat_gecmisi_table.setItem(row_idx, 4, QTableWidgetItem(aktif_text))
        
        # Karşılaştırma yap
        karsilastirma = self.db.compare_birim_fiyatlar(poz_no)
    
    def edit_birim_fiyat(self) -> None:
        """Seçili pozun birim fiyatını düzelt"""
        current_row = self.birim_fiyat_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Uyarı", "Lütfen düzeltmek istediğiniz bir fiyat satırını seçin")
            return
        
        poz_no_item = self.birim_fiyat_table.item(current_row, 0)
        if not poz_no_item:
            return
        
        poz_no = poz_no_item.data(Qt.ItemDataRole.UserRole)
        if not poz_no:
            poz_no = poz_no_item.text()
        
        # Mevcut fiyatı al
        fiyat_item = self.birim_fiyat_table.item(current_row, 2)
        mevcut_fiyat = 0.0
        if fiyat_item:
            fiyat_text = fiyat_item.text().replace("₺", "").replace(",", ".").strip()
            try:
                mevcut_fiyat = float(fiyat_text)
            except:
                pass
        
        # Yeni fiyat gir
        from PyQt6.QtWidgets import QInputDialog
        yeni_fiyat, ok = QInputDialog.getDouble(
            self,
            "Fiyat Düzelt",
            f"Poz {poz_no} için yeni birim fiyatı girin:",
            mevcut_fiyat,
            0.0,
            999999999.99,
            2
        )
        
        if ok and yeni_fiyat > 0:
            # Poz bilgisini al
            poz_data = self.db.get_poz_by_no(poz_no)
            if not poz_data:
                QMessageBox.warning(self, "Uyarı", f"Poz {poz_no} bulunamadı")
                return
            
            poz_id = poz_data.get('id')
            
            # Eski aktif fiyatları pasif yap
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE birim_fiyatlar SET aktif = 0
                    WHERE poz_id = ? AND aktif = 1
                """, (poz_id,))
            
            # Yeni fiyatı ekle
            fiyat_id = self.db.add_birim_fiyat(
                poz_id=poz_id,
                poz_no=poz_no,
                birim_fiyat=yeni_fiyat,
                kaynak='Manuel Düzeltme',
                aciklama=f'Eski fiyat: {mevcut_fiyat:,.2f} ₺'
            )
            
            if fiyat_id:
                # Poz'un resmi_fiyat'ını da güncelle
                with self.db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE pozlar SET resmi_fiyat = ?
                        WHERE poz_no = ?
                    """, (yeni_fiyat, poz_no))
                
                QMessageBox.information(self, "Başarılı", f"Poz {poz_no} için birim fiyat {yeni_fiyat:,.2f} ₺ olarak güncellendi")
                self.load_birim_fiyatlar()
                # Fiyat geçmişini de yenile
                poz_no_item = self.birim_fiyat_table.item(current_row, 0)
                if poz_no_item:
                    self.view_fiyat_gecmisi(poz_no_item)
            else:
                QMessageBox.warning(self, "Hata", "Fiyat güncellenirken bir hata oluştu")
        
        if karsilastirma['fiyat_sayisi'] > 0:
            text = f"📊 Poz: {poz_no}\n\n"
            text += f"💰 Toplam Fiyat Kaydı: {karsilastirma['fiyat_sayisi']}\n"
            text += f"📉 En Düşük: {karsilastirma['en_dusuk']:,.2f} ₺\n"
            text += f"📈 En Yüksek: {karsilastirma['en_yuksek']:,.2f} ₺\n"
            text += f"📊 Ortalama: {karsilastirma['ortalama']:,.2f} ₺\n"
            text += f"📏 Fark: {karsilastirma['en_yuksek'] - karsilastirma['en_dusuk']:,.2f} ₺\n\n"
            
            if karsilastirma['kaynaklar']:
                text += "📋 Kaynaklar:\n"
                for kaynak, fiyatlar in karsilastirma['kaynaklar'].items():
                    ortalama_kaynak = sum(fiyatlar) / len(fiyatlar)
                    text += f"  • {kaynak}: {ortalama_kaynak:,.2f} ₺ ({len(fiyatlar)} kayıt)\n"
        else:
            text = f"Poz {poz_no} için henüz fiyat kaydı yok."
        
        self.fiyat_karsilastirma_label.setText(text)
    
    def add_birim_fiyat(self) -> None:
        """Birim fiyat ekle dialogu"""
        from PyQt6.QtWidgets import QDialog, QFormLayout, QDateEdit
        from PyQt6.QtCore import QDate
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Birim Fiyat Ekle")
        dialog.setMinimumWidth(400)
        
        layout = QFormLayout(dialog)
        
        poz_no_input = QLineEdit()
        poz_no_input.setPlaceholderText("Örn: 03.001")
        layout.addRow("Poz No:", poz_no_input)
        
        birim_fiyat_spin = QDoubleSpinBox()
        birim_fiyat_spin.setMaximum(999999999)
        birim_fiyat_spin.setDecimals(2)
        birim_fiyat_spin.setPrefix("₺ ")
        layout.addRow("Birim Fiyat:", birim_fiyat_spin)
        
        tarih_input = QDateEdit()
        tarih_input.setDate(QDate.currentDate())
        tarih_input.setCalendarPopup(True)
        layout.addRow("Tarih:", tarih_input)
        
        kaynak_input = QLineEdit()
        kaynak_input.setPlaceholderText("Örn: Tedarikçi A, Resmi Fiyat")
        layout.addRow("Kaynak:", kaynak_input)
        
        aciklama_input = QTextEdit()
        aciklama_input.setMaximumHeight(80)
        layout.addRow("Açıklama:", aciklama_input)
        
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("Kaydet")
        btn_ok.clicked.connect(dialog.accept)
        btn_cancel = QPushButton("İptal")
        btn_cancel.clicked.connect(dialog.reject)
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addRow(btn_layout)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            poz_no = poz_no_input.text().strip()
            birim_fiyat = birim_fiyat_spin.value()
            tarih = tarih_input.date().toString("yyyy-MM-dd")
            kaynak = kaynak_input.text().strip()
            aciklama = aciklama_input.toPlainText().strip()
            
            if not poz_no:
                QMessageBox.warning(self, "Uyarı", "Poz numarası gereklidir")
                return
            
            if birim_fiyat <= 0:
                QMessageBox.warning(self, "Uyarı", "Birim fiyat 0'dan büyük olmalıdır")
                return
            
            fiyat_id = self.db.add_birim_fiyat(
                poz_no=poz_no,
                birim_fiyat=birim_fiyat,
                tarih=tarih,
                kaynak=kaynak,
                aciklama=aciklama
            )
            
            if fiyat_id:
                QMessageBox.information(self, "Başarılı", "Birim fiyat eklendi")
                self.load_birim_fiyatlar()
                self.statusBar().showMessage(f"Birim fiyat eklendi: {poz_no}")
            else:
                QMessageBox.critical(self, "Hata", "Birim fiyat eklenirken bir hata oluştu")
    
    def create_ihale_tab(self, add_to_tabs: bool = True) -> None:
        """İhale Dosyası Hazırlama sekmesini oluştur"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Üst panel: İhale seçimi ve poz arama
        top_layout = QHBoxLayout()
        
        # İhale seçimi
        ihale_label = QLabel("İhale:")
        top_layout.addWidget(ihale_label)
        
        self.ihale_combo = QComboBox()
        self.ihale_combo.setMinimumWidth(200)
        self.ihale_combo.currentIndexChanged.connect(self.on_ihale_changed)
        top_layout.addWidget(self.ihale_combo)
        
        btn_new_ihale = QPushButton("Yeni İhale")
        btn_new_ihale.clicked.connect(self.new_ihale)
        top_layout.addWidget(btn_new_ihale)
        
        top_layout.addStretch()
        
        # Poz arama
        search_label = QLabel("Poz Ara:")
        top_layout.addWidget(search_label)
        
        self.ihale_poz_search = QLineEdit()
        self.ihale_poz_search.setPlaceholderText("Poz no veya tanım ara...")
        self.ihale_poz_search.setMinimumWidth(200)
        self.ihale_poz_search.textChanged.connect(self.on_ihale_poz_search)
        top_layout.addWidget(self.ihale_poz_search)
        
        btn_add_poz = QPushButton("Listeye Ekle")
        btn_add_poz.clicked.connect(self.add_poz_to_ihale)
        top_layout.addWidget(btn_add_poz)
        
        layout.addLayout(top_layout)
        
        # Splitter: Sol tarafta poz arama sonuçları, sağ tarafta ihale kalemleri
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Sol: Poz arama sonuçları
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        poz_title = QLabel("🔍 Poz Arama Sonuçları")
        poz_title.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        left_layout.addWidget(poz_title)
        
        self.ihale_poz_results_table = QTableWidget()
        self.ihale_poz_results_table.setColumnCount(4)
        self.ihale_poz_results_table.setHorizontalHeaderLabels(["Poz No", "Tanım", "Birim", "Birim Fiyat"])
        self.ihale_poz_results_table.setAlternatingRowColors(True)
        self.ihale_poz_results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.ihale_poz_results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.ihale_poz_results_table.horizontalHeader().setStretchLastSection(True)
        self.ihale_poz_results_table.setColumnWidth(0, 120)
        self.ihale_poz_results_table.setColumnWidth(1, 300)
        self.ihale_poz_results_table.setColumnWidth(2, 80)
        self.ihale_poz_results_table.setColumnWidth(3, 120)
        self.ihale_poz_results_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.ihale_poz_results_table.itemDoubleClicked.connect(self.add_selected_poz_to_ihale)
        # Tablo görünürlüğünü garanti et
        self.ihale_poz_results_table.setVisible(True)
        left_layout.addWidget(self.ihale_poz_results_table)
        
        splitter.addWidget(left_widget)
        
        # Sağ: İhale kalemleri
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        kalem_title = QLabel("📋 İhale Kalem Listesi")
        kalem_title.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        right_layout.addWidget(kalem_title)
        
        # Butonlar
        kalem_btn_layout = QHBoxLayout()
        
        btn_delete_kalem = QPushButton("Kalem Sil")
        btn_delete_kalem.clicked.connect(self.delete_ihale_kalem)
        btn_delete_kalem.setStyleSheet("background-color: #c9184a;")
        
        btn_edit_tanim = QPushButton("✏️ Tanımı Düzelt")
        btn_edit_tanim.clicked.connect(self.edit_ihale_tanim)
        right_layout.addWidget(btn_edit_tanim)
        kalem_btn_layout.addWidget(btn_delete_kalem)
        
        btn_export = QPushButton("İhale Dosyası Oluştur (PDF)")
        btn_export.clicked.connect(self.export_ihale_pdf)
        kalem_btn_layout.addWidget(btn_export)
        
        btn_export_excel = QPushButton("İhale Dosyası Oluştur (Excel)")
        btn_export_excel.clicked.connect(self.export_ihale_excel)
        kalem_btn_layout.addWidget(btn_export_excel)
        
        kalem_btn_layout.addStretch()
        
        # KDV oranı seçimi
        kdv_label = QLabel("KDV:")
        kalem_btn_layout.addWidget(kdv_label)
        self.ihale_kdv_rate = QComboBox()
        self.ihale_kdv_rate.addItems(["%1", "%10", "%20"])
        self.ihale_kdv_rate.setCurrentText("%20")
        self.ihale_kdv_rate.currentTextChanged.connect(self.load_ihale_kalemleri)
        kalem_btn_layout.addWidget(self.ihale_kdv_rate)
        
        # Toplam etiketleri
        self.ihale_total_label = QLabel("Toplam (KDV Hariç): 0.00 ₺")
        self.ihale_total_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        kalem_btn_layout.addWidget(self.ihale_total_label)
        
        self.ihale_total_kdv_label = QLabel("Toplam (KDV Dahil): 0.00 ₺")
        self.ihale_total_kdv_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.ihale_total_kdv_label.setStyleSheet("color: #00BFFF;")
        kalem_btn_layout.addWidget(self.ihale_total_kdv_label)
        
        right_layout.addLayout(kalem_btn_layout)
        
        self.ihale_kalem_table = QTableWidget()
        self.ihale_kalem_table.setColumnCount(7)
        self.ihale_kalem_table.setHorizontalHeaderLabels([
            "Sıra", "Poz No", "Tanım", "Birim Miktar", "Birim", "Birim Fiyat", "Toplam"
        ])
        self.ihale_kalem_table.setAlternatingRowColors(True)
        self.ihale_kalem_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.ihale_kalem_table.horizontalHeader().setStretchLastSection(True)
        self.ihale_kalem_table.setColumnWidth(0, 50)
        self.ihale_kalem_table.setColumnWidth(1, 120)
        self.ihale_kalem_table.setColumnWidth(2, 400)  # Tanım sütunu genişletildi
        self.ihale_kalem_table.setColumnWidth(3, 120)
        self.ihale_kalem_table.setColumnWidth(4, 80)
        self.ihale_kalem_table.setColumnWidth(5, 120)
        # Tanım sütununu genişletilebilir yap
        self.ihale_kalem_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        # Birim Miktar ve Birim Fiyat sütunları düzenlenebilir
        self.ihale_kalem_table.itemChanged.connect(self.on_ihale_kalem_changed)
        # Tanım sütununa çift tıklayınca tam metni göster
        self.ihale_kalem_table.itemDoubleClicked.connect(self.show_full_tanim)
        right_layout.addWidget(self.ihale_kalem_table)
        
        splitter.addWidget(right_widget)
        
        splitter.setSizes([400, 600])
        layout.addWidget(splitter)
        
        # Mevcut ihale ID'si
        self.current_ihale_id: Optional[int] = None
        
        self.ihale_widget = tab
        if add_to_tabs:
            self.tabs.addTab(tab, "📄 İhale Dosyası")
    
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
        
        # Yedekleme menüsü
        backup_menu = file_menu.addMenu("Yedekleme")
        
        # Proje yedekle
        backup_project_action = backup_menu.addAction("Projeyi Yedekle")
        backup_project_action.triggered.connect(self.backup_current_project)
        
        # Tüm projeleri yedekle
        backup_all_action = backup_menu.addAction("Tüm Projeleri Yedekle")
        backup_all_action.triggered.connect(self.backup_all_projects)
        
        backup_menu.addSeparator()
        
        # Geri yükle
        restore_action = backup_menu.addAction("Yedekten Geri Yükle")
        restore_action.triggered.connect(self.restore_project)
        
        # Versiyonlama menüsü
        version_menu = file_menu.addMenu("Versiyonlama")
        
        # Versiyon oluştur
        create_version_action = version_menu.addAction("Versiyon Oluştur")
        create_version_action.triggered.connect(self.create_project_version)
        
        # Versiyonları görüntüle
        view_versions_action = version_menu.addAction("Versiyonları Görüntüle")
        view_versions_action.triggered.connect(self.view_project_versions)
        
        # Versiyondan geri yükle
        restore_version_action = version_menu.addAction("Versiyondan Geri Yükle")
        restore_version_action.triggered.connect(self.restore_from_version)
        
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
        
        # Excel Import
        excel_import_action = data_menu.addAction("Excel'den Kalem İçe Aktar")
        excel_import_action.triggered.connect(self.import_from_excel)
        
        # PDF Import
        pdf_import_action = data_menu.addAction("PDF'den Birim Fiyat İçe Aktar")
        pdf_import_action.triggered.connect(self.import_from_pdf)
        
        # PDF Import Temizle
        pdf_clear_action = data_menu.addAction("PDF'den Eklenen Pozları Temizle")
        pdf_clear_action.triggered.connect(self.clear_pdf_imported_data)

        # Tüm Pozları Temizle
        clear_all_action = data_menu.addAction("⚠️ TÜM Pozları ve Fiyatları Temizle")
        clear_all_action.triggered.connect(self.clear_all_poz_data)

        data_menu.addSeparator()

        # Fiyatsız Pozları Göster
        show_missing_prices_action = data_menu.addAction("🔍 Fiyatsız Pozları Göster")
        show_missing_prices_action.triggered.connect(self.show_missing_prices)

        check_pozlar_action = data_menu.addAction("Poz Durumunu Kontrol Et")
        check_pozlar_action.triggered.connect(self.check_pozlar_status)
        
        # Araçlar menüsü
        tools_menu = menubar.addMenu("Araçlar")
        
        # Demir Hesaplama
        demir_hesaplama_action = tools_menu.addAction("Yapısal Demir Hesaplama")
        demir_hesaplama_action.triggered.connect(self.open_demir_hesaplama)

        # Saha Demiri Hesabı
        saha_demiri_action = tools_menu.addAction("Saha Demiri Hesabı")
        saha_demiri_action.triggered.connect(self.open_saha_demiri)

        # Duvar Maliyet Hesaplama
        duvar_maliyet_action = tools_menu.addAction("Duvar Maliyet Hesaplama")
        duvar_maliyet_action.triggered.connect(self.open_duvar_maliyet)

        # Alçı (Sıva) Maliyet Hesaplama
        alci_maliyet_action = tools_menu.addAction("Makine Alçı Maliyet Hesaplama")
        alci_maliyet_action.triggered.connect(self.open_alci_maliyet)

        # Kara Sıva (El ile) Maliyet Hesaplama
        kara_siva_action = tools_menu.addAction("Kara Sıva (El ile) Maliyet Hesaplama")
        kara_siva_action.triggered.connect(self.open_kara_siva)

        # Boya Maliyet Hesaplama (Gelişmiş)
        boya_maliyet_action = tools_menu.addAction("Boya Maliyet Hesaplama (Gelişmiş)")
        boya_maliyet_action.triggered.connect(self.open_boya_maliyet)

        # Fayans Hesaplama (Oda Bazli)
        fayans_hesaplama_action = tools_menu.addAction("Fayans Hesaplama (Oda Bazli)")
        fayans_hesaplama_action.triggered.connect(self.open_fayans_hesaplama)

        # Sap (Tesviye Betonu) Maliyet Hesaplama
        sap_maliyet_action = tools_menu.addAction("Sap (Tesviye Betonu) Maliyet Hesaplama")
        sap_maliyet_action.triggered.connect(self.open_sap_maliyet)

        # Laminat Parke ve Supurgelik Hesaplama
        parke_maliyet_action = tools_menu.addAction("Laminat Parke ve Supurgelik Hesaplama")
        parke_maliyet_action.triggered.connect(self.open_parke_maliyet)

        # Dış Cephe Mantolama Hesaplama (Minha Kuralı)
        mantolama_action = tools_menu.addAction("Dış Cephe Mantolama Hesaplama (Minha)")
        mantolama_action.triggered.connect(self.open_mantolama_hesaplama)

        # Mermer İşleri Hesaplama (Merdiven, Denizlik, Harç)
        mermer_action = tools_menu.addAction("Mermer İşleri Hesaplama (Merdiven/Denizlik)")
        mermer_action.triggered.connect(self.open_mermer_hesaplama)

        # PVC Doğrama Hesaplama (Pencere/Kapı)
        pvc_action = tools_menu.addAction("PVC Doğrama Hesaplama (Pencere/Kapı)")
        pvc_action.triggered.connect(self.open_pvc_dograma_hesaplama)

        # Mobilya Maliyet Hesaplama (Mutfak/Vestiyer/Banyo/Kapi)
        mobilya_action = tools_menu.addAction("Mobilya Maliyet Hesaplama (Mutfak/Vestiyer/Banyo/Kapi)")
        mobilya_action.triggered.connect(self.open_mobilya_maliyet)

        # Su Yalitim Maliyet Hesaplama (Bez/Toz/Surme)
        yalitim_action = tools_menu.addAction("Su Yalitim Maliyet Hesaplama (Bez/Toz/Surme)")
        yalitim_action.triggered.connect(self.open_yalitim_maliyet)

        # Elektrik Tesisat Maliyet Hesaplama
        elektrik_action = tools_menu.addAction("Elektrik Tesisat Maliyet Hesaplama")
        elektrik_action.triggered.connect(self.open_elektrik_maliyet)

        # Vitrifiye ve Armatur Maliyet Hesaplama
        vitrifiye_action = tools_menu.addAction("Vitrifiye ve Armatur Maliyet Hesaplama")
        vitrifiye_action.triggered.connect(self.open_vitrifiye_maliyet)

        # Kaba Yapi Maliyet Hesaplama (Hafriyat/Demir/Beton)
        kaba_yapi_action = tools_menu.addAction("Kaba Yapi Maliyet Hesaplama (Hafriyat/Demir/Beton)")
        kaba_yapi_action.triggered.connect(self.open_kaba_yapi_maliyet)

        # Akilli Metraj Analizi (Kiris/Duvar Cakisma Tespiti)
        metraj_analiz_action = tools_menu.addAction("Akilli Metraj Analizi")
        metraj_analiz_action.triggered.connect(self.open_metraj_analiz)

        tools_menu.addSeparator()

        # Mobil Puantaj Sunucusu
        puantaj_server_action = tools_menu.addAction("📱 Mobil Puantaj Sunucusu")
        puantaj_server_action.triggered.connect(self.open_puantaj_server)

        # Puantaj Raporu
        puantaj_rapor_action = tools_menu.addAction("📊 Puantaj Raporu")
        puantaj_rapor_action.triggered.connect(self.open_puantaj_rapor)

        tools_menu.addSeparator()

        # Birim dönüştürücü
        unit_converter_action = tools_menu.addAction("Birim Dönüştürücü")
        unit_converter_action.triggered.connect(self.show_unit_converter)
        
        tools_menu.addSeparator()
        
        # Yenile (Modül yeniden yükleme)
        reload_action = tools_menu.addAction("🔄 Yenile (Modülleri Yeniden Yükle)")
        reload_action.setShortcut("Ctrl+R")
        reload_action.triggered.connect(self.reload_modules)
        
        tools_menu.addSeparator()
        
        # Otomatik fire oranı hesaplama
        auto_fire_action = tools_menu.addAction("Otomatik Fire Oranı Hesapla")
        auto_fire_action.triggered.connect(self.calculate_auto_fire_rates)
        
        # Yardım menüsü
        help_menu = menubar.addMenu("Yardim")
        guide_action = help_menu.addAction("Kullanim Kilavuzu")
        guide_action.triggered.connect(self.show_kullanim_kilavuzu)
        help_menu.addSeparator()
        about_action = help_menu.addAction("Hakkinda")
        about_action.triggered.connect(self.show_about)
        
    # Proje İşlemleri
    def load_data_async(self) -> None:
        """Veritabanı verilerini async yükle"""
        # Projeleri async yükle
        self.initial_data_thread = InitialDataLoaderThread(self.db)
        self.initial_data_thread.projects_loaded.connect(self.on_projects_loaded)
        self.initial_data_thread.start()
    
    @pyqtSlot(list)
    def on_projects_loaded(self, projects: List[Dict[str, Any]]) -> None:
        """Projeler yüklendiğinde çağrılır"""
        self.project_tree.clear()
        for project in projects:
            item = QTreeWidgetItem(self.project_tree)
            item.setText(0, project['ad'])
            item.setData(0, Qt.ItemDataRole.UserRole, project['id'])
        self.statusBar().showMessage(f"{len(projects)} proje yüklendi")
    
    def load_projects(self) -> None:
        """Projeleri yükle (sync versiyon - eski)"""
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
            # Verileri yükle (sadece sekmeler oluşturulmuşsa)
            if hasattr(self, 'metraj_table'):
                self.load_metraj_data()
            if hasattr(self, 'taseron_table'):
                self.load_taseron_data()
            if hasattr(self, 'ozet_kalem_label'):
                self.update_proje_ozet()
            self.load_project_notes()
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
                # Projeleri async yükle
                self.load_data_async()
                # Yeni oluşturulan projeyi otomatik seç (biraz bekle)
                from PyQt6.QtWidgets import QApplication
                QApplication.processEvents()
                # Proje listesi yüklendikten sonra seç
                from PyQt6.QtCore import QTimer
                def select_new_project():
                    for i in range(self.project_tree.topLevelItemCount()):
                        item = self.project_tree.topLevelItem(i)
                        if item and item.data(0, Qt.ItemDataRole.UserRole) == project_id:
                            self.project_tree.setCurrentItem(item)
                            self.on_project_selected(item, 0)
                            break
                QTimer.singleShot(100, select_new_project)  # 100ms sonra seç
                self.statusBar().showMessage(f"Yeni proje oluşturuldu: {name}")
                
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
                        # Tabloları temizle (lazy loading kontrolü ile)
                        if hasattr(self, 'metraj_table') and self._tabs_created.get('metraj', False):
                            self.metraj_table.setRowCount(0)
                        if hasattr(self, 'taseron_table') and self._tabs_created.get('taseron', False):
                            self.taseron_table.setRowCount(0)
                        if hasattr(self, 'total_label'):
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
        # Sekme henüz oluşturulmamışsa (lazy loading) yükleme yapma
        if not hasattr(self, 'metraj_table') or not self._tabs_created.get('metraj', False):
            return
        
        if not self.current_project_id:
            return
        
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()  # UI'ı güncelle
            
        items = self.db.get_project_metraj(self.current_project_id)
        QApplication.processEvents()  # UI'ı güncelle
        self.metraj_table.setRowCount(len(items))
        
        total = 0.0
        for row, item in enumerate(items):
            self.metraj_table.setItem(row, 0, QTableWidgetItem(str(item['id'])))
            self.metraj_table.setItem(row, 1, QTableWidgetItem(item.get('poz_no', '')))
            self.metraj_table.setItem(row, 2, QTableWidgetItem(item['tanim']))
            # Miktar - virgülden sonra max 2 hane
            miktar = round(item.get('miktar', 0), 2)
            miktar_text = f"{miktar:,.2f}"
            self.metraj_table.setItem(row, 3, QTableWidgetItem(miktar_text))
            self.metraj_table.setItem(row, 4, QTableWidgetItem(item['birim']))
            self.metraj_table.setItem(row, 5, QTableWidgetItem(f"{item['birim_fiyat']:.2f}"))
            self.metraj_table.setItem(row, 6, QTableWidgetItem(f"{item['toplam']:.2f}"))
            total += item['toplam']
            
            # Her 50 satırda bir UI'ı güncelle
            if row % 50 == 0:
                QApplication.processEvents()
            
        # KDV hesaplama
        kdv_rate_text = self.metraj_kdv_rate.currentText().replace("%", "")
        kdv_rate = float(kdv_rate_text)
        kdv_hesap = self.calculator.calculate_with_kdv(total, kdv_rate)
        
        self.total_label.setText(f"Toplam (KDV Hariç): {total:,.2f} ₺")
        self.total_kdv_label.setText(f"Toplam (KDV %{kdv_rate_text} Dahil): {kdv_hesap['kdv_dahil']:,.2f} ₺")
        
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
                    toplam=data.get('toplam', data['miktar'] * data['birim_fiyat']),  # Düzenlenebilir toplam
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
    
    def load_dxf_for_metraj(self) -> None:
        """DXF dosyası yükle ve duvar yüksekliği tahmin et"""
        if not self.current_project_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce bir proje seçin")
            return
        
        # Birim seçimi dialog'u
        birim, ok = QInputDialog.getItem(
            self,
            "DXF Birim Seçimi",
            "DXF dosyasının çizim birimi nedir?",
            ["cm (Santimetre)", "m (Metre)", "mm (Milimetre)"],
            0,  # Varsayılan: cm
            False
        )
        
        if not ok:
            return
        
        # Birim string'ini parse et
        if "cm" in birim.lower():
            cizim_birimi = "cm"
        elif "m" in birim.lower() and "mm" not in birim.lower():
            cizim_birimi = "m"
        else:
            cizim_birimi = "mm"
        
        # DXF dosyası seç
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "DXF Dosyası Seç",
            "",
            "DXF Dosyaları (*.dxf);;Tüm Dosyalar (*.*)"
        )
        
        if not file_path:
            return
        
        try:
            # DXF dosyasını yükle
            from app.core.dxf_engine import DXFAnaliz
            dxf_analiz = DXFAnaliz(file_path, cizim_birimi=cizim_birimi)
            katmanlar = dxf_analiz.katmanlari_listele()
            
            if not katmanlar:
                QMessageBox.warning(self, "Uyarı", "DXF dosyasında katman bulunamadı")
                return
            
            # Duvar katmanlarını filtrele (DIS_DUVAR, IC_DUVAR vb.)
            duvar_katmanlari = [k for k in katmanlar if 'DUVAR' in k.upper() or 'DIS' in k.upper()]
            
            if not duvar_katmanlari:
                QMessageBox.information(
                    self, "Bilgi",
                    f"DXF dosyasında {len(katmanlar)} katman bulundu ancak duvar katmanı bulunamadı.\n"
                    f"Katmanlar: {', '.join(katmanlar[:10])}"
                )
                return
            
            # Duvar yüksekliği tahmin dialog'u göster
            self.show_duvar_yukseklik_dialog(dxf_analiz, duvar_katmanlari, file_path)
            
        except Exception as e:
            QMessageBox.critical(
                self, "Hata",
                f"DXF dosyası yüklenirken hata oluştu:\n{str(e)}"
            )
    
    def show_duvar_yukseklik_dialog(self, dxf_analiz: DXFAnaliz, 
                                    katmanlar: List[str], file_path: str) -> None:
        """Duvar yüksekliği tahmin dialog'unu göster"""
        dialog = QDialog(self)
        dialog.setWindowTitle("AI Duvar Yüksekliği Tahmini")
        dialog.setMinimumWidth(600)
        dialog.setMinimumHeight(400)
        
        layout = QVBoxLayout(dialog)
        
        # Başlık
        title = QLabel("📐 DXF Dosyasından Duvar Yüksekliği Tahmini")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Bilgi
        info_text = (
            f"Dosya: {Path(file_path).name}\n"
            f"Bulunan duvar katmanları: {len(katmanlar)}\n"
            f"Çizim birimi: {dxf_analiz.birim}\n\n"
            f"💡 İpucu: Eğer uzunluk veya alan değerleri beklenenden farklıysa,\n"
            f"   birim seçimini kontrol edin (cm/m/mm)."
        )
        info = QLabel(info_text)
        info.setStyleSheet("color: #666; padding: 5px; font-size: 9pt;")
        layout.addWidget(info)
        
        # Açıklık Seçimi Bölümü
        aciklik_group = QGroupBox("🚪 Açıklık Katmanları (Pencere ve Kapı)")
        aciklik_layout = QVBoxLayout()
        
        # Otomatik tespit edilen açıklıklar
        tespit_edilen_acikliklar = dxf_analiz.acikliklari_tespit_et()
        pencere_katmanlari = tespit_edilen_acikliklar.get('pencere', [])
        kapi_katmanlari = tespit_edilen_acikliklar.get('kapi', [])
        
        # Pencere seçimi
        pencere_label = QLabel("Pencere Katmanları:")
        aciklik_layout.addWidget(pencere_label)
        pencere_list = QListWidget()
        pencere_list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        pencere_list.setMaximumHeight(80)
        for katman in pencere_katmanlari:
            pencere_list.addItem(katman)
        # Eğer otomatik tespit edilmediyse, tüm katmanlardan seçim yapılabilir
        if not pencere_katmanlari:
            pencere_list.addItem("(Otomatik tespit edilmedi - manuel seçim için tüm katmanları kontrol edin)")
        aciklik_layout.addWidget(pencere_list)
        
        # Kapı seçimi
        kapi_label = QLabel("Kapı Katmanları:")
        aciklik_layout.addWidget(kapi_label)
        kapi_list = QListWidget()
        kapi_list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        kapi_list.setMaximumHeight(80)
        for katman in kapi_katmanlari:
            kapi_list.addItem(katman)
        if not kapi_katmanlari:
            kapi_list.addItem("(Otomatik tespit edilmedi - manuel seçim için tüm katmanları kontrol edin)")
        aciklik_layout.addWidget(kapi_list)
        
        # Manuel katman ekleme (opsiyonel)
        manuel_label = QLabel("Manuel Katman Ekleme (opsiyonel):")
        aciklik_layout.addWidget(manuel_label)
        manuel_input = QLineEdit()
        manuel_input.setPlaceholderText("Örn: PENCERE_1, KAPI_1 (virgülle ayırın)")
        aciklik_layout.addWidget(manuel_input)
        
        aciklik_group.setLayout(aciklik_layout)
        layout.addWidget(aciklik_group)
        
        # Açıklık bilgisi sakla (dialog kapanana kadar)
        dialog.pencere_list = pencere_list
        dialog.kapi_list = kapi_list
        dialog.manuel_input = manuel_input
        
        # Tablo: Katman, Bulunan Uzunluk, Tahmin Yükseklik, Kalınlık, Cins, Tahmini Alan, Kaynak, Düzeltme
        table = QTableWidget()
        table.setColumnCount(8)
        table.setHorizontalHeaderLabels([
            "Katman Adı", "Bulunan Uzunluk (m)", "Tahmin Yükseklik (m)", "Kalınlık (cm)", "Cins", "Tahmini Alan (m²)", "Kaynak", "Düzelt"
        ])
        table.setRowCount(len(katmanlar))
        table.horizontalHeader().setStretchLastSection(True)
        table.setColumnWidth(0, 150)
        table.setColumnWidth(1, 120)
        table.setColumnWidth(2, 120)
        table.setColumnWidth(3, 100)
        table.setColumnWidth(4, 100)
        table.setColumnWidth(5, 120)
        table.setColumnWidth(6, 120)
        
        yukseklikler = {}
        # Tabloyu güncellemek için referans sakla
        self._dxf_dialog_table = table
        self._dxf_dialog_katmanlar = katmanlar
        self._dxf_dialog_dxf_analiz = dxf_analiz
        
        for row, katman in enumerate(katmanlar):
            # Önce uzunluk hesapla (önizleme için)
            uzunluk_sonuc = dxf_analiz.uzunluk_hesapla(katman)
            uzunluk_m = uzunluk_sonuc['toplam_miktar']
            parca_sayisi = uzunluk_sonuc.get('parca_sayisi', 0)
            detay = uzunluk_sonuc.get('detay', [])
            
            # Tahmin et
            tahmin = dxf_analiz.duvar_yuksekligi_tahmin_et(katman, self.db)
            yukseklik = tahmin['yukseklik']
            kalinlik = tahmin.get('kalinlik')
            cins = tahmin.get('cins')
            
            # Tahmini alan hesapla
            tahmini_alan = uzunluk_m * yukseklik if uzunluk_m > 0 else 0.0
            
            table.setItem(row, 0, QTableWidgetItem(katman))
            
            # Uzunluk bilgisi
            uzunluk_text = f"{uzunluk_m:.2f}"
            if parca_sayisi > 0:
                uzunluk_text += f" ({parca_sayisi} parça)"
            uzunluk_item = QTableWidgetItem(uzunluk_text)
            if uzunluk_m == 0:
                uzunluk_item.setForeground(Qt.GlobalColor.red)
            else:
                # Uzunluk çok küçükse veya çok büyükse uyarı
                if uzunluk_m < 0.1:
                    uzunluk_item.setForeground(Qt.GlobalColor.yellow)
                    uzunluk_item.setToolTip("⚠️ Uzunluk çok küçük! Birim kontrolü gerekebilir.")
                elif uzunluk_m > 1000:
                    uzunluk_item.setForeground(Qt.GlobalColor.yellow)
                    uzunluk_item.setToolTip("⚠️ Uzunluk çok büyük! Birim kontrolü gerekebilir.")
            table.setItem(row, 1, uzunluk_item)
            
            table.setItem(row, 2, QTableWidgetItem(f"{yukseklik:.2f}"))
            
            # Kalınlık bilgisi
            kalinlik_text = f"{kalinlik:.1f}" if kalinlik else "-"
            kalinlik_item = QTableWidgetItem(kalinlik_text)
            if kalinlik:
                kalinlik_item.setForeground(Qt.GlobalColor.green)
            else:
                kalinlik_item.setForeground(Qt.GlobalColor.gray)
            table.setItem(row, 3, kalinlik_item)
            
            # Cins bilgisi
            cins_text = cins if cins else "-"
            cins_item = QTableWidgetItem(cins_text)
            if cins:
                cins_item.setForeground(Qt.GlobalColor.green)
            else:
                cins_item.setForeground(Qt.GlobalColor.gray)
            table.setItem(row, 4, cins_item)
            
            # Tahmini alan
            alan_item = QTableWidgetItem(f"{tahmini_alan:.2f}")
            if tahmini_alan > 0:
                if tahmini_alan > 1000:
                    alan_item.setForeground(Qt.GlobalColor.yellow)
                    alan_item.setToolTip("⚠️ Alan çok büyük! Birim kontrolü gerekebilir.")
            else:
                alan_item.setForeground(Qt.GlobalColor.red)
            table.setItem(row, 5, alan_item)
            
            table.setItem(row, 6, QTableWidgetItem(tahmin['kaynak']))
            
            # Düzeltme butonu
            btn_duzelt = QPushButton("Düzelt")
            btn_duzelt.clicked.connect(
                lambda checked, k=katman, y=yukseklik, kal=kalinlik, c=cins: 
                self.duzelt_duvar_yuksekligi(k, y, dialog, kal, c)
            )
            table.setCellWidget(row, 7, btn_duzelt)
            
            yukseklikler[katman] = tahmin
        
        layout.addWidget(table)
        
        # Butonlar
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        btn_kaydet = QPushButton("Kaydet ve Metraj'a Ekle")
        def kaydet_ve_metraj_ekle():
            # Tablodan güncel değerleri oku
            guncel_yukseklikler = {}
            for row in range(table.rowCount()):
                katman = table.item(row, 0).text()
                yukseklik_text = table.item(row, 2).text()
                kalinlik_text = table.item(row, 3).text()
                cins_text = table.item(row, 4).text()
                kaynak_text = table.item(row, 6).text()
                
                try:
                    yukseklik = float(yukseklik_text)
                except:
                    yukseklik = 2.80  # Varsayılan
                
                kalinlik = None
                if kalinlik_text and kalinlik_text != "-":
                    try:
                        kalinlik = float(kalinlik_text)
                    except:
                        pass
                
                cins = None
                if cins_text and cins_text != "-":
                    cins = cins_text
                
                guncel_yukseklikler[katman] = {
                    'yukseklik': yukseklik,
                    'birim': 'm',
                    'kaynak': kaynak_text,
                    'katman_adi': katman,
                    'kalinlik': kalinlik,
                    'cins': cins
                }
            
            # Seçilen açıklık katmanlarını al
            secilen_pencere_katmanlari = []
            for item in pencere_list.selectedItems():
                katman_text = item.text()
                if not katman_text.startswith("(Otomatik"):
                    secilen_pencere_katmanlari.append(katman_text)
            
            secilen_kapi_katmanlari = []
            for item in kapi_list.selectedItems():
                katman_text = item.text()
                if not katman_text.startswith("(Otomatik"):
                    secilen_kapi_katmanlari.append(katman_text)
            
            # Manuel eklenen katmanlar
            manuel_text = manuel_input.text().strip()
            if manuel_text:
                manuel_katmanlar = [k.strip() for k in manuel_text.split(',') if k.strip()]
                # Manuel katmanları pencere veya kapı olarak ayırmak için pattern kontrolü
                for katman in manuel_katmanlar:
                    katman_lower = katman.lower()
                    if any(p in katman_lower for p in ['pencere', 'window', 'win', 'p-', 'w-']):
                        secilen_pencere_katmanlari.append(katman)
                    elif any(p in katman_lower for p in ['kapı', 'kapi', 'door', 'd-', 'k-']):
                        secilen_kapi_katmanlari.append(katman)
                    else:
                        # Belirsizse kullanıcıya sor (şimdilik kapı olarak ekle)
                        secilen_kapi_katmanlari.append(katman)
            
            aciklik_katmanlari = {
                'pencere': secilen_pencere_katmanlari,
                'kapi': secilen_kapi_katmanlari
            }
            
            # Güncel değerlerle metraj ekle
            self.kaydet_duvar_metraji(dxf_analiz, guncel_yukseklikler, dialog, aciklik_katmanlari)
        
        btn_kaydet.clicked.connect(kaydet_ve_metraj_ekle)
        btn_layout.addWidget(btn_kaydet)
        
        btn_kapat = QPushButton("Kapat")
        btn_kapat.clicked.connect(dialog.reject)
        btn_layout.addWidget(btn_kapat)
        
        layout.addLayout(btn_layout)
        
        dialog.exec()
    
    def duzelt_duvar_yuksekligi(self, katman_adi: str, mevcut_yukseklik: float, 
                                    parent_dialog: QDialog, mevcut_kalinlik: float = None, 
                                    mevcut_cins: str = None) -> None:
        """Duvar yüksekliğini, cinsini ve kalınlığını düzelt ve öğrenme veritabanına kaydet"""
        # Önce mevcut öğrenilmiş değerleri al
        mevcut_ogrenme = self.db.get_ai_learning(katman_adi)
        # Parametrelerden gelen değerler varsa onları kullan, yoksa veritabanından al
        if mevcut_cins is None:
            mevcut_cins = mevcut_ogrenme.get('duvar_cinsi', '') if mevcut_ogrenme else ''
        if mevcut_kalinlik is None:
            mevcut_kalinlik = mevcut_ogrenme.get('duvar_kalinligi', 0.0) if mevcut_ogrenme else 0.0
        
        # Dialog oluştur
        dialog = QDialog(parent_dialog)
        dialog.setWindowTitle("Duvar Bilgilerini Düzelt")
        dialog.setMinimumWidth(450)
        layout = QVBoxLayout(dialog)
        
        # Katman adı
        katman_label = QLabel(f"<b>Katman:</b> {katman_adi}")
        katman_label.setStyleSheet("font-size: 12pt; padding: 5px;")
        layout.addWidget(katman_label)
        layout.addWidget(QLabel(""))  # Boşluk
        
        # Yükseklik
        yukseklik_label = QLabel("Duvar Yüksekliği (m):")
        layout.addWidget(yukseklik_label)
        yukseklik_spin = QDoubleSpinBox()
        yukseklik_spin.setValue(mevcut_yukseklik)
        yukseklik_spin.setMinimum(0.5)
        yukseklik_spin.setMaximum(10.0)
        yukseklik_spin.setDecimals(2)
        yukseklik_spin.setSuffix(" m")
        yukseklik_spin.setSingleStep(0.1)
        layout.addWidget(yukseklik_spin)
        
        # Duvar cinsi
        cins_label = QLabel("Duvar Cinsi:")
        layout.addWidget(cins_label)
        cins_combo = QComboBox()
        cins_combo.setEditable(True)  # Kullanıcı kendi değerini yazabilsin
        cins_combo.addItems([
            "",  # Boş seçenek
            "Tuğla",
            "Beton",
            "Gazbeton",
            "Bims",
            "Ahşap",
            "Çelik",
            "Diğer"
        ])
        if mevcut_cins:
            index = cins_combo.findText(mevcut_cins)
            if index >= 0:
                cins_combo.setCurrentIndex(index)
            else:
                cins_combo.setCurrentText(mevcut_cins)
        layout.addWidget(cins_combo)
        
        # Duvar kalınlığı
        kalinlik_label = QLabel("Duvar Kalınlığı (cm):")
        layout.addWidget(kalinlik_label)
        kalinlik_spin = QDoubleSpinBox()
        # None kontrolü yap
        if mevcut_kalinlik is not None and mevcut_kalinlik > 0:
            kalinlik_spin.setValue(mevcut_kalinlik)
        else:
            kalinlik_spin.setValue(20.0)  # Varsayılan 20 cm
        kalinlik_spin.setMinimum(5.0)
        kalinlik_spin.setMaximum(100.0)
        kalinlik_spin.setDecimals(1)
        kalinlik_spin.setSuffix(" cm")
        kalinlik_spin.setSingleStep(5.0)
        layout.addWidget(kalinlik_spin)
        
        layout.addStretch()
        
        # Butonlar
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        btn_iptal = QPushButton("İptal")
        btn_kaydet = QPushButton("Kaydet")
        btn_kaydet.setDefault(True)
        
        def kaydet():
            yukseklik = yukseklik_spin.value()
            cins = cins_combo.currentText().strip() or None
            kalinlik = kalinlik_spin.value() if kalinlik_spin.value() > 0 else None
            
            # Öğrenme veritabanına kaydet
            try:
                self.db.save_ai_learning(
                    katman_adi=katman_adi,
                    duvar_yuksekligi=yukseklik,
                    birim='m',
                    kaynak='kullanici',
                    duvar_cinsi=cins,
                    duvar_kalinligi=kalinlik
                )
                logger.info(f"✅ AI öğrenme veritabanına kaydedildi: {katman_adi} - Yükseklik: {yukseklik}m, Kalınlık: {kalinlik}cm, Cins: {cins}")
            except Exception as e:
                logger.error(f"❌ AI öğrenme veritabanına kaydetme hatası: {e}", exc_info=True)
                QMessageBox.critical(dialog, "Hata", f"Değerler kaydedilemedi:\n{str(e)}")
                return
            
            # Parent dialog'daki tabloyu güncelle
            if hasattr(self, '_dxf_dialog_table') and self._dxf_dialog_table:
                self._guncelle_dxf_dialog_tablo_satiri(katman_adi, yukseklik, kalinlik, cins)
            
            # Başarı mesajı
            mesaj = f"✅ Duvar bilgileri kaydedildi:\n\nYükseklik: {yukseklik:.2f} m"
            if cins:
                mesaj += f"\nCins: {cins}"
            if kalinlik:
                mesaj += f"\nKalınlık: {kalinlik:.1f} cm"
            mesaj += "\n\n✅ AI bu değerleri öğrendi ve bir sonraki analizde kullanacak.\n\nTablo güncellendi!"
            
            QMessageBox.information(dialog, "Başarılı", mesaj)
            dialog.accept()
            # Parent dialog'u kapatma, sadece tabloyu güncelledik
        
        btn_kaydet.clicked.connect(kaydet)
        btn_iptal.clicked.connect(dialog.reject)
        
        btn_layout.addWidget(btn_iptal)
        btn_layout.addWidget(btn_kaydet)
        layout.addLayout(btn_layout)
        
        dialog.exec()
    
    def _guncelle_dxf_dialog_tablo_satiri(self, katman_adi: str, yukseklik: float, 
                                          kalinlik: float = None, cins: str = None) -> None:
        """DXF dialog tablosundaki belirli bir satırı güncelle"""
        if not hasattr(self, '_dxf_dialog_table') or not self._dxf_dialog_table:
            return
        
        table = self._dxf_dialog_table
        dxf_analiz = getattr(self, '_dxf_dialog_dxf_analiz', None)
        
        if not dxf_analiz:
            return
        
        # Katmanın satır numarasını bul
        katmanlar = getattr(self, '_dxf_dialog_katmanlar', [])
        try:
            row = katmanlar.index(katman_adi)
        except ValueError:
            logger.warning(f"Katman bulunamadı: {katman_adi}")
            return
        
        # Uzunluk hesapla (yeniden)
        uzunluk_sonuc = dxf_analiz.uzunluk_hesapla(katman_adi)
        uzunluk_m = uzunluk_sonuc['toplam_miktar']
        parca_sayisi = uzunluk_sonuc.get('parca_sayisi', 0)
        
        # Tahmini alan hesapla
        tahmini_alan = uzunluk_m * yukseklik if uzunluk_m > 0 else 0.0
        
        # Uzunluk bilgisini güncelle
        uzunluk_text = f"{uzunluk_m:.2f}"
        if parca_sayisi > 0:
            uzunluk_text += f" ({parca_sayisi} parça)"
        uzunluk_item = QTableWidgetItem(uzunluk_text)
        if uzunluk_m == 0:
            uzunluk_item.setForeground(Qt.GlobalColor.red)
        table.setItem(row, 1, uzunluk_item)
        
        # Yüksekliği güncelle
        table.setItem(row, 2, QTableWidgetItem(f"{yukseklik:.2f}"))
        
        # Kalınlık bilgisini güncelle
        kalinlik_text = f"{kalinlik:.1f}" if kalinlik else "-"
        kalinlik_item = QTableWidgetItem(kalinlik_text)
        if kalinlik:
            kalinlik_item.setForeground(Qt.GlobalColor.green)
        else:
            kalinlik_item.setForeground(Qt.GlobalColor.gray)
        table.setItem(row, 3, kalinlik_item)
        
        # Cins bilgisini güncelle
        cins_text = cins if cins else "-"
        cins_item = QTableWidgetItem(cins_text)
        if cins:
            cins_item.setForeground(Qt.GlobalColor.green)
        else:
            cins_item.setForeground(Qt.GlobalColor.gray)
        table.setItem(row, 4, cins_item)
        
        # Tahmini alanı güncelle
        alan_item = QTableWidgetItem(f"{tahmini_alan:.2f}")
        if tahmini_alan > 0:
            if tahmini_alan > 1000:
                alan_item.setForeground(Qt.GlobalColor.yellow)
                alan_item.setToolTip("⚠️ Alan çok büyük! Birim kontrolü gerekebilir.")
        else:
            alan_item.setForeground(Qt.GlobalColor.red)
        table.setItem(row, 5, alan_item)
        
        # Kaynak bilgisini güncelle (kullanıcı düzeltmesi)
        table.setItem(row, 6, QTableWidgetItem("kullanici"))
        
        logger.info(f"✅ DXF dialog tablosu güncellendi: {katman_adi} - Yükseklik: {yukseklik}m, Kalınlık: {kalinlik}cm, Cins: {cins}")
    
    def kaydet_duvar_metraji(self, dxf_analiz: DXFAnaliz, 
                             yukseklikler: Dict[str, Dict], 
                             dialog: QDialog, 
                             aciklik_katmanlari: Dict[str, List[str]] = None) -> None:
        """Duvar metrajını hesapla ve metraj tablosuna ekle (açıklık çıkarma ile)"""
        try:
            eklenen_sayisi = 0
            atlanan_katmanlar = []
            
            # Açıklık alanlarını hesapla (tüm pencere ve kapı katmanları için)
            toplam_aciklik_alani = 0.0
            aciklik_detaylari = []
            
            if aciklik_katmanlari:
                # Pencere alanları
                for pencere_katman in aciklik_katmanlari.get('pencere', []):
                    try:
                        pencere_alani = dxf_analiz.aciklik_alani_hesapla(pencere_katman)
                        if pencere_alani > 0:
                            toplam_aciklik_alani += pencere_alani
                            aciklik_detaylari.append(f"Pencere ({pencere_katman}): {pencere_alani:.2f} m²")
                            logger.info(f"🚪 Pencere alanı: {pencere_katman} = {pencere_alani:.2f} m²")
                    except Exception as e:
                        logger.warning(f"⚠️ Pencere alanı hesaplanamadı ({pencere_katman}): {e}")
                
                # Kapı alanları
                for kapi_katman in aciklik_katmanlari.get('kapi', []):
                    try:
                        kapi_alani = dxf_analiz.aciklik_alani_hesapla(kapi_katman)
                        if kapi_alani > 0:
                            toplam_aciklik_alani += kapi_alani
                            aciklik_detaylari.append(f"Kapı ({kapi_katman}): {kapi_alani:.2f} m²")
                            logger.info(f"🚪 Kapı alanı: {kapi_katman} = {kapi_alani:.2f} m²")
                    except Exception as e:
                        logger.warning(f"⚠️ Kapı alanı hesaplanamadı ({kapi_katman}): {e}")
            
            logger.info(f"📊 Toplam açıklık alanı: {toplam_aciklik_alani:.2f} m²")
            
            for katman, tahmin in yukseklikler.items():
                yukseklik = tahmin['yukseklik']
                brut_duvar_alani_m2 = 0.0
                
                # Önce uzunluk hesapla (duvarlar genelde LINE entity'leriyle çizilir)
                uzunluk_sonuc = dxf_analiz.uzunluk_hesapla(katman)
                uzunluk_m = uzunluk_sonuc['toplam_miktar']
                parca_sayisi = uzunluk_sonuc.get('parca_sayisi', 0)
                detay = uzunluk_sonuc.get('detay', [])
                
                # Debug: Ham değerleri göster (birim dönüşümü öncesi)
                logger.info(f"=== Katman: {katman} ===")
                logger.info(f"Çizim birimi: {dxf_analiz.birim}")
                logger.info(f"Bulunan uzunluk (m): {uzunluk_m:.4f}")
                logger.info(f"Parça sayısı: {parca_sayisi}")
                logger.info(f"Detay: {detay}")
                
                if uzunluk_m > 0:
                    # Brüt duvar alanı = uzunluk × yükseklik
                    brut_duvar_alani_m2 = uzunluk_m * yukseklik
                    
                    logger.info(f"Hesaplanan brüt duvar alanı: {uzunluk_m:.4f}m × {yukseklik:.2f}m = {brut_duvar_alani_m2:.4f}m²")
                    
                    # Birim kontrolü: Eğer sonuç çok büyükse (örn. 10000 m²), birim yanlış olabilir
                    if brut_duvar_alani_m2 > 1000:
                        logger.warning(f"⚠️ UYARI: Duvar alanı çok büyük ({brut_duvar_alani_m2:.2f}m²). Birim kontrolü gerekebilir!")
                else:
                    # Uzunluk bulunamadıysa alan hesaplamayı dene (kapalı poligonlar için)
                    alan_sonuc = dxf_analiz.alan_hesapla(katman)
                    alan_m2 = alan_sonuc['toplam_miktar']
                    
                    logger.info(f"Uzunluk bulunamadı, alan hesaplandı: {alan_m2:.4f}m²")
                    
                    if alan_m2 > 0:
                        # Eğer alan varsa, bu zaten m² cinsinden duvar alanı olabilir
                        # Ama genelde duvarlar için uzunluk × yükseklik kullanılır
                        # Bu durumda alanı direkt kullan (yükseklik zaten dahil olabilir)
                        brut_duvar_alani_m2 = alan_m2
                        logger.info(f"Katman {katman}: Alan bulundu: {alan_m2:.2f}m²")
                    else:
                        atlanan_katmanlar.append(
                            f"{katman} (çizgi/alan bulunamadı - {parca_sayisi} parça kontrol edildi)"
                        )
                        continue
                
                if brut_duvar_alani_m2 <= 0:
                    atlanan_katmanlar.append(f"{katman} (hesaplanan değer 0)")
                    continue
                
                # Net duvar alanı = Brüt duvar alanı - Açıklık alanları
                net_duvar_alani_m2 = brut_duvar_alani_m2 - toplam_aciklik_alani
                if net_duvar_alani_m2 < 0:
                    logger.warning(f"⚠️ Net duvar alanı negatif! ({net_duvar_alani_m2:.2f} m²) - Açıklık alanı çok büyük olabilir.")
                    net_duvar_alani_m2 = 0.0
                
                logger.info(f"📐 {katman}: Brüt: {brut_duvar_alani_m2:.2f} m² - Açıklık: {toplam_aciklik_alani:.2f} m² = Net: {net_duvar_alani_m2:.2f} m²")
                
                # Metraj kalemi ekle (net duvar alanı m² cinsinden)
                tanim = f"{katman} - Duvar Metrajı (H={yukseklik:.2f}m)"
                if toplam_aciklik_alani > 0:
                    tanim += f" [Net: {net_duvar_alani_m2:.2f} m², Açıklık: -{toplam_aciklik_alani:.2f} m²]"
                
                self.db.add_metraj_kalem(
                    proje_id=self.current_project_id,
                    tanim=tanim,
                    miktar=net_duvar_alani_m2,
                    birim="m²",  # Duvar metrajı m² cinsinden
                    birim_fiyat=0.0,
                    poz_no="",  # Poz no yoksa boş
                    kategori="Duvar"
                )
                eklenen_sayisi += 1
                
                # Malzeme adet hesaplama (duvar cinsi ve kalınlığına göre)
                # NET alan kullanılmalı (açıklık çıkarıldıktan sonra)
                kalinlik = tahmin.get('kalinlik')  # cm cinsinden
                cins = tahmin.get('cins')  # Bims, Tuğla, vb.
                
                if kalinlik and cins:
                    # Duvar cinsi ve kalınlığına göre malzeme adet hesapla
                    malzeme_adi, adet_per_m2 = self._duvar_malzeme_hesapla(cins, kalinlik)
                    
                    if malzeme_adi and adet_per_m2:
                        # Fire oranı %5
                        fire_orani = 0.05
                        gerekli_adet = (net_duvar_alani_m2 * adet_per_m2) * (1 + fire_orani)
                        
                        logger.info(f"📦 Malzeme hesaplama: {katman}")
                        logger.info(f"   Cins: {cins}, Kalınlık: {kalinlik}cm")
                        logger.info(f"   Net Alan: {net_duvar_alani_m2:.2f}m² (Brüt: {brut_duvar_alani_m2:.2f}m² - Açıklık: {toplam_aciklik_alani:.2f}m²)")
                        logger.info(f"   m² başına adet: {adet_per_m2}")
                        logger.info(f"   Fire oranı: %{fire_orani*100}")
                        logger.info(f"   Gerekli adet: {gerekli_adet:.0f} adet")
                        
                        # Malzeme kalemi ekle
                        self.db.add_metraj_kalem(
                            proje_id=self.current_project_id,
                            tanim=f"{katman} - {malzeme_adi} (Kalınlık: {kalinlik}cm, Fire: %5)",
                            miktar=round(gerekli_adet, 0),  # Adet olduğu için yuvarla
                            birim="adet",
                            birim_fiyat=0.0,
                            poz_no="",
                            kategori="Duvar Malzemeleri"
                        )
                        eklenen_sayisi += 1
                        logger.info(f"✅ Malzeme kalemi eklendi: {malzeme_adi} - {gerekli_adet:.0f} adet")
            
            if eklenen_sayisi > 0:
                # Toplam hesaplanan alanı göster
                toplam_hesaplanan = sum([
                    dxf_analiz.uzunluk_hesapla(k).get('toplam_miktar', 0) * yukseklikler[k]['yukseklik']
                    for k in yukseklikler.keys()
                    if dxf_analiz.uzunluk_hesapla(k).get('toplam_miktar', 0) > 0
                ])
                
                mesaj = f"✅ {eklenen_sayisi} duvar metraj kalemi eklendi.\n\n"
                mesaj += f"📊 Toplam brüt duvar alanı: {toplam_hesaplanan:.2f} m²\n"
                
                if toplam_aciklik_alani > 0:
                    mesaj += f"🚪 Çıkarılan açıklık alanı: {toplam_aciklik_alani:.2f} m²\n"
                    mesaj += f"📐 Net duvar alanı: {toplam_hesaplanan - toplam_aciklik_alani:.2f} m²\n"
                    if aciklik_detaylari:
                        mesaj += f"\n📋 Açıklık detayları:\n" + "\n".join([f"  • {d}" for d in aciklik_detaylari])
                else:
                    mesaj += f"📐 Net duvar alanı: {toplam_hesaplanan:.2f} m² (açıklık çıkarılmadı)\n"
                
                mesaj += f"\nMetraj Cetveli sekmesinde görüntüleyebilirsiniz.\n\n"
                mesaj += f"💡 İpucu: Eğer sonuç beklenenden farklıysa, birim seçimini kontrol edin.\n"
                mesaj += f"   (Çizim birimi: {dxf_analiz.birim})"
                
                if atlanan_katmanlar:
                    mesaj += f"\n\n⚠️ Atlanan katmanlar:\n" + "\n".join(atlanan_katmanlar)
                
                QMessageBox.information(dialog, "Başarılı", mesaj)
                self.load_metraj_data()
                dialog.accept()
            else:
                mesaj = "❌ Hiçbir duvar metrajı eklenemedi.\n\n"
                if atlanan_katmanlar:
                    mesaj += "Atlanan katmanlar:\n" + "\n".join(atlanan_katmanlar)
                else:
                    mesaj += "Çizgi veya alan bulunamayan katmanlar atlandı."
                QMessageBox.warning(dialog, "Uyarı", mesaj)
        except Exception as e:
            logger.error(f"❌ Metraj kaydetme hatası: {e}", exc_info=True)
            QMessageBox.critical(
                dialog, "Hata",
                f"Metraj kaydedilirken hata oluştu:\n{str(e)}"
            )
    
    def _duvar_malzeme_hesapla(self, cins: str, kalinlik: float) -> tuple:
        """
        Duvar cinsi ve kalınlığına göre malzeme adet hesapla.
        
        Args:
            cins: Duvar cinsi (Bims, Tuğla, Gazbeton, vb.)
            kalinlik: Duvar kalınlığı (cm)
            
        Returns:
            tuple: (malzeme_adi, adet_per_m2) veya (None, None)
        """
        if not cins or not kalinlik:
            return (None, None)
        
        cins_lower = cins.lower()
        kalinlik = round(kalinlik, 0)  # cm'ye yuvarla
        
        # Duvar cinsi ve kalınlığına göre m² başına adet
        # Kaynak: Standart inşaat formülleri
        # Bims tuğla boyutları: 20x39x18.5 cm (kalınlık x uzunluk x yükseklik)
        malzeme_formulleri = {
            # Bims / Gazbeton
            ('bims', 20): ('Bims', 12.5),  # 20x39x18.5 cm bims tuğla (standart)
            ('bims', 25): ('Bims', 10.0),   # 25x39x18.5 cm bims tuğla
            ('bims', 30): ('Bims', 8.33),   # 30x39x18.5 cm bims tuğla
            ('gazbeton', 20): ('Gazbeton', 6.25),  # 60x25x20 cm gazbeton blok (standart)
            ('gazbeton', 25): ('Gazbeton', 5.0),   # 60x25x25 cm gazbeton blok
            ('gazbeton', 30): ('Gazbeton', 4.17),  # 60x25x30 cm gazbeton blok
            
            # Tuğla
            ('tuğla', 9): ('Tuğla', 55),   # 9cm tuğla duvar
            ('tuğla', 19): ('Tuğla', 55),  # 19cm tuğla duvar
            ('tugla', 9): ('Tuğla', 55),
            ('tugla', 19): ('Tuğla', 55),
            
            # Briket
            ('briket', 20): ('Briket', 12.5),  # 20cm briket
            ('briket', 25): ('Briket', 10.0),  # 25cm briket
            
            # Beton
            ('beton', 20): ('Beton', 0.0),  # Beton için adet hesaplanmaz (m³)
            ('beton', 25): ('Beton', 0.0),
        }
        
        # Tam eşleşme ara
        key = (cins_lower, kalinlik)
        if key in malzeme_formulleri:
            return malzeme_formulleri[key]
        
        # Yakın kalınlık ara (5cm tolerans)
        for (c, k), (malzeme, adet) in malzeme_formulleri.items():
            if c == cins_lower and abs(k - kalinlik) <= 5:
                logger.info(f"⚠️ Tam eşleşme bulunamadı, yakın değer kullanıldı: {cins} {kalinlik}cm -> {malzeme} {k}cm ({adet} adet/m²)")
                return (malzeme, adet)
        
        # Varsayılan değerler (cins eşleşirse)
        if 'bims' in cins_lower:
            if 15 <= kalinlik <= 25:
                return ('Bims', 12.5)  # 20cm varsayılan (standart bims tuğla)
            elif kalinlik > 25:
                return ('Bims', 10.0)   # 25cm varsayılan
        
        if 'gazbeton' in cins_lower:
            if 15 <= kalinlik <= 25:
                return ('Gazbeton', 6.25)  # 20cm varsayılan (standart gazbeton blok)
            elif kalinlik > 25:
                return ('Gazbeton', 5.0)   # 25cm varsayılan
        
        if 'tuğla' in cins_lower or 'tugla' in cins_lower:
            return ('Tuğla', 55)  # Standart tuğla
        
        if 'briket' in cins_lower:
            if kalinlik <= 20:
                return ('Briket', 12.5)
            else:
                return ('Briket', 10.0)
        
        logger.warning(f"⚠️ Duvar cinsi/kalınlık için formül bulunamadı: {cins} {kalinlik}cm")
        return (None, None)
            
    # Taşeron İşlemleri
    def load_taseron_data(self) -> None:
        """Taşeron verilerini yükle"""
        # Sekme henüz oluşturulmamışsa (lazy loading) yükleme yapma
        if not hasattr(self, 'taseron_table') or not self._tabs_created.get('taseron', False):
            return
        
        if not self.current_project_id:
            return
        
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()  # UI'ı güncelle
            
        offers = self.db.get_taseron_teklifleri(self.current_project_id)
        QApplication.processEvents()  # UI'ı güncelle
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
            
            # Her 50 satırda bir UI'ı güncelle
            if row % 50 == 0:
                QApplication.processEvents()
        
        # Toplam hesaplama (KDV ile)
        total = sum(offer.get('toplam', 0) for offer in offers)
        kdv_rate_text = self.taseron_kdv_rate.currentText().replace("%", "")
        kdv_rate = float(kdv_rate_text)
        kdv_hesap = self.calculator.calculate_with_kdv(total, kdv_rate)
        
        self.taseron_total_label.setText(f"Toplam (KDV Hariç): {total:,.2f} ₺")
        self.taseron_total_kdv_label.setText(f"Toplam (KDV %{kdv_rate_text} Dahil): {kdv_hesap['kdv_dahil']:,.2f} ₺")
            
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
        """Pozları veritabanına yükle (async - UI'ı bloklamaz)"""
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
            
            # Progress dialog göster
            from PyQt6.QtWidgets import QProgressDialog
            progress = QProgressDialog("Pozlar yükleniyor...", "İptal", 0, 0, self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(0)
            progress.setCancelButton(None)  # İptal butonunu kaldır (uzun sürmeyecek)
            progress.show()
            QApplication.processEvents()  # UI'ı güncelle
            
            # Pozları yükle (kısa süreli işlem, ama yine de progress göster)
            result = initialize_database_data(self.db, force_reload=False)
            
            progress.close()
            from PyQt6.QtWidgets import QApplication
            QApplication.processEvents()  # UI'ı güncelle
            
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
        """Sekme değiştiğinde çağrılır (lazy loading ile)"""
        try:
            # Index 0 (Metraj Cetveli) için bir şey yapma, zaten oluşturulmuş
            if index == 0:
                return
            
            # Lazy loading: Sekmeyi ilk kez açıldığında oluştur
            if index == 1 and not self._tabs_created['ozet']:
                try:
                    # Proje Özeti sekmesi
                    placeholder = self.tabs.widget(1)
                    self.create_proje_ozet_tab(add_to_tabs=False)
                    # Signal'ı geçici olarak blokla (sonsuz döngüyü önlemek için)
                    self.tabs.blockSignals(True)
                    self.tabs.removeTab(1)
                    self.tabs.insertTab(1, self.ozet_widget, "📈 Proje Özeti")
                    self.tabs.setCurrentIndex(1)
                    self.tabs.blockSignals(False)
                    self._tabs_created['ozet'] = True
                    if placeholder:
                        placeholder.deleteLater()
                except Exception as e:
                    self.tabs.blockSignals(False)  # Hata durumunda da bloklamayı kaldır
                    print(f"Proje Özeti sekmesi oluşturma hatası: {e}")
                    import traceback
                    traceback.print_exc()
                    raise
            elif index == 2 and not self._tabs_created['taseron']:
                try:
                    # Taşeron Analizi sekmesi
                    placeholder = self.tabs.widget(2)
                    self.create_taseron_tab(add_to_tabs=False)
                    self.tabs.blockSignals(True)
                    self.tabs.removeTab(2)
                    self.tabs.insertTab(2, self.taseron_widget, "💼 Taşeron Analizi")
                    self.tabs.setCurrentIndex(2)
                    self.tabs.blockSignals(False)
                    self._tabs_created['taseron'] = True
                    if placeholder:
                        placeholder.deleteLater()
                except Exception as e:
                    self.tabs.blockSignals(False)
                    print(f"Taşeron Analizi sekmesi oluşturma hatası: {e}")
                    import traceback
                    traceback.print_exc()
                    raise
            elif index == 3 and not self._tabs_created['malzeme']:
                try:
                    # Malzeme Listesi sekmesi
                    placeholder = self.tabs.widget(3)
                    self.create_malzeme_tab(add_to_tabs=False)
                    self.tabs.blockSignals(True)
                    self.tabs.removeTab(3)
                    self.tabs.insertTab(3, self.malzeme_widget, "📦 Malzeme Listesi")
                    self.tabs.setCurrentIndex(3)
                    self.tabs.blockSignals(False)
                    self._tabs_created['malzeme'] = True
                    if placeholder:
                        placeholder.deleteLater()
                except Exception as e:
                    self.tabs.blockSignals(False)
                    print(f"Malzeme Listesi sekmesi oluşturma hatası: {e}")
                    import traceback
                    traceback.print_exc()
                    raise
            elif index == 4 and not self._tabs_created['sablonlar']:
                try:
                    # Şablonlar sekmesi
                    placeholder = self.tabs.widget(4)
                    self.create_sablonlar_tab(add_to_tabs=False)
                    self.tabs.blockSignals(True)
                    self.tabs.removeTab(4)
                    self.tabs.insertTab(4, self.sablonlar_widget, "📋 Şablonlar")
                    self.tabs.setCurrentIndex(4)
                    self.tabs.blockSignals(False)
                    self._tabs_created['sablonlar'] = True
                    self.load_templates()  # İlk açılışta yükle
                    if placeholder:
                        placeholder.deleteLater()
                except Exception as e:
                    self.tabs.blockSignals(False)
                    print(f"Şablonlar sekmesi oluşturma hatası: {e}")
                    import traceback
                    traceback.print_exc()
                    raise
            elif index == 5 and not self._tabs_created['birim_fiyat']:
                try:
                    # Birim Fiyat Yönetimi sekmesi
                    placeholder = self.tabs.widget(5)
                    self.create_birim_fiyat_tab(add_to_tabs=False)
                    self.tabs.blockSignals(True)
                    self.tabs.removeTab(5)
                    self.tabs.insertTab(5, self.birim_fiyat_widget, "💰 Birim Fiyatlar")
                    self.tabs.setCurrentIndex(5)
                    self.tabs.blockSignals(False)
                    self._tabs_created['birim_fiyat'] = True
                    self.load_birim_fiyatlar()  # İlk açılışta yükle
                    if placeholder:
                        placeholder.deleteLater()
                except Exception as e:
                    self.tabs.blockSignals(False)
                    print(f"Birim Fiyat sekmesi oluşturma hatası: {e}")
                    import traceback
                    traceback.print_exc()
                    raise
            elif index == 6 and not self._tabs_created['ihale']:
                try:
                    # İhale Dosyası Hazırlama sekmesi
                    placeholder = self.tabs.widget(6)
                    self.create_ihale_tab(add_to_tabs=False)
                    self.tabs.blockSignals(True)
                    self.tabs.removeTab(6)
                    self.tabs.insertTab(6, self.ihale_widget, "📄 İhale Dosyası")
                    self.tabs.setCurrentIndex(6)
                    self.tabs.blockSignals(False)
                    self._tabs_created['ihale'] = True
                    self.load_ihaleler()  # İlk açılışta yükle
                    if placeholder:
                        placeholder.deleteLater()
                except Exception as e:
                    self.tabs.blockSignals(False)
                    print(f"İhale Dosyası sekmesi oluşturma hatası: {e}")
                    import traceback
                    traceback.print_exc()
                    raise
            elif index == 7 and not self._tabs_created.get('enflasyon', False):
                try:
                    # Enflasyon ve Fiyat Farkı sekmesi
                    placeholder = self.tabs.widget(7)
                    from app.ui.enflasyon_window import EnflasyonWindow
                    enflasyon_widget = EnflasyonWindow(self.db)
                    self.tabs.blockSignals(True)
                    self.tabs.removeTab(7)
                    self.tabs.insertTab(7, enflasyon_widget, "📊 Enflasyon ve Fiyat Farkı")
                    self.tabs.setCurrentIndex(7)
                    self.tabs.blockSignals(False)
                    self._tabs_created['enflasyon'] = True
                    if placeholder:
                        placeholder.deleteLater()
                except Exception as e:
                    self.tabs.blockSignals(False)
                    print(f"Enflasyon sekmesi oluşturma hatası: {e}")
                    import traceback
                    traceback.print_exc()
                    raise
            elif index == 8 and not self._tabs_created.get('tedarikci', False):
                try:
                    # Tedarikçi Fiyat Karşılaştırma sekmesi
                    placeholder = self.tabs.widget(8)
                    from app.ui.tedarikci_window import TedarikciWindow
                    tedarikci_widget = TedarikciWindow(self.db)
                    self.tabs.blockSignals(True)
                    self.tabs.removeTab(8)
                    self.tabs.insertTab(8, tedarikci_widget, "🏪 Tedarikçi Fiyat Karşılaştırma")
                    self.tabs.setCurrentIndex(8)
                    self.tabs.blockSignals(False)
                    self._tabs_created['tedarikci'] = True
                    if placeholder:
                        placeholder.deleteLater()
                except Exception as e:
                    self.tabs.blockSignals(False)
                    print(f"Tedarikçi sekmesi oluşturma hatası: {e}")
                    import traceback
                    traceback.print_exc()
                    raise
            elif index == 9 and not self._tabs_created.get('bi_dashboard', False):
                try:
                    # BI Dashboard sekmesi
                    placeholder = self.tabs.widget(9)
                    from app.ui.bi_dashboard_window import BIDashboardWindow
                    bi_widget = BIDashboardWindow(self.db)
                    self.tabs.blockSignals(True)
                    self.tabs.removeTab(9)
                    self.tabs.insertTab(9, bi_widget, "📊 BI Dashboard")
                    self.tabs.setCurrentIndex(9)
                    self.tabs.blockSignals(False)
                    self._tabs_created['bi_dashboard'] = True
                    if placeholder:
                        placeholder.deleteLater()
                except Exception as e:
                    self.tabs.blockSignals(False)
                    print(f"BI Dashboard sekmesi oluşturma hatası: {e}")
                    import traceback
                    traceback.print_exc()
                    raise
            elif index == 10 and not self._tabs_created.get('surdurulebilirlik', False):
                try:
                    # Çevre ve Sürdürülebilirlik sekmesi
                    placeholder = self.tabs.widget(10)
                    from app.ui.surdurulebilirlik_window import SurdurulebilirlikWindow
                    surdurulebilirlik_widget = SurdurulebilirlikWindow(self.db)
                    self.tabs.blockSignals(True)
                    self.tabs.removeTab(10)
                    self.tabs.insertTab(10, surdurulebilirlik_widget, "🌍 Çevre ve Sürdürülebilirlik")
                    self.tabs.setCurrentIndex(10)
                    self.tabs.blockSignals(False)
                    self._tabs_created['surdurulebilirlik'] = True
                    if placeholder:
                        placeholder.deleteLater()
                except Exception as e:
                    self.tabs.blockSignals(False)
                    print(f"Sürdürülebilirlik sekmesi oluşturma hatası: {e}")
                    import traceback
                    traceback.print_exc()
                    raise
            elif index == 11 and not self._tabs_created.get('gantt', False):
                try:
                    # Gantt Chart ve İş Programı sekmesi
                    placeholder = self.tabs.widget(11)
                    from app.ui.gantt_window import GanttWindow
                    gantt_widget = GanttWindow(self.db)
                    self.tabs.blockSignals(True)
                    self.tabs.removeTab(11)
                    self.tabs.insertTab(11, gantt_widget, "📅 Gantt Chart")
                    self.tabs.setCurrentIndex(11)
                    self.tabs.blockSignals(False)
                    self._tabs_created['gantt'] = True
                    if placeholder:
                        placeholder.deleteLater()
                except Exception as e:
                    self.tabs.blockSignals(False)
                    print(f"Gantt Chart sekmesi oluşturma hatası: {e}")
                    import traceback
                    traceback.print_exc()
                    raise

            # Proje Özeti sekmesine geçildiğinde güncelle (sadece sekme zaten oluşturulmuşsa)
            if index == 1 and self._tabs_created['ozet']:
                try:
                    self.update_proje_ozet()
                except Exception as e:
                    print(f"Proje özeti güncelleme hatası: {e}")
                    import traceback
                    traceback.print_exc()
        except Exception as e:
            # Hata durumunda logla ve dosyaya yaz
            error_msg = f"Sekme değiştirme hatası (index: {index}): {e}"
            print(f"\n❌ {error_msg}")
            import traceback
            error_trace = traceback.format_exc()
            print(error_trace)
            
            # Hatayı dosyaya yaz
            try:
                error_log_path = Path(__file__).parent.parent.parent / "error_log.txt"
                with open(error_log_path, 'a', encoding='utf-8') as f:
                    from datetime import datetime
                    f.write(f"\n{'='*60}\n")
                    f.write(f"Tarih: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"{error_msg}\n")
                    f.write(f"{error_trace}\n")
                    f.write(f"{'='*60}\n")
                print(f"✅ Hata log dosyasına yazıldı: {error_log_path}")
            except Exception as log_error:
                print(f"❌ Log yazma hatası: {log_error}")
                import traceback
                traceback.print_exc()
            
            # Kullanıcıya bilgi ver (ama uygulamayı kapatma)
            try:
                QMessageBox.critical(
                    self, "Hata",
                    f"Sekme değiştirilirken bir hata oluştu:\n{str(e)}\n\n"
                    f"Hata detayları 'error_log.txt' dosyasına kaydedildi.\n\n"
                    f"Lütfen programı yeniden başlatın."
            )
            except Exception as msg_error:
                print(f"QMessageBox hatası: {msg_error}")
                # Uygulamayı kapatma, sadece logla
            
    def update_proje_ozet(self) -> None:
        """Proje özeti sekmesini güncelle"""
        # Sekme henüz oluşturulmamışsa (lazy loading) güncelleme yapma
        if not hasattr(self, 'ozet_kalem_label') or not self._tabs_created.get('ozet', False):
            return
        
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
            self.stats_table.setRowCount(0)
            
            # Grafikleri temizle
            if hasattr(self, 'kategori_canvas') and self.kategori_canvas:
                try:
                    self.kategori_ax.clear()
                    self.kategori_ax.text(0.5, 0.5, 'Veri yok', ha='center', va='center', 
                                         transform=self.kategori_ax.transAxes, fontsize=12)
                    self.kategori_canvas.draw()
                except:
                    pass
            
            if hasattr(self, 'pahali_canvas') and self.pahali_canvas:
                try:
                    self.pahali_ax.clear()
                    self.pahali_ax.text(0.5, 0.5, 'Veri yok', ha='center', va='center',
                                       transform=self.pahali_ax.transAxes, fontsize=12)
                    self.pahali_canvas.draw()
                except:
                    pass
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
            sorted_kategoriler = sorted(kategori_dict.items(), key=lambda x: x[1]['toplam'], reverse=True)
            for row, (kategori, data) in enumerate(sorted_kategoriler):
                self.ozet_kategori_table.setItem(row, 0, QTableWidgetItem(kategori))
                self.ozet_kategori_table.setItem(row, 1, QTableWidgetItem(str(data['sayi'])))
                toplam_item = QTableWidgetItem(f"{data['toplam']:,.2f} ₺")
                toplam_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.ozet_kategori_table.setItem(row, 2, toplam_item)
            
            # Kategori Pie Chart
            if self.kategori_canvas and kategori_dict:
                try:
                    self.kategori_ax.clear()
                    kategoriler = [k for k, _ in sorted_kategoriler]
                    toplamlar = [d['toplam'] for _, d in sorted_kategoriler]
                    
                    # Renk paleti
                    colors = ['#c9184a', '#00BFFF', '#4CAF50', '#FF9800', '#9C27B0', '#F44336', '#2196F3', '#FFC107']
                    colors = colors[:len(kategoriler)] if len(kategoriler) <= len(colors) else colors * (len(kategoriler) // len(colors) + 1)
                    
                    wedges, texts, autotexts = self.kategori_ax.pie(
                        toplamlar, labels=kategoriler, autopct='%1.1f%%',
                        colors=colors[:len(kategoriler)], startangle=90
                    )
                    
                    # Yüzde metinlerini daha okunabilir yap
                    for autotext in autotexts:
                        autotext.set_color('white')
                        autotext.set_fontweight('bold')
                        autotext.set_fontsize(9)
                    
                    self.kategori_ax.set_title('Kategori Bazında Maliyet Dağılımı', fontsize=11, fontweight='bold')
                    self.kategori_figure.tight_layout()
                    self.kategori_canvas.draw()
                except Exception as e:
                    print(f"Pie chart çizme hatası: {e}")
            
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
            
            # En Pahalı Kalemler Bar Chart
            if self.pahali_canvas and sorted_items:
                try:
                    self.pahali_ax.clear()
                    kalem_isimleri = [item.get('tanim', '')[:30] + ('...' if len(item.get('tanim', '')) > 30 else '') 
                                     for item in sorted_items]
                    toplamlar = [item.get('toplam', 0) for item in sorted_items]
                    
                    bars = self.pahali_ax.barh(kalem_isimleri, toplamlar, color='#c9184a', alpha=0.8)
                    
                    # Değerleri çubukların üzerine yaz
                    for i, (bar, toplam) in enumerate(zip(bars, toplamlar)):
                        width = bar.get_width()
                        self.pahali_ax.text(width, bar.get_y() + bar.get_height()/2, 
                                          f'{toplam:,.0f} ₺',
                                          ha='left', va='center', fontweight='bold', fontsize=9)
                    
                    self.pahali_ax.set_xlabel('Toplam Maliyet (₺)', fontsize=10)
                    self.pahali_ax.set_title('En Pahalı 5 Kalem', fontsize=11, fontweight='bold')
                    self.pahali_ax.grid(axis='x', alpha=0.3)
                    self.pahali_figure.tight_layout()
                    self.pahali_canvas.draw()
                except Exception as e:
                    print(f"Bar chart çizme hatası: {e}")
            
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
                from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
                from datetime import datetime
                
                # Logo yolu kontrolü
                logo_path = Path(__file__).parent.parent.parent / "assets" / "logo.png"
                has_logo = logo_path.exists()
                
                doc = SimpleDocTemplate(str(file_path), pagesize=A4)
                story = []
                styles = getSampleStyleSheet()
                
                # Logo ekle
                if has_logo:
                    try:
                        logo = Image(str(logo_path), width=2*inch, height=0.8*inch)
                        logo.hAlign = 'CENTER'
                        story.append(logo)
                        story.append(Spacer(1, 0.2*inch))
                    except Exception as e:
                        print(f"Logo yükleme hatası: {e}")
                
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
                    ['Toplam Maliyet (KDV Hariç)', f"{toplam_maliyet:,.2f} TL"],
                    ['KDV (%' + kdv_rate_text + ')', f"{kdv_hesap['kdv']:,.2f} TL"],
                    ['Toplam Maliyet (KDV Dahil)', f"{kdv_hesap['kdv_dahil']:,.2f} TL"],
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
                            f"{data['toplam']:,.2f} TL"
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
                            f"{toplam_maliyet:,.2f} TL",
                            f"{kdv_hesap['kdv']:,.2f} TL",
                            f"{kdv_hesap['kdv_dahil']:,.2f} TL",
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
                            kategori_data['Toplam Maliyet'].append(f"{data['toplam']:,.2f} TL")
                        
                        df_kategori = pd.DataFrame(kategori_data)
                        df_kategori.to_excel(writer, sheet_name='Kategori Dağılımı', index=False)
                    
                    # En pahalı kalemler
                    sorted_items = sorted(metraj_items, key=lambda x: x.get('toplam', 0), reverse=True)[:10]
                    pahali_data = {
                        'Kalem': [item.get('tanim', '') for item in sorted_items],
                        'Miktar': [f"{item.get('miktar', 0):,.2f} {item.get('birim', '')}" for item in sorted_items],
                        'Toplam': [f"{item.get('toplam', 0):,.2f} TL" for item in sorted_items]
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
    
    def backup_current_project(self) -> None:
        """Seçili projeyi yedekle"""
        if not self.current_project_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce bir proje seçin")
            return
        
        # Proje adını al
        project = self.db.get_project(self.current_project_id)
        if not project:
            QMessageBox.warning(self, "Uyarı", "Proje bulunamadı")
            return
        
        # Yedek dosyası seç
        default_name = f"{project['ad']}_yedek_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Projeyi Yedekle", default_name, "JSON Dosyaları (*.json)"
        )
        
        if file_path:
            if self.db.backup_project(self.current_project_id, Path(file_path)):
                QMessageBox.information(
                    self, "Başarılı",
                    f"Proje başarıyla yedeklendi:\n{file_path}"
                )
                self.statusBar().showMessage(f"Proje yedeklendi: {file_path}")
            else:
                QMessageBox.critical(
                    self, "Hata",
                    "Yedekleme sırasında bir hata oluştu."
                )
    
    def backup_all_projects(self) -> None:
        """Tüm projeleri yedekle"""
        # Yedek dosyası seç
        default_name = f"tum_projeler_yedek_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Tüm Projeleri Yedekle", default_name, "JSON Dosyaları (*.json)"
        )
        
        if file_path:
            if self.db.backup_all_projects(Path(file_path)):
                QMessageBox.information(
                    self, "Başarılı",
                    f"Tüm projeler başarıyla yedeklendi:\n{file_path}"
                )
                self.statusBar().showMessage(f"Tüm projeler yedeklendi: {file_path}")
            else:
                QMessageBox.critical(
                    self, "Hata",
                    "Yedekleme sırasında bir hata oluştu."
                )
    
    def restore_project(self) -> None:
        """Yedekten proje geri yükle"""
        # Yedek dosyası seç
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Yedekten Geri Yükle", "", "JSON Dosyaları (*.json)"
        )
        
        if file_path:
            # Proje adı sor
            from PyQt6.QtWidgets import QInputDialog
            project_name, ok = QInputDialog.getText(
                self, "Proje Adı",
                "Yeni proje adı (boş bırakırsanız yedekteki ad kullanılır):"
            )
            
            if ok:
                new_name = project_name.strip() if project_name.strip() else None
                project_id = self.db.restore_project(Path(file_path), new_name)
                
                if project_id:
                    QMessageBox.information(
                        self, "Başarılı",
                        f"Proje başarıyla geri yüklendi!"
                    )
                    # Proje listesini yenile
                    self.load_projects()
                    # Yeni projeyi seç
                    self.current_project_id = project_id
                    self.load_metraj_data()
                    self.load_taseron_data()
                    self.update_proje_ozet()
                    self.statusBar().showMessage("Proje geri yüklendi")
                else:
                    QMessageBox.critical(
                        self, "Hata",
                        "Geri yükleme sırasında bir hata oluştu."
                    )
    
    def create_project_version(self) -> None:
        """Proje versiyonu oluştur"""
        if not self.current_project_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce bir proje seçin")
            return
        
        from PyQt6.QtWidgets import QInputDialog
        
        # Versiyon adı al
        version_name, ok = QInputDialog.getText(
            self, "Versiyon Oluştur",
            "Versiyon adı:",
            text=f"Versiyon {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
        
        if not ok or not version_name.strip():
            return
        
        # Açıklama al
        description, ok = QInputDialog.getText(
            self, "Versiyon Açıklaması",
            "Versiyon açıklaması (isteğe bağlı):"
        )
        
        if not ok:
            return
        
        # Versiyon oluştur
        try:
            version_id = self.db.create_project_version(
                project_id=self.current_project_id,
                version_name=version_name.strip(),
                description=description.strip(),
                created_by="Kullanıcı"
            )
            
            QMessageBox.information(
                self, "Başarılı",
                f"Versiyon başarıyla oluşturuldu!\nVersiyon ID: {version_id}"
            )
            self.statusBar().showMessage(f"Versiyon oluşturuldu: {version_name}")
        except Exception as e:
            QMessageBox.critical(
                self, "Hata",
                f"Versiyon oluşturulurken hata oluştu:\n{str(e)}"
            )
    
    def view_project_versions(self) -> None:
        """Proje versiyonlarını görüntüle"""
        if not self.current_project_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce bir proje seçin")
            return
        
        versions = self.db.get_project_versions(self.current_project_id)
        
        if not versions:
            QMessageBox.information(
                self, "Bilgi",
                "Bu proje için henüz versiyon oluşturulmamış."
            )
            return
        
        # Versiyon listesi dialogu
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem, QPushButton, QHeaderView
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Proje Versiyonları")
        dialog.setGeometry(200, 200, 800, 500)
        
        layout = QVBoxLayout(dialog)
        
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels([
            "Versiyon No", "Versiyon Adı", "Oluşturulma Tarihi", "Açıklama", "Oluşturan"
        ])
        table.setRowCount(len(versions))
        table.horizontalHeader().setStretchLastSection(True)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        
        for row, version in enumerate(versions):
            table.setItem(row, 0, QTableWidgetItem(str(version.get('version_number', ''))))
            table.setItem(row, 1, QTableWidgetItem(version.get('version_name', '')))
            table.setItem(row, 2, QTableWidgetItem(version.get('created_at', '')))
            table.setItem(row, 3, QTableWidgetItem(version.get('description', '')))
            table.setItem(row, 4, QTableWidgetItem(version.get('created_by', '')))
        
        layout.addWidget(table)
        
        btn_layout = QHBoxLayout()
        btn_restore = QPushButton("Seçili Versiyondan Geri Yükle")
        btn_restore.clicked.connect(lambda: self.restore_selected_version(dialog, table))
        btn_layout.addWidget(btn_restore)
        
        btn_close = QPushButton("Kapat")
        btn_close.clicked.connect(dialog.close)
        btn_layout.addWidget(btn_close)
        
        layout.addLayout(btn_layout)
        
        dialog.exec()
    
    def restore_selected_version(self, dialog: QDialog, table: QTableWidget) -> None:
        """Seçili versiyondan geri yükle"""
        current_row = table.currentRow()
        if current_row < 0:
            QMessageBox.warning(dialog, "Uyarı", "Lütfen bir versiyon seçin")
            return
        
        version_id_item = table.item(current_row, 0)
        if not version_id_item:
            return
        
        # Versiyon ID'yi bul
        version_number = int(version_id_item.text())
        versions = self.db.get_project_versions(self.current_project_id)
        selected_version = next((v for v in versions if v['version_number'] == version_number), None)
        
        if not selected_version:
            QMessageBox.warning(dialog, "Uyarı", "Versiyon bulunamadı")
            return
        
        from PyQt6.QtWidgets import QInputDialog
        
        # Yeni proje adı al
        project_name, ok = QInputDialog.getText(
            dialog, "Yeni Proje Adı",
            "Yeni proje adı (boş bırakırsanız versiyon adı kullanılır):",
            text=f"{selected_version['version_name']} (Geri Yüklenen)"
        )
        
        if not ok:
            return
        
        new_name = project_name.strip() if project_name.strip() else None
        
        # Geri yükle
        try:
            new_project_id = self.db.restore_project_version(selected_version['id'], new_name)
            
            if new_project_id:
                QMessageBox.information(
                    dialog, "Başarılı",
                    f"Versiyon başarıyla geri yüklendi!\nYeni proje ID: {new_project_id}"
                )
                dialog.close()
                self.load_projects()
                self.statusBar().showMessage("Versiyon geri yüklendi")
            else:
                QMessageBox.critical(
                    dialog, "Hata",
                    "Geri yükleme sırasında bir hata oluştu."
                )
        except Exception as e:
            QMessageBox.critical(
                dialog, "Hata",
                f"Geri yükleme sırasında hata oluştu:\n{str(e)}"
            )
    
    def restore_from_version(self) -> None:
        """Versiyondan geri yükle (kısayol)"""
        self.view_project_versions()
    
    def load_project_notes(self) -> None:
        """Proje notlarını yükle"""
        # Lazy loading kontrolü
        if not hasattr(self, 'project_notes_text'):
            return

        if not self.current_project_id:
            self.project_notes_text.clear()
            self.project_notes_text.setEnabled(False)
            return

        project = self.db.get_project(self.current_project_id)
        if project:
            notes = project.get('notlar', '') or ''
            self.project_notes_text.setPlainText(notes)
            self.project_notes_text.setEnabled(True)
        else:
            self.project_notes_text.clear()
            self.project_notes_text.setEnabled(False)
    
    def save_project_notes(self) -> None:
        """Proje notlarını kaydet"""
        if not self.current_project_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce bir proje seçin")
            return
        
        notes = self.project_notes_text.toPlainText()
        if self.db.update_project(self.current_project_id, notlar=notes):
            QMessageBox.information(self, "Başarılı", "Notlar kaydedildi")
            self.statusBar().showMessage("Proje notları kaydedildi")
        else:
            QMessageBox.critical(self, "Hata", "Notlar kaydedilirken bir hata oluştu")
    
    def import_from_excel(self) -> None:
        """Excel dosyasından kalem içe aktar"""
        if not self.current_project_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce bir proje seçin")
            return
        
        # Excel dosyası seç
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Excel Dosyası Seç", "", "Excel Dosyaları (*.xlsx *.xls)"
        )
        
        if not file_path:
            return
        
        try:
            import pandas as pd
            
            # Excel dosyasını oku
            df = pd.read_excel(file_path)
            
            # Sütun adlarını normalize et (boşlukları temizle)
            original_columns = df.columns.tolist()
            df.columns = [str(col).strip() for col in df.columns]
            
            # Sütun adlarını eşleştir (Türkçe ve İngilizce desteği)
            # Hem tam eşleşme hem de case-insensitive eşleşme
            column_mapping_dict = {
                # Türkçe -> İngilizce
                'Poz No': 'poz_no',
                'poz no': 'poz_no',
                'POZ NO': 'poz_no',
                'Tanım': 'tanim',
                'tanım': 'tanim',
                'TANIM': 'tanim',
                'Tanim': 'tanim',
                'Miktar': 'miktar',
                'miktar': 'miktar',
                'MIKTAR': 'miktar',
                'Birim': 'birim',
                'birim': 'birim',
                'BİRİM': 'birim',
                'Birim Fiyat': 'birim_fiyat',
                'birim fiyat': 'birim_fiyat',
                'BİRİM FİYAT': 'birim_fiyat',
                'BirimFiyat': 'birim_fiyat',
                'Kategori': 'kategori',
                'kategori': 'kategori',
                'KATEGORİ': 'kategori',
                'Kaynak': 'kaynak',
                'kaynak': 'kaynak',
                'KAYNAK': 'kaynak',
            }
            
            # İngilizce sütun adları zaten doğruysa ekle
            for eng_col in ['poz_no', 'tanim', 'miktar', 'birim', 'birim_fiyat', 'kategori', 'kaynak']:
                if eng_col not in column_mapping_dict:
                    column_mapping_dict[eng_col] = eng_col
            
            # Sütun adlarını normalize et
            normalized_columns = {}
            for col in df.columns:
                col_clean = str(col).strip()
                # Önce tam eşleşme
                if col_clean in column_mapping_dict:
                    normalized_columns[col] = column_mapping_dict[col_clean]
                # Sonra case-insensitive eşleşme
                else:
                    col_lower = col_clean.lower()
                    found = False
                    for key, value in column_mapping_dict.items():
                        if key.lower() == col_lower:
                            normalized_columns[col] = value
                            found = True
                            break
                    if not found:
                        # Eşleşme bulunamadı, olduğu gibi bırak
                        normalized_columns[col] = col_clean
            
            # Sütun adlarını değiştir
            df = df.rename(columns=normalized_columns)
            
            # Debug: Sütun adlarını kontrol et
            print(f"Original columns: {original_columns}")
            print(f"Normalized columns: {df.columns.tolist()}")
            
            # Gerekli sütunları kontrol et (miktar ve birim opsiyonel)
            required_columns = ['poz_no', 'tanim']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                # Mevcut sütunları göster
                available_cols = ', '.join(df.columns.tolist())
                QMessageBox.warning(
                    self, "Hata",
                    f"Excel dosyasında gerekli sütunlar eksik:\n{', '.join(missing_columns)}\n\n"
                    f"Gerekli sütunlar:\n"
                    f"  - poz_no (veya 'Poz No')\n"
                    f"  - tanim (veya 'Tanım')\n\n"
                    f"Opsiyonel sütunlar:\n"
                    f"  - birim (veya 'Birim') - Yoksa varsayılan 'adet' kullanılır\n"
                    f"  - miktar (veya 'Miktar') - Yoksa varsayılan 1.0 kullanılır\n"
                    f"  - birim_fiyat (veya 'Birim Fiyat') - Yoksa 0 kullanılır\n\n"
                    f"Mevcut sütunlar:\n{available_cols}"
                )
                return
            
            # Miktar sütunu yoksa ekle (varsayılan 1.0)
            if 'miktar' not in df.columns:
                df['miktar'] = 1.0
                print(f"Added 'miktar' column with default value 1.0")
            
            # Birim sütunu yoksa ekle (varsayılan 'adet')
            if 'birim' not in df.columns:
                df['birim'] = 'adet'
                print(f"Added 'birim' column with default value 'adet'")
            
            # Birim fiyat sütunu yoksa ekle (varsayılan 0)
            if 'birim_fiyat' not in df.columns:
                df['birim_fiyat'] = 0.0
                print(f"Added 'birim_fiyat' column with default value 0.0")
            
            print(f"Final columns before processing: {df.columns.tolist()}")
            
            # Veri kontrolü: Boş satırları temizle
            df = df.dropna(subset=['poz_no', 'tanim'], how='all')  # Her iki sütun da boşsa sil
            
            if df.empty:
                QMessageBox.warning(
                    self, "Uyarı",
                    "Excel dosyasında işlenecek veri bulunamadı.\n\n"
                    "Lütfen 'Poz No' ve 'Tanım' sütunlarının dolu olduğundan emin olun."
                )
                return
            
            print(f"Processing {len(df)} rows...")
            
            # Progress dialog ekle (çok satır varsa)
            from PyQt6.QtWidgets import QProgressDialog
            from PyQt6.QtCore import Qt
            if len(df) > 100:
                progress = QProgressDialog("Excel verileri işleniyor...", "İptal", 0, len(df), self)
                progress.setWindowModality(Qt.WindowModality.WindowModal)
                progress.setMinimumDuration(0)
                progress.show()
            
            # Kalemleri ekle
            success_count = 0
            error_count = 0
            errors = []
            skipped_empty = 0
            
            for idx, (index, row) in enumerate(df.iterrows()):
                try:
                    # Progress güncelle
                    if len(df) > 100 and idx % 100 == 0:
                        progress.setValue(idx)
                        progress.setLabelText(f"Excel verileri işleniyor... {idx}/{len(df)}")
                        from PyQt6.QtWidgets import QApplication
                        QApplication.processEvents()
                        if progress.wasCanceled():
                            break
                    
                    # Sütun değerlerini al (normalize edilmiş sütun adları ile)
                    poz_no_raw = row.get('poz_no', '')
                    tanim_raw = row.get('tanim', '')
                    
                    # NaN kontrolü ve string'e çevirme
                    if pd.isna(poz_no_raw):
                        poz_no = ''
                    else:
                        poz_no = str(poz_no_raw).strip()
                        if poz_no.lower() == 'nan' or poz_no == '':
                            poz_no = ''
                    
                    if pd.isna(tanim_raw):
                        tanim = ''
                    else:
                        tanim = str(tanim_raw).strip()
                        if tanim.lower() == 'nan' or tanim == '':
                            tanim = ''
                    
                    # Boş satırları atla
                    if not poz_no and not tanim:
                        skipped_empty += 1
                        continue
                    
                    # Poz no veya tanım boşsa hata
                    if not poz_no:
                        error_count += 1
                        if len(errors) < 20:  # İlk 20 hatayı göster
                            errors.append(f"Satır {index + 2}: Poz no boş (Tanım: '{tanim[:50]}...' if len(tanim) > 50 else tanim)")
                        continue
                    
                    if not tanim:
                        error_count += 1
                        if len(errors) < 20:
                            errors.append(f"Satır {index + 2}: Tanım boş (Poz: '{poz_no}')")
                        continue
                    
                    # Kategori (opsiyonel)
                    kategori = ''
                    if 'kategori' in df.columns:
                        kategori_raw = row.get('kategori', '')
                        if pd.notna(kategori_raw):
                            kategori_str = str(kategori_raw).strip()
                            if kategori_str.lower() != 'nan' and kategori_str:
                                kategori = kategori_str
                    
                    # Miktar - varsa kullan, yoksa 1.0
                    miktar_val = row.get('miktar', 1.0)
                    if pd.isna(miktar_val):
                        miktar = 1.0
                    else:
                        try:
                            miktar_str = str(miktar_val).strip()
                            if miktar_str.lower() == 'nan' or miktar_str == '':
                                miktar = 1.0
                            else:
                                miktar = float(miktar_val)
                                if miktar < 0:
                                    miktar = 1.0
                        except (ValueError, TypeError) as e:
                            print(f"Satır {index + 2}: Miktar dönüşüm hatası: {miktar_val} -> 1.0")
                            miktar = 1.0
                    
                    # Birim - varsa kullan, yoksa 'adet'
                    birim_val = row.get('birim', 'adet')
                    if pd.isna(birim_val):
                        birim = 'adet'
                    else:
                        birim_str = str(birim_val).strip()
                        if birim_str.lower() == 'nan' or not birim_str:
                            birim = 'adet'
                        else:
                            birim = birim_str
                    
                    # Birim fiyat - varsa kullan, yoksa 0
                    birim_fiyat_val = row.get('birim_fiyat', 0)
                    if pd.isna(birim_fiyat_val):
                        birim_fiyat = 0.0
                    else:
                        try:
                            birim_fiyat_str = str(birim_fiyat_val).strip()
                            if birim_fiyat_str.lower() == 'nan' or birim_fiyat_str == '':
                                birim_fiyat = 0.0
                            else:
                                # Virgülü noktaya çevir (Türkçe format)
                                birim_fiyat_str = birim_fiyat_str.replace(',', '.').replace(' ', '')
                                # Binlik ayırıcıları temizle (1.234,56 -> 1234.56)
                                if '.' in birim_fiyat_str and ',' in birim_fiyat_str:
                                    # Türkçe format: 1.234,56
                                    birim_fiyat_str = birim_fiyat_str.replace('.', '').replace(',', '.')
                                birim_fiyat = float(birim_fiyat_str)
                                if birim_fiyat < 0:
                                    birim_fiyat = 0.0
                                print(f"DEBUG: Satır {index + 2}: Birim fiyat okundu: {birim_fiyat_val} -> {birim_fiyat}")
                        except (ValueError, TypeError) as e:
                            print(f"Satır {index + 2}: Birim fiyat dönüşüm hatası: {birim_fiyat_val} -> 0.0")
                            birim_fiyat = 0.0
                    
                    # Önce poz'u ekle/güncelle (add_poz zaten varsa günceller)
                    poz_id = self.db.add_poz(
                        poz_no=poz_no,
                        tanim=tanim,
                        birim=birim,
                        kategori=kategori if kategori else "",
                        resmi_fiyat=birim_fiyat if birim_fiyat > 0 else 0
                    )
                    
                    # Birim fiyat ekle (eğer birim fiyat > 0 ise)
                    if birim_fiyat > 0:
                        fiyat_id = self.db.add_birim_fiyat(
                            poz_id=poz_id,
                            poz_no=poz_no,
                        birim_fiyat=birim_fiyat,
                            kaynak='Excel Import'
                    )
                        print(f"DEBUG: Poz {poz_no} için birim fiyat eklendi: {birim_fiyat} (ID: {fiyat_id})")
                    else:
                        print(f"DEBUG: Poz {poz_no} için birim fiyat 0, eklenmedi")
                    
                    success_count += 1
                    
                except Exception as e:
                    error_count += 1
                    error_msg = str(e)
                    if len(errors) < 20:  # İlk 20 hatayı göster
                        errors.append(f"Satır {index + 2}: {error_msg}")
                    print(f"Satır {index + 2} hatası: {error_msg}")
                    import traceback
                    if error_count <= 5:  # İlk 5 hatanın detayını göster
                        traceback.print_exc()
                    continue
            
            # Progress dialog'u kapat
            if len(df) > 100:
                progress.setValue(len(df))
                progress.close()
            
            # Sonuç mesajı
            message = f"İçe aktarma tamamlandı!\n\n"
            message += f"✅ Başarılı: {success_count}\n"
            message += f"❌ Hatalı: {error_count}\n"
            if skipped_empty > 0:
                message += f"⏭️ Boş satırlar atlandı: {skipped_empty}\n"
            
            if errors:
                if error_count <= 20:
                    message += f"\n\nHatalar:\n" + "\n".join(errors)
                else:
                    message += f"\n\n(İlk 20 hata gösteriliyor, toplam {error_count} hata var)\n\nHatalar:\n" + "\n".join(errors[:20])
            
            if success_count > 0:
                QMessageBox.information(self, "Başarılı", message)
                # Verileri yenile
                self.load_metraj_data()
                self.update_proje_ozet()
                self.statusBar().showMessage(f"{success_count} kalem içe aktarıldı")
            else:
                QMessageBox.warning(
                    self, "Uyarı", 
                    message + "\n\nHiçbir kalem eklenemedi. Lütfen Excel dosyasını kontrol edin."
                )
                
        except Exception as e:
            QMessageBox.critical(
                self, "Hata",
                f"Excel dosyası işlenirken hata oluştu:\n{str(e)}\n\n"
                f"Lütfen Excel dosyasının formatını kontrol edin:\n"
                f"- 'Poz No' veya 'poz_no' sütunu olmalı\n"
                f"- 'Tanım' veya 'tanim' sütunu olmalı\n"
                f"- Diğer sütunlar (Miktar, Birim, Birim Fiyat) opsiyoneldir"
            )
            import traceback
            traceback.print_exc()
    
    def import_from_pdf(self) -> None:
        """PDF'den birim fiyat içe aktar"""
        # PDF dosyası seç
        file_path, _ = QFileDialog.getOpenFileName(
            self, "PDF Dosyası Seç", "", "PDF Dosyaları (*.pdf)"
        )
        
        if not file_path:
            return
        
        try:
            from PyQt6.QtWidgets import QProgressDialog, QDialog, QVBoxLayout, QLabel, QTableWidget, QPushButton, QHBoxLayout
            from PyQt6.QtCore import Qt
            
            # Progress dialog
            progress = QProgressDialog("PDF işleniyor...", "İptal", 0, 100, self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(0)
            
            def progress_callback(current, total):
                percent = int((current / total) * 100)
                progress.setValue(percent)
                progress.setLabelText(f"PDF işleniyor... Sayfa {current}/{total}")
                if progress.wasCanceled():
                    return False
                return True
            
            # PDF'i işle
            from app.utils.pdf_importer import PDFBirimFiyatImporter
            importer = PDFBirimFiyatImporter()
            extracted_data = importer.extract_from_pdf(Path(file_path), progress_callback)
            
            progress.setValue(100)
            
            if not extracted_data:
                QMessageBox.warning(
                    self, "Uyarı",
                    "PDF'den poz ve fiyat bilgisi çıkarılamadı.\n\n"
                    "PDF formatını kontrol edin veya manuel olarak ekleyin."
                )
                return
            
            # Önizleme ve onay dialogu
            preview_dialog = QDialog(self)
            preview_dialog.setWindowTitle("PDF İçe Aktarma Önizleme")
            preview_dialog.setMinimumSize(900, 650)
            
            layout = QVBoxLayout(preview_dialog)
            
            info_label = QLabel(
                f"📄 {len(extracted_data)} adet poz ve fiyat bulundu.\n\n"
                f"Lütfen önizlemeyi kontrol edin ve onaylayın:"
            )
            layout.addWidget(info_label)
            
            preview_table = QTableWidget()
            preview_table.setColumnCount(5)
            preview_table.setHorizontalHeaderLabels(["Poz No", "Tanım", "Birim", "Birim Fiyat", "Kaynak"])
            preview_table.setRowCount(min(len(extracted_data), 100))  # İlk 100 kayıt

            for row, item in enumerate(extracted_data[:100]):
                preview_table.setItem(row, 0, QTableWidgetItem(item.get('poz_no', '')))
                preview_table.setItem(row, 1, QTableWidgetItem(item.get('tanim', '')[:50]))
                preview_table.setItem(row, 2, QTableWidgetItem(item.get('birim', '') or '-'))
                fiyat = item.get('birim_fiyat', 0)
                preview_table.setItem(row, 3, QTableWidgetItem(f"{fiyat:,.2f} ₺" if fiyat else "Bulunamadı"))
                preview_table.setItem(row, 4, QTableWidgetItem(item.get('kaynak', '')))
            
            preview_table.horizontalHeader().setStretchLastSection(True)
            layout.addWidget(preview_table)
            
            if len(extracted_data) > 100:
                more_label = QLabel(f"... ve {len(extracted_data) - 100} kayıt daha")
                layout.addWidget(more_label)
            
            btn_layout = QHBoxLayout()
            
            # Excel'e Aktar butonu
            btn_export_excel = QPushButton("📊 Excel'e Aktar")
            btn_export_excel.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 8px;")
            
            def export_to_excel():
                """PDF verilerini Excel'e aktar"""
                excel_path, _ = QFileDialog.getSaveFileName(
                    preview_dialog, 
                    "Excel Dosyası Oluştur", 
                    f"PDF_Pozlar_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    "Excel Dosyaları (*.xlsx)"
                )
                
                if excel_path:
                    try:
                        import pandas as pd
                        from openpyxl.styles import Font, Alignment, PatternFill
                        
                        # DataFrame oluştur
                        data = []
                        for item in extracted_data:
                            data.append({
                                'Poz No': item.get('poz_no', ''),
                                'Tanım': item.get('tanim', ''),
                                'Miktar': 1.0,  # Varsayılan miktar (kullanıcı düzenleyebilir)
                                'Birim': item.get('birim', '') or '',  # PDF'den gelen birim
                                'Birim Fiyat': item.get('birim_fiyat', 0) if item.get('birim_fiyat') else '',
                                'Kategori': '',  # Kullanıcı dolduracak
                                'Kaynak': item.get('kaynak', 'PDF Import')
                            })
                        
                        df = pd.DataFrame(data)
                        
                        # Excel'e yaz
                        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
                            df.to_excel(writer, sheet_name='Pozlar', index=False)
                            
                            # Stil ayarları
                            worksheet = writer.sheets['Pozlar']
                            
                            # Sütun genişlikleri
                            worksheet.column_dimensions['A'].width = 20  # Poz No
                            worksheet.column_dimensions['B'].width = 60  # Tanım
                            worksheet.column_dimensions['C'].width = 12  # Miktar
                            worksheet.column_dimensions['D'].width = 10  # Birim
                            worksheet.column_dimensions['E'].width = 15  # Birim Fiyat
                            worksheet.column_dimensions['F'].width = 20  # Kategori
                            worksheet.column_dimensions['G'].width = 15  # Kaynak
                            
                            # Başlık satırını stilize et
                            header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
                            header_font = Font(bold=True, color="FFFFFF")
                            header_alignment = Alignment(horizontal='center', vertical='center')
                            
                            for cell in worksheet[1]:
                                cell.font = header_font
                                cell.fill = header_fill
                                cell.alignment = header_alignment
                            
                            # Sayı formatları
                            from openpyxl.styles import numbers
                            # Miktar sütunu (C)
                            for row in range(2, len(df) + 2):
                                cell = worksheet[f'C{row}']
                                if cell.value:
                                    cell.number_format = '#,##0.00'
                            # Birim Fiyat sütunu (E)
                            for row in range(2, len(df) + 2):
                                cell = worksheet[f'E{row}']
                                if cell.value:
                                    cell.number_format = '#,##0.00'
                        
                        QMessageBox.information(
                            preview_dialog,
                            "Başarılı",
                            f"✅ Excel dosyası oluşturuldu!\n\n"
                            f"📁 Konum: {excel_path}\n\n"
                            f"📝 {len(extracted_data)} adet poz Excel'e aktarıldı.\n\n"
                            f"💡 Excel'de verileri kontrol edip düzenleyebilir,\n"
                            f"sonra 'Excel'den Kalem İçe Aktar' ile programa yükleyebilirsiniz."
                        )
                        
                        # Dialog'u kapat
                        preview_dialog.accept()
                        
                    except Exception as e:
                        QMessageBox.critical(
                            preview_dialog,
                            "Hata",
                            f"Excel dosyası oluşturulurken hata oluştu:\n{str(e)}"
                        )
                        import traceback
                        traceback.print_exc()
            
            btn_export_excel.clicked.connect(export_to_excel)
            
            btn_ok = QPushButton("✅ Doğrudan İçe Aktar")
            btn_ok.clicked.connect(preview_dialog.accept)
            btn_cancel = QPushButton("❌ İptal")
            btn_cancel.clicked.connect(preview_dialog.reject)
            
            btn_layout.addWidget(btn_export_excel)
            btn_layout.addStretch()
            btn_layout.addWidget(btn_ok)
            btn_layout.addWidget(btn_cancel)
            layout.addLayout(btn_layout)
            
            # Bilgi mesajı ekle
            info_text = QLabel(
                "💡 İpucu: Excel'e aktarıp kontrol etmek daha güvenilirdir!\n"
                "Excel'de verileri düzenleyebilir, sonra 'Excel'den Kalem İçe Aktar' ile yükleyebilirsiniz."
            )
            info_text.setStyleSheet("color: #666; font-style: italic; padding: 5px;")
            layout.insertWidget(1, info_text)
            
            if preview_dialog.exec() != QDialog.DialogCode.Accepted:
                return
            
            # Veritabanına kaydet
            success_count = 0
            error_count = 0
            poz_added_count = 0
            fiyat_added_count = 0
            errors = []
            
            progress = QProgressDialog("Veritabanına kaydediliyor...", "İptal", 0, len(extracted_data), self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(0)
            
            for idx, item in enumerate(extracted_data):
                progress.setValue(idx)
                progress.setLabelText(f"Kaydediliyor... {idx + 1}/{len(extracted_data)}")
                
                if progress.wasCanceled():
                    break
                
                try:
                    poz_no = item.get('poz_no', '').strip()
                    birim_fiyat = item.get('birim_fiyat') or 0  # None ise 0 yap
                    if birim_fiyat is None:
                        birim_fiyat = 0
                    birim_fiyat = float(birim_fiyat) if birim_fiyat else 0
                    tanim = item.get('tanim', '') or "PDF'den içe aktarıldı"
                    
                    if not poz_no:
                        error_count += 1
                        continue
                    
                    # ÖNCE POZU POZLAR TABLOSUNA EKLE (yoksa)
                    poz = self.db.get_poz(poz_no)
                    if not poz:
                        # Poz yoksa ekle
                        try:
                            # Birim bilgisi: Önce PDF'den gelen, yoksa tanımdan tahmin et
                            birim = item.get('birim', '') or ''
                            if not birim:
                                # PDF'den birim gelmemişse tanımdan tahmin et
                                birim = "m²"  # Varsayılan birim
                                if "m³" in tanim.lower() or "metreküp" in tanim.lower():
                                    birim = "m³"
                                elif "m²" in tanim.lower() or "metrekare" in tanim.lower():
                                    birim = "m²"
                                elif "kg" in tanim.lower() or "kilogram" in tanim.lower():
                                    birim = "kg"
                                elif "adet" in tanim.lower() or "ad." in tanim.lower():
                                    birim = "adet"
                                elif "m" in tanim.lower() and "m²" not in tanim.lower() and "m³" not in tanim.lower():
                                    birim = "m"
                            
                            # Kategoriyi poz numarasından tahmin et
                            kategori = ""
                            if poz_no.startswith("03.") or poz_no.startswith("03-"):
                                kategori = "Toprak İşleri"
                            elif poz_no.startswith("04.") or poz_no.startswith("04-"):
                                kategori = "Beton İşleri"
                            elif poz_no.startswith("05.") or poz_no.startswith("05-"):
                                kategori = "Demir İşleri"
                            elif poz_no.startswith("15.") or poz_no.startswith("15-"):
                                kategori = "Yalıtım İşleri"
                            else:
                                kategori = "Genel"
                            
                            self.db.add_poz(
                                poz_no=poz_no,
                                tanim=tanim[:200],  # İlk 200 karakter
                                birim=birim,
                                resmi_fiyat=birim_fiyat if birim_fiyat and birim_fiyat > 0 else 0,
                                kategori=kategori,
                                fire_orani=0.05  # Varsayılan fire oranı
                            )
                            poz_added_count += 1
                        except Exception as e:
                            errors.append(f"Poz {poz_no} eklenirken hata: {str(e)}")
                    
                    # SONRA BİRİM FİYATI EKLE (varsa)
                    # Fiyat varsa hem poz tablosundaki resmi_fiyat hem de birim_fiyatlar tablosuna ekle
                    if birim_fiyat and birim_fiyat > 0:
                        try:
                            # Birim fiyatlar tablosuna ekle
                            fiyat_id = self.db.add_birim_fiyat(
                                poz_no=poz_no,
                                birim_fiyat=birim_fiyat,
                                kaynak=item.get('kaynak', 'PDF Import'),
                                aciklama=tanim[:100]
                            )
                            if fiyat_id:
                                fiyat_added_count += 1
                            
                            # Poz tablosundaki resmi_fiyat'ı da güncelle (eğer poz eklendiyse)
                            if poz_added_count > 0 or poz:
                                try:
                                    with self.db.get_connection() as conn:
                                        cursor = conn.cursor()
                                        cursor.execute("""
                                            UPDATE pozlar 
                                            SET resmi_fiyat = ? 
                                            WHERE poz_no = ? AND (resmi_fiyat = 0 OR resmi_fiyat IS NULL)
                                        """, (birim_fiyat, poz_no))
                                except:
                                    pass  # Güncelleme başarısız olsa bile devam et
                        except Exception as e:
                            errors.append(f"Poz {poz_no} fiyat eklenirken hata: {str(e)}")
                    else:
                        # Fiyat yoksa da poz eklendi, bu başarılı sayılır
                        pass
                    
                    success_count += 1
                    
                except Exception as e:
                    error_count += 1
                    errors.append(f"Poz {item.get('poz_no', '')}: {str(e)}")
                    continue
            
            progress.setValue(len(extracted_data))
            
            # Sonuç mesajı
            message = f"PDF içe aktarma tamamlandı!\n\n"
            message += f"✅ Toplam işlenen: {success_count}\n"
            if poz_added_count > 0:
                message += f"📝 Yeni poz eklendi: {poz_added_count}\n"
            if fiyat_added_count > 0:
                message += f"💰 Birim fiyat eklendi: {fiyat_added_count}\n"
            message += f"❌ Hatalı: {error_count}"
            
            if errors and error_count <= 20:
                message += f"\n\nHatalar:\n" + "\n".join(errors[:20])
            elif errors:
                message += f"\n\n(İlk 20 hata gösteriliyor, toplam {error_count} hata var)"
            
            if success_count > 0:
                QMessageBox.information(self, "Başarılı", message)
                # Birim fiyat sekmesi açıksa güncelle
                if hasattr(self, 'fiyat_filter_combo') and self._tabs_created.get('birim_fiyat', False):
                    self.load_birim_fiyatlar()
                self.statusBar().showMessage(f"{success_count} birim fiyat içe aktarıldı")
            else:
                QMessageBox.warning(self, "Uyarı", message)
                
        except Exception as e:
            QMessageBox.critical(
                self, "Hata",
                f"PDF dosyası işlenirken hata oluştu:\n{str(e)}"
            )
            import traceback
            traceback.print_exc()
    
    def clear_pdf_imported_data(self) -> None:
        """PDF'den eklenen pozları ve birim fiyatları temizle"""
        # Onay mesajı
        reply = QMessageBox.question(
            self, 
            "PDF Pozları Temizle",
            "PDF'den eklenen tüm pozları ve birim fiyatları silmek istediğinizden emin misiniz?\n\n"
            "Bu işlem geri alınamaz!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        try:
            # PDF'den eklenen verileri sil
            result = self.db.delete_pdf_imported_data()
            
            poz_count = result.get('pozlar', 0)
            fiyat_count = result.get('birim_fiyatlar', 0)
            
            message = f"PDF'den eklenen veriler temizlendi!\n\n"
            message += f"✅ Silinen poz sayısı: {poz_count}\n"
            message += f"✅ Silinen birim fiyat sayısı: {fiyat_count}\n\n"
            message += "Artık PDF'yi yeniden yükleyebilirsiniz."
            
            QMessageBox.information(self, "Başarılı", message)
            
            # İlgili sekmeleri güncelle
            if hasattr(self, 'fiyat_filter_combo') and self._tabs_created.get('birim_fiyat', False):
                self.load_birim_fiyatlar()
            
            self.statusBar().showMessage(f"{poz_count} poz ve {fiyat_count} birim fiyat silindi")
            
        except Exception as e:
            QMessageBox.critical(
                self, 
                "Hata",
                f"PDF verileri temizlenirken hata oluştu:\n{str(e)}"
            )
            import traceback
            traceback.print_exc()

    def clear_all_poz_data(self) -> None:
        """TÜM pozları ve birim fiyatları temizle"""
        # Çift onay mesajı (kritik işlem)
        reply = QMessageBox.warning(
            self,
            "⚠️ TÜM VERİLERİ TEMİZLE",
            "DİKKAT: Bu işlem TÜM pozları ve birim fiyatları silecektir!\n\n"
            "• Tüm poz kayıtları silinecek\n"
            "• Tüm birim fiyat kayıtları silinecek\n"
            "• Bu işlem GERİ ALINAMAZ!\n\n"
            "Devam etmek istediğinizden emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # İkinci onay
        reply2 = QMessageBox.critical(
            self,
            "⛔ SON ONAY",
            "Bu işlem tüm poz ve fiyat verilerini kalıcı olarak silecek!\n\n"
            "EMIN MISINIZ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply2 != QMessageBox.StandardButton.Yes:
            return

        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                # Mevcut sayıları al
                cursor.execute('SELECT COUNT(*) FROM birim_fiyatlar')
                fiyat_count = cursor.fetchone()[0]

                cursor.execute('SELECT COUNT(*) FROM pozlar')
                poz_count = cursor.fetchone()[0]

                # Tabloları temizle
                cursor.execute('DELETE FROM birim_fiyatlar')
                cursor.execute('DELETE FROM pozlar')

            message = f"TÜM veriler temizlendi!\n\n"
            message += f"🗑️ Silinen poz sayısı: {poz_count}\n"
            message += f"🗑️ Silinen birim fiyat sayısı: {fiyat_count}\n\n"
            message += "Artık yeni PDF yükleyebilirsiniz."

            QMessageBox.information(self, "Temizlendi", message)

            # İlgili sekmeleri güncelle
            if hasattr(self, 'fiyat_filter_combo') and self._tabs_created.get('birim_fiyat', False):
                self.load_birim_fiyatlar()

            self.statusBar().showMessage(f"TÜM VERİLER TEMİZLENDİ: {poz_count} poz, {fiyat_count} fiyat silindi")

        except Exception as e:
            QMessageBox.critical(
                self,
                "Hata",
                f"Veriler temizlenirken hata oluştu:\n{str(e)}"
            )
            import traceback
            traceback.print_exc()

    def show_missing_prices(self) -> None:
        """Fiyatı olmayan pozları göster"""
        try:
            from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem, QPushButton, QLabel, QFileDialog, QHBoxLayout
            from PyQt6.QtCore import Qt

            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                # Fiyatı 0 veya NULL olan pozları bul
                cursor.execute("""
                    SELECT poz_no, tanim, birim, resmi_fiyat
                    FROM pozlar
                    WHERE resmi_fiyat IS NULL OR resmi_fiyat = 0 OR resmi_fiyat = ''
                    ORDER BY poz_no
                """)
                rows = cursor.fetchall()

                # Toplam poz sayısını al
                cursor.execute("SELECT COUNT(*) FROM pozlar")
                total_count = cursor.fetchone()[0]

            if not rows:
                QMessageBox.information(
                    self,
                    "Tamamlandı",
                    f"Tüm pozların fiyatı mevcut!\n\nToplam poz: {total_count}"
                )
                return

            # Dialog oluştur
            dialog = QDialog(self)
            dialog.setWindowTitle("Fiyatsız Pozlar")
            dialog.setMinimumSize(900, 600)

            layout = QVBoxLayout(dialog)

            # Bilgi etiketi
            info_label = QLabel(
                f"⚠️ Fiyatı olmayan poz sayısı: {len(rows)} / {total_count}\n\n"
                f"Bu pozların PDF'deki fiyatları okunamadı. Format sorunu olabilir."
            )
            info_label.setStyleSheet("font-size: 12px; padding: 10px; background-color: #fff3cd; border-radius: 5px;")
            layout.addWidget(info_label)

            # Tablo
            table = QTableWidget()
            table.setColumnCount(4)
            table.setHorizontalHeaderLabels(["Poz No", "Tanım", "Birim", "Fiyat"])
            table.setRowCount(len(rows))

            for row_idx, row in enumerate(rows):
                poz_no, tanim, birim, fiyat = row
                table.setItem(row_idx, 0, QTableWidgetItem(poz_no or ''))
                table.setItem(row_idx, 1, QTableWidgetItem((tanim or '')[:80]))
                table.setItem(row_idx, 2, QTableWidgetItem(birim or ''))
                table.setItem(row_idx, 3, QTableWidgetItem(str(fiyat) if fiyat else '0'))

            table.horizontalHeader().setStretchLastSection(True)
            table.setColumnWidth(0, 120)
            table.setColumnWidth(1, 500)
            table.setColumnWidth(2, 80)
            layout.addWidget(table)

            # Butonlar
            btn_layout = QHBoxLayout()

            # Excel'e aktar butonu
            btn_export = QPushButton("📊 Excel'e Aktar")
            btn_export.setStyleSheet("background-color: #28a745; color: white; padding: 8px;")

            def export_to_excel():
                try:
                    import pandas as pd
                    excel_path, _ = QFileDialog.getSaveFileName(
                        dialog, "Excel Dosyası Kaydet",
                        f"fiyatsiz_pozlar.xlsx",
                        "Excel Dosyaları (*.xlsx)"
                    )
                    if excel_path:
                        data = []
                        for row in rows:
                            data.append({
                                'Poz No': row[0],
                                'Tanım': row[1],
                                'Birim': row[2],
                                'Fiyat': row[3] or 0
                            })
                        df = pd.DataFrame(data)
                        df.to_excel(excel_path, index=False)
                        QMessageBox.information(dialog, "Başarılı", f"Excel'e aktarıldı:\n{excel_path}")
                except Exception as e:
                    QMessageBox.critical(dialog, "Hata", f"Excel aktarım hatası:\n{str(e)}")

            btn_export.clicked.connect(export_to_excel)
            btn_layout.addWidget(btn_export)

            btn_layout.addStretch()

            btn_close = QPushButton("Kapat")
            btn_close.clicked.connect(dialog.close)
            btn_layout.addWidget(btn_close)

            layout.addLayout(btn_layout)

            dialog.exec()

        except Exception as e:
            QMessageBox.critical(
                self,
                "Hata",
                f"Fiyatsız pozlar listelenirken hata oluştu:\n{str(e)}"
            )
            import traceback
            traceback.print_exc()

    def on_search_text_changed(self) -> None:
        """Gelişmiş arama ve filtreleme - Tüm modüllerde arama"""
        search_text = self.search_input.text().strip()
        search_type = self.search_type_combo.currentText()
        
        if not search_text:
            # Arama boşsa normal listeyi göster
            self.load_projects()
            if self.current_project_id:
                if hasattr(self, 'metraj_table') and self._tabs_created.get('metraj', False):
                    self.load_metraj_data()
                if hasattr(self, 'taseron_table') and self._tabs_created.get('taseron', False):
                    self.load_taseron_data()
            if hasattr(self, 'ihale_kalem_table') and self._tabs_created.get('ihale', False):
                if hasattr(self, 'current_ihale_id') and self.current_ihale_id:
                    self.load_ihale_kalemleri()
            return
        
        search_lower = search_text.lower()
        
        # Proje araması
        if search_type in ["Tümü", "Projeler"]:
            projects = self.db.get_all_projects()
            self.project_tree.clear()
            for project in projects:
                project_name = project['ad'].lower()
                project_desc = (project.get('aciklama', '') or '').lower()
                project_notes = (project.get('notlar', '') or '').lower()
                
                if (search_lower in project_name or 
                    search_lower in project_desc or 
                    search_lower in project_notes):
                    item = QTreeWidgetItem(self.project_tree)
                    item.setText(0, project['ad'])
                    item.setData(0, Qt.ItemDataRole.UserRole, project['id'])
        
        # Kalem araması (seçili projede - Metraj)
        if search_type in ["Tümü", "Kalemler"] and self.current_project_id:
            if hasattr(self, 'metraj_table') and self._tabs_created.get('metraj', False):
                metraj_items = self.db.get_project_metraj(self.current_project_id)
                filtered_items = []
                for item in metraj_items:
                    tanim = (item.get('tanim', '') or '').lower()
                    poz_no = (item.get('poz_no', '') or '').lower()
                    kategori = (item.get('kategori', '') or '').lower()
                    notlar = (item.get('notlar', '') or '').lower()
                    
                    if (search_lower in tanim or
                        search_lower in poz_no or
                        search_lower in kategori or
                        search_lower in notlar):
                        filtered_items.append(item)
            
                # Metraj tablosunu filtrele
                self.metraj_table.setRowCount(len(filtered_items))
                for row, item in enumerate(filtered_items):
                    self.metraj_table.setItem(row, 0, QTableWidgetItem(str(item.get('id', ''))))
                    self.metraj_table.setItem(row, 1, QTableWidgetItem(item.get('poz_no', '')))
                    self.metraj_table.setItem(row, 2, QTableWidgetItem(item.get('tanim', '')))
                    self.metraj_table.setItem(row, 3, QTableWidgetItem(f"{item.get('miktar', 0):,.2f}"))
                    self.metraj_table.setItem(row, 4, QTableWidgetItem(item.get('birim', '')))
                    self.metraj_table.setItem(row, 5, QTableWidgetItem(f"{item.get('birim_fiyat', 0):,.2f}"))
                    self.metraj_table.setItem(row, 6, QTableWidgetItem(f"{item.get('toplam', 0):,.2f}"))
            
                # Toplamı güncelle (KDV ile)
                toplam = sum(item.get('toplam', 0) for item in filtered_items)
                kdv_rate_text = self.metraj_kdv_rate.currentText().replace("%", "")
                kdv_rate = float(kdv_rate_text)
                kdv_hesap = self.calculator.calculate_with_kdv(toplam, kdv_rate)
                self.total_label.setText(f"Toplam (KDV Hariç): {toplam:,.2f} ₺ (Filtrelenmiş: {len(filtered_items)} kalem)")
                self.total_kdv_label.setText(f"Toplam (KDV %{kdv_rate_text} Dahil): {kdv_hesap['kdv_dahil']:,.2f} ₺")
        
        # Poz araması (tüm pozlar)
        if search_type in ["Tümü", "Pozlar"]:
            if hasattr(self, 'birim_fiyat_table') and self._tabs_created.get('birim_fiyat', False):
                pozlar = self.db.search_pozlar(search_text, limit=100)
                self.birim_fiyat_table.setRowCount(len(pozlar))
                for row, poz in enumerate(pozlar):
                    self.birim_fiyat_table.setItem(row, 0, QTableWidgetItem(poz.get('poz_no', '')))
                    self.birim_fiyat_table.setItem(row, 1, QTableWidgetItem(poz.get('tanim', '')))
                    self.birim_fiyat_table.setItem(row, 2, QTableWidgetItem(poz.get('birim', '')))
                    self.birim_fiyat_table.setItem(row, 3, QTableWidgetItem(f"{poz.get('resmi_fiyat', 0):,.2f}"))
                    self.birim_fiyat_table.setItem(row, 4, QTableWidgetItem(poz.get('kategori', '')))
        
        # İhale kalemleri araması
        if search_type in ["Tümü", "Kalemler"]:
            if hasattr(self, 'ihale_kalem_table') and self._tabs_created.get('ihale', False):
                if hasattr(self, 'current_ihale_id') and self.current_ihale_id:
                    kalemler = self.db.get_ihale_kalemleri(self.current_ihale_id)
                    filtered_kalemler = []
                    for kalem in kalemler:
                        poz_no = (kalem.get('poz_no', '') or '').lower()
                        tanim = (kalem.get('poz_tanim', '') or '').lower()
                        kategori = (kalem.get('kategori', '') or '').lower()
                        
                        if (search_lower in poz_no or
                            search_lower in tanim or
                            search_lower in kategori):
                            filtered_kalemler.append(kalem)
                    
                    # İhale tablosunu filtrele
                    self.ihale_kalem_table.setRowCount(len(filtered_kalemler))
                    for row, kalem in enumerate(filtered_kalemler):
                        self.ihale_kalem_table.setItem(row, 0, QTableWidgetItem(str(kalem.get('sira_no', ''))))
                        self.ihale_kalem_table.setItem(row, 1, QTableWidgetItem(kalem.get('poz_no', '')))
                        self.ihale_kalem_table.setItem(row, 2, QTableWidgetItem(kalem.get('poz_tanim', '')))
                        self.ihale_kalem_table.setItem(row, 3, QTableWidgetItem(f"{kalem.get('birim_miktar', 0):,.2f}"))
                        self.ihale_kalem_table.setItem(row, 4, QTableWidgetItem(kalem.get('birim', '')))
                        self.ihale_kalem_table.setItem(row, 5, QTableWidgetItem(f"{kalem.get('birim_fiyat', 0):,.2f}"))
                        self.ihale_kalem_table.setItem(row, 6, QTableWidgetItem(f"{kalem.get('toplam', 0):,.2f}"))
                    
                    # Toplamı güncelle
                    toplam = sum(kalem.get('toplam', 0) for kalem in filtered_kalemler)
                    if hasattr(self, 'ihale_total_label'):
                        # KDV hesaplama
                        kdv_rate_text = self.ihale_kdv_rate.currentText().replace("%", "")
                        kdv_rate = float(kdv_rate_text)
                        kdv_hesap = self.calculator.calculate_with_kdv(toplam, kdv_rate)
                        
                        self.ihale_total_label.setText(f"Toplam (KDV Hariç): {toplam:,.2f} ₺ (Filtrelenmiş: {len(filtered_kalemler)} kalem)")
                        self.ihale_total_kdv_label.setText(f"Toplam (KDV %{kdv_rate_text} Dahil): {kdv_hesap['kdv_dahil']:,.2f} ₺")
        
        # Taşeron araması
        if search_type in ["Tümü", "Kalemler"]:
            if hasattr(self, 'taseron_table') and self._tabs_created.get('taseron', False):
                if self.current_project_id:
                    teklifler = self.db.get_taseron_teklifleri(self.current_project_id)
                    filtered_teklifler = []
                    for teklif in teklifler:
                        firma = (teklif.get('firma_adi', '') or '').lower()
                        poz_no = (teklif.get('poz_no', '') or '').lower()
                        tanim = (teklif.get('tanim', '') or '').lower()
                        notlar = (teklif.get('notlar', '') or '').lower()
                        
                        if (search_lower in firma or
                            search_lower in poz_no or
                            search_lower in tanim or
                            search_lower in notlar):
                            filtered_teklifler.append(teklif)
                    
                    # Taşeron tablosunu filtrele
                    self.taseron_table.setRowCount(len(filtered_teklifler))
                    for row, teklif in enumerate(filtered_teklifler):
                        self.taseron_table.setItem(row, 0, QTableWidgetItem(teklif.get('firma_adi', '')))
                        self.taseron_table.setItem(row, 1, QTableWidgetItem(teklif.get('poz_no', '')))
                        self.taseron_table.setItem(row, 2, QTableWidgetItem(teklif.get('tanim', '')))
                        self.taseron_table.setItem(row, 3, QTableWidgetItem(f"{teklif.get('miktar', 0):,.2f}"))
                        self.taseron_table.setItem(row, 4, QTableWidgetItem(teklif.get('birim', '')))
                        self.taseron_table.setItem(row, 5, QTableWidgetItem(f"{teklif.get('fiyat', 0):,.2f}"))
                        self.taseron_table.setItem(row, 6, QTableWidgetItem(f"{teklif.get('toplam', 0):,.2f}"))
    
    def load_templates(self) -> None:
        """Şablonları yükle"""
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()  # UI'ı güncelle
        
        templates = self.db.get_all_templates()
        self.template_table.setRowCount(len(templates))
        
        for row, template in enumerate(templates):
            self.template_table.setItem(row, 0, QTableWidgetItem(template.get('ad', '')))
            self.template_table.setItem(row, 1, QTableWidgetItem(template.get('aciklama', '')))
            tarih = template.get('olusturma_tarihi', '')[:10] if template.get('olusturma_tarihi') else ''
            self.template_table.setItem(row, 2, QTableWidgetItem(tarih))
            
            # Kalem sayısını al
            items = self.db.get_template_items(template['id'])
            self.template_table.setItem(row, 3, QTableWidgetItem(str(len(items))))
            
            # ID'yi sakla
            item = self.template_table.item(row, 0)
            if item:
                item.setData(Qt.ItemDataRole.UserRole, template['id'])
            
            # Her 10 şablonda bir UI'ı güncelle
            if row % 10 == 0:
                QApplication.processEvents()
    
    def view_template_items(self, item: QTableWidgetItem) -> None:
        """Şablon kalemlerini göster"""
        row = item.row()
        template_item = self.template_table.item(row, 0)
        if not template_item:
            return
        
        template_id = template_item.data(Qt.ItemDataRole.UserRole)
        if not template_id:
            return
        
        self.current_template_id = template_id
        items = self.db.get_template_items(template_id)
        self.template_items_table.setRowCount(len(items))
        
        for row_idx, item_data in enumerate(items):
            # ID (gizli)
            id_item = QTableWidgetItem(str(item_data.get('id', '')))
            id_item.setData(Qt.ItemDataRole.UserRole, item_data.get('id'))
            self.template_items_table.setItem(row_idx, 0, id_item)
            
            self.template_items_table.setItem(row_idx, 1, QTableWidgetItem(item_data.get('poz_no', '')))
            self.template_items_table.setItem(row_idx, 2, QTableWidgetItem(item_data.get('tanim', '')))
            self.template_items_table.setItem(row_idx, 3, QTableWidgetItem(item_data.get('kategori', '')))
            self.template_items_table.setItem(row_idx, 4, QTableWidgetItem(f"{item_data.get('miktar', 0):,.2f}"))
            self.template_items_table.setItem(row_idx, 5, QTableWidgetItem(item_data.get('birim', '')))
            self.template_items_table.setItem(row_idx, 6, QTableWidgetItem(f"{item_data.get('birim_fiyat', 0):,.2f}"))
            self.template_items_table.setItem(row_idx, 7, QTableWidgetItem(f"{item_data.get('toplam', 0):,.2f}"))
    
    def create_template_from_project(self) -> None:
        """Mevcut projeden şablon oluştur"""
        if not self.current_project_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce bir proje seçin")
            return
        
        project = self.db.get_project(self.current_project_id)
        if not project:
            QMessageBox.warning(self, "Uyarı", "Proje bulunamadı")
            return
        
        # Şablon adı ve açıklaması sor
        from PyQt6.QtWidgets import QInputDialog
        
        template_name, ok1 = QInputDialog.getText(
            self, "Şablon Oluştur",
            f"Şablon adı:\n(Proje: {project['ad']})"
        )
        
        if not ok1 or not template_name.strip():
            return
        
        template_description, ok2 = QInputDialog.getText(
            self, "Şablon Açıklaması",
            "Şablon açıklaması (isteğe bağlı):"
        )
        
        if not ok2:
            return
        
        # Şablon oluştur
        template_id = self.db.create_template_from_project(
            self.current_project_id,
            template_name.strip(),
            template_description.strip()
        )
        
        if template_id:
            QMessageBox.information(
                self, "Başarılı",
                f"Şablon başarıyla oluşturuldu!\n\n"
                f"Şablon adı: {template_name}\n"
                f"Kalem sayısı: {len(self.db.get_project_metraj(self.current_project_id))}"
            )
            self.load_templates()
            self.statusBar().showMessage(f"Şablon oluşturuldu: {template_name}")
        else:
            QMessageBox.critical(self, "Hata", "Şablon oluşturulurken bir hata oluştu")
    
    def create_project_from_template(self) -> None:
        """Şablondan proje oluştur"""
        current_row = self.template_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Uyarı", "Lütfen bir şablon seçin")
            return
        
        template_item = self.template_table.item(current_row, 0)
        if not template_item:
            return
        
        template_id = template_item.data(Qt.ItemDataRole.UserRole)
        if not template_id:
            return
        
        template = self.db.get_template(template_id)
        if not template:
            QMessageBox.warning(self, "Uyarı", "Şablon bulunamadı")
            return
        
        # Proje adı ve açıklaması sor
        from PyQt6.QtWidgets import QInputDialog
        
        project_name, ok1 = QInputDialog.getText(
            self, "Proje Oluştur",
            f"Yeni proje adı:\n(Şablon: {template['ad']})"
        )
        
        if not ok1 or not project_name.strip():
            return
        
        project_description, ok2 = QInputDialog.getText(
            self, "Proje Açıklaması",
            "Proje açıklaması (isteğe bağlı):"
        )
        
        if not ok2:
            return
        
        # Proje oluştur
        project_id = self.db.create_project_from_template(
            template_id,
            project_name.strip(),
            project_description.strip()
        )
        
        if project_id:
            QMessageBox.information(
                self, "Başarılı",
                f"Proje başarıyla oluşturuldu!\n\n"
                f"Proje adı: {project_name}\n"
                f"Kalem sayısı: {len(self.db.get_template_items(template_id))}"
            )
            # Proje listesini yenile
            self.load_projects()
            # Yeni projeyi seç
            self.current_project_id = project_id
            self.load_metraj_data()
            self.load_taseron_data()
            self.update_proje_ozet()
            self.load_project_notes()
            self.statusBar().showMessage(f"Proje oluşturuldu: {project_name}")
        else:
            QMessageBox.critical(self, "Hata", "Proje oluşturulurken bir hata oluştu")
    
    def delete_template(self) -> None:
        """Şablonu sil"""
        current_row = self.template_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Uyarı", "Lütfen silmek istediğiniz şablonu seçin")
            return
        
        template_item = self.template_table.item(current_row, 0)
        if not template_item:
            return
        
        template_id = template_item.data(Qt.ItemDataRole.UserRole)
        template_name = template_item.text()
        
        if not template_id:
            return
        
        # Onay al
        reply = QMessageBox.question(
            self, "Şablon Sil",
            f"'{template_name}' şablonunu silmek istediğinize emin misiniz?\n\n"
            "Bu işlem geri alınamaz!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if self.db.delete_template(template_id):
                QMessageBox.information(self, "Başarılı", "Şablon silindi")
                self.load_templates()
                self.template_items_table.setRowCount(0)
                self.statusBar().showMessage("Şablon silindi")
            else:
                QMessageBox.critical(self, "Hata", "Şablon silinirken bir hata oluştu")
    
    def create_empty_template(self) -> None:
        """Boş şablon oluştur"""
        from PyQt6.QtWidgets import QInputDialog
        
        template_name, ok1 = QInputDialog.getText(
            self, "Boş Şablon Oluştur",
            "Şablon adı:"
        )
        
        if not ok1 or not template_name.strip():
            return
        
        template_description, ok2 = QInputDialog.getText(
            self, "Şablon Açıklaması",
            "Şablon açıklaması (isteğe bağlı):"
        )
        
        if not ok2:
            return
        
        template_id = self.db.create_template(template_name.strip(), template_description.strip())
        
        if template_id:
            QMessageBox.information(
                self, "Başarılı",
                f"Boş şablon başarıyla oluşturuldu!\n\n"
                f"Şablon adı: {template_name}\n"
                f"Şimdi şablona kalem ekleyebilirsiniz."
            )
            self.load_templates()
            # Yeni oluşturulan şablonu seç
            for row in range(self.template_table.rowCount()):
                item = self.template_table.item(row, 0)
                if item and item.data(Qt.ItemDataRole.UserRole) == template_id:
                    self.template_table.selectRow(row)
                    self.current_template_id = template_id
                    self.view_template_items(item)
                    break
            self.statusBar().showMessage(f"Boş şablon oluşturuldu: {template_name}")
        else:
            QMessageBox.critical(self, "Hata", "Şablon oluşturulurken bir hata oluştu")
    
    def create_template_from_categories(self) -> None:
        """Kategori bazlı şablon oluştur"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QCheckBox, QScrollArea, QWidget, QPushButton, QHBoxLayout, QMessageBox
        
        # Kategorileri al
        kategoriler = self.db.get_all_kategoriler()
        
        if not kategoriler:
            QMessageBox.warning(self, "Uyarı", "Sistemde kategori bulunamadı. Önce projeler oluşturun.")
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Kategori Bazlı Şablon Oluştur")
        dialog.setMinimumWidth(500)
        dialog.setMinimumHeight(400)
        
        layout = QVBoxLayout(dialog)
        
        # Şablon adı ve açıklama
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Şablon Adı:"))
        name_input = QLineEdit()
        name_layout.addWidget(name_input)
        layout.addLayout(name_layout)
        
        desc_layout = QHBoxLayout()
        desc_layout.addWidget(QLabel("Açıklama:"))
        desc_input = QLineEdit()
        desc_layout.addWidget(desc_input)
        layout.addLayout(desc_layout)
        
        layout.addWidget(QLabel("Kategorileri seçin:"))
        
        # Kategori checkbox'ları
        scroll = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        category_checkboxes = {}
        for kategori in kategoriler:
            checkbox = QCheckBox(kategori)
            category_checkboxes[kategori] = checkbox
            scroll_layout.addWidget(checkbox)
        
        scroll.setWidget(scroll_widget)
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)
        
        # Butonlar
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("Oluştur")
        btn_cancel = QPushButton("İptal")
        btn_ok.clicked.connect(dialog.accept)
        btn_cancel.clicked.connect(dialog.reject)
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
        
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        
        template_name = name_input.text().strip()
        if not template_name:
            QMessageBox.warning(self, "Uyarı", "Şablon adı boş olamaz")
            return
        
        # Seçili kategorileri al
        selected_categories = [k for k, cb in category_checkboxes.items() if cb.isChecked()]
        
        if not selected_categories:
            QMessageBox.warning(self, "Uyarı", "En az bir kategori seçmelisiniz")
            return
        
        # Şablon oluştur
        template_id = self.db.create_template(template_name, desc_input.text().strip())
        
        if not template_id:
            QMessageBox.critical(self, "Hata", "Şablon oluşturulurken bir hata oluştu")
            return
        
        # Kategorilerden kalemleri al ve ekle
        items = self.db.get_items_by_kategoriler(selected_categories)
        
        if not items:
            QMessageBox.warning(self, "Uyarı", "Seçili kategorilerde kalem bulunamadı")
            self.db.delete_template(template_id)
            return
        
        added_count = 0
        for item in items:
            birim_fiyat = item.get('birim_fiyat', 0) or 0
            self.db.add_template_item(
                sablon_id=template_id,
                poz_no=item.get('poz_no', ''),
                tanim=item.get('tanim', ''),
                kategori=item.get('kategori', ''),
                miktar=0,  # Varsayılan miktar 0
                birim=item.get('birim', ''),
                birim_fiyat=birim_fiyat,
                toplam=0
            )
            added_count += 1
        
        QMessageBox.information(
            self, "Başarılı",
            f"Kategori bazlı şablon oluşturuldu!\n\n"
            f"Şablon adı: {template_name}\n"
            f"Eklenen kalem sayısı: {added_count}"
        )
        self.load_templates()
        self.statusBar().showMessage(f"Kategori bazlı şablon oluşturuldu: {template_name}")
    
    def create_template_from_preset(self) -> None:
        """Hazır şablon şablonlarından oluştur"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QComboBox, QPushButton, QHBoxLayout
        
        # Hazır şablon şablonları
        presets = {
            "100m² Konut Standart": {
                "kategoriler": ["Beton İşleri", "Demir İşleri", "Sıva İşleri", "Boyama İşleri", "Elektrik İşleri", "Tesisat İşleri"],
                "aciklama": "100m² standart konut için temel iş kalemleri"
            },
            "200m² Villa Standart": {
                "kategoriler": ["Beton İşleri", "Demir İşleri", "Sıva İşleri", "Boyama İşleri", "Elektrik İşleri", "Tesisat İşleri", "Yalıtım İşleri"],
                "aciklama": "200m² villa için standart iş kalemleri"
            },
            "Ticari Bina Standart": {
                "kategoriler": ["Beton İşleri", "Demir İşleri", "Sıva İşleri", "Boyama İşleri", "Elektrik İşleri", "Tesisat İşleri", "Asma Tavan İşleri"],
                "aciklama": "Ticari bina için standart iş kalemleri"
            },
            "Altyapı İşleri": {
                "kategoriler": ["Toprak İşleri", "Beton İşleri", "Demir İşleri", "Yol İşleri"],
                "aciklama": "Altyapı projeleri için temel iş kalemleri"
            }
        }
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Hazır Şablonlardan Oluştur")
        dialog.setMinimumWidth(400)
        
        layout = QVBoxLayout(dialog)
        
        layout.addWidget(QLabel("Hazır şablon seçin:"))
        
        preset_combo = QComboBox()
        preset_combo.addItems(list(presets.keys()))
        layout.addWidget(preset_combo)
        
        desc_label = QLabel()
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
        
        def update_description():
            selected = preset_combo.currentText()
            desc_label.setText(f"Açıklama: {presets[selected]['aciklama']}")
        
        preset_combo.currentTextChanged.connect(update_description)
        update_description()
        
        layout.addWidget(QLabel("Şablon Adı:"))
        name_input = QLineEdit()
        layout.addWidget(name_input)
        
        # Butonlar
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("Oluştur")
        btn_cancel = QPushButton("İptal")
        btn_ok.clicked.connect(dialog.accept)
        btn_cancel.clicked.connect(dialog.reject)
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
        
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        
        selected_preset = preset_combo.currentText()
        template_name = name_input.text().strip() or selected_preset
        
        preset_data = presets[selected_preset]
        
        # Şablon oluştur
        template_id = self.db.create_template(template_name, preset_data['aciklama'])
        
        if not template_id:
            QMessageBox.critical(self, "Hata", "Şablon oluşturulurken bir hata oluştu")
            return
        
        # Kategorilerden kalemleri al ve ekle
        items = self.db.get_items_by_kategoriler(preset_data['kategoriler'])
        
        added_count = 0
        for item in items:
            birim_fiyat = item.get('birim_fiyat', 0) or 0
            self.db.add_template_item(
                sablon_id=template_id,
                poz_no=item.get('poz_no', ''),
                tanim=item.get('tanim', ''),
                kategori=item.get('kategori', ''),
                miktar=0,
                birim=item.get('birim', ''),
                birim_fiyat=birim_fiyat,
                toplam=0
            )
            added_count += 1
        
        QMessageBox.information(
            self, "Başarılı",
            f"Hazır şablondan şablon oluşturuldu!\n\n"
            f"Şablon adı: {template_name}\n"
            f"Eklenen kalem sayısı: {added_count}"
        )
        self.load_templates()
        self.statusBar().showMessage(f"Hazır şablondan şablon oluşturuldu: {template_name}")
    
    def edit_template(self) -> None:
        """Şablon bilgilerini düzenle"""
        current_row = self.template_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Uyarı", "Lütfen düzenlemek istediğiniz şablonu seçin")
            return
        
        template_item = self.template_table.item(current_row, 0)
        if not template_item:
            return
        
        template_id = template_item.data(Qt.ItemDataRole.UserRole)
        if not template_id:
            return
        
        template = self.db.get_template(template_id)
        if not template:
            QMessageBox.warning(self, "Uyarı", "Şablon bulunamadı")
            return
        
        from PyQt6.QtWidgets import QInputDialog
        
        new_name, ok1 = QInputDialog.getText(
            self, "Şablon Adını Düzenle",
            "Yeni şablon adı:",
            text=template.get('ad', '')
        )
        
        if not ok1:
            return
        
        new_description, ok2 = QInputDialog.getText(
            self, "Şablon Açıklamasını Düzenle",
            "Yeni açıklama:",
            text=template.get('aciklama', '')
        )
        
        if not ok2:
            return
        
        if self.db.update_template(template_id, ad=new_name.strip(), aciklama=new_description.strip()):
            QMessageBox.information(self, "Başarılı", "Şablon güncellendi")
            self.load_templates()
            self.statusBar().showMessage("Şablon güncellendi")
        else:
            QMessageBox.critical(self, "Hata", "Şablon güncellenirken bir hata oluştu")
    
    def copy_template(self) -> None:
        """Şablonu kopyala"""
        current_row = self.template_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Uyarı", "Lütfen kopyalamak istediğiniz şablonu seçin")
            return
        
        template_item = self.template_table.item(current_row, 0)
        if not template_item:
            return
        
        template_id = template_item.data(Qt.ItemDataRole.UserRole)
        template_name = template_item.text()
        
        if not template_id:
            return
        
        from PyQt6.QtWidgets import QInputDialog
        
        new_name, ok1 = QInputDialog.getText(
            self, "Şablon Kopyala",
            f"Yeni şablon adı:\n(Orjinal: {template_name})",
            text=f"{template_name} (Kopya)"
        )
        
        if not ok1 or not new_name.strip():
            return
        
        new_description, ok2 = QInputDialog.getText(
            self, "Şablon Açıklaması",
            "Yeni açıklama (isteğe bağlı):"
        )
        
        if not ok2:
            return
        
        new_template_id = self.db.copy_template(template_id, new_name.strip(), new_description.strip())
        
        if new_template_id:
            items_count = len(self.db.get_template_items(new_template_id))
            QMessageBox.information(
                self, "Başarılı",
                f"Şablon başarıyla kopyalandı!\n\n"
                f"Yeni şablon adı: {new_name}\n"
                f"Kalem sayısı: {items_count}"
            )
            self.load_templates()
            self.statusBar().showMessage(f"Şablon kopyalandı: {new_name}")
        else:
            QMessageBox.critical(self, "Hata", "Şablon kopyalanırken bir hata oluştu")
    
    def add_template_item(self) -> None:
        """Şablona kalem ekle"""
        if not self.current_template_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce bir şablon seçin")
            return
        
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout, QDoubleSpinBox, QComboBox
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Şablona Kalem Ekle")
        dialog.setMinimumWidth(500)
        
        layout = QVBoxLayout(dialog)
        
        # Poz No
        layout.addWidget(QLabel("Poz No:"))
        poz_no_input = QLineEdit()
        layout.addWidget(poz_no_input)
        
        # Tanım
        layout.addWidget(QLabel("Tanım:"))
        tanim_input = QLineEdit()
        layout.addWidget(tanim_input)
        
        # Kategori
        layout.addWidget(QLabel("Kategori:"))
        kategori_input = QLineEdit()
        layout.addWidget(kategori_input)
        
        # Miktar
        layout.addWidget(QLabel("Miktar:"))
        miktar_input = QDoubleSpinBox()
        miktar_input.setMinimum(0)
        miktar_input.setMaximum(999999)
        miktar_input.setDecimals(2)
        layout.addWidget(miktar_input)
        
        # Birim
        layout.addWidget(QLabel("Birim:"))
        birim_input = QComboBox()
        birim_input.setEditable(True)
        birim_input.addItems(["m²", "m³", "m", "kg", "adet", "ton", "lt"])
        layout.addWidget(birim_input)
        
        # Birim Fiyat
        layout.addWidget(QLabel("Birim Fiyat:"))
        birim_fiyat_input = QDoubleSpinBox()
        birim_fiyat_input.setMinimum(0)
        birim_fiyat_input.setMaximum(999999)
        birim_fiyat_input.setDecimals(2)
        layout.addWidget(birim_fiyat_input)
        
        # Butonlar
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("Ekle")
        btn_cancel = QPushButton("İptal")
        
        def calculate_and_add():
            miktar = miktar_input.value()
            birim_fiyat = birim_fiyat_input.value()
            toplam = miktar * birim_fiyat
            
            if not tanim_input.text().strip():
                QMessageBox.warning(dialog, "Uyarı", "Tanım boş olamaz")
                return
            
            item_id = self.db.add_template_item(
                sablon_id=self.current_template_id,
                poz_no=poz_no_input.text().strip(),
                tanim=tanim_input.text().strip(),
                kategori=kategori_input.text().strip(),
                miktar=miktar,
                birim=birim_input.currentText().strip(),
                birim_fiyat=birim_fiyat,
                toplam=toplam
            )
            
            if item_id:
                QMessageBox.information(dialog, "Başarılı", "Kalem eklendi")
                dialog.accept()
                # Şablon kalemlerini yenile
                template_item = self.template_table.item(self.template_table.currentRow(), 0)
                if template_item:
                    self.view_template_items(template_item)
                self.load_templates()
            else:
                QMessageBox.critical(dialog, "Hata", "Kalem eklenirken bir hata oluştu")
        
        btn_ok.clicked.connect(calculate_and_add)
        btn_cancel.clicked.connect(dialog.reject)
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
        
        dialog.exec()
    
    def edit_template_item(self) -> None:
        """Şablon kalemini düzenle"""
        if not self.current_template_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce bir şablon seçin")
            return
        
        current_row = self.template_items_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Uyarı", "Lütfen düzenlemek istediğiniz kalemi seçin")
            return
        
        id_item = self.template_items_table.item(current_row, 0)
        if not id_item:
            return
        
        item_id = id_item.data(Qt.ItemDataRole.UserRole)
        if not item_id:
            return
        
        item = self.db.get_template_item(item_id)
        if not item:
            QMessageBox.warning(self, "Uyarı", "Kalem bulunamadı")
            return
        
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout, QDoubleSpinBox, QComboBox
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Şablon Kalemini Düzenle")
        dialog.setMinimumWidth(500)
        
        layout = QVBoxLayout(dialog)
        
        # Poz No
        layout.addWidget(QLabel("Poz No:"))
        poz_no_input = QLineEdit(item.get('poz_no', ''))
        layout.addWidget(poz_no_input)
        
        # Tanım
        layout.addWidget(QLabel("Tanım:"))
        tanim_input = QLineEdit(item.get('tanim', ''))
        layout.addWidget(tanim_input)
        
        # Kategori
        layout.addWidget(QLabel("Kategori:"))
        kategori_input = QLineEdit(item.get('kategori', ''))
        layout.addWidget(kategori_input)
        
        # Miktar
        layout.addWidget(QLabel("Miktar:"))
        miktar_input = QDoubleSpinBox()
        miktar_input.setMinimum(0)
        miktar_input.setMaximum(999999)
        miktar_input.setDecimals(2)
        miktar_input.setValue(item.get('miktar', 0))
        layout.addWidget(miktar_input)
        
        # Birim
        layout.addWidget(QLabel("Birim:"))
        birim_input = QComboBox()
        birim_input.setEditable(True)
        birim_input.addItems(["m²", "m³", "m", "kg", "adet", "ton", "lt"])
        birim_input.setCurrentText(item.get('birim', ''))
        layout.addWidget(birim_input)
        
        # Birim Fiyat
        layout.addWidget(QLabel("Birim Fiyat:"))
        birim_fiyat_input = QDoubleSpinBox()
        birim_fiyat_input.setMinimum(0)
        birim_fiyat_input.setMaximum(999999)
        birim_fiyat_input.setDecimals(2)
        birim_fiyat_input.setValue(item.get('birim_fiyat', 0))
        layout.addWidget(birim_fiyat_input)
        
        # Butonlar
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("Kaydet")
        btn_cancel = QPushButton("İptal")
        
        def calculate_and_save():
            miktar = miktar_input.value()
            birim_fiyat = birim_fiyat_input.value()
            toplam = miktar * birim_fiyat
            
            if not tanim_input.text().strip():
                QMessageBox.warning(dialog, "Uyarı", "Tanım boş olamaz")
                return
            
            if self.db.update_template_item(
                item_id,
                poz_no=poz_no_input.text().strip(),
                tanim=tanim_input.text().strip(),
                kategori=kategori_input.text().strip(),
                miktar=miktar,
                birim=birim_input.currentText().strip(),
                birim_fiyat=birim_fiyat,
                toplam=toplam
            ):
                QMessageBox.information(dialog, "Başarılı", "Kalem güncellendi")
                dialog.accept()
                # Şablon kalemlerini yenile
                template_item = self.template_table.item(self.template_table.currentRow(), 0)
                if template_item:
                    self.view_template_items(template_item)
            else:
                QMessageBox.critical(dialog, "Hata", "Kalem güncellenirken bir hata oluştu")
        
        btn_ok.clicked.connect(calculate_and_save)
        btn_cancel.clicked.connect(dialog.reject)
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
        
        dialog.exec()
    
    def delete_template_item(self) -> None:
        """Şablon kalemini sil"""
        if not self.current_template_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce bir şablon seçin")
            return
        
        current_row = self.template_items_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Uyarı", "Lütfen silmek istediğiniz kalemi seçin")
            return
        
        id_item = self.template_items_table.item(current_row, 0)
        if not id_item:
            return
        
        item_id = id_item.data(Qt.ItemDataRole.UserRole)
        tanim = self.template_items_table.item(current_row, 2).text()
        
        if not item_id:
            return
        
        reply = QMessageBox.question(
            self, "Kalem Sil",
            f"'{tanim}' kalemini silmek istediğinize emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if self.db.delete_template_item(item_id):
                QMessageBox.information(self, "Başarılı", "Kalem silindi")
                # Şablon kalemlerini yenile
                template_item = self.template_table.item(self.template_table.currentRow(), 0)
                if template_item:
                    self.view_template_items(template_item)
                self.load_templates()
            else:
                QMessageBox.critical(self, "Hata", "Kalem silinirken bir hata oluştu")
    
    def load_ihaleler(self) -> None:
        """İhaleleri yükle"""
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()  # UI'ı güncelle
        
        ihaleler = self.db.get_all_ihaleler()
        self.ihale_combo.clear()
        self.ihale_combo.addItem("-- İhale Seçin --", None)
        for ihale in ihaleler:
            self.ihale_combo.addItem(ihale['ad'], ihale['id'])
            QApplication.processEvents()  # UI'ı güncelle
    
    def on_ihale_changed(self) -> None:
        """İhale seçildiğinde"""
        ihale_id = self.ihale_combo.currentData()
        self.current_ihale_id = ihale_id
        if ihale_id:
            if hasattr(self, 'ihale_total_label'):
                self.ihale_total_label.setText("Toplam (KDV Hariç): 0.00 ₺")
                if hasattr(self, 'ihale_total_kdv_label'):
                    self.ihale_total_kdv_label.setText("Toplam (KDV Dahil): 0.00 ₺")
            self.load_ihale_kalemleri()
        else:
            self.ihale_kalem_table.setRowCount(0)
            self.ihale_total_label.setText("Toplam: 0.00 ₺")
    
    def new_ihale(self) -> None:
        """Yeni ihale oluştur"""
        from PyQt6.QtWidgets import QInputDialog
        
        ad, ok1 = QInputDialog.getText(self, "Yeni İhale", "İhale adı:")
        if not ok1 or not ad.strip():
            return
        
        aciklama, ok2 = QInputDialog.getText(self, "İhale Açıklaması", "Açıklama (isteğe bağlı):")
        if not ok2:
            return
        
        ihale_id = self.db.create_ihale(ad.strip(), aciklama.strip())
        if ihale_id:
            self.load_ihaleler()
            # Yeni oluşturulan ihale seçili olsun
            index = self.ihale_combo.findData(ihale_id)
            if index >= 0:
                self.ihale_combo.setCurrentIndex(index)
            QMessageBox.information(self, "Başarılı", "İhale oluşturuldu")
            self.statusBar().showMessage(f"İhale oluşturuldu: {ad}")
    
    def on_ihale_poz_search(self) -> None:
        """Poz arama metni değiştiğinde"""
        # Tablo widget'ı henüz oluşturulmamışsa (lazy loading) işlem yapma
        if not hasattr(self, 'ihale_poz_results_table'):
            print("DEBUG: ihale_poz_results_table henüz oluşturulmamış")
            return
        
        if not self._tabs_created.get('ihale', False):
            print("DEBUG: İhale sekmesi henüz oluşturulmamış")
            return
        
        search_text = self.ihale_poz_search.text().strip()
        
        # Minimum 1 karakter yeterli olsun (poz numarası tek karakter olabilir)
        if len(search_text) < 1:
            self.ihale_poz_results_table.setRowCount(0)
            return
        
        try:
            # Önce pozları ara
            print(f"DEBUG: Arama yapılıyor: '{search_text}'")
            pozlar = self.db.search_pozlar(search_text, limit=50)
            print(f"DEBUG: {len(pozlar)} poz bulundu")
            
            # Sonuçları göster
            self.ihale_poz_results_table.setRowCount(len(pozlar))
            
            if len(pozlar) == 0:
                # Sonuç yoksa kullanıcıya bilgi ver ve manuel ekleme seçeneği sun
                self.statusBar().showMessage(f"'{search_text}' için poz bulunamadı. Manuel eklemek için 'Listeye Ekle' butonuna tıklayın.", 5000)
                
                # Eğer arama metni poz numarası formatındaysa (nokta içeriyorsa), 
                # manuel olarak eklenebilir şekilde tabloya tek satır ekle
                if '.' in search_text and len(search_text) > 3:
                    # Poz numarası formatında görünüyor, manuel ekleme için göster
                    self.ihale_poz_results_table.setRowCount(1)
                    poz_no_item = QTableWidgetItem(search_text)
                    self.ihale_poz_results_table.setItem(0, 0, poz_no_item)
                    self.ihale_poz_results_table.setItem(0, 1, QTableWidgetItem("(Manuel ekleme - Poz bulunamadı)"))
                    self.ihale_poz_results_table.setItem(0, 2, QTableWidgetItem(""))
                    self.ihale_poz_results_table.setItem(0, 3, QTableWidgetItem("Fiyat yok"))
                    
                    # Poz bilgisini sakla (sadece poz_no ile)
                    poz_data = {
                        'poz_no': search_text,
                        'tanim': '',
                        'birim': '',
                        'kategori': ''
                    }
                    poz_no_item.setData(Qt.ItemDataRole.UserRole, poz_data)
            else:
                self.statusBar().showMessage(f"{len(pozlar)} poz bulundu", 2000)
            
            for row, poz in enumerate(pozlar):
                poz_no = poz.get('poz_no', '')
                poz_tanim = poz.get('tanim', '')
                birim = poz.get('birim', '')
                kategori = poz.get('kategori', '')
                
                # Poz no
                poz_no_item = QTableWidgetItem(poz_no)
                self.ihale_poz_results_table.setItem(row, 0, poz_no_item)
                
                # Tanım
                self.ihale_poz_results_table.setItem(row, 1, QTableWidgetItem(poz_tanim))
                
                # Birim
                self.ihale_poz_results_table.setItem(row, 2, QTableWidgetItem(birim))
                
                # Birim fiyatı getir
                fiyat_data = self.db.get_birim_fiyat(poz_no=poz_no)
                birim_fiyat = fiyat_data.get('birim_fiyat', 0) if fiyat_data else 0
                self.ihale_poz_results_table.setItem(row, 3, QTableWidgetItem(f"{birim_fiyat:,.2f} ₺" if birim_fiyat else "Fiyat yok"))
                
                # Poz bilgisini sakla (tüm bilgileri içeren dict)
                poz_data = {
                    'poz_no': poz_no,
                    'tanim': poz_tanim,
                    'birim': birim,
                    'kategori': kategori
                }
                poz_no_item.setData(Qt.ItemDataRole.UserRole, poz_data)
            
            # Tabloyu güncelle ve görünür yap
            self.ihale_poz_results_table.resizeColumnsToContents()
            self.ihale_poz_results_table.setVisible(True)
            self.ihale_poz_results_table.update()  # Tabloyu yeniden çiz
            
        except Exception as e:
            error_msg = f"Poz arama sırasında hata oluştu:\n{str(e)}"
            QMessageBox.critical(self, "Hata", error_msg)
            self.statusBar().showMessage(f"Hata: {str(e)}", 5000)
            import traceback
            traceback.print_exc()
    
    def add_selected_poz_to_ihale(self, item: QTableWidgetItem) -> None:
        """Seçili pozu ihale listesine ekle (çift tıklama)"""
        if not self.current_ihale_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce bir ihale seçin")
            return
        
        row = item.row()
        poz_item = self.ihale_poz_results_table.item(row, 0)
        if not poz_item:
            QMessageBox.warning(self, "Uyarı", "Poz bilgisi bulunamadı")
            return
        
        poz_data = poz_item.data(Qt.ItemDataRole.UserRole)
        if not poz_data:
            # Poz data yoksa, tablodan manuel olarak al
            poz_no = poz_item.text()
            poz_tanim_item = self.ihale_poz_results_table.item(row, 1)
            poz_tanim = poz_tanim_item.text() if poz_tanim_item else ""
            birim_item = self.ihale_poz_results_table.item(row, 2)
            birim = birim_item.text() if birim_item else ""
            
            # Poz bilgilerini veritabanından getir
            poz = self.db.get_poz_by_no(poz_no)
            if not poz:
                QMessageBox.warning(self, "Uyarı", f"Poz bulunamadı: {poz_no}")
                return
            
            poz_data = {
                'poz_no': poz_no,
                'tanim': poz_tanim or poz.get('tanim', ''),
                'kategori': poz.get('kategori', ''),
                'birim': birim or poz.get('birim', '')
            }
        
        try:
            self._add_poz_to_ihale_list(poz_data)
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Poz eklenirken hata oluştu:\n{str(e)}")
            import traceback
            traceback.print_exc()
    
    def add_poz_to_ihale(self) -> None:
        """Arama sonuçlarından seçili pozu ekle"""
        if not self.current_ihale_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce bir ihale seçin")
            return
        
        current_row = self.ihale_poz_results_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Uyarı", "Lütfen bir poz seçin")
            return
        
        poz_item = self.ihale_poz_results_table.item(current_row, 0)
        if not poz_item:
            QMessageBox.warning(self, "Uyarı", "Poz bilgisi bulunamadı")
            return
        
        poz_data = poz_item.data(Qt.ItemDataRole.UserRole)
        if not poz_data:
            # Poz data yoksa, tablodan manuel olarak al
            poz_no = poz_item.text()
            poz_tanim_item = self.ihale_poz_results_table.item(current_row, 1)
            poz_tanim = poz_tanim_item.text() if poz_tanim_item else ""
            birim_item = self.ihale_poz_results_table.item(current_row, 2)
            birim = birim_item.text() if birim_item else ""
            
            # Poz bilgilerini veritabanından getir (yoksa manuel ekleme yapılacak)
            poz = self.db.get_poz_by_no(poz_no)
            if poz:
                # Poz bulundu, bilgileri kullan
                poz_data = {
                    'poz_no': poz_no,
                    'tanim': poz_tanim or poz.get('tanim', ''),
                    'kategori': poz.get('kategori', ''),
                    'birim': birim or poz.get('birim', '')
                }
            else:
                # Poz bulunamadı, manuel ekleme için sadece poz_no ile devam et
                poz_data = {
                    'poz_no': poz_no,
                    'tanim': poz_tanim,
                    'kategori': '',
                    'birim': birim
                }
        
        try:
            self._add_poz_to_ihale_list(poz_data)
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Poz eklenirken hata oluştu:\n{str(e)}")
            import traceback
            traceback.print_exc()
    
    def _add_poz_to_ihale_list(self, poz_data: Dict[str, Any]) -> None:
        """Pozu ihale listesine ekle (iç fonksiyon)"""
        try:
            poz_no = poz_data.get('poz_no', '')
            if not poz_no:
                QMessageBox.warning(self, "Uyarı", "Poz numarası bulunamadı")
                return
            
            poz_tanim = poz_data.get('tanim', '')
            kategori = poz_data.get('kategori', '')
            birim = poz_data.get('birim', '')
            
            # Eğer poz veritabanında yoksa, veritabanından tekrar kontrol et
            if not poz_tanim or poz_tanim == "(Manuel ekleme - Poz bulunamadı)":
                poz = self.db.get_poz_by_no(poz_no)
                if poz:
                    poz_tanim = poz.get('tanim', '')
                    birim = poz.get('birim', '') if not birim else birim
                    kategori = poz.get('kategori', '') if not kategori else kategori
                else:
                    # Poz veritabanında yok, kullanıcıdan bilgi al
                    from PyQt6.QtWidgets import QInputDialog
                    tanim, ok = QInputDialog.getText(
                        self, "Poz Bilgisi",
                        f"Poz '{poz_no}' veritabanında bulunamadı.\n\nLütfen poz tanımını girin:",
                        text=""
                    )
                    if not ok or not tanim.strip():
                        return
                    poz_tanim = tanim.strip()
                    
                    # Birim seçimi
                    birim_text, ok = QInputDialog.getText(
                        self, "Birim",
                        "Birim (m², m³, kg, adet, vb.):",
                        text="m²"
                    )
                    if not ok:
                        birim_text = "m²"
                    birim = birim_text.strip() if birim_text.strip() else "m²"
            
            # Birim fiyatı getir (otomatik) - önce aktif, sonra herhangi bir fiyat
            fiyat_data = self.db.get_birim_fiyat(poz_no=poz_no, aktif_only=True)
            if not fiyat_data or not fiyat_data.get('birim_fiyat'):
                # Aktif fiyat yoksa, aktif olmayan fiyatları da kontrol et
                fiyat_data = self.db.get_birim_fiyat(poz_no=poz_no, aktif_only=False)
            birim_fiyat = fiyat_data.get('birim_fiyat', 0) if fiyat_data else 0
            
            # Eğer hala 0 ise, poz'un resmi_fiyat'ını kontrol et
            if birim_fiyat == 0:
                poz_data = self.db.get_poz_by_no(poz_no)
                if poz_data and poz_data.get('resmi_fiyat'):
                    birim_fiyat = poz_data.get('resmi_fiyat', 0)
            
            # İhale kalemine ekle (birim miktar 0, kullanıcı girecek)
            kalem_id = self.db.add_ihale_kalem(
                ihale_id=self.current_ihale_id,
                poz_no=poz_no,
                poz_tanim=poz_tanim,
                kategori=kategori,
                birim_miktar=0,  # Kullanıcı girecek
                birim=birim,
                birim_fiyat=birim_fiyat,
                toplam=0
            )
            
            if kalem_id:
                # Tabloyu yeniden yükleme - kullanıcının düzenlemelerini kaybetmemek için
                # Sadece yeni eklenen satırı ekle, tüm tabloyu yeniden yükleme
                self.statusBar().showMessage(f"Poz eklendi: {poz_no}")
                QMessageBox.information(self, "Başarılı", f"Poz başarıyla eklendi:\n{poz_no} - {poz_tanim}")
                # Tabloyu yeniden yükle (sadece yeni ekleme sonrası)
                self.load_ihale_kalemleri()
            else:
                QMessageBox.warning(self, "Uyarı", "Poz eklenirken bir hata oluştu")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Poz eklenirken hata oluştu:\n{str(e)}")
            import traceback
            traceback.print_exc()
    
    def load_ihale_kalemleri(self) -> None:
        """İhale kalemlerini yükle"""
        # Lazy loading kontrolü - sekme henüz oluşturulmamışsa çık
        if not hasattr(self, 'ihale_kalem_table') or not self._tabs_created.get('ihale', False):
            return
        
        if not self.current_ihale_id:
            try:
                self.ihale_kalem_table.setRowCount(0)
            except:
                pass
            return
        
        try:
            import re
            # itemChanged sinyalini blokla (tablo yüklenirken sinyal tetiklenmesin)
            self.ihale_kalem_table.blockSignals(True)
            try:
                kalemler = self.db.get_ihale_kalemleri(self.current_ihale_id)
                self.ihale_kalem_table.setRowCount(len(kalemler))
                
                toplam = 0.0
                
                for row, kalem in enumerate(kalemler):
                    # Sıra (düzenlenemez)
                    sira_item = QTableWidgetItem(str(kalem.get('sira_no', row + 1)))
                    sira_item.setFlags(sira_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.ihale_kalem_table.setItem(row, 0, sira_item)
                    
                    # Poz No (düzenlenemez)
                    poz_no_item = QTableWidgetItem(kalem.get('poz_no', ''))
                    poz_no_item.setFlags(poz_no_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.ihale_kalem_table.setItem(row, 1, poz_no_item)
                    
                    # Tanım (temizle - fiyat bilgisi varsa çıkar, düzenlenebilir)
                    poz_tanim = str(kalem.get('poz_tanim', '')).strip()
                    # "Sa 250,00" veya "Sa 250.00" gibi pattern'leri temizle
                    poz_tanim = re.sub(r'\s*Sa\s*\d+[.,]\d+', '', poz_tanim).strip()
                    tanim_item = QTableWidgetItem(poz_tanim)
                    # Tanım düzenlenebilir yapıldı
                    # Tam metni tooltip olarak ekle (tüm metin görünsün)
                    tanim_item.setToolTip(poz_tanim)
                    # Word wrap özelliği için hizalama
                    tanim_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
                    self.ihale_kalem_table.setItem(row, 2, tanim_item)
                    # Satır yüksekliğini otomatik ayarla (uzun metinler için)
                    if len(poz_tanim) > 80:
                        # Uzun metinler için satır yüksekliğini artır
                        self.ihale_kalem_table.setRowHeight(row, max(40, min(100, len(poz_tanim) // 40 * 20)))
                    # Satır yüksekliğini otomatik ayarla (uzun metinler için)
                    if len(poz_tanim) > 80:
                        # Uzun metinler için satır yüksekliğini artır
                        self.ihale_kalem_table.setRowHeight(row, max(40, min(100, len(poz_tanim) // 40 * 20)))
                    
                    # Birim Miktar (düzenlenebilir) - 0 ise boş göster
                    birim_miktar = kalem.get('birim_miktar', 0) or 0
                    # Eğer birim_miktar None veya 0 ise, tablodan oku (kullanıcı yazmış olabilir)
                    if birim_miktar == 0:
                        # Tablodan oku (eğer kullanıcı yazdıysa)
                        existing_item = self.ihale_kalem_table.item(row, 3)
                        if existing_item and existing_item.text().strip():
                            try:
                                miktar_text_existing = existing_item.text().replace(",", ".").strip()
                                birim_miktar = float(miktar_text_existing) if miktar_text_existing else 0.0
                            except:
                                pass
                    miktar_text = f"{birim_miktar:,.2f}" if birim_miktar > 0 else ""
                    miktar_item = QTableWidgetItem(miktar_text)
                    miktar_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    # Font'u büyüt ve kalın yap
                    font = miktar_item.font()
                    font.setPointSize(font.pointSize() + 2)  # 2 punto büyüt
                    font.setBold(True)  # Kalın yap
                    miktar_item.setFont(font)
                    self.ihale_kalem_table.setItem(row, 3, miktar_item)
                    
                    # Birim (düzenlenebilir)
                    birim_item = QTableWidgetItem(kalem.get('birim', ''))
                    birim_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
                    self.ihale_kalem_table.setItem(row, 4, birim_item)
                    
                    # Birim Fiyat (düzenlenebilir)
                    birim_fiyat = kalem.get('birim_fiyat', 0) or 0
                    # Eğer ihale_kalemleri tablosunda birim_fiyat 0 ise, birim_fiyatlar tablosundan al
                    if birim_fiyat == 0:
                        poz_no = kalem.get('poz_no', '')
                        if poz_no:
                            fiyat_data = self.db.get_birim_fiyat(poz_no=poz_no, aktif_only=False)
                            if fiyat_data and fiyat_data.get('birim_fiyat'):
                                birim_fiyat = fiyat_data.get('birim_fiyat', 0)
                                # İhale kalemindeki birim fiyatı güncelle
                                kalem_id = kalem.get('id')
                                if kalem_id:
                                    self.db.update_ihale_kalem(kalem_id, birim_fiyat=birim_fiyat)
                            else:
                                # Poz'un resmi_fiyat'ını kontrol et
                                poz_data = self.db.get_poz_by_no(poz_no)
                                if poz_data and poz_data.get('resmi_fiyat'):
                                    birim_fiyat = poz_data.get('resmi_fiyat', 0)
                                    kalem_id = kalem.get('id')
                                    if kalem_id:
                                        self.db.update_ihale_kalem(kalem_id, birim_fiyat=birim_fiyat)
                    
                    fiyat_item = QTableWidgetItem(f"{birim_fiyat:,.2f}")
                    fiyat_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    self.ihale_kalem_table.setItem(row, 5, fiyat_item)
                    
                    # Toplam (hesaplanır, düzenlenemez) - HER ZAMAN birim miktar ve birim fiyattan hesapla
                    # ÖNEMLİ: Tabloda görünen değerleri kullan (kullanıcı yazmış olabilir)
                    # Tablodan birim miktar ve birim fiyatı oku
                    miktar_item_tablo = self.ihale_kalem_table.item(row, 3)
                    fiyat_item_tablo = self.ihale_kalem_table.item(row, 5)
                    
                    birim_miktar_hesap = birim_miktar
                    birim_fiyat_hesap = birim_fiyat
                    
                    # Eğer tabloda değerler varsa onları kullan
                    if miktar_item_tablo and miktar_item_tablo.text().strip():
                        try:
                            miktar_text_tablo = miktar_item_tablo.text().strip()
                            # Türkçe ve İngilizce format desteği
                            miktar_text_tablo = miktar_text_tablo.replace(" ", "")
                            if ',' in miktar_text_tablo and '.' in miktar_text_tablo:
                                last_dot = miktar_text_tablo.rfind('.')
                                last_comma = miktar_text_tablo.rfind(',')
                                if last_dot > last_comma:
                                    birim_miktar_hesap = float(miktar_text_tablo.replace(',', ''))
                                else:
                                    birim_miktar_hesap = float(miktar_text_tablo.replace('.', '').replace(',', '.'))
                            elif ',' in miktar_text_tablo:
                                birim_miktar_hesap = float(miktar_text_tablo.replace(',', '.'))
                            else:
                                birim_miktar_hesap = float(miktar_text_tablo.replace(',', '.'))
                        except:
                            pass
                    
                    if fiyat_item_tablo and fiyat_item_tablo.text().strip():
                        try:
                            fiyat_text_tablo = fiyat_item_tablo.text().replace("₺", "").strip()
                            # Türkçe ve İngilizce format desteği
                            fiyat_text_tablo = fiyat_text_tablo.replace(" ", "")
                            if ',' in fiyat_text_tablo and '.' in fiyat_text_tablo:
                                last_dot = fiyat_text_tablo.rfind('.')
                                last_comma = fiyat_text_tablo.rfind(',')
                                if last_dot > last_comma:
                                    birim_fiyat_hesap = float(fiyat_text_tablo.replace(',', ''))
                                else:
                                    birim_fiyat_hesap = float(fiyat_text_tablo.replace('.', '').replace(',', '.'))
                            elif ',' in fiyat_text_tablo:
                                birim_fiyat_hesap = float(fiyat_text_tablo.replace(',', '.'))
                            else:
                                birim_fiyat_hesap = float(fiyat_text_tablo.replace(',', '.'))
                        except:
                            pass
                    
                    # Toplamı hesapla
                    toplam_deger = birim_miktar_hesap * birim_fiyat_hesap
                    
                    # Veritabanını güncelle
                    kalem_id = kalem.get('id')
                    if kalem_id:
                        # Veritabanındaki toplam ile hesaplanan toplam farklıysa güncelle
                        db_toplam = kalem.get('toplam', 0) or 0
                        if abs(db_toplam - toplam_deger) > 0.01:
                            self.db.update_ihale_kalem(kalem_id, birim_miktar=birim_miktar_hesap, birim_fiyat=birim_fiyat_hesap, toplam=toplam_deger)
                    
                    toplam += toplam_deger
                    toplam_item = QTableWidgetItem(f"{toplam_deger:,.2f} ₺")
                    toplam_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    toplam_item.setFlags(toplam_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.ihale_kalem_table.setItem(row, 6, toplam_item)
                    
                    # ID'yi sakla
                    item = self.ihale_kalem_table.item(row, 0)
                    if item:
                        item.setData(Qt.ItemDataRole.UserRole, kalem.get('id'))
                
                if hasattr(self, 'ihale_total_label'):
                    # KDV hesaplama
                    kdv_rate_text = self.ihale_kdv_rate.currentText().replace("%", "")
                    kdv_rate = float(kdv_rate_text)
                    kdv_hesap = self.calculator.calculate_with_kdv(toplam, kdv_rate)
                    
                    self.ihale_total_label.setText(f"Toplam (KDV Hariç): {toplam:,.2f} ₺")
                    self.ihale_total_kdv_label.setText(f"Toplam (KDV %{kdv_rate_text} Dahil): {kdv_hesap['kdv_dahil']:,.2f} ₺")
            finally:
                # Sinyali tekrar aç
                self.ihale_kalem_table.blockSignals(False)
        except Exception as e:
            print(f"İhale kalemleri yükleme hatası: {e}")
            import traceback
            traceback.print_exc()
            # Hata olsa bile tabloyu temizle
            try:
                self.ihale_kalem_table.blockSignals(True)
                self.ihale_kalem_table.setRowCount(0)
                self.ihale_kalem_table.blockSignals(False)
            except:
                pass
    
    def show_full_tanim(self, item: QTableWidgetItem) -> None:
        """Tanım sütununa çift tıklayınca tam metni göster"""
        # Sadece tanım sütunu (2) için işlem yap
        if item.column() != 2:
            return
        
        tanim_text = item.text()
        if not tanim_text:
            return
        
        # Dialog oluştur
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton
        dialog = QDialog(self)
        dialog.setWindowTitle("Tam Tanım")
        dialog.setMinimumWidth(700)
        dialog.setMinimumHeight(400)
        
        layout = QVBoxLayout(dialog)
        
        # Metin alanı
        text_edit = QTextEdit()
        text_edit.setPlainText(tanim_text)
        text_edit.setReadOnly(True)
        text_edit.setFont(QFont("Arial", 10))
        layout.addWidget(text_edit)
        
        # Kapat butonu
        btn_close = QPushButton("Kapat")
        btn_close.clicked.connect(dialog.close)
        layout.addWidget(btn_close)
        
        dialog.exec()
    
    def on_ihale_kalem_changed(self, item: QTableWidgetItem) -> None:
        """İhale kalemi değiştiğinde (tanım, birim miktar, birim veya birim fiyat)"""
        # Düzenlenebilir sütunlar (2: Tanım, 3: Birim Miktar, 4: Birim, 5: Birim Fiyat)
        if item.column() not in [2, 3, 4, 5]:
            return
        
        # Tanım değiştiyse sadece tanımı güncelle
        if item.column() == 2:
            row = item.row()
            kalem_id_item = self.ihale_kalem_table.item(row, 0)
        if not kalem_id_item:
            return
        
        kalem_id = kalem_id_item.data(Qt.ItemDataRole.UserRole)
        if not kalem_id:
            return
        
            yeni_tanim = item.text().strip()
            if yeni_tanim:
                self.db.update_ihale_kalem(kalem_id, poz_tanim=yeni_tanim)
                # Tooltip'i de güncelle
                item.setToolTip(yeni_tanim)
                # Satır yüksekliğini güncelle
                if len(yeni_tanim) > 80:
                    self.ihale_kalem_table.setRowHeight(row, max(40, min(100, len(yeni_tanim) // 40 * 20)))
            return
        
        row = item.row()
        kalem_id_item = self.ihale_kalem_table.item(row, 0)
        if not kalem_id_item:
            return
        
        kalem_id = kalem_id_item.data(Qt.ItemDataRole.UserRole)
        if not kalem_id:
            return
        
        # Birim miktar, birim ve birim fiyatı al
        miktar_item = self.ihale_kalem_table.item(row, 3)
        birim_item = self.ihale_kalem_table.item(row, 4)
        fiyat_item = self.ihale_kalem_table.item(row, 5)
        
        if not miktar_item or not birim_item or not fiyat_item:
            return
        
        # Birim miktar için font ayarlarını koru (büyük ve kalın)
        if item.column() == 3:
            # Mevcut font'u al ve ayarları koru
            font = miktar_item.font()
            if not font.bold() or font.pointSize() <= 10:
                font.setPointSize(font.pointSize() + 2)
                font.setBold(True)
                miktar_item.setFont(font)
        
        try:
            miktar_text = miktar_item.text().strip()
            birim_text = birim_item.text().strip()
            fiyat_text = fiyat_item.text().replace("₺", "").strip()
            
            # Birim miktar parse - Türkçe ve İngilizce format desteği
            birim_miktar = 0.0
            if miktar_text:
                try:
                    # Önce boşlukları temizle
                    miktar_text = miktar_text.replace(" ", "")
                    # Eğer hem virgül hem nokta varsa
                    if ',' in miktar_text and '.' in miktar_text:
                        # Son noktadan önceki kısmı kontrol et
                        last_dot = miktar_text.rfind('.')
                        last_comma = miktar_text.rfind(',')
                        if last_dot > last_comma:
                            # Nokta ondalık ayırıcı (İngilizce format: 1,234.56)
                            # Virgülleri kaldır, noktayı koru
                            birim_miktar = float(miktar_text.replace(',', ''))
                        else:
                            # Virgül ondalık ayırıcı (Türkçe format: 1.234,56)
                            # Noktaları kaldır, virgülü noktaya çevir
                            birim_miktar = float(miktar_text.replace('.', '').replace(',', '.'))
                    elif ',' in miktar_text:
                        # Sadece virgül var - Türkçe format (ondalık ayırıcı)
                        birim_miktar = float(miktar_text.replace(',', '.'))
                    elif '.' in miktar_text:
                        # Sadece nokta var - kontrol et
                        # Eğer birden fazla nokta varsa, son nokta ondalık, diğerleri binlik
                        dot_count = miktar_text.count('.')
                        if dot_count > 1:
                            # Son noktadan önceki noktaları kaldır
                            last_dot = miktar_text.rfind('.')
                            before_last = miktar_text[:last_dot].replace('.', '')
                            after_last = miktar_text[last_dot:]
                            birim_miktar = float(before_last + after_last)
                        else:
                            # Tek nokta - ondalık ayırıcı
                            birim_miktar = float(miktar_text)
                    else:
                        # Sadece sayı
                        birim_miktar = float(miktar_text)
                except (ValueError, AttributeError) as e:
                    print(f"Birim miktar parse hatası: {miktar_text} -> {e}")
                    birim_miktar = 0.0
            
            birim = birim_text if birim_text else ""
            
            # Birim fiyat parse - Türkçe ve İngilizce format desteği
            birim_fiyat = 0.0
            if fiyat_text:
                try:
                    # Önce boşlukları temizle
                    fiyat_text = fiyat_text.replace(" ", "")
                    # Eğer hem virgül hem nokta varsa
                    if ',' in fiyat_text and '.' in fiyat_text:
                        # Son noktadan önceki kısmı kontrol et
                        last_dot = fiyat_text.rfind('.')
                        last_comma = fiyat_text.rfind(',')
                        if last_dot > last_comma:
                            # Nokta ondalık ayırıcı (İngilizce format: 19,100.00)
                            # Virgülleri kaldır, noktayı koru
                            birim_fiyat = float(fiyat_text.replace(',', ''))
                        else:
                            # Virgül ondalık ayırıcı (Türkçe format: 19.100,00)
                            # Noktaları kaldır, virgülü noktaya çevir
                            birim_fiyat = float(fiyat_text.replace('.', '').replace(',', '.'))
                    elif ',' in fiyat_text:
                        # Sadece virgül var - Türkçe format (ondalık ayırıcı)
                        birim_fiyat = float(fiyat_text.replace(',', '.'))
                    elif '.' in fiyat_text:
                        # Sadece nokta var - kontrol et
                        # Eğer birden fazla nokta varsa, son nokta ondalık, diğerleri binlik
                        dot_count = fiyat_text.count('.')
                        if dot_count > 1:
                            # Son noktadan önceki noktaları kaldır
                            last_dot = fiyat_text.rfind('.')
                            before_last = fiyat_text[:last_dot].replace('.', '')
                            after_last = fiyat_text[last_dot:]
                            birim_fiyat = float(before_last + after_last)
                        else:
                            # Tek nokta - ondalık ayırıcı
                            birim_fiyat = float(fiyat_text)
                    else:
                        # Sadece sayı
                        birim_fiyat = float(fiyat_text)
                except (ValueError, AttributeError) as e:
                    print(f"Birim fiyat parse hatası: {fiyat_text} -> {e}")
                    birim_fiyat = 0.0
            
            # Toplam hesapla
            toplam = birim_miktar * birim_fiyat
            
            # Veritabanını güncelle
            success = self.db.update_ihale_kalem(kalem_id, birim_miktar=birim_miktar, birim=birim, birim_fiyat=birim_fiyat, toplam=toplam)
            
            if success:
                # itemChanged sinyalini blokla (sadece toplam sütununu güncellerken)
                self.ihale_kalem_table.blockSignals(True)
                try:
                    # Kullanıcının yazdığı değerleri KORU - hiçbir şey yapma
                    # Birim miktar, birim ve birim fiyat sütunları kullanıcının yazdığı gibi kalacak
                    
                    # Sadece toplam sütununu güncelle
                    toplam_item = QTableWidgetItem(f"{toplam:,.2f} ₺")
                    toplam_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    toplam_item.setFlags(toplam_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.ihale_kalem_table.setItem(row, 6, toplam_item)
                    
                    # Genel toplamı güncelle
                    self.update_ihale_total()
                finally:
                    # Sinyali tekrar aç
                    self.ihale_kalem_table.blockSignals(False)
            else:
                QMessageBox.warning(self, "Hata", "Veritabanı güncellemesi başarısız oldu")
            
        except ValueError:
            QMessageBox.warning(self, "Hata", "Geçersiz sayı formatı")
        except Exception as e:
            print(f"İhale kalemi güncelleme hatası: {e}")
            import traceback
            traceback.print_exc()
    
    def update_ihale_total(self) -> None:
        """İhale toplamını güncelle"""
        if not hasattr(self, 'ihale_kalem_table') or not hasattr(self, 'ihale_total_label'):
            return
        
        try:
            toplam = 0.0
            for row in range(self.ihale_kalem_table.rowCount()):
                    # Toplam sütunundan oku (6. sütun)
                    toplam_item = self.ihale_kalem_table.item(row, 6)
                    if toplam_item:
                        toplam_text = toplam_item.text().replace("₺", "").strip()
                        try:
                            # Türkçe ve İngilizce format desteği
                            toplam_text = toplam_text.replace(" ", "")
                            if ',' in toplam_text and '.' in toplam_text:
                                # Son noktadan önceki kısmı kontrol et
                                last_dot = toplam_text.rfind('.')
                                last_comma = toplam_text.rfind(',')
                                if last_dot > last_comma:
                                    # Nokta ondalık ayırıcı (İngilizce format: 19,100.00)
                                    toplam += float(toplam_text.replace(',', ''))
                                else:
                                    # Virgül ondalık ayırıcı (Türkçe format: 19.100,00)
                                    toplam += float(toplam_text.replace('.', '').replace(',', '.'))
                            elif ',' in toplam_text:
                                # Sadece virgül var - Türkçe format (ondalık ayırıcı)
                                toplam += float(toplam_text.replace(',', '.'))
                            elif '.' in toplam_text:
                                # Sadece nokta var - kontrol et
                                dot_count = toplam_text.count('.')
                                if dot_count > 1:
                                    # Son noktadan önceki noktaları kaldır
                                    last_dot = toplam_text.rfind('.')
                                    before_last = toplam_text[:last_dot].replace('.', '')
                                    after_last = toplam_text[last_dot:]
                                    toplam += float(before_last + after_last)
                                else:
                                    # Tek nokta - ondalık ayırıcı
                                    toplam += float(toplam_text)
                            else:
                                # Sadece sayı
                                toplam += float(toplam_text)
                        except (ValueError, AttributeError) as e:
                            print(f"Toplam parse hatası (satır {row}): {toplam_text} -> {e}")
                            # Alternatif: Birim miktar ve birim fiyattan hesapla
                            try:
                                miktar_item = self.ihale_kalem_table.item(row, 3)
                                fiyat_item = self.ihale_kalem_table.item(row, 5)
                                if miktar_item and fiyat_item:
                                    miktar_text = miktar_item.text().strip()
                                    fiyat_text = fiyat_item.text().replace("₺", "").strip()
                                    
                                    # Miktar parse
                                    miktar_val = 0.0
                                    if miktar_text:
                                        miktar_text = miktar_text.replace(" ", "")
                                        if ',' in miktar_text and '.' in miktar_text:
                                            last_dot = miktar_text.rfind('.')
                                            last_comma = miktar_text.rfind(',')
                                            if last_dot > last_comma:
                                                miktar_val = float(miktar_text.replace(',', ''))
                                            else:
                                                miktar_val = float(miktar_text.replace('.', '').replace(',', '.'))
                                        elif ',' in miktar_text:
                                            miktar_val = float(miktar_text.replace(',', '.'))
                                        else:
                                            miktar_val = float(miktar_text.replace(',', '.'))
                                    
                                    # Fiyat parse
                                    fiyat_val = 0.0
                                    if fiyat_text:
                                        fiyat_text = fiyat_text.replace(" ", "")
                                        if ',' in fiyat_text and '.' in fiyat_text:
                                            last_dot = fiyat_text.rfind('.')
                                            last_comma = fiyat_text.rfind(',')
                                            if last_dot > last_comma:
                                                fiyat_val = float(fiyat_text.replace(',', ''))
                                            else:
                                                fiyat_val = float(fiyat_text.replace('.', '').replace(',', '.'))
                                        elif ',' in fiyat_text:
                                            fiyat_val = float(fiyat_text.replace(',', '.'))
                                        else:
                                            fiyat_val = float(fiyat_text.replace(',', '.'))
                                    
                                    # Çarp ve ekle
                                    toplam += miktar_val * fiyat_val
                            except:
                                pass
            
            # KDV hesaplama
            kdv_rate_text = self.ihale_kdv_rate.currentText().replace("%", "")
            kdv_rate = float(kdv_rate_text)
            kdv_hesap = self.calculator.calculate_with_kdv(toplam, kdv_rate)
            
            self.ihale_total_label.setText(f"Toplam (KDV Hariç): {toplam:,.2f} ₺")
            self.ihale_total_kdv_label.setText(f"Toplam (KDV %{kdv_rate_text} Dahil): {kdv_hesap['kdv_dahil']:,.2f} ₺")
        except Exception as e:
            print(f"İhale toplam güncelleme hatası: {e}")
            import traceback
            traceback.print_exc()
    
    def edit_ihale_tanim(self) -> None:
        """Seçili kalemin tanımını düzelt"""
        current_row = self.ihale_kalem_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Uyarı", "Lütfen düzeltmek istediğiniz bir satırı seçin")
            return
        
        kalem_id_item = self.ihale_kalem_table.item(current_row, 0)
        if not kalem_id_item:
            return
        
        kalem_id = kalem_id_item.data(Qt.ItemDataRole.UserRole)
        if not kalem_id:
            return
        
        # Mevcut tanımı al
        tanim_item = self.ihale_kalem_table.item(current_row, 2)
        mevcut_tanim = tanim_item.text() if tanim_item else ""
        poz_no_item = self.ihale_kalem_table.item(current_row, 1)
        poz_no = poz_no_item.text() if poz_no_item else ""
        
        # Yeni tanım gir
        from PyQt6.QtWidgets import QInputDialog
        yeni_tanim, ok = QInputDialog.getMultiLineText(
            self,
            "Tanım Düzelt",
            f"Poz {poz_no} için yeni tanımı girin:",
            mevcut_tanim
        )
        
        if ok and yeni_tanim.strip():
            # Veritabanını güncelle
            success = self.db.update_ihale_kalem(kalem_id, poz_tanim=yeni_tanim.strip())
            if success:
                # Tabloyu güncelle
                tanim_item.setText(yeni_tanim.strip())
                tanim_item.setToolTip(yeni_tanim.strip())
                # Satır yüksekliğini güncelle
                if len(yeni_tanim.strip()) > 80:
                    self.ihale_kalem_table.setRowHeight(current_row, max(40, min(100, len(yeni_tanim.strip()) // 40 * 20)))
                QMessageBox.information(self, "Başarılı", f"Poz {poz_no} için tanım güncellendi")
            else:
                QMessageBox.warning(self, "Hata", "Tanım güncellenirken bir hata oluştu")
    
    def delete_ihale_kalem(self) -> None:
        """İhale kalemini sil"""
        if not self.current_ihale_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce bir ihale seçin")
            return
        
        current_row = self.ihale_kalem_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Uyarı", "Lütfen silmek istediğiniz kalemi seçin")
            return
        
        kalem_id_item = self.ihale_kalem_table.item(current_row, 0)
        if not kalem_id_item:
            return
        
        kalem_id = kalem_id_item.data(Qt.ItemDataRole.UserRole)
        poz_no = self.ihale_kalem_table.item(current_row, 1).text()
        
        reply = QMessageBox.question(
            self, "Kalem Sil",
            f"'{poz_no}' kalemini silmek istediğinize emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if self.db.delete_ihale_kalem(kalem_id):
                self.load_ihale_kalemleri()
                self.statusBar().showMessage("Kalem silindi")
    
    def export_ihale_pdf(self) -> None:
        """İhale dosyasını PDF olarak export et"""
        if not self.current_ihale_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce bir ihale seçin")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "PDF İhale Dosyası Oluştur", "", "PDF Dosyaları (*.pdf)"
        )
        
        if file_path:
            try:
                ihale = self.db.get_ihale(self.current_ihale_id)
                kalemler = self.db.get_ihale_kalemleri(self.current_ihale_id)
                
                from reportlab.lib.pagesizes import A4
                from reportlab.lib import colors
                from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                from reportlab.lib.units import cm
                from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
                from reportlab.pdfbase import pdfmetrics
                from reportlab.pdfbase.ttfonts import TTFont
                
                # Türkçe karakter desteği için font yükle (eğer yoksa varsayılan font kullanılır)
                font_name = 'Helvetica'
                font_bold_name = 'Helvetica-Bold'
                try:
                    # Windows'ta Arial fontunu kullan
                    import platform
                    if platform.system() == 'Windows':
                        arial_path = 'C:/Windows/Fonts/arial.ttf'
                        arial_bold_path = 'C:/Windows/Fonts/arialbd.ttf'
                        if Path(arial_path).exists():
                            pdfmetrics.registerFont(TTFont('Arial', arial_path))
                            font_name = 'Arial'
                            # Arial Bold fontunu da yükle
                            if Path(arial_bold_path).exists():
                                try:
                                    pdfmetrics.registerFont(TTFont('Arial-Bold', arial_bold_path))
                                    font_bold_name = 'Arial-Bold'
                                except:
                                    # Arial-Bold yüklenemezse Helvetica-Bold kullan
                                    font_bold_name = 'Helvetica-Bold'
                            else:
                                # Arial Bold yoksa, Helvetica-Bold kullan
                                font_bold_name = 'Helvetica-Bold'
                        else:
                            font_name = 'Helvetica'
                            font_bold_name = 'Helvetica-Bold'
                    else:
                        font_name = 'Helvetica'
                        font_bold_name = 'Helvetica-Bold'
                except Exception as e:
                    print(f"Font yükleme hatası: {e}")
                    font_name = 'Helvetica'
                    font_bold_name = 'Helvetica-Bold'
                
                # Logo yolu kontrolü
                logo_path = Path(__file__).parent.parent.parent / "assets" / "logo.png"
                has_logo = logo_path.exists()
                
                doc = SimpleDocTemplate(str(file_path), pagesize=A4)
                story = []
                styles = getSampleStyleSheet()
                
                # Logo ekle
                if has_logo:
                    try:
                        from reportlab.platypus import Image
                        from reportlab.lib.units import inch
                        logo = Image(str(logo_path), width=2*inch, height=0.8*inch)
                        logo.hAlign = 'CENTER'
                        story.append(logo)
                        story.append(Spacer(1, 0.2*inch))
                    except Exception as e:
                        print(f"Logo yükleme hatası: {e}")
                
                # Başlık
                title_style = ParagraphStyle(
                    'CustomTitle',
                    parent=styles['Heading1'],
                    fontName=font_name,
                    fontSize=18,
                    textColor=colors.HexColor('#1a1a2e'),
                    spaceAfter=30,
                    alignment=1
                )
                story.append(Paragraph(f"İHALE DOSYASI - {ihale.get('ad', '')}", title_style))
                story.append(Spacer(1, 0.5*cm))
                
                # İhale bilgileri
                info_data = [
                    ['İhale Adı', ihale.get('ad', '')],
                    ['Açıklama', ihale.get('aciklama', '')],
                    ['Oluşturulma Tarihi', ihale.get('olusturma_tarihi', '')[:10] if ihale.get('olusturma_tarihi') else ''],
                ]
                
                info_table = Table(info_data, colWidths=[6*cm, 6*cm])
                info_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#16213e')),
                    ('TEXTCOLOR', (0, 0), (0, -1), colors.whitesmoke),
                    ('BACKGROUND', (1, 0), (1, -1), colors.white),
                    ('TEXTCOLOR', (1, 0), (1, -1), colors.black),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (0, -1), font_bold_name),
                    ('FONTNAME', (1, 0), (1, -1), font_name),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ]))
                story.append(info_table)
                story.append(Spacer(1, 0.5*cm))
                
                # Kalem listesi
                if kalemler:
                    heading2_style = ParagraphStyle(
                        'CustomHeading2',
                        parent=styles['Heading2'],
                        fontName=font_name,
                        fontSize=14,
                        textColor=colors.HexColor('#1a1a2e'),
                        spaceAfter=20
                    )
                    story.append(Paragraph("İhale Kalem Listesi", heading2_style))
                    kalem_data = [['Sıra', 'Poz No', 'Tanım', 'Miktar', 'Birim', 'Birim Fiyat', 'Toplam']]
                    
                    toplam_genel = 0.0
                    for kalem in kalemler:
                        toplam_genel += kalem.get('toplam', 0)
                        kalem_data.append([
                            str(kalem.get('sira_no', '')),
                            kalem.get('poz_no', ''),
                            kalem.get('poz_tanim', '')[:40],
                            f"{kalem.get('birim_miktar', 0):,.2f}",
                            kalem.get('birim', ''),
                            f"{kalem.get('birim_fiyat', 0):,.2f} TL",
                            f"{kalem.get('toplam', 0):,.2f} TL"
                        ])
                    
                    kalem_table = Table(kalem_data, colWidths=[1*cm, 2*cm, 5*cm, 2*cm, 1.5*cm, 2*cm, 2*cm])
                    kalem_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#16213e')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('ALIGN', (2, 1), (2, -1), 'LEFT'),
                        ('FONTNAME', (0, 0), (-1, 0), f'{font_name}-Bold' if font_name == 'Arial' else 'Helvetica-Bold'),
                        ('FONTNAME', (0, 1), (-1, -1), font_name),
                        ('FONTSIZE', (0, 0), (-1, 0), 10),
                        ('FONTSIZE', (0, 1), (-1, -1), 9),
                        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
                    ]))
                    story.append(kalem_table)
                    story.append(Spacer(1, 0.5*cm))
                    
                    # Toplam
                    toplam_data = [['GENEL TOPLAM', f"{toplam_genel:,.2f} TL"]]
                    toplam_table = Table(toplam_data, colWidths=[10*cm, 4*cm])
                    toplam_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#16213e')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 12),
                        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                    ]))
                    story.append(toplam_table)
                
                doc.build(story)
                QMessageBox.information(self, "Başarılı", f"İhale dosyası PDF'e aktarıldı:\n{file_path}")
                self.statusBar().showMessage(f"PDF ihale dosyası oluşturuldu: {file_path}")
                
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"PDF oluşturulurken hata oluştu:\n{str(e)}")
    
    def export_ihale_excel(self) -> None:
        """İhale dosyasını Excel olarak export et"""
        if not self.current_ihale_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce bir ihale seçin")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Excel İhale Dosyası Oluştur", "", "Excel Dosyaları (*.xlsx)"
        )
        
        if file_path:
            try:
                import pandas as pd
                from openpyxl import load_workbook
                from openpyxl.styles import Font, Alignment, PatternFill
                
                ihale = self.db.get_ihale(self.current_ihale_id)
                kalemler = self.db.get_ihale_kalemleri(self.current_ihale_id)
                
                # Excel writer
                with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                    # İhale bilgileri
                    info_data = {
                        'Bilgi': ['İhale Adı', 'Açıklama', 'Oluşturulma Tarihi'],
                        'Değer': [
                            ihale.get('ad', ''),
                            ihale.get('aciklama', ''),
                            ihale.get('olusturma_tarihi', '')[:10] if ihale.get('olusturma_tarihi') else ''
                        ]
                    }
                    df_info = pd.DataFrame(info_data)
                    df_info.to_excel(writer, sheet_name='İhale Bilgileri', index=False)
                    
                    # Kalem listesi
                    if kalemler:
                        kalem_data = {
                            'Sıra': [k.get('sira_no', '') for k in kalemler],
                            'Poz No': [k.get('poz_no', '') for k in kalemler],
                            'Tanım': [k.get('poz_tanim', '') for k in kalemler],
                            'Birim Miktar': [k.get('birim_miktar', 0) for k in kalemler],
                            'Birim': [k.get('birim', '') for k in kalemler],
                            'Birim Fiyat': [f"{k.get('birim_fiyat', 0):,.2f} TL" for k in kalemler],
                            'Toplam': [f"{k.get('toplam', 0):,.2f} TL" for k in kalemler]
                        }
                        df_kalem = pd.DataFrame(kalem_data)
                        df_kalem.to_excel(writer, sheet_name='Kalem Listesi', index=False)
                        
                        # Toplam satırı
                        toplam_genel = sum(k.get('toplam', 0) for k in kalemler)
                        toplam_row = pd.DataFrame({
                            'Sıra': [''],
                            'Poz No': [''],
                            'Tanım': ['GENEL TOPLAM'],
                            'Birim Miktar': [''],
                            'Birim': [''],
                            'Birim Fiyat': [''],
                            'Toplam': [f"{toplam_genel:,.2f} TL"]
                        })
                        df_kalem = pd.concat([df_kalem, toplam_row], ignore_index=True)
                        df_kalem.to_excel(writer, sheet_name='Kalem Listesi', index=False)
                
                # Stil ayarları
                wb = load_workbook(file_path)
                for sheet_name in wb.sheetnames:
                    ws = wb[sheet_name]
                    header_fill = PatternFill(start_color='16213e', end_color='16213e', fill_type='solid')
                    for cell in ws[1]:
                        cell.font = Font(bold=True, color='FFFFFF')
                        cell.fill = header_fill
                        cell.alignment = Alignment(horizontal='center', vertical='center')
                wb.save(file_path)
                
                QMessageBox.information(self, "Başarılı", f"İhale dosyası Excel'e aktarıldı:\n{file_path}")
                self.statusBar().showMessage(f"Excel ihale dosyası oluşturuldu: {file_path}")
                
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Excel oluşturulurken hata oluştu:\n{str(e)}")
    
    def show_unit_converter(self) -> None:
        """Birim dönüştürücü dialogu göster"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QDoubleSpinBox, QComboBox, QLabel, QPushButton
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Birim Dönüştürücü")
        dialog.setGeometry(300, 300, 400, 300)
        
        layout = QVBoxLayout(dialog)
        
        form_layout = QFormLayout()
        
        # Değer girişi
        value_input = QDoubleSpinBox()
        value_input.setRange(0, 999999999)
        value_input.setDecimals(4)
        value_input.setValue(1.0)
        form_layout.addRow("Değer:", value_input)
        
        # Kaynak birim
        from_unit_combo = QComboBox()
        from_unit_combo.addItems(["m", "cm", "mm", "km", "İnç", "Ayak", "Mil"])
        form_layout.addRow("Kaynak Birim:", from_unit_combo)
        
        # Hedef birim
        to_unit_combo = QComboBox()
        to_unit_combo.addItems(["m", "cm", "mm", "km", "İnç", "Ayak", "Mil"])
        to_unit_combo.setCurrentText("cm")
        form_layout.addRow("Hedef Birim:", to_unit_combo)
        
        # Sonuç
        result_label = QLabel("0")
        form_layout.addRow("Sonuç:", result_label)
        
        layout.addLayout(form_layout)
        
        # Dönüştür butonu
        btn_convert = QPushButton("Dönüştür")
        def convert():
            value = value_input.value()
            from_unit = from_unit_combo.currentText()
            to_unit = to_unit_combo.currentText()
            
            # Birim dönüştürme tablosu (mm cinsinden)
            units = {
                "mm": 1,
                "cm": 10,
                "m": 1000,
                "km": 1000000,
                "İnç": 25.4,
                "Ayak": 304.8,
                "Mil": 1609344
            }
            
            if from_unit in units and to_unit in units:
                mm_value = value * units[from_unit]
                result = mm_value / units[to_unit]
                result_label.setText(f"{result:.6f} {to_unit}")
        
        btn_convert.clicked.connect(convert)
        layout.addWidget(btn_convert)
        
        dialog.exec()
    
    def open_demir_hesaplama(self) -> None:
        """Demir hesaplama penceresini aç"""
        try:
            from app.ui.demir_hesaplama_window import DemirHesaplamaWindow
            self.demir_window = DemirHesaplamaWindow(self)
            self.demir_window.show()
            logger.info("Demir hesaplama penceresi açıldı")
        except Exception as e:
            logger.error(f"Demir hesaplama penceresi açılamadı: {e}")
            QMessageBox.critical(self, "Hata", f"Pencere açılamadı:\n{str(e)}")

    def open_saha_demiri(self) -> None:
        """Saha demiri hesabı penceresini aç"""
        try:
            from app.ui.saha_demiri_window import SahaDemiriWindow
            self.saha_demiri_window = SahaDemiriWindow(self.db)
            self.saha_demiri_window.setWindowTitle("Saha Demiri Hesabı")
            self.saha_demiri_window.resize(1200, 800)
            self.saha_demiri_window.show()
            logger.info("Saha demiri hesabı penceresi açıldı")
        except Exception as e:
            logger.error(f"Saha demiri hesabı penceresi açılamadı: {e}")
            QMessageBox.critical(self, "Hata", f"Pencere açılamadı:\n{str(e)}")

    def open_duvar_maliyet(self) -> None:
        """Duvar maliyet hesaplama penceresini aç"""
        try:
            from app.ui.duvar_maliyet_window import DuvarMaliyetWindow
            self.duvar_maliyet_window = DuvarMaliyetWindow(self)
            self.duvar_maliyet_window.show()
            logger.info("Duvar maliyet hesaplama penceresi açıldı")
        except Exception as e:
            logger.error(f"Duvar maliyet penceresi açılamadı: {e}")
            QMessageBox.critical(self, "Hata", f"Pencere açılamadı:\n{str(e)}")

    def open_alci_maliyet(self) -> None:
        """Makine alçı maliyet hesaplama penceresini aç"""
        try:
            from app.ui.alci_maliyet_window import AlciMaliyetWindow
            self.alci_maliyet_window = AlciMaliyetWindow(self)
            self.alci_maliyet_window.show()
            logger.info("Alçı maliyet hesaplama penceresi açıldı")
        except Exception as e:
            logger.error(f"Alçı maliyet penceresi açılamadı: {e}")
            QMessageBox.critical(self, "Hata", f"Pencere açılamadı:\n{str(e)}")

    def open_kara_siva(self) -> None:
        """Kara sıva (el ile) maliyet hesaplama penceresini aç"""
        try:
            from app.ui.kara_siva_window import KaraSivaWindow
            self.kara_siva_window = KaraSivaWindow(self)
            self.kara_siva_window.show()
            logger.info("Kara sıva maliyet hesaplama penceresi açıldı")
        except Exception as e:
            logger.error(f"Kara sıva penceresi açılamadı: {e}")
            QMessageBox.critical(self, "Hata", f"Pencere açılamadı:\n{str(e)}")

    def open_boya_maliyet(self) -> None:
        """Gelişmiş boya maliyet hesaplama penceresini aç"""
        try:
            from app.ui.boya_maliyet_window import BoyaMaliyetWindow
            self.boya_maliyet_window = BoyaMaliyetWindow(self)
            self.boya_maliyet_window.show()
            logger.info("Boya maliyet hesaplama penceresi açıldı")
        except Exception as e:
            logger.error(f"Boya maliyet penceresi açılamadı: {e}")
            QMessageBox.critical(self, "Hata", f"Pencere açılamadı:\n{str(e)}")

    def open_fayans_hesaplama(self) -> None:
        """Oda bazli fayans hesaplama penceresini ac"""
        try:
            from app.ui.fayans_hesaplama_window import FayansHesaplamaWindow
            self.fayans_hesaplama_window = FayansHesaplamaWindow(self)
            self.fayans_hesaplama_window.show()
            logger.info("Fayans hesaplama penceresi acildi")
        except Exception as e:
            logger.error(f"Fayans hesaplama penceresi acilamadi: {e}")
            QMessageBox.critical(self, "Hata", f"Pencere acilamadi:\n{str(e)}")

    def open_sap_maliyet(self) -> None:
        """Sap (tesviye betonu) maliyet hesaplama penceresini ac"""
        try:
            from app.ui.sap_maliyet_window import SapMaliyetWindow
            self.sap_maliyet_window = SapMaliyetWindow(self)
            self.sap_maliyet_window.show()
            logger.info("Sap maliyet hesaplama penceresi acildi")
        except Exception as e:
            logger.error(f"Sap maliyet penceresi acilamadi: {e}")
            QMessageBox.critical(self, "Hata", f"Pencere acilamadi:\n{str(e)}")

    def open_parke_maliyet(self) -> None:
        """Laminat parke ve supurgelik maliyet hesaplama penceresini ac"""
        try:
            from app.ui.parke_maliyet_window import ParkeMaliyetWindow
            self.parke_maliyet_window = ParkeMaliyetWindow(self)
            self.parke_maliyet_window.show()
            logger.info("Parke maliyet hesaplama penceresi acildi")
        except Exception as e:
            logger.error(f"Parke maliyet penceresi acilamadi: {e}")
            QMessageBox.critical(self, "Hata", f"Pencere acilamadi:\n{str(e)}")

    def open_mantolama_hesaplama(self) -> None:
        """Dis cephe mantolama (Minha kurali) hesaplama penceresini ac"""
        try:
            from app.ui.mantolama_dialog import MantolamaHesaplamaDialog
            self.mantolama_dialog = MantolamaHesaplamaDialog(self, self.db)
            self.mantolama_dialog.hesaplama_tamamlandi.connect(self.on_mantolama_hesaplandi)
            self.mantolama_dialog.show()
            logger.info("Mantolama hesaplama penceresi acildi")
        except Exception as e:
            logger.error(f"Mantolama hesaplama penceresi acilamadi: {e}")
            QMessageBox.critical(self, "Hata", f"Pencere acilamadi:\n{str(e)}")

    def on_mantolama_hesaplandi(self, sonuc: Dict[str, Any]) -> None:
        """Mantolama hesaplama tamamlandiginda metraja ekle"""
        if not self.current_project_id:
            QMessageBox.warning(self, "Uyari", "Metraja eklemek icin once bir proje secin!")
            return

        try:
            # Ana kalemi metraja ekle
            item_data = {
                'proje_id': self.current_project_id,
                'poz_no': 'MANTOLAMA-001',
                'tanim': f"Dis Cephe Mantolama ({sonuc['levha_tipi'].replace('_', ' ').title()}) - {sonuc['uygulamaya_esas_net_alan_m2']:.2f} m2",
                'miktar': sonuc['uygulamaya_esas_net_alan_m2'],
                'birim': 'm2',
                'birim_fiyat': sonuc['maliyet_ozeti']['birim_maliyet_m2'],
                'toplam': sonuc['maliyet_ozeti']['genel_toplam_tl'],
                'kategori': 'Dis Cephe Isleri',
                'notlar': f"Brut alan: {sonuc['girilen_brut_alan_m2']} m2, "
                         f"Dusulen bosluk: {sonuc['dusulen_bosluk_alani_m2']} m2, "
                         f"Denizlik donus: {sonuc['eklenen_denizlik_donus_m2']} m2"
            }

            self.db.add_metraj_item(**item_data)
            self.load_metraj_items()
            logger.info(f"Mantolama kalemi metraja eklendi: {sonuc['uygulamaya_esas_net_alan_m2']:.2f} m2")
        except Exception as e:
            logger.error(f"Mantolama kalemi eklenirken hata: {e}")

    def open_mermer_hesaplama(self) -> None:
        """Mermer isleri (merdiven, denizlik, harc) hesaplama penceresini ac"""
        try:
            from app.ui.mermer_dialog import MermerHesaplamaDialog
            self.mermer_dialog = MermerHesaplamaDialog(self, self.db)
            self.mermer_dialog.hesaplama_tamamlandi.connect(self.on_mermer_hesaplandi)
            self.mermer_dialog.show()
            logger.info("Mermer isleri hesaplama penceresi acildi")
        except Exception as e:
            logger.error(f"Mermer hesaplama penceresi acilamadi: {e}")
            QMessageBox.critical(self, "Hata", f"Pencere acilamadi:\n{str(e)}")

    def on_mermer_hesaplandi(self, sonuc: Dict[str, Any]) -> None:
        """Mermer hesaplama tamamlandiginda metraja ekle"""
        if not self.current_project_id:
            QMessageBox.warning(self, "Uyari", "Metraja eklemek icin once bir proje secin!")
            return

        try:
            # Merdiven kalemi
            if sonuc['toplam_basamak_adet'] > 0:
                md = sonuc['merdiven_detay']
                merdiven_item = {
                    'proje_id': self.current_project_id,
                    'poz_no': 'MERMER-MRD-001',
                    'tanim': f"Merdiven Tasi ({md['toplam_basamak']} basamak, {md['basamak_genisligi_cm']:.0f}cm)",
                    'miktar': md['toplam_merdiven_m2'],
                    'birim': 'm2',
                    'birim_fiyat': sonuc['parametreler']['mermer_m2_fiyat'],
                    'toplam': md['toplam_merdiven_m2'] * sonuc['parametreler']['mermer_m2_fiyat'],
                    'kategori': 'Merdiven Isleri',
                    'notlar': f"Basamak: {md['basamak_alani_m2']:.2f} m2, Supurgelik: {md['supurgelik_alani_m2']:.2f} m2, Sahanlik: {md['sahanlik_alani_m2']:.2f} m2"
                }
                self.db.add_metraj_item(**merdiven_item)

            # Denizlik kalemi
            if sonuc['toplam_denizlik_adet'] > 0:
                denizlik_item = {
                    'proje_id': self.current_project_id,
                    'poz_no': 'MERMER-DNZ-001',
                    'tanim': f"Mermer Denizlik ({sonuc['toplam_denizlik_adet']} adet, {sonuc['toplam_denizlik_mtul']:.2f} mtul)",
                    'miktar': sonuc['toplam_denizlik_mtul'],
                    'birim': 'mtul',
                    'birim_fiyat': sonuc['parametreler']['mermer_iscilik_mtul_fiyat'],
                    'toplam': sonuc['iscilik_detay']['denizlik_iscilik_tl'],
                    'kategori': 'Pencere/Kapi Isleri',
                    'notlar': f"Toplam {sonuc['toplam_denizlik_adet']} adet pencere denizligi"
                }
                self.db.add_metraj_item(**denizlik_item)

            self.load_metraj_items()
            logger.info(f"Mermer kalemleri metraja eklendi: {sonuc['gereken_mermer_m2']:.2f} m2")
        except Exception as e:
            logger.error(f"Mermer kalemleri eklenirken hata: {e}")

    def open_pvc_dograma_hesaplama(self) -> None:
        """PVC dograma (pencere/kapi) hesaplama penceresini ac"""
        try:
            from app.ui.pvc_dograma_dialog import PVCDogramaHesaplamaDialog
            self.pvc_dialog = PVCDogramaHesaplamaDialog(self, self.db)
            self.pvc_dialog.hesaplama_tamamlandi.connect(self.on_pvc_hesaplandi)
            self.pvc_dialog.show()
            logger.info("PVC dograma hesaplama penceresi acildi")
        except Exception as e:
            logger.error(f"PVC dograma penceresi acilamadi: {e}")
            QMessageBox.critical(self, "Hata", f"Pencere acilamadi:\n{str(e)}")

    def on_pvc_hesaplandi(self, sonuc: Dict[str, Any]) -> None:
        """PVC dograma hesaplama tamamlandiginda metraja ekle"""
        if not self.current_project_id:
            QMessageBox.warning(self, "Uyari", "Metraja eklemek icin once bir proje secin!")
            return

        try:
            # PVC Dograma kalemi
            pvc_item = {
                'proje_id': self.current_project_id,
                'poz_no': 'PVC-DGR-001',
                'tanim': f"PVC Dograma ({sonuc['profil_rengi']}, {sonuc['cam_tipi']}) - {sonuc['toplam_dograma_adet']} adet",
                'miktar': sonuc['toplam_dograma_adet'],
                'birim': 'adet',
                'birim_fiyat': sonuc['genel_toplam_maliyet_tl'] / sonuc['toplam_dograma_adet'] if sonuc['toplam_dograma_adet'] > 0 else 0,
                'toplam': sonuc['genel_toplam_maliyet_tl'],
                'kategori': 'Kapi/Pencere',
                'notlar': f"Profil: {sonuc['hesaplanan_toplam_profil_mtul']:.2f} mtul, Cam: {sonuc['hesaplanan_net_cam_m2']:.2f} m2, Sineklik: {sonuc['gereken_sineklik_adet']} adet"
            }
            self.db.add_metraj_item(**pvc_item)

            self.load_metraj_items()
            logger.info(f"PVC dograma metraja eklendi: {sonuc['toplam_dograma_adet']} adet")
        except Exception as e:
            logger.error(f"PVC dograma kalemi eklenirken hata: {e}")

    def open_mobilya_maliyet(self) -> None:
        """Mobilya maliyet hesaplama penceresini ac"""
        try:
            from app.ui.mobilya_maliyet_window import MobilyaMaliyetWindow
            self.mobilya_maliyet_window = MobilyaMaliyetWindow(self)
            self.mobilya_maliyet_window.show()
            logger.info("Mobilya maliyet hesaplama penceresi acildi")
        except Exception as e:
            logger.error(f"Mobilya maliyet penceresi acilamadi: {e}")
            QMessageBox.critical(self, "Hata", f"Pencere acilamadi:\n{str(e)}")

    def open_yalitim_maliyet(self) -> None:
        """Su yalitim maliyet hesaplama penceresini ac"""
        try:
            from app.ui.yalitim_maliyet_window import YalitimMaliyetWindow
            self.yalitim_maliyet_window = YalitimMaliyetWindow(self)
            self.yalitim_maliyet_window.show()
            logger.info("Su yalitim maliyet hesaplama penceresi acildi")
        except Exception as e:
            logger.error(f"Su yalitim maliyet penceresi acilamadi: {e}")
            QMessageBox.critical(self, "Hata", f"Pencere acilamadi:\n{str(e)}")

    def open_elektrik_maliyet(self) -> None:
        """Elektrik tesisat maliyet hesaplama penceresini ac"""
        try:
            from app.ui.elektrik_maliyet_window import ElektrikMaliyetWindow
            self.elektrik_maliyet_window = ElektrikMaliyetWindow(self)
            self.elektrik_maliyet_window.show()
            logger.info("Elektrik tesisat maliyet hesaplama penceresi acildi")
        except Exception as e:
            logger.error(f"Elektrik maliyet penceresi acilamadi: {e}")
            QMessageBox.critical(self, "Hata", f"Pencere acilamadi:\n{str(e)}")

    def open_vitrifiye_maliyet(self) -> None:
        """Vitrifiye ve armatur maliyet hesaplama penceresini ac"""
        try:
            from app.ui.vitrifiye_maliyet_window import VitrifiyeMaliyetWindow
            self.vitrifiye_maliyet_window = VitrifiyeMaliyetWindow(self)
            self.vitrifiye_maliyet_window.show()
            logger.info("Vitrifiye ve armatur maliyet hesaplama penceresi acildi")
        except Exception as e:
            logger.error(f"Vitrifiye maliyet penceresi acilamadi: {e}")
            QMessageBox.critical(self, "Hata", f"Pencere acilamadi:\n{str(e)}")

    def open_kaba_yapi_maliyet(self) -> None:
        """Kaba yapi maliyet hesaplama penceresini ac"""
        try:
            from app.ui.kaba_yapi_maliyet_window import KabaYapiMaliyetWindow
            self.kaba_yapi_maliyet_window = KabaYapiMaliyetWindow(self)
            self.kaba_yapi_maliyet_window.show()
            logger.info("Kaba yapi maliyet hesaplama penceresi acildi")
        except Exception as e:
            logger.error(f"Kaba yapi maliyet penceresi acilamadi: {e}")
            QMessageBox.critical(self, "Hata", f"Pencere acilamadi:\n{str(e)}")

    def open_metraj_analiz(self) -> None:
        """Akilli metraj analizi penceresini ac (Kiris/Duvar cakisma tespiti)"""
        try:
            from app.ui.metraj_analiz_window import MetrajAnalizWindow
            self.metraj_analiz_window = MetrajAnalizWindow(self)
            self.metraj_analiz_window.show()
            logger.info("Akilli metraj analizi penceresi acildi")
        except Exception as e:
            logger.error(f"Metraj analizi penceresi acilamadi: {e}")
            QMessageBox.critical(self, "Hata", f"Pencere acilamadi:\n{str(e)}")


    def open_puantaj_server(self) -> None:
        """Mobil puantaj sunucusu penceresini aç"""
        try:
            from app.ui.puantaj_server_window import PuantajServerWindow
            self.puantaj_server_window = PuantajServerWindow(self.db)
            self.puantaj_server_window.show()
            logger.info("Mobil puantaj sunucusu penceresi açıldı")
        except Exception as e:
            logger.error(f"Puantaj sunucusu penceresi açılamadı: {e}")
            QMessageBox.critical(self, "Hata", f"Pencere açılamadı:\n{str(e)}")

    def open_puantaj_rapor(self) -> None:
        """Puantaj rapor penceresini aç"""
        try:
            from app.ui.puantaj_rapor_window import PuantajRaporWindow
            self.puantaj_rapor_window = PuantajRaporWindow(self.db)
            self.puantaj_rapor_window.show()
            logger.info("Puantaj rapor penceresi açıldı")
        except Exception as e:
            logger.error(f"Puantaj rapor penceresi açılamadı: {e}")
            QMessageBox.critical(self, "Hata", f"Pencere açılamadı:\n{str(e)}")

    def calculate_auto_fire_rates(self) -> None:
        """Tüm pozlar için otomatik fire oranı hesapla"""
        if not self.current_project_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce bir proje seçin")
            return
        
        reply = QMessageBox.question(
            self, "Onay",
            "Tüm metraj kalemleri için kategori bazlı otomatik fire oranı hesaplanacak.\n"
            "Mevcut fire oranları güncellenecek. Devam etmek istiyor musunuz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        try:
            metraj_items = self.db.get_project_metraj(self.current_project_id)
            updated_count = 0
            
            for item in metraj_items:
                kategori = item.get('kategori', '')
                auto_fire = self.calculator.get_auto_fire_rate(kategori)
                
                # Poz varsa fire oranını güncelle
                poz_no = item.get('poz_no', '')
                if poz_no:
                    poz = self.db.get_poz(poz_no)
                    if poz and poz.get('fire_orani', 0.05) != auto_fire:
                        self.db.update_poz(
                            poz_no=poz_no,
                            fire_orani=auto_fire
                        )
                        updated_count += 1
            
            QMessageBox.information(
                self, "Başarılı",
                f"{updated_count} poz için fire oranı otomatik olarak güncellendi.\n"
                f"Kategori bazlı fire oranları uygulandı."
            )
            self.statusBar().showMessage(f"{updated_count} poz için fire oranı güncellendi")
        except Exception as e:
            QMessageBox.critical(
                self, "Hata",
                f"Fire oranı hesaplama sırasında hata oluştu:\n{str(e)}"
            )
    
    def reload_modules(self) -> None:
        """Modülleri yeniden yükle ve UI'ı güncelle"""
        reply = QMessageBox.question(
            self, "Yenile",
            "Tüm modüller yeniden yüklenecek.\n"
            "Açık pencereler kapatılıp yeniden açılacak.\n\n"
            "Devam etmek istiyor musunuz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            from PyQt6.QtWidgets import QApplication
            self.statusBar().showMessage("Modüller yeniden yükleniyor...")
            QApplication.processEvents()

            # 1. Açık alt pencereleri kaydet ve kapat
            acik_pencereler = []
            for child in QApplication.topLevelWidgets():
                if child != self and child.isVisible():
                    pencere_tipi = type(child).__name__
                    acik_pencereler.append(pencere_tipi)
                    child.close()
                    logger.info(f"🔄 Pencere kapatıldı: {pencere_tipi}")

            QApplication.processEvents()

            # 2. Tüm app modüllerini yeniden yükle (sıralama önemli - önce core, sonra ui)
            modules_to_reload = []

            # Önce tüm app.* modüllerini bul
            for module_name in list(sys.modules.keys()):
                if module_name.startswith('app.'):
                    modules_to_reload.append(module_name)

            # Sıralama: önce core, sonra utils, sonra ui
            def module_priority(name):
                if 'core' in name:
                    return 0
                elif 'utils' in name:
                    return 1
                elif 'ui' in name:
                    return 2
                return 3

            modules_to_reload.sort(key=module_priority)

            reloaded_count = 0
            reload_errors = []

            for module_name in modules_to_reload:
                try:
                    if module_name in sys.modules and sys.modules[module_name] is not None:
                        importlib.reload(sys.modules[module_name])
                        reloaded_count += 1
                        logger.info(f"✅ Modül yeniden yüklendi: {module_name}")
                except Exception as e:
                    reload_errors.append(f"{module_name}: {e}")
                    logger.warning(f"⚠️ Modül yeniden yüklenemedi {module_name}: {e}")

            QApplication.processEvents()

            # 3. Database migration'larını çalıştır
            try:
                logger.info("🔄 Database migration'ları çalıştırılıyor...")
                with self.db.get_connection() as conn:
                    cursor = conn.cursor()
                    try:
                        cursor.execute("ALTER TABLE ai_metraj_ogrenme ADD COLUMN duvar_cinsi TEXT")
                        logger.info("✅ Migration: duvar_cinsi kolonu eklendi")
                    except sqlite3.OperationalError:
                        pass

                    try:
                        cursor.execute("ALTER TABLE ai_metraj_ogrenme ADD COLUMN duvar_kalinligi REAL")
                        logger.info("✅ Migration: duvar_kalinligi kolonu eklendi")
                    except sqlite3.OperationalError:
                        pass

                    conn.commit()
                logger.info("✅ Database migration'ları tamamlandı")
            except Exception as e:
                logger.warning(f"⚠️ Database migration hatası: {e}")

            QApplication.processEvents()

            # 4. UI bileşenlerini güncelle
            if self.current_project_id:
                try:
                    if hasattr(self, 'metraj_table') and self._tabs_created.get('metraj', False):
                        logger.info("🔄 Metraj verileri yenileniyor...")
                        self.load_metraj_data()
                    if hasattr(self, 'taseron_table') and self._tabs_created.get('taseron', False):
                        logger.info("🔄 Taşeron verileri yenileniyor...")
                        self.load_taseron_data()
                    if hasattr(self, 'ozet_kalem_label'):
                        logger.info("🔄 Proje özeti yenileniyor...")
                        self.update_proje_ozet()
                except Exception as e:
                    logger.warning(f"⚠️ Veri yenileme hatası: {e}")

            QApplication.processEvents()

            # 5. Projeleri yeniden yükle
            try:
                logger.info("🔄 Proje listesi yenileniyor...")
                self.load_projects()
            except Exception as e:
                logger.warning(f"⚠️ Proje listesi yenileme hatası: {e}")

            QApplication.processEvents()

            # 6. Kapatılan pencereleri yeniden aç
            for pencere_tipi in acik_pencereler:
                try:
                    if pencere_tipi == 'MetrajAnalizWindow':
                        self.show_metraj_analizi()
                        logger.info(f"✅ Pencere yeniden açıldı: {pencere_tipi}")
                    elif pencere_tipi == 'GanttWindow':
                        self.show_gantt_chart()
                        logger.info(f"✅ Pencere yeniden açıldı: {pencere_tipi}")
                    elif pencere_tipi == 'BIDashboardWindow':
                        self.show_bi_dashboard()
                        logger.info(f"✅ Pencere yeniden açıldı: {pencere_tipi}")
                    elif pencere_tipi == 'TedarikciWindow':
                        self.show_tedarikci_portal()
                        logger.info(f"✅ Pencere yeniden açıldı: {pencere_tipi}")
                    elif pencere_tipi == 'EnflasyonWindow':
                        self.show_enflasyon_analizi()
                        logger.info(f"✅ Pencere yeniden açıldı: {pencere_tipi}")
                    elif pencere_tipi == 'SurdurulebilirlikWindow':
                        self.show_surdurulebilirlik_raporu()
                        logger.info(f"✅ Pencere yeniden açıldı: {pencere_tipi}")

                except Exception as e:
                    logger.warning(f"⚠️ Pencere yeniden açılamadı {pencere_tipi}: {e}")

            QApplication.processEvents()

            # Sonuç mesajı
            mesaj = f"✅ {reloaded_count} modül yeniden yüklendi.\n"
            mesaj += f"🔄 Database migration'ları çalıştırıldı.\n"
            mesaj += f"📊 Veriler yenilendi.\n"

            if acik_pencereler:
                mesaj += f"🪟 {len(acik_pencereler)} pencere yeniden açıldı.\n"

            if reload_errors:
                mesaj += f"\n⚠️ {len(reload_errors)} modül yüklenemedi (detaylar logda)."

            mesaj += "\n\nYeni güncellemeler aktif!"

            QMessageBox.information(self, "Başarılı", mesaj)
            self.statusBar().showMessage("✅ Modüller başarıyla yeniden yüklendi - Yeni özellikler aktif!", 5000)
            
        except Exception as e:
            logger.error(f"❌ Modül yeniden yükleme hatası: {e}", exc_info=True)
            QMessageBox.critical(
                self, "Hata",
                f"Modüller yeniden yüklenirken hata oluştu:\n{str(e)}\n\n"
                f"Detaylar için error_log.txt dosyasını kontrol edin.\n\n"
                f"Uygulamayı kapatıp tekrar açmanız önerilir."
            )
    
    def show_kullanim_kilavuzu(self) -> None:
        """Kategorili kullanim kilavuzu dialogu"""
        dlg = QDialog(self)
        dlg.setWindowTitle("Kullanim Kilavuzu - InsaatMetrajPro")
        dlg.resize(900, 650)
        dlg.setStyleSheet("""
            QDialog { background-color: #1a1a2e; }
            QTreeWidget {
                background-color: #16213e;
                color: #e0e0e0;
                border: 1px solid #0f3460;
                font-size: 13px;
                outline: none;
            }
            QTreeWidget::item {
                padding: 4px 8px;
                border-bottom: 1px solid #0f3460;
            }
            QTreeWidget::item:selected {
                background-color: #0f3460;
                color: #00e5ff;
            }
            QTreeWidget::branch { background-color: #16213e; }
            QTextEdit {
                background-color: #16213e;
                color: #e0e0e0;
                border: 1px solid #0f3460;
                font-size: 13px;
                padding: 12px;
            }
            QLabel {
                color: #00e5ff;
                font-size: 16px;
                font-weight: bold;
                padding: 8px 0;
            }
            QPushButton {
                background-color: #0f3460;
                color: white;
                border: none;
                padding: 8px 24px;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #1a5276; }
        """)

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(12, 12, 12, 12)

        baslik = QLabel("INSAAT METRAJ PRO - KULLANIM KILAVUZU")
        baslik.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(baslik)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Sol: Kategori agaci
        tree = QTreeWidget()
        tree.setHeaderHidden(True)
        tree.setMinimumWidth(260)
        tree.setMaximumWidth(320)

        # Sag: Icerik alani
        icerik = QTextEdit()
        icerik.setReadOnly(True)

        splitter.addWidget(tree)
        splitter.addWidget(icerik)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter, 1)

        btn_kapat = QPushButton("Kapat")
        btn_kapat.clicked.connect(dlg.close)
        h_lay = QHBoxLayout()
        h_lay.addStretch()
        h_lay.addWidget(btn_kapat)
        layout.addLayout(h_lay)

        # --- KILAVUZ VERILERI ---
        kilavuz = {
            "BASLANGIC": {
                "Programa Genel Bakis": (
                    "InsaatMetrajPro, insaat sektorune ozel gelistirilmis profesyonel bir "
                    "metraj ve maliyet analiz uygulamasidir.\n\n"
                    "TEMEL OZELLIKLER:\n"
                    "  - Konut yapisi icin 150+ is kalemi\n"
                    "  - Offline-First yaklasim (internet gerektirmez)\n"
                    "  - DXF (CAD) dosyalarindan otomatik metraj cikartma\n"
                    "  - 25+ uzman hesaplama araci\n"
                    "  - Excel/PDF iceaktarma ve disaaktarma\n"
                    "  - Proje yedekleme ve versiyonlama\n"
                    "  - Mobil puantaj destegi\n"
                    "  - Gantt semalari ile is programi"
                ),
                "Klavye Kisayollari": (
                    "KLAVYE KISAYOLLARI:\n\n"
                    "  Ctrl + N    Yeni Proje Olustur\n"
                    "  Ctrl + O    Proje Ac\n"
                    "  Ctrl + R    Modulleri Yeniden Yukle\n"
                    "  Ctrl + Q    Programdan Cik\n\n"
                    "GENEL KULLANIM:\n"
                    "  - Sol panelden proje secin veya yeni proje olusturun\n"
                    "  - Ust sekmeleri kullanarak farkli modullere erisebilirsiniz\n"
                    "  - Sag tikla menuleri ek islemler sunar"
                ),
                "Arayuz Yapisi": (
                    "ARAYUZ BOLUMLERI:\n\n"
                    "1. SOL PANEL:\n"
                    "   - Proje agaci (tum projeleriniz listelenir)\n"
                    "   - Yeni Proje / Proje Sil / Yenile butonlari\n"
                    "   - Hizli arama kutusu (proje, kalem, poz arama)\n"
                    "   - Proje notlari alani\n\n"
                    "2. UST MENU CUBUGU:\n"
                    "   - Dosya: Proje islemleri, yedekleme, versiyonlama\n"
                    "   - Veri: Poz yukleme, Excel/PDF iceaktarma\n"
                    "   - Araclar: 25+ hesaplama araci\n"
                    "   - Yardim: Kilavuz ve hakkinda\n\n"
                    "3. ANA ALAN (SEKMELER):\n"
                    "   - 13 farkli sekme ile tum islemlere erisim\n"
                    "   - Sekmeler ilk tiklamada yuklenir (hizli acilis)"
                ),
            },
            "PROJE YONETIMI": {
                "Yeni Proje Olusturma": (
                    "YENI PROJE OLUSTURMA:\n\n"
                    "1. Sol paneldeki 'Yeni Proje' butonuna basin\n"
                    "   veya Dosya > Yeni Proje (Ctrl+N)\n"
                    "2. Proje adini girin\n"
                    "3. Proje otomatik olarak kaydedilir\n\n"
                    "NOT: Her proje bagimsiz bir veritabani kaydidir.\n"
                    "Projeler arasi gecis icin sol paneldeki agactan\n"
                    "istediginiz projeye cift tiklayin."
                ),
                "Proje Yedekleme": (
                    "YEDEKLEME ISLEMLERI:\n\n"
                    "Dosya > Yedekleme menusunden:\n\n"
                    "  - Projeyi Yedekle: Secili projeyi yedekler\n"
                    "  - Tum Projeleri Yedekle: Tum projeleri tek seferde yedekler\n"
                    "  - Yedekten Geri Yukle: Onceki bir yedekten projeyi geri getirir\n\n"
                    "ONERI: Onemli degisikliklerden once mutlaka yedek alin."
                ),
                "Proje Versiyonlama": (
                    "VERSIYONLAMA:\n\n"
                    "Dosya > Versiyonlama menusunden:\n\n"
                    "  - Versiyon Olustur: Projenin mevcut halini bir versiyon\n"
                    "    olarak kaydeder (isim ve aciklama ile)\n"
                    "  - Versiyonlari Goruntule: Tum versiyonlarin listesi\n"
                    "  - Versiyondan Geri Yukle: Secilen versiyona geri doner\n\n"
                    "Versiyonlar projenin farkli asamalarini takip etmenizi saglar."
                ),
            },
            "METRAJ CETVELI": {
                "Kalem Ekleme": (
                    "METRAJ CETVELINDE KALEM EKLEME:\n\n"
                    "1. 'Kalem Ekle' butonuna basin\n"
                    "2. Poz listesinden is kalemini secin\n"
                    "3. Miktari girin\n"
                    "4. Birim ve birim fiyat otomatik gelir\n"
                    "5. Toplam tutar hesaplanir\n\n"
                    "TABLO SUTUNLARI:\n"
                    "  ID | Poz No | Aciklama | Miktar | Birim | Birim Fiyat | Toplam"
                ),
                "Duzenleme ve Silme": (
                    "KALEM DUZENLEME:\n"
                    "  - Tablodan kalemi secin\n"
                    "  - 'Duzenle' butonuna basin\n"
                    "  - Miktar, birim fiyat gibi alanlari degistirin\n\n"
                    "KALEM SILME:\n"
                    "  - Tablodan kalemi secin\n"
                    "  - 'Sil' butonuna basin\n"
                    "  - Onay verdikten sonra kalem silinir\n\n"
                    "KDV AYARI:\n"
                    "  - KDV orani secimi: %1, %10, %20\n"
                    "  - Toplam tutar KDV dahil/haric gosterilir"
                ),
                "Malzeme Hesaplama": (
                    "MALZEME IHTIYAC HESABI:\n\n"
                    "Her is kalemi eklendiginde otomatik olarak\n"
                    "gereken malzemeler hesaplanir.\n\n"
                    "  - Malzeme adi ve miktari tabloda goruntulenir\n"
                    "  - Fire (israf) oranlari otomatik uygulanir\n"
                    "  - Malzeme birim fiyatlari duzenlenebilir\n\n"
                    "FIRE ORANLARI:\n"
                    "  Araclar > Otomatik Fire Orani Hesapla ile\n"
                    "  kategorilere gore fire oranlari otomatik belirlenir."
                ),
            },
            "VERI YONETIMI": {
                "Poz Yukleme": (
                    "POZ (IS KALEMI) YUKLEME:\n\n"
                    "Veri > Pozlari Yukle ile hazir is kalemlerini\n"
                    "sisteme yukleyebilirsiniz.\n\n"
                    "Sistem 150+ konut yapisi is kalemi icerir:\n"
                    "  - Kaba yapi (hafriyat, demir, beton)\n"
                    "  - Duvar imalatlari\n"
                    "  - Siva ve boya\n"
                    "  - Doseme kaplamalari\n"
                    "  - Tesisat\n"
                    "  - Dis cephe\n"
                    "  ve daha fazlasi..."
                ),
                "Excel Iceaktarma": (
                    "EXCEL'DEN KALEM ICEAKTARMA:\n\n"
                    "Veri > Excel'den Kalem Ice Aktar\n\n"
                    "Excel dosyanizdan is kalemlerini dogrudan\n"
                    "iceaktarabilirsiniz.\n\n"
                    "DESTEKLENEN FORMAT:\n"
                    "  - .xlsx ve .xls dosyalari\n"
                    "  - Sutunlar: Poz No, Aciklama, Miktar, Birim, Fiyat"
                ),
                "PDF Birim Fiyat": (
                    "PDF'DEN BIRIM FIYAT ICEAKTARMA:\n\n"
                    "Veri > PDF'den Birim Fiyat Ice Aktar\n\n"
                    "Resmi birim fiyat cetvellerinden (PDF) fiyatlari\n"
                    "otomatik olarak sisteme aktarabilirsiniz.\n\n"
                    "  - PDF dosyasini secin\n"
                    "  - Sistem fiyatlari otomatik tanir\n"
                    "  - Eslesen pozlara fiyatlar atanir\n\n"
                    "TEMIZLEME:\n"
                    "  Veri > PDF'den Eklenen Pozlari Temizle\n"
                    "  ile PDF'den gelen verileri kaldirilabilir."
                ),
            },
            "HESAPLAMA ARACLARI": {
                "Yapi Hesaplamalari": (
                    "YAPI HESAPLAMA ARACLARI:\n\n"
                    "Araclar menusunden erisilebilir:\n\n"
                    "  - Yapisal Demir Hesaplama\n"
                    "    Betonarme demir ihtiyaci hesabi\n\n"
                    "  - Saha Demiri Hesabi\n"
                    "    Sahada kullanilan demir miktarlari\n\n"
                    "  - Kaba Yapi Maliyet Hesaplama\n"
                    "    Hafriyat, demir, beton maliyetleri\n\n"
                    "Her arac ayri pencerede acilir ve sonuclar\n"
                    "dogrudan metraj cetvelina aktarilabilir."
                ),
                "Duvar ve Siva": (
                    "DUVAR VE SIVA ARACLARI:\n\n"
                    "  - Duvar Maliyet Hesaplama\n"
                    "    Tugla, bims, ytong, gazbeton secenekleri\n"
                    "    Otomatik malzeme sarfiyat hesabi\n\n"
                    "  - Makine Alci Maliyet Hesaplama\n"
                    "    Makine ile alci siva maliyeti\n\n"
                    "  - Kara Siva (El ile) Maliyet Hesaplama\n"
                    "    Geleneksel el sivasi maliyeti"
                ),
                "Kaplama ve Boya": (
                    "KAPLAMA VE BOYA ARACLARI:\n\n"
                    "  - Boya Maliyet Hesaplama (Gelismis)\n"
                    "    Ic/dis cephe boya hesabi\n\n"
                    "  - Fayans Hesaplama (Oda Bazli)\n"
                    "    Oda oda fayans ihtiyaci\n\n"
                    "  - Sap (Tesviye Betonu) Maliyet Hesaplama\n"
                    "    Zemin tesviye maliyeti\n\n"
                    "  - Laminat Parke ve Supurgelik Hesaplama\n"
                    "    Doseme kaplama maliyeti\n\n"
                    "  - Dis Cephe Mantolama Hesaplama\n"
                    "    Isil yalitim (minha kurali ile)"
                ),
                "Diger Hesaplamalar": (
                    "DIGER HESAPLAMA ARACLARI:\n\n"
                    "  - Mermer Isleri (Merdiven/Denizlik)\n"
                    "  - PVC Dograma (Pencere/Kapi)\n"
                    "  - Mobilya Maliyet (Mutfak/Vestiyer/Banyo/Kapi)\n"
                    "  - Su Yalitim (Bez/Toz/Surme)\n"
                    "  - Elektrik Tesisat Maliyet\n"
                    "  - Vitrifiye ve Armatur Maliyet\n"
                    "  - Birim Donusturucu\n\n"
                    "Her arac icin:\n"
                    "  1. Parametreleri girin\n"
                    "  2. Hesapla butonuna basin\n"
                    "  3. Sonuclari inceleyin\n"
                    "  4. Metraj cetvelina aktarin"
                ),
            },
            "AKILLI METRAJ ANALIZI": {
                "DXF Dosyasi Yukleme": (
                    "AKILLI METRAJ ANALIZI - DXF YUKLEME:\n\n"
                    "Araclar > Akilli Metraj Analizi\n\n"
                    "Bu modul DXF (CAD) dosyalarindan otomatik\n"
                    "metraj cikartma yapar.\n\n"
                    "ADIMLAR:\n"
                    "1. 'DXF Yukle' butonuna basin\n"
                    "2. DXF dosyanizi secin\n"
                    "3. Katman secim dialogunda katmanlari eslestin:\n"
                    "   - Kiris katmani (S_KIRIS_H60 gibi)\n"
                    "   - Duvar katmani (M_DUVAR gibi)\n"
                    "   - Kolon katmani\n"
                    "   - Kapi/Pencere (minha) katmani\n"
                    "   - Oda isimleri katmani\n"
                    "   - Kat isimleri katmani\n"
                    "   - m2 (alan) katmani\n"
                    "4. Birim secimi yapin (mm, cm, m)\n"
                    "5. Duvar malzemesi secin (Tugla, Bims, Ytong...)"
                ),
                "Gorsel Kat Plani": (
                    "GORSEL KAT PLANI:\n\n"
                    "DXF yuklendikten sonra otomatik olarak\n"
                    "profesyonel bir kat plani cizilir:\n\n"
                    "RENK KODLAMASI:\n"
                    "  Cyan/Turkuaz  : Duvarlar\n"
                    "  Beyaz Kareler : Kolonlar\n"
                    "  Kahverengi    : Kapilar (acilma yayi ile)\n"
                    "  Mavi          : Pencereler\n\n"
                    "ODA ETIKETLERI:\n"
                    "  Sari   : Kuru hacimler (Salon, Yatak Odasi)\n"
                    "  Yesil  : Koridor, Antre, Hol\n"
                    "  Mor    : Islak hacimler (Banyo, WC)\n\n"
                    "Her oda etiketi m2 degerini de gosterir.\n"
                    "Alt kisimda lejant cubugu bulunur."
                ),
                "Duvar Metraj Hesabi": (
                    "DUVAR METRAJ HESABI:\n\n"
                    "Sistem otomatik olarak:\n\n"
                    "  1. Duvarlari tespit eder\n"
                    "  2. Kiris-duvar cakismalarini bulur\n"
                    "  3. Kapi/pencere boslugu duser\n"
                    "  4. Net duvar alanini hesaplar\n\n"
                    "PARAMETRELER:\n"
                    "  - Kat Yuksekligi (cm)\n"
                    "  - Doseme Kalinligi (cm)\n"
                    "  - Duvar Malzemesi\n\n"
                    "SONUCLAR:\n"
                    "  - Duvar ID, kalinlik, brut/net alan\n"
                    "  - Malzeme ihtiyac listesi\n"
                    "  - Excel'e aktarim (coklu sayfa)"
                ),
                "Excel Ciktisi": (
                    "EXCEL AKTARIM:\n\n"
                    "Akilli Metraj sonuclari Excel'e aktarilabilir.\n\n"
                    "EXCEL SAYFALARI:\n"
                    "  1. Duvar Olculeri - Tum duvarlarin detaylari\n"
                    "  2. Alan Hesaplari - Oda bazli m2 degerleri\n"
                    "  3. Imalat Listesi - Yapilacak isler\n"
                    "  4. Malzeme Ozeti - Toplam malzeme ihtiyaci\n"
                    "  5. Tedarik Siparisi - Satin alma listesi\n"
                    "  6. Duvar Malzeme - Duvar malzeme detayi"
                ),
            },
            "RAPORLAMA": {
                "Proje Ozeti": (
                    "PROJE OZETI SEKMESI:\n\n"
                    "Projenin genel durumunu gosteren ozet kartlar:\n"
                    "  - Toplam kalem sayisi\n"
                    "  - Toplam maliyet (KDV haric)\n"
                    "  - Toplam maliyet (KDV dahil)\n"
                    "  - Taseron teklif sayisi\n\n"
                    "GRAFIKLER:\n"
                    "  - Kategori bazli dagilim\n"
                    "  - En pahali 5 kalem\n\n"
                    "DISAAKTARMA:\n"
                    "  - PDF raporu olusturma\n"
                    "  - Excel raporu olusturma"
                ),
                "Taseron Analizi": (
                    "TASERON ANALIZI SEKMESI:\n\n"
                    "Taseron tekliflerini yonetme ve karsilastirma.\n\n"
                    "  - Taseron teklifleri ekleme\n"
                    "  - Teklif karsilastirma\n"
                    "  - En uygun teklif secimi\n"
                    "  - Excel ve PDF disaaktarma"
                ),
                "Malzeme Listesi": (
                    "MALZEME LISTESI SEKMESI:\n\n"
                    "Tum projenin malzeme ihtiyac ozeti.\n\n"
                    "  - Malzeme adi ve toplam miktar\n"
                    "  - Birim fiyat ve toplam tutar\n"
                    "  - Fire oranlari dahil hesaplama\n\n"
                    "DISAAKTARMA FORMATLARI:\n"
                    "  - Excel (.xlsx)\n"
                    "  - PDF\n"
                    "  - Tedarikci formati"
                ),
            },
            "IHALE VE FINANS": {
                "Ihale Dosyasi Hazirlama": (
                    "IHALE DOSYASI HAZIRLAMA SEKMESI:\n\n"
                    "Resmi ihale dokumanlari olusturma.\n\n"
                    "  - Kalem listesi duzenleme\n"
                    "  - Aciklama, miktar, birim, fiyat\n"
                    "  - PDF ve Excel ciktisi\n\n"
                    "SUTUNLAR:\n"
                    "  Sira | Poz No | Aciklama | Miktar | Birim | "
                    "Birim Fiyat | Toplam"
                ),
                "Enflasyon ve Fiyat Farki": (
                    "ENFLASYON VE FIYAT FARKI SEKMESI:\n\n"
                    "Enflasyon takibi ve fiyat farki analizi.\n\n"
                    "  - Baslangic ve bitis donemi karsilastirma\n"
                    "  - Fiyat artis oranlari\n"
                    "  - Fiyat farki hesaplama"
                ),
                "Tedarikci Fiyat Karsilastirma": (
                    "TEDARIKCI FIYAT KARSILASTIRMA SEKMESI:\n\n"
                    "Farkli tedarikcilerden fiyat karsilastirma.\n\n"
                    "  - Birden fazla tedarikci fiyati girme\n"
                    "  - En uygun fiyat secimi\n"
                    "  - Fiyat gecmisi takibi"
                ),
                "Birim Fiyatlar": (
                    "BIRIM FIYATLAR SEKMESI:\n\n"
                    "Birim fiyat yonetimi.\n\n"
                    "  - Tum pozlarin birim fiyatlari\n"
                    "  - Fiyat guncelleme\n"
                    "  - Fiyat gecmisi karsilastirma"
                ),
            },
            "DIGER MODULLER": {
                "Gantt Semasi": (
                    "GANTT SEMASI VE IS PROGRAMI:\n\n"
                    "Proje zamanlama ve is programi olusturma.\n\n"
                    "  - Gorsel zaman cizelgesi\n"
                    "  - Is kalemlerini zamana yayma\n"
                    "  - Baslangic/bitis tarihleri\n"
                    "  - Ilerleme takibi"
                ),
                "Mobil Puantaj": (
                    "MOBIL PUANTAJ SUNUCUSU:\n\n"
                    "Araclar > Mobil Puantaj Sunucusu\n\n"
                    "Saha personelinin yoklama/puantaj islemlerini\n"
                    "mobil cihazlardan yapmasini saglar.\n\n"
                    "  - Sunucuyu baslatma/durdurma\n"
                    "  - QR kod ile erisim\n"
                    "  - Puantaj raporu olusturma"
                ),
                "BI Dashboard": (
                    "BI DASHBOARD (IS ZEKASI):\n\n"
                    "Proje verilerinin gorsel analizi.\n\n"
                    "  - Ozet kartlar ve grafikler\n"
                    "  - Performans metrikleri\n"
                    "  - Veri gorsellestirme"
                ),
                "Cevre ve Surdurulebilirlik": (
                    "CEVRE VE SURDURULEBILIRLIK:\n\n"
                    "Projenin cevre etkisi ve surdurulebilirlik analizi.\n\n"
                    "  - Karbon ayak izi hesaplama\n"
                    "  - Yesil bina kriterleri\n"
                    "  - Cevre dostu malzeme onerileri"
                ),
                "Sablonlar": (
                    "SABLONLAR SEKMESI:\n\n"
                    "Tekrar kullanilabilir proje sablonlari.\n\n"
                    "  - Mevcut projeden sablon olusturma\n"
                    "  - Sablon kopyalama\n"
                    "  - Yeni projeye sablon uygulama\n\n"
                    "Benzer projelerde zaman kazandirici."
                ),
            },
        }

        item_contents = {}

        for kategori, alt_basliklar in kilavuz.items():
            parent = QTreeWidgetItem(tree, [kategori])
            parent.setExpanded(True)
            f = parent.font(0)
            f.setBold(True)
            f.setPointSize(11)
            parent.setFont(0, f)
            parent.setForeground(0, QColor("#00e5ff"))

            for baslik, icerik_text in alt_basliklar.items():
                child = QTreeWidgetItem(parent, [baslik])
                child.setForeground(0, QColor("#e0e0e0"))
                item_contents[id(child)] = icerik_text

        def on_item_clicked(item, column):
            cid = id(item)
            if cid in item_contents:
                icerik.setPlainText(item_contents[cid])
            else:
                # Kategori basligina tiklandiginda alt baslik listesi goster
                alt_list = []
                for i in range(item.childCount()):
                    alt_list.append(f"  - {item.child(i).text(0)}")
                if alt_list:
                    icerik.setPlainText(
                        f"{item.text(0)} KATEGORISI\n"
                        f"{'=' * 40}\n\n"
                        f"Bu kategorideki konular:\n\n" +
                        "\n".join(alt_list) +
                        "\n\nDetay icin alt basliklara tiklayin."
                    )

        tree.itemClicked.connect(on_item_clicked)

        # Baslangic icerigi
        icerik.setPlainText(
            "INSAAT METRAJ PRO - KULLANIM KILAVUZU\n"
            "=" * 44 + "\n\n"
            "Hosgeldiniz!\n\n"
            "Sol taraftaki kategori agacindan bir konu\n"
            "secerek detayli bilgiye ulasabilirsiniz.\n\n"
            "KATEGORILER:\n\n"
            "  BASLANGIC\n"
            "    Programa genel bakis ve arayuz yapisi\n\n"
            "  PROJE YONETIMI\n"
            "    Proje olusturma, yedekleme, versiyonlama\n\n"
            "  METRAJ CETVELI\n"
            "    Kalem ekleme, duzenleme, malzeme hesabi\n\n"
            "  VERI YONETIMI\n"
            "    Poz yukleme, Excel/PDF iceaktarma\n\n"
            "  HESAPLAMA ARACLARI\n"
            "    25+ uzman hesaplama araci\n\n"
            "  AKILLI METRAJ ANALIZI\n"
            "    DXF'den otomatik metraj cikartma\n\n"
            "  RAPORLAMA\n"
            "    Proje ozeti, taseron, malzeme raporlari\n\n"
            "  IHALE VE FINANS\n"
            "    Ihale dosyasi, enflasyon, fiyat takibi\n\n"
            "  DIGER MODULLER\n"
            "    Gantt, puantaj, BI, cevre ve daha fazlasi"
        )

        dlg.exec()

    def show_about(self) -> None:
        """Hakkinda dialogu"""
        QMessageBox.about(
            self, "Hakkinda",
            "InsaatMetrajPro v1.0.0\n\n"
            "Insaat sektoru icin profesyonel metraj uygulamasi\n"
            "Python ve PyQt6 ile gelistirilmistir.\n\n"
            "Offline-First yaklasim ile calisir.\n\n"
            "Konut yapisi icin 150+ is kalemi icerir."
        )

