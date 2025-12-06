"""
Ana Pencere
PyQt6 ile modern kullanıcı arayüzü
"""

from typing import Optional, List, Dict, Any
from pathlib import Path
from datetime import datetime
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
from app.utils.pdf_importer import PDFBirimFiyatImporter
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
    
    def __init__(self, splash: Optional[Any] = None) -> None:
        """Ana pencereyi başlat"""
        super().__init__()
        
        self.splash = splash
        
        # Core modüller (hafif olanlar hemen yükle)
        self.db = DatabaseManager()
        self.calculator = Calculator()
        self.export_manager = ExportManager()
        
        # Ağır modüller lazy loading ile (sadece gerektiğinde yüklenecek)
        self._material_calculator: Optional[MaterialCalculator] = None
        
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
    def material_calculator(self) -> MaterialCalculator:
        """MaterialCalculator'ı lazy loading ile yükle"""
        if self._material_calculator is None:
            self._material_calculator = MaterialCalculator(self.db)
        return self._material_calculator
        
    def init_ui(self) -> None:
        """Arayüzü başlat"""
        self.setWindowTitle("InsaatMetrajPro - İnşaat Metraj Uygulaması")
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
        self.tabs.addTab(QWidget(), "Taşeron Analizi")
        self.tabs.addTab(QWidget(), "Malzeme Listesi")
        self.tabs.addTab(QWidget(), "Şablonlar")
        self.tabs.addTab(QWidget(), "Birim Fiyat Yönetimi")
        self.tabs.addTab(QWidget(), "İhale Dosyası Hazırlama")
        
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
        
        # Kart 4: Taşeron Teklif Sayısı
        self.ozet_taseron_card = QGroupBox("Taşeron Teklifleri")
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
        
        btn_create_from_project = QPushButton("Mevcut Projeden Şablon Oluştur")
        btn_create_from_project.clicked.connect(self.create_template_from_project)
        btn_layout.addWidget(btn_create_from_project)
        
        btn_create_project = QPushButton("Şablondan Proje Oluştur")
        btn_create_project.clicked.connect(self.create_project_from_template)
        btn_layout.addWidget(btn_create_project)
        
        btn_refresh = QPushButton("Yenile")
        btn_refresh.clicked.connect(self.load_templates)
        btn_layout.addWidget(btn_refresh)
        
        btn_layout.addStretch()
        
        btn_delete = QPushButton("Şablon Sil")
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
        layout.addWidget(self.template_table)
        
        # Şablon kalemleri (seçili şablon için)
        items_group = QGroupBox("Şablon Kalemleri")
        items_layout = QVBoxLayout()
        
        self.template_items_table = QTableWidget()
        self.template_items_table.setColumnCount(7)
        self.template_items_table.setHorizontalHeaderLabels([
            "Poz No", "Tanım", "Kategori", "Miktar", "Birim", "Birim Fiyat", "Toplam"
        ])
        self.template_items_table.setAlternatingRowColors(True)
        self.template_items_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.template_items_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.template_items_table.horizontalHeader().setStretchLastSection(True)
        items_layout.addWidget(self.template_items_table)
        
        items_group.setLayout(items_layout)
        layout.addWidget(items_group)
        
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
        kalem_btn_layout.addWidget(btn_delete_kalem)
        
        btn_export = QPushButton("İhale Dosyası Oluştur (PDF)")
        btn_export.clicked.connect(self.export_ihale_pdf)
        kalem_btn_layout.addWidget(btn_export)
        
        btn_export_excel = QPushButton("İhale Dosyası Oluştur (Excel)")
        btn_export_excel.clicked.connect(self.export_ihale_excel)
        kalem_btn_layout.addWidget(btn_export_excel)
        
        kalem_btn_layout.addStretch()
        
        # Toplam etiketi
        self.ihale_total_label = QLabel("Toplam: 0.00 ₺")
        self.ihale_total_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        kalem_btn_layout.addWidget(self.ihale_total_label)
        
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
        self.ihale_kalem_table.setColumnWidth(2, 250)
        self.ihale_kalem_table.setColumnWidth(3, 120)
        self.ihale_kalem_table.setColumnWidth(4, 80)
        self.ihale_kalem_table.setColumnWidth(5, 120)
        # Birim Miktar ve Birim Fiyat sütunları düzenlenebilir
        self.ihale_kalem_table.itemChanged.connect(self.on_ihale_kalem_changed)
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
        
        data_menu.addSeparator()
        check_pozlar_action = data_menu.addAction("Poz Durumunu Kontrol Et")
        check_pozlar_action.triggered.connect(self.check_pozlar_status)
        
        # Yardım menüsü
        help_menu = menubar.addMenu("Yardım")
        about_action = help_menu.addAction("Hakkında")
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
            self.metraj_table.setItem(row, 3, QTableWidgetItem(str(item['miktar'])))
            self.metraj_table.setItem(row, 4, QTableWidgetItem(item['birim']))
            self.metraj_table.setItem(row, 5, QTableWidgetItem(f"{item['birim_fiyat']:.2f}"))
            self.metraj_table.setItem(row, 6, QTableWidgetItem(f"{item['toplam']:.2f}"))
            total += item['toplam']
            
            # Her 50 satırda bir UI'ı güncelle
            if row % 50 == 0:
                QApplication.processEvents()
            
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
    
    def load_project_notes(self) -> None:
        """Proje notlarını yükle"""
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
                                birim_fiyat_str = birim_fiyat_str.replace(',', '.')
                                birim_fiyat = float(birim_fiyat_str)
                                if birim_fiyat < 0:
                                    birim_fiyat = 0.0
                        except (ValueError, TypeError) as e:
                            print(f"Satır {index + 2}: Birim fiyat dönüşüm hatası: {birim_fiyat_val} -> 0.0")
                            birim_fiyat = 0.0
                    
                    # Toplam hesapla
                    toplam = miktar * birim_fiyat if birim_fiyat > 0 else 0
                    
                    # Kalemi ekle
                    self.db.add_item(
                        proje_id=self.current_project_id,
                        poz_no=poz_no,
                        tanim=tanim,
                        kategori=kategori,
                        miktar=miktar,
                        birim=birim,
                        birim_fiyat=birim_fiyat,
                        toplam=toplam
                    )
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
            preview_table.setColumnCount(4)
            preview_table.setHorizontalHeaderLabels(["Poz No", "Tanım", "Birim Fiyat", "Kaynak"])
            preview_table.setRowCount(min(len(extracted_data), 100))  # İlk 100 kayıt
            
            for row, item in enumerate(extracted_data[:100]):
                preview_table.setItem(row, 0, QTableWidgetItem(item.get('poz_no', '')))
                preview_table.setItem(row, 1, QTableWidgetItem(item.get('tanim', '')[:50]))
                fiyat = item.get('birim_fiyat', 0)
                preview_table.setItem(row, 2, QTableWidgetItem(f"{fiyat:,.2f} ₺" if fiyat else "Bulunamadı"))
                preview_table.setItem(row, 3, QTableWidgetItem(item.get('kaynak', '')))
            
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
                                'Birim': '',  # Kullanıcı dolduracak
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
                    birim_fiyat = item.get('birim_fiyat', 0)
                    tanim = item.get('tanim', '') or "PDF'den içe aktarıldı"
                    
                    if not poz_no:
                        error_count += 1
                        continue
                    
                    # ÖNCE POZU POZLAR TABLOSUNA EKLE (yoksa)
                    poz = self.db.get_poz(poz_no)
                    if not poz:
                        # Poz yoksa ekle
                        try:
                            # Birim bilgisini tahmin et (tanımdan veya varsayılan)
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
                                resmi_fiyat=birim_fiyat if birim_fiyat > 0 else 0,
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
    
    def on_search_text_changed(self) -> None:
        """Arama metni değiştiğinde"""
        search_text = self.search_input.text().strip().lower()
        search_type = self.search_type_combo.currentText()
        
        if not search_text:
            # Arama boşsa normal listeyi göster
            self.load_projects()
            if self.current_project_id:
                self.load_metraj_data()
            return
        
        # Proje araması
        if search_type in ["Tümü", "Projeler"]:
            projects = self.db.get_all_projects()
            self.project_tree.clear()
            for project in projects:
                if search_text in project['ad'].lower() or (project.get('aciklama', '') and search_text in project['aciklama'].lower()):
                    item = QTreeWidgetItem(self.project_tree)
                    item.setText(0, project['ad'])
                    item.setData(0, Qt.ItemDataRole.UserRole, project['id'])
        
        # Kalem araması (seçili projede)
        if search_type in ["Tümü", "Kalemler"] and self.current_project_id:
            metraj_items = self.db.get_project_metraj(self.current_project_id)
            filtered_items = []
            for item in metraj_items:
                if (search_text in item.get('tanim', '').lower() or
                    search_text in item.get('poz_no', '').lower() or
                    search_text in item.get('kategori', '').lower()):
                    filtered_items.append(item)
            
            # Metraj tablosunu filtrele
            self.metraj_table.setRowCount(len(filtered_items))
            for row, item in enumerate(filtered_items):
                self.metraj_table.setItem(row, 0, QTableWidgetItem(item.get('poz_no', '')))
                self.metraj_table.setItem(row, 1, QTableWidgetItem(item.get('tanim', '')))
                self.metraj_table.setItem(row, 2, QTableWidgetItem(item.get('kategori', '')))
                self.metraj_table.setItem(row, 3, QTableWidgetItem(f"{item.get('miktar', 0):,.2f}"))
                self.metraj_table.setItem(row, 4, QTableWidgetItem(item.get('birim', '')))
                self.metraj_table.setItem(row, 5, QTableWidgetItem(f"{item.get('birim_fiyat', 0):,.2f}"))
                self.metraj_table.setItem(row, 6, QTableWidgetItem(f"{item.get('toplam', 0):,.2f}"))
            
            # Toplamı güncelle
            toplam = sum(item.get('toplam', 0) for item in filtered_items)
            self.total_label.setText(f"Toplam: {toplam:,.2f} ₺")
        
        # Poz araması (tüm pozlar)
        if search_type in ["Tümü", "Pozlar"]:
            # Poz araması için bir dialog veya sonuç gösterimi eklenebilir
            # Şimdilik sadece proje ve kalem araması yapıyoruz
            pass
    
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
        
        items = self.db.get_template_items(template_id)
        self.template_items_table.setRowCount(len(items))
        
        for row_idx, item_data in enumerate(items):
            self.template_items_table.setItem(row_idx, 0, QTableWidgetItem(item_data.get('poz_no', '')))
            self.template_items_table.setItem(row_idx, 1, QTableWidgetItem(item_data.get('tanim', '')))
            self.template_items_table.setItem(row_idx, 2, QTableWidgetItem(item_data.get('kategori', '')))
            self.template_items_table.setItem(row_idx, 3, QTableWidgetItem(f"{item_data.get('miktar', 0):,.2f}"))
            self.template_items_table.setItem(row_idx, 4, QTableWidgetItem(item_data.get('birim', '')))
            self.template_items_table.setItem(row_idx, 5, QTableWidgetItem(f"{item_data.get('birim_fiyat', 0):,.2f}"))
            self.template_items_table.setItem(row_idx, 6, QTableWidgetItem(f"{item_data.get('toplam', 0):,.2f}"))
    
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
            
            # Birim fiyatı getir (otomatik)
            fiyat_data = self.db.get_birim_fiyat(poz_no=poz_no)
            birim_fiyat = fiyat_data.get('birim_fiyat', 0) if fiyat_data else 0
            
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
                self.load_ihale_kalemleri()
                self.statusBar().showMessage(f"Poz eklendi: {poz_no}")
                QMessageBox.information(self, "Başarılı", f"Poz başarıyla eklendi:\n{poz_no} - {poz_tanim}")
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
            kalemler = self.db.get_ihale_kalemleri(self.current_ihale_id)
            self.ihale_kalem_table.setRowCount(len(kalemler))
            
            toplam = 0.0
            
            for row, kalem in enumerate(kalemler):
                # Sıra
                self.ihale_kalem_table.setItem(row, 0, QTableWidgetItem(str(kalem.get('sira_no', row + 1))))
                
                # Poz No
                self.ihale_kalem_table.setItem(row, 1, QTableWidgetItem(kalem.get('poz_no', '')))
                
                # Tanım (temizle - fiyat bilgisi varsa çıkar)
                poz_tanim = str(kalem.get('poz_tanim', '')).strip()
                # "Sa 250,00" veya "Sa 250.00" gibi pattern'leri temizle
                poz_tanim = re.sub(r'\s*Sa\s*\d+[.,]\d+', '', poz_tanim).strip()
                self.ihale_kalem_table.setItem(row, 2, QTableWidgetItem(poz_tanim))
                
                # Birim Miktar (düzenlenebilir) - 0 ise boş göster
                birim_miktar = kalem.get('birim_miktar', 0) or 0
                miktar_text = f"{birim_miktar:,.2f}" if birim_miktar > 0 else ""
                miktar_item = QTableWidgetItem(miktar_text)
                miktar_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.ihale_kalem_table.setItem(row, 3, miktar_item)
                
                # Birim
                self.ihale_kalem_table.setItem(row, 4, QTableWidgetItem(kalem.get('birim', '')))
                
                # Birim Fiyat (düzenlenebilir)
                birim_fiyat = kalem.get('birim_fiyat', 0) or 0
                fiyat_item = QTableWidgetItem(f"{birim_fiyat:,.2f}")
                fiyat_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.ihale_kalem_table.setItem(row, 5, fiyat_item)
                
                # Toplam (hesaplanır, düzenlenemez)
                toplam_deger = kalem.get('toplam', 0) or 0
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
                self.ihale_total_label.setText(f"Toplam: {toplam:,.2f} ₺")
        except Exception as e:
            print(f"İhale kalemleri yükleme hatası: {e}")
            import traceback
            traceback.print_exc()
            # Hata olsa bile tabloyu temizle
            try:
                self.ihale_kalem_table.setRowCount(0)
            except:
                pass
    
    def on_ihale_kalem_changed(self, item: QTableWidgetItem) -> None:
        """İhale kalemi değiştiğinde (birim miktar veya birim fiyat)"""
        row = item.row()
        kalem_id_item = self.ihale_kalem_table.item(row, 0)
        if not kalem_id_item:
            return
        
        kalem_id = kalem_id_item.data(Qt.ItemDataRole.UserRole)
        if not kalem_id:
            return
        
        # Birim miktar ve birim fiyatı al
        miktar_item = self.ihale_kalem_table.item(row, 3)
        fiyat_item = self.ihale_kalem_table.item(row, 5)
        
        if not miktar_item or not fiyat_item:
            return
        
        try:
            miktar_text = miktar_item.text().replace(",", ".").strip()
            fiyat_text = fiyat_item.text().replace(",", ".").replace("₺", "").strip()
            
            birim_miktar = float(miktar_text) if miktar_text else 0.0
            birim_fiyat = float(fiyat_text) if fiyat_text else 0.0
            
            # Toplam hesapla
            toplam = birim_miktar * birim_fiyat
            
            # Veritabanını güncelle
            self.db.update_ihale_kalem(kalem_id, birim_miktar=birim_miktar, birim_fiyat=birim_fiyat, toplam=toplam)
            
            # Toplam sütununu güncelle
            toplam_item = QTableWidgetItem(f"{toplam:,.2f} ₺")
            toplam_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            toplam_item.setFlags(toplam_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.ihale_kalem_table.setItem(row, 6, toplam_item)
            
            # Genel toplamı güncelle
            self.update_ihale_total()
            
        except ValueError:
            QMessageBox.warning(self, "Hata", "Geçersiz sayı formatı")
    
    def update_ihale_total(self) -> None:
        """İhale toplamını güncelle"""
        toplam = 0.0
        for row in range(self.ihale_kalem_table.rowCount()):
            toplam_item = self.ihale_kalem_table.item(row, 6)
            if toplam_item:
                toplam_text = toplam_item.text().replace("₺", "").replace(",", ".").strip()
                try:
                    toplam += float(toplam_text)
                except ValueError:
                    pass
        
        self.ihale_total_label.setText(f"Toplam: {toplam:,.2f} ₺")
    
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
                    ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                    ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ]))
                story.append(info_table)
                story.append(Spacer(1, 0.5*cm))
                
                # Kalem listesi
                if kalemler:
                    story.append(Paragraph("İhale Kalem Listesi", styles['Heading2']))
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
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 10),
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

