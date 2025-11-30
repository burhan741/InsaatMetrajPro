"""
Veritabanı İşlemleri
SQLite kullanarak proje ve metraj verilerini yönetir
"""

import sqlite3
import os
from datetime import datetime


class DatabaseManager:
    """Veritabanı yönetim sınıfı"""
    
    def __init__(self, db_path="metraj.db"):
        """Veritabanı bağlantısını başlat"""
        self.db_path = db_path
        self.init_database()
        
    def get_connection(self):
        """Veritabanı bağlantısı al"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Sözlük benzeri erişim
        return conn
        
    def init_database(self):
        """Veritabanı tablolarını oluştur"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Projeler tablosu
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        
        # Metraj kalemleri tablosu
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                quantity REAL NOT NULL,
                unit TEXT NOT NULL,
                unit_price REAL DEFAULT 0,
                total REAL DEFAULT 0,
                category TEXT,
                notes TEXT,
                created_at TEXT,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            )
        """)
        
        # Kategoriler tablosu
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT
            )
        """)
        
        # Birim fiyatlar tablosu
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS unit_prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_name TEXT NOT NULL,
                unit TEXT NOT NULL,
                price REAL NOT NULL,
                category TEXT,
                updated_at TEXT
            )
        """)
        
        # Varsayılan kategorileri ekle
        default_categories = [
            ("Toprak İşleri", "Kazı, dolgu, tesviye işleri"),
            ("Beton İşleri", "Beton, demir, kalıp işleri"),
            ("Duvar İşleri", "Tuğla, briket, gazbeton"),
            ("Sıva İşleri", "İç ve dış sıva"),
            ("Boya İşleri", "İç ve dış boya"),
            ("Döşeme İşleri", "Seramik, parke, laminat"),
            ("Çatı İşleri", "Kiremit, membran, izolasyon"),
            ("Elektrik Tesisatı", "Elektrik işleri"),
            ("Su Tesisatı", "Su ve kanalizasyon"),
            ("Isıtma/Soğutma", "Klima ve ısıtma sistemleri")
        ]
        
        cursor.executemany("""
            INSERT OR IGNORE INTO categories (name, description)
            VALUES (?, ?)
        """, default_categories)
        
        conn.commit()
        conn.close()
        
    def create_project(self, name, description=""):
        """Yeni proje oluştur"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO projects (name, description, created_at, updated_at)
            VALUES (?, ?, ?, ?)
        """, (name, description, now, now))
        
        project_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return project_id
        
    def get_all_projects(self):
        """Tüm projeleri getir"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM projects ORDER BY created_at DESC")
        projects = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        return projects
        
    def get_project(self, project_id):
        """Belirli bir projeyi getir"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
        row = cursor.fetchone()
        
        conn.close()
        return dict(row) if row else None
        
    def update_project(self, project_id, name, description=""):
        """Projeyi güncelle"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        cursor.execute("""
            UPDATE projects
            SET name = ?, description = ?, updated_at = ?
            WHERE id = ?
        """, (name, description, now, project_id))
        
        conn.commit()
        conn.close()
        return cursor.rowcount > 0
        
    def delete_project(self, project_id):
        """Projeyi sil (ilişkili kalemler de silinir)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        
        conn.commit()
        conn.close()
        return cursor.rowcount > 0
        
    def add_item(self, project_id, name, quantity, unit, unit_price=0, category="", notes=""):
        """Yeni metraj kalemi ekle"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        total = quantity * unit_price
        now = datetime.now().isoformat()
        
        cursor.execute("""
            INSERT INTO items (project_id, name, quantity, unit, unit_price, total, category, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (project_id, name, quantity, unit, unit_price, total, category, notes, now))
        
        item_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return item_id
        
    def get_project_items(self, project_id):
        """Projeye ait tüm kalemleri getir"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM items
            WHERE project_id = ?
            ORDER BY category, name
        """, (project_id,))
        
        items = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return items
        
    def update_item(self, item_id, name, quantity, unit, unit_price, category="", notes=""):
        """Metraj kalemini güncelle"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        total = quantity * unit_price
        
        cursor.execute("""
            UPDATE items
            SET name = ?, quantity = ?, unit = ?, unit_price = ?, total = ?, category = ?, notes = ?
            WHERE id = ?
        """, (name, quantity, unit, unit_price, total, category, notes, item_id))
        
        conn.commit()
        conn.close()
        return cursor.rowcount > 0
        
    def delete_item(self, item_id):
        """Metraj kalemini sil"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM items WHERE id = ?", (item_id,))
        
        conn.commit()
        conn.close()
        return cursor.rowcount > 0
        
    def get_project_total(self, project_id):
        """Projenin toplam maliyetini hesapla"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT SUM(total) as total
            FROM items
            WHERE project_id = ?
        """, (project_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        return result['total'] if result['total'] else 0
        
    def get_categories(self):
        """Tüm kategorileri getir"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM categories ORDER BY name")
        categories = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        return categories
        
    def add_unit_price(self, item_name, unit, price, category=""):
        """Birim fiyat ekle/güncelle"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        cursor.execute("""
            INSERT OR REPLACE INTO unit_prices (item_name, unit, price, category, updated_at)
            VALUES (?, ?, ?, ?, ?)
        """, (item_name, unit, price, category, now))
        
        conn.commit()
        conn.close()
        
    def get_unit_price(self, item_name, unit):
        """Birim fiyat getir"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT price FROM unit_prices
            WHERE item_name = ? AND unit = ?
            ORDER BY updated_at DESC
            LIMIT 1
        """, (item_name, unit))
        
        result = cursor.fetchone()
        conn.close()
        
        return result['price'] if result else None


