"""
Başlangıç Ekranı - Müteahhit/Taşeron Seçimi
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QPixmap
from pathlib import Path


class StartupDialog(QDialog):
    """Başlangıç ekranı - Kullanıcı tipi seçimi"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.user_type = None  # 'muteahhit' veya 'taseron'
        self.init_ui()
    
    def init_ui(self):
        """Arayüzü oluştur"""
        self.setWindowTitle("İnşaat Metraj Pro - Hoş Geldiniz")
        self.setGeometry(300, 300, 500, 400)
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1a2e;
            }
            QLabel {
                color: #e0e0e0;
            }
            QPushButton {
                background-color: #16213e;
                color: #e0e0e0;
                border: 2px solid #00BFFF;
                border-radius: 10px;
                padding: 20px;
                font-size: 16pt;
                font-weight: bold;
                min-height: 80px;
            }
            QPushButton:hover {
                background-color: #00BFFF;
                color: #1a1a2e;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(30)
        layout.setContentsMargins(40, 40, 40, 40)
        
        # Başlık
        title = QLabel("🏗️ İnşaat Metraj Pro")
        title.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #00BFFF;")
        layout.addWidget(title)
        
        subtitle = QLabel("Lütfen kullanıcı tipinizi seçin:")
        subtitle.setFont(QFont("Arial", 12))
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)
        
        layout.addStretch()
        
        # Butonlar
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(20)
        
        # Müteahhit butonu
        btn_muteahhit = QPushButton("👷 MÜTEAHHİT")
        btn_muteahhit.clicked.connect(lambda: self.select_user_type('muteahhit'))
        btn_layout.addWidget(btn_muteahhit)
        
        # Taşeron butonu
        btn_taseron = QPushButton("🔧 TAŞERON")
        btn_taseron.clicked.connect(lambda: self.select_user_type('taseron'))
        btn_layout.addWidget(btn_taseron)
        
        layout.addLayout(btn_layout)
        layout.addStretch()
        
        # Alt bilgi
        info = QLabel("Müteahhit: Proje yönetimi, metraj, ihale hazırlama\n"
                     "Taşeron: İş takibi, puantaj, gelir/gider yönetimi")
        info.setFont(QFont("Arial", 9))
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.setStyleSheet("color: #888;")
        layout.addWidget(info)
    
    def select_user_type(self, user_type: str):
        """Kullanıcı tipini seç ve dialogu kapat"""
        self.user_type = user_type
        self.accept()

