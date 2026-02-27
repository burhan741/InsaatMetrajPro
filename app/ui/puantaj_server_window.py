"""
Puantaj Sunucu Yönetim Penceresi
Mobil puantaj API sunucusunu başlatma ve yönetme
"""

from PyQt6.QtWidgets import (
 QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
 QGroupBox, QFormLayout, QLineEdit, QSpinBox, QTextEdit,
 QMessageBox, QFrame, QGridLayout
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QDesktopServices
from PyQt6.QtCore import QUrl
import subprocess
import sys
import os
import socket
import logging

logger = logging.getLogger(__name__)


class ServerThread(QThread):
 """Flask sunucusu için ayrı thread"""
 log_signal = pyqtSignal(str)
 started_signal = pyqtSignal(str, int) # ip, port
 error_signal = pyqtSignal(str)

 def __init__(self, host, port, username, password):
 super().__init__()
 self.host = host
 self.port = port
 self.username = username
 self.password = password
 self._running = False

 def run(self):
 try:
 # API modülünü import et
 from app.api import puantaj_api

 # Ayarları güncelle
 puantaj_api.API_USERNAME = self.username
 puantaj_api.API_PASSWORD = self.password

 # Tabloları oluştur
 puantaj_api.init_puantaj_tables()

 self._running = True
 local_ip = self.get_local_ip()
 self.started_signal.emit(local_ip, self.port)
 self.log_signal.emit(f"Sunucu başlatıldı: http://{local_ip}:{self.port}")

 # Flask'ı çalıştır
 puantaj_api.app.run(
 host=self.host,
 port=self.port,
 debug=False,
 use_reloader=False,
 threaded=True
 )

 except Exception as e:
 self.error_signal.emit(str(e))
 logger.error(f"Sunucu hatası: {e}")

 def get_local_ip(self):
 try:
 s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
 s.connect(("8.8.8.8", 80))
 ip = s.getsockname()[0]
 s.close()
 return ip
 except:
 return "127.0.0.1"

 def stop(self):
 self._running = False
 self.terminate()


class PuantajServerWindow(QWidget):
 """Puantaj sunucu yönetim penceresi"""

 def __init__(self, db=None):
 super().__init__()
 self.db = db
 self.server_thread = None
 self.server_running = False
 self.init_ui()

 def init_ui(self):
 self.setWindowTitle("Mobil Puantaj Sunucusu")
 self.setMinimumSize(600, 500)

 layout = QVBoxLayout()

 # Başlık
 title = QLabel(" Mobil Puantaj Sunucusu")
 title.setStyleSheet("font-size: 22px; font-weight: bold; color: #2c3e50; margin: 10px;")
 layout.addWidget(title)

 # Açıklama
 desc = QLabel("iOS/Android telefonunuzdan işçi puantajı girmek için sunucuyu başlatın.")
 desc.setStyleSheet("color: #666; margin-bottom: 15px;")
 desc.setWordWrap(True)
 layout.addWidget(desc)

 # Ayarlar
 settings_group = QGroupBox("Sunucu Ayarları")
 settings_layout = QFormLayout()

 self.port_input = QSpinBox()
 self.port_input.setRange(1000, 65535)
 self.port_input.setValue(5000)
 settings_layout.addRow("Port:", self.port_input)

 self.username_input = QLineEdit("santiye")
 settings_layout.addRow("Kullanıcı Adı:", self.username_input)

 self.password_input = QLineEdit("2024")
 settings_layout.addRow("Şifre:", self.password_input)

 settings_group.setLayout(settings_layout)
 layout.addWidget(settings_group)

 # Kontrol butonları
 btn_layout = QHBoxLayout()

 self.start_btn = QPushButton("▶ Sunucuyu Başlat")
 self.start_btn.setStyleSheet("""
 QPushButton {
 background-color: #27ae60;
 color: white;
 padding: 12px 30px;
 font-size: 14px;
 font-weight: bold;
 border-radius: 6px;
 }
 QPushButton:hover { background-color: #219a52; }
 """)
 self.start_btn.clicked.connect(self.toggle_server)
 btn_layout.addWidget(self.start_btn)

 self.open_browser_btn = QPushButton(" Tarayıcıda Aç")
 self.open_browser_btn.setEnabled(False)
 self.open_browser_btn.clicked.connect(self.open_in_browser)
 btn_layout.addWidget(self.open_browser_btn)

 layout.addLayout(btn_layout)

 # Bağlantı Bilgileri
 self.connection_group = QGroupBox("Bağlantı Bilgileri")
 conn_layout = QGridLayout()

 self.status_label = QLabel(" Sunucu kapalı")
 self.status_label.setStyleSheet("font-size: 14px; font-weight: bold;")
 conn_layout.addWidget(self.status_label, 0, 0, 1, 2)

 conn_layout.addWidget(QLabel("Yerel Adres:"), 1, 0)
 self.local_url_label = QLabel("-")
 self.local_url_label.setStyleSheet("font-weight: bold; color: #3498db;")
 self.local_url_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
 conn_layout.addWidget(self.local_url_label, 1, 1)

 conn_layout.addWidget(QLabel("Kullanıcı:"), 2, 0)
 self.user_info_label = QLabel("-")
 conn_layout.addWidget(self.user_info_label, 2, 1)

 self.connection_group.setLayout(conn_layout)
 layout.addWidget(self.connection_group)

 # iOS Kurulum Talimatları
 ios_group = QGroupBox(" iPhone'da Kurulum")
 ios_layout = QVBoxLayout()

 instructions = """
 <ol style="margin:5px; padding-left:20px;">
 <li>Telefonunuzun <b>aynı WiFi</b> ağına bağlı olduğundan emin olun</li>
 <li><b>Safari</b>'yi açın (Chrome değil!)</li>
 <li>Yukarıdaki adresi girin</li>
 <li>Kullanıcı adı ve şifreyi girin</li>
 <li>Safari'de <b>Paylaş</b> butonuna tıklayın ()</li>
 <li><b>"Ana Ekrana Ekle"</b> seçin</li>
 <li>Artık ana ekrandan uygulama gibi açabilirsiniz!</li>
 </ol>
 """
 ios_label = QLabel(instructions)
 ios_label.setWordWrap(True)
 ios_label.setStyleSheet("font-size: 12px;")
 ios_layout.addWidget(ios_label)

 ios_group.setLayout(ios_layout)
 layout.addWidget(ios_group)

 # Log alanı
 self.log_text = QTextEdit()
 self.log_text.setReadOnly(True)
 self.log_text.setMaximumHeight(100)
 self.log_text.setStyleSheet("background-color: #1a1a2e; color: #00ff00; font-family: monospace;")
 layout.addWidget(self.log_text)

 layout.addStretch()
 self.setLayout(layout)

 def toggle_server(self):
 if self.server_running:
 self.stop_server()
 else:
 self.start_server()

 def start_server(self):
 try:
 port = self.port_input.value()
 username = self.username_input.text()
 password = self.password_input.text()

 self.server_thread = ServerThread('0.0.0.0', port, username, password)
 self.server_thread.log_signal.connect(self.add_log)
 self.server_thread.started_signal.connect(self.on_server_started)
 self.server_thread.error_signal.connect(self.on_server_error)
 self.server_thread.start()

 self.add_log("Sunucu başlatılıyor...")

 except Exception as e:
 QMessageBox.critical(self, "Hata", f"Sunucu başlatılamadı:\n{str(e)}")

 def on_server_started(self, ip, port):
 self.server_running = True
 self.start_btn.setText(" Sunucuyu Durdur")
 self.start_btn.setStyleSheet("""
 QPushButton {
 background-color: #e74c3c;
 color: white;
 padding: 12px 30px;
 font-size: 14px;
 font-weight: bold;
 border-radius: 6px;
 }
 QPushButton:hover { background-color: #c0392b; }
 """)

 self.status_label.setText(" Sunucu çalışıyor")
 self.status_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #27ae60;")

 url = f"http://{ip}:{port}"
 self.local_url_label.setText(url)
 self.user_info_label.setText(f"{self.username_input.text()} / {self.password_input.text()}")

 self.open_browser_btn.setEnabled(True)
 self.port_input.setEnabled(False)
 self.username_input.setEnabled(False)
 self.password_input.setEnabled(False)

 def on_server_error(self, error):
 self.add_log(f"HATA: {error}")
 QMessageBox.critical(self, "Sunucu Hatası", error)
 self.stop_server()

 def stop_server(self):
 if self.server_thread:
 self.server_thread.stop()
 self.server_thread = None

 self.server_running = False
 self.start_btn.setText("▶ Sunucuyu Başlat")
 self.start_btn.setStyleSheet("""
 QPushButton {
 background-color: #27ae60;
 color: white;
 padding: 12px 30px;
 font-size: 14px;
 font-weight: bold;
 border-radius: 6px;
 }
 QPushButton:hover { background-color: #219a52; }
 """)

 self.status_label.setText(" Sunucu kapalı")
 self.status_label.setStyleSheet("font-size: 14px; font-weight: bold;")
 self.local_url_label.setText("-")
 self.user_info_label.setText("-")

 self.open_browser_btn.setEnabled(False)
 self.port_input.setEnabled(True)
 self.username_input.setEnabled(True)
 self.password_input.setEnabled(True)

 self.add_log("Sunucu durduruldu")

 def open_in_browser(self):
 url = self.local_url_label.text()
 if url and url != "-":
 QDesktopServices.openUrl(QUrl(url))

 def add_log(self, message):
 from datetime import datetime
 timestamp = datetime.now().strftime("%H:%M:%S")
 self.log_text.append(f"[{timestamp}] {message}")

 def closeEvent(self, event):
 if self.server_running:
 reply = QMessageBox.question(
 self, "Onay",
 "Sunucu çalışıyor. Durdurup kapatmak istiyor musunuz?",
 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
 )
 if reply == QMessageBox.StandardButton.Yes:
 self.stop_server()
 event.accept()
 else:
 event.ignore()
 else:
 event.accept()
