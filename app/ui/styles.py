"""
Qt Style Sheets (QSS)
Modern inşaat teması - Gün batımı gökyüzü ve modern mimari esinli
"""


def apply_dark_theme(app) -> None:
    """
    Modern inşaat temasını uygula (gün batımı gökyüzü ve modern mimari esinli).
    
    Args:
        app: QApplication instance
    """
    dark_theme = """
    /* Genel Stil - Wireframe şehir teması (koyu gri-mavi) */
    QMainWindow {
        background-color: #0a0a0a;
        color: #e0e0e0;
    }
    
    QWidget {
        background-color: #0a0a0a;
        color: #e0e0e0;
        font-family: "Segoe UI", Arial, sans-serif;
        font-size: 10pt;
        font-weight: 500;
    }
    
    /* Menü Çubuğu - Wireframe teması */
    QMenuBar {
        background-color: rgba(20, 25, 30, 200);
        color: #e0e0e0;
        border-bottom: 2px solid #00BFFF;
        padding: 4px;
        font-weight: 600;
    }
    
    QMenuBar::item {
        background-color: transparent;
        padding: 6px 12px;
        border-radius: 4px;
    }
    
    QMenuBar::item:selected {
        background-color: rgba(0, 191, 255, 150);
        color: #ffffff;
    }
    
    QMenu {
        background-color: rgba(20, 25, 30, 240);
        color: #e0e0e0;
        border: 2px solid #00BFFF;
        border-radius: 6px;
    }
    
    QMenu::item {
        padding: 6px 24px;
        border-radius: 3px;
    }
    
    QMenu::item:selected {
        background-color: rgba(0, 191, 255, 200);
        color: #ffffff;
    }
    
    /* Durum Çubuğu - Mavi tonları */
    QStatusBar {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 #2a3a4a, stop:1 #1a2a3a);
        color: #e0e0e0;
        border-top: 2px solid #00BFFF;
        font-weight: bold;
    }
    
    /* Butonlar - Wireframe teması (mavi tonları) */
    QPushButton {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 #2a4a6a, stop:1 #1a3a5a);
        color: #e0e0e0;
        border: 2px solid #00BFFF;
        border-radius: 6px;
        padding: 8px 16px;
        min-width: 80px;
        font-weight: bold;
    }
    
    QPushButton:hover {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 #3a5a7a, stop:1 #2a4a6a);
        border: 2px solid #00DDFF;
        color: #ffffff;
    }
    
    QPushButton:pressed {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 #1a3a5a, stop:1 #0a2a4a);
    }
    
    QPushButton:disabled {
        background-color: #1a1a2a;
        color: #6e6e6e;
        border: 2px solid #3a3a4a;
    }
    
    /* Tablo - Wireframe teması */
    QTableWidget {
        background-color: #14191e;
        color: #e0e0e0;
        border: 2px solid #00BFFF;
        border-radius: 8px;
        gridline-color: #0066cc;
        selection-background-color: #00BFFF;
        selection-color: #ffffff;
        font-weight: 500;
    }
    
    QTableWidget::item {
        padding: 6px;
        border: none;
    }
    
    QTableWidget::item:selected {
        background-color: #00BFFF;
        color: #ffffff;
    }
    
    QTableWidget::item:alternate {
        background-color: rgba(42, 45, 46, 180);
    }
    
    QHeaderView::section {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 #2a4a6a, stop:1 #1a3a5a);
        color: #ffffff;
        padding: 8px;
        border: none;
        border-right: 1px solid #00BFFF;
        border-bottom: 2px solid #00BFFF;
        font-weight: bold;
    }
    
    QHeaderView::section:hover {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 #3a5a7a, stop:1 #2a4a6a);
    }
    
    /* Ağaç Widget - Yarı saydam, görselle uyumlu */
    QTreeWidget {
        background-color: rgba(37, 37, 38, 200);
        color: #ffffff;
        border: 2px solid #ffa07a;
        border-radius: 8px;
        selection-background-color: rgba(255, 160, 122, 220);
        selection-color: #ffffff;
        font-weight: 500;
    }
    
    QTreeWidget::item {
        padding: 6px;
        border-radius: 3px;
    }
    
    QTreeWidget::item:selected {
        background-color: rgba(255, 160, 122, 250);
        color: #ffffff;
    }
    
    QTreeWidget::item:hover {
        background-color: rgba(255, 182, 193, 150);
    }
    
    /* Sekmeler - Yarı saydam, görselle uyumlu */
    QTabWidget::pane {
        border: 2px solid #00BFFF;
        border-radius: 8px;
        background-color: rgba(20, 25, 30, 220);
        top: -1px;
    }
    
    QTabBar::tab {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 rgba(45, 45, 48, 200), stop:1 rgba(37, 37, 38, 200));
        color: #ffffff;
        padding: 10px 20px;
        border: 2px solid rgba(255, 160, 122, 100);
        border-bottom: none;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
        margin-right: 3px;
        min-width: 100px;
    }
    
    QTabBar::tab:selected {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 #3a5a7a, stop:1 #2a4a6a);
        color: #ffffff;
        border: 2px solid #00BFFF;
        border-bottom: 3px solid #00BFFF;
        font-weight: bold;
    }
    
    QTabBar::tab:hover {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 #3a4a5a, stop:1 #2a3a4a);
        border: 2px solid #00DDFF;
        color: #e0e0e0;
    }
    
    /* Label */
    QLabel {
        color: #d4d4d4;
    }
    
    /* Line Edit - Yarı saydam, görselle uyumlu */
    QLineEdit {
        background-color: rgba(60, 60, 60, 200);
        color: #ffffff;
        border: 2px solid #ffa07a;
        border-radius: 6px;
        padding: 6px;
        font-weight: 500;
    }
    
    QLineEdit:focus {
        border: 2px solid #ffb6c1;
        background-color: rgba(60, 60, 60, 240);
    }
    
    /* Combo Box - Yarı saydam, görselle uyumlu */
    QComboBox {
        background-color: rgba(60, 60, 60, 200);
        color: #ffffff;
        border: 2px solid #ffa07a;
        border-radius: 6px;
        padding: 6px;
        min-width: 120px;
        font-weight: 500;
    }
    
    QComboBox:hover {
        border: 2px solid #ffb6c1;
        background-color: rgba(60, 60, 60, 240);
    }
    
    QComboBox::drop-down {
        border: none;
        width: 20px;
    }
    
    QComboBox::down-arrow {
        image: none;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 4px solid #d4d4d4;
        width: 0;
        height: 0;
    }
    
    QComboBox QAbstractItemView {
        background-color: rgba(37, 37, 38, 240);
        color: #ffffff;
        selection-background-color: rgba(255, 160, 122, 220);
        border: 2px solid #ffa07a;
        border-radius: 6px;
    }
    
    /* Text Edit - Yarı saydam, görselle uyumlu */
    QTextEdit {
        background-color: rgba(37, 37, 38, 200);
        color: #ffffff;
        border: 2px solid #ffa07a;
        border-radius: 8px;
        font-weight: 500;
    }
    
    /* Group Box - Yarı saydam, görselle uyumlu */
    QGroupBox {
        border: 2px solid #ffa07a;
        border-radius: 8px;
        margin-top: 12px;
        padding-top: 12px;
        font-weight: 600;
        color: #ffffff;
        background-color: rgba(30, 30, 30, 180);
    }
    
    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 8px;
        background-color: rgba(255, 160, 122, 220);
        color: #ffffff;
        border-radius: 4px;
        font-weight: 600;
    }
    
    /* Spin Box */
    QDoubleSpinBox, QSpinBox {
        background-color: #3c3c3c;
        color: #d4d4d4;
        border: 1px solid #3e3e42;
        border-radius: 3px;
        padding: 4px;
    }
    
    QDoubleSpinBox:focus, QSpinBox:focus {
        border: 1px solid #007acc;
    }
    
    /* Scroll Bar */
    QScrollBar:vertical {
        background-color: #252526;
        width: 12px;
        border: none;
    }
    
    QScrollBar::handle:vertical {
        background-color: #424242;
        min-height: 20px;
        border-radius: 6px;
    }
    
    QScrollBar::handle:vertical:hover {
        background-color: #4e4e4e;
    }
    
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0px;
    }
    
    QScrollBar:horizontal {
        background-color: #252526;
        height: 12px;
        border: none;
    }
    
    QScrollBar::handle:horizontal {
        background-color: #424242;
        min-width: 20px;
        border-radius: 6px;
    }
    
    QScrollBar::handle:horizontal:hover {
        background-color: #4e4e4e;
    }
    
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
        width: 0px;
    }
    """
    
    app.setStyleSheet(dark_theme)










