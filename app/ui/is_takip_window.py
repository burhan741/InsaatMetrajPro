"""
İş Takip Penceresi
Taşeron modu için iş takibi
"""

from typing import Optional, List, Dict, Any
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QPushButton, QMessageBox,
    QLabel, QDateEdit, QDoubleSpinBox, QComboBox, QTextEdit
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QFont

from app.core.database import DatabaseManager


class IsTakipWindow(QMainWindow):
    """İş takip yönetim penceresi"""
    
    def __init__(self, db: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db = db
        self.current_is_id: Optional[int] = None
        
        self.init_ui()
    
    def init_ui(self):
        """Arayüzü oluştur"""
        self.setWindowTitle("İş Takibi")
        self.setGeometry(100, 100, 1200, 800)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # TODO: Implement iş takip UI
        label = QLabel("İş Takibi")
        label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(label)
        
        self.statusBar().showMessage("Hazır")
