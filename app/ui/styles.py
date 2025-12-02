"""
Qt Style Sheets (QSS)
Koyu kurumsal tema stilleri
"""


def apply_dark_theme(app) -> None:
    """
    Koyu kurumsal temayı uygula.
    
    Args:
        app: QApplication instance
    """
    dark_theme = """
    /* Genel Stil */
    QMainWindow {
        background-color: #1e1e1e;
        color: #d4d4d4;
    }
    
    QWidget {
        background-color: #1e1e1e;
        color: #d4d4d4;
        font-family: "Segoe UI", Arial, sans-serif;
        font-size: 10pt;
    }
    
    /* Menü Çubuğu */
    QMenuBar {
        background-color: #252526;
        color: #d4d4d4;
        border-bottom: 1px solid #3e3e42;
        padding: 2px;
    }
    
    QMenuBar::item {
        background-color: transparent;
        padding: 4px 8px;
    }
    
    QMenuBar::item:selected {
        background-color: #2a2d2e;
    }
    
    QMenu {
        background-color: #252526;
        color: #d4d4d4;
        border: 1px solid #3e3e42;
    }
    
    QMenu::item {
        padding: 4px 20px;
    }
    
    QMenu::item:selected {
        background-color: #094771;
    }
    
    /* Durum Çubuğu */
    QStatusBar {
        background-color: #007acc;
        color: #ffffff;
        border-top: 1px solid #3e3e42;
    }
    
    /* Butonlar */
    QPushButton {
        background-color: #0e639c;
        color: #ffffff;
        border: none;
        border-radius: 3px;
        padding: 6px 12px;
        min-width: 80px;
    }
    
    QPushButton:hover {
        background-color: #1177bb;
    }
    
    QPushButton:pressed {
        background-color: #0a4d73;
    }
    
    QPushButton:disabled {
        background-color: #3e3e42;
        color: #6e6e6e;
    }
    
    /* Tablo */
    QTableWidget {
        background-color: #252526;
        color: #d4d4d4;
        border: 1px solid #3e3e42;
        gridline-color: #3e3e42;
        selection-background-color: #094771;
        selection-color: #ffffff;
    }
    
    QTableWidget::item {
        padding: 4px;
    }
    
    QTableWidget::item:selected {
        background-color: #094771;
        color: #ffffff;
    }
    
    QTableWidget::item:alternate {
        background-color: #2a2d2e;
    }
    
    QHeaderView::section {
        background-color: #2d2d30;
        color: #d4d4d4;
        padding: 6px;
        border: none;
        border-right: 1px solid #3e3e42;
        border-bottom: 1px solid #3e3e42;
        font-weight: bold;
    }
    
    QHeaderView::section:hover {
        background-color: #3e3e42;
    }
    
    /* Ağaç Widget */
    QTreeWidget {
        background-color: #252526;
        color: #d4d4d4;
        border: 1px solid #3e3e42;
        selection-background-color: #094771;
        selection-color: #ffffff;
    }
    
    QTreeWidget::item {
        padding: 4px;
    }
    
    QTreeWidget::item:selected {
        background-color: #094771;
        color: #ffffff;
    }
    
    QTreeWidget::item:hover {
        background-color: #2a2d2e;
    }
    
    /* Sekmeler */
    QTabWidget::pane {
        border: 1px solid #3e3e42;
        background-color: #1e1e1e;
    }
    
    QTabBar::tab {
        background-color: #2d2d30;
        color: #d4d4d4;
        padding: 8px 16px;
        border: 1px solid #3e3e42;
        border-bottom: none;
        margin-right: 2px;
    }
    
    QTabBar::tab:selected {
        background-color: #1e1e1e;
        color: #ffffff;
        border-bottom: 2px solid #007acc;
    }
    
    QTabBar::tab:hover {
        background-color: #2a2d2e;
    }
    
    /* Label */
    QLabel {
        color: #d4d4d4;
    }
    
    /* Line Edit */
    QLineEdit {
        background-color: #3c3c3c;
        color: #d4d4d4;
        border: 1px solid #3e3e42;
        border-radius: 3px;
        padding: 4px;
    }
    
    QLineEdit:focus {
        border: 1px solid #007acc;
    }
    
    /* Combo Box */
    QComboBox {
        background-color: #3c3c3c;
        color: #d4d4d4;
        border: 1px solid #3e3e42;
        border-radius: 3px;
        padding: 4px;
        min-width: 120px;
    }
    
    QComboBox:hover {
        border: 1px solid #007acc;
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
        background-color: #252526;
        color: #d4d4d4;
        selection-background-color: #094771;
        border: 1px solid #3e3e42;
    }
    
    /* Text Edit */
    QTextEdit {
        background-color: #252526;
        color: #d4d4d4;
        border: 1px solid #3e3e42;
        border-radius: 3px;
    }
    
    /* Group Box */
    QGroupBox {
        border: 1px solid #3e3e42;
        border-radius: 3px;
        margin-top: 10px;
        padding-top: 10px;
        font-weight: bold;
    }
    
    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 5px;
        background-color: #1e1e1e;
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





