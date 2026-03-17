"""
Minimal Dialogs Stub
Dialog modülü syntax hataları nedeniyle minimal versiyona dönüştürüldü.
"""

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel


class MetrajItemDialog(QDialog):
    """Metraj kalemi dialog (minimal)"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Metraj Kalemi")
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Metraj kalemi ekle"))
        self.setLayout(layout)


class TaseronOfferDialog(QDialog):
    """Taşeron teklifi dialog (minimal)"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Taşeron Teklifi")
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Taşeron teklifi"))
        self.setLayout(layout)
