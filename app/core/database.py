"""
Veritabanı Yöneticisi
SQLite veritabanı bağlantısı ve işlemleri için core modül
"""

import sqlite3
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
from contextlib import contextmanager


class DatabaseManager:
    """
    SQLite veritabanı yönetim sınıfı.
    
    Offline-first yaklaşım ile yerel veritabanı işlemlerini yönetir.
    İleride online senkronizasyon için genişletilebilir yapı.
    """
    
    def __init__(self, db_path: Optional[Path] = None) -> None:
        """
        Veritabanı yöneticisini başlat.
        
        Args:
            db_path: Veritabanı dosya yolu. None ise varsayılan konum kullanılır.
        """
        if db_path is None:
            # Varsayılan: proje kök dizininde
            db_path = Path(__file__).parent.parent.parent / "data" / "insaat_metraj.db"
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
        
    @contextmanager
    def get_connection(self):
        """
        Veritabanı bağlantısı context manager.
        
        Yields:
            sqlite3.Connection: Veritabanı bağlantısı
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row  # Sözlük benzeri erişim
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
            
    def _init_database(self) -> None:
        """Veritabanı tablolarını oluştur."""
        with self.get_connection() as conn:
            # WAL mode aktif et (daha hızlı okuma/yazma)
            conn.execute("PRAGMA journal_mode=WAL")
            # Synchronous mode'u optimize et (güvenlik vs hız dengesi)
            conn.execute("PRAGMA synchronous=NORMAL")
            # Cache size artır (daha hızlı sorgular)
            conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
            # Foreign key kontrolünü aktif et
            conn.execute("PRAGMA foreign_keys=ON")
            
            cursor = conn.cursor()
            
            # Projeler tablosu
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ad TEXT NOT NULL,
                    aciklama TEXT,
                    olusturma_tarihi TEXT NOT NULL,
                    guncelleme_tarihi TEXT,
                    durum TEXT DEFAULT 'aktif',
                    toplam_maliyet REAL DEFAULT 0,
                    notlar TEXT
                )
            """)
            
            # Proje notları sütunu ekle (migration)
            try:
                cursor.execute("ALTER TABLE projects ADD COLUMN notlar TEXT")
            except sqlite3.OperationalError:
                # Sütun zaten varsa hata verme
                pass
            
            # Şablonlar tablosu
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sablonlar (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ad TEXT NOT NULL,
                    aciklama TEXT,
                    olusturma_tarihi TEXT NOT NULL,
                    guncelleme_tarihi TEXT
                )
            """)
            
            # Şablon kalemleri tablosu
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sablon_kalemleri (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sablon_id INTEGER NOT NULL,
                    poz_no TEXT,
                    tanim TEXT NOT NULL,
                    kategori TEXT,
                    miktar REAL DEFAULT 0,
                    birim TEXT,
                    birim_fiyat REAL DEFAULT 0,
                    toplam REAL DEFAULT 0,
                    FOREIGN KEY (sablon_id) REFERENCES sablonlar(id) ON DELETE CASCADE
                )
            """)
            
            # Birim fiyatlar tablosu (poz bazlı, tarihli fiyat takibi)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS birim_fiyatlar (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    poz_id INTEGER,
                    poz_no TEXT,
                    birim_fiyat REAL NOT NULL,
                    tarih TEXT NOT NULL,
                    kaynak TEXT,
                    aciklama TEXT,
                    aktif INTEGER DEFAULT 1,
                    FOREIGN KEY (poz_id) REFERENCES pozlar(id) ON DELETE SET NULL
                )
            """)
            
            # İhaleler tablosu
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ihaleler (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ad TEXT NOT NULL,
                    aciklama TEXT,
                    olusturma_tarihi TEXT NOT NULL,
                    guncelleme_tarihi TEXT,
                    durum TEXT DEFAULT 'hazirlaniyor'
                )
            """)
            
            # İhale kalemleri tablosu
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ihale_kalemleri (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ihale_id INTEGER NOT NULL,
                    poz_no TEXT,
                    poz_tanim TEXT,
                    kategori TEXT,
                    birim_miktar REAL DEFAULT 0,
                    birim TEXT,
                    birim_fiyat REAL DEFAULT 0,
                    toplam REAL DEFAULT 0,
                    sira_no INTEGER,
                    FOREIGN KEY (ihale_id) REFERENCES ihaleler(id) ON DELETE CASCADE
                )
            """)
            
            # Pozlar tablosu (Çevre ve Şehircilik Bakanlığı verileri için)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pozlar (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    poz_no TEXT NOT NULL UNIQUE,
                    tanim TEXT NOT NULL,
                    birim TEXT NOT NULL,
                    resmi_fiyat REAL DEFAULT 0,
                    kategori TEXT,
                    aciklama TEXT,
                    fire_orani REAL DEFAULT 0.05,
                    guncelleme_tarihi TEXT
                )
            """)
            
            # Mevcut tablolara fire_orani sütunu ekle (migration)
            try:
                cursor.execute("ALTER TABLE pozlar ADD COLUMN fire_orani REAL DEFAULT 0.05")
            except sqlite3.OperationalError:
                # Sütun zaten varsa hata verme
                pass
            
            # Metraj kalemleri tablosu
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS metraj_kalemleri (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    proje_id INTEGER NOT NULL,
                    poz_no TEXT,
                    tanim TEXT NOT NULL,
                    miktar REAL NOT NULL DEFAULT 0,
                    birim TEXT NOT NULL,
                    birim_fiyat REAL DEFAULT 0,
                    toplam REAL DEFAULT 0,
                    kategori TEXT,
                    notlar TEXT,
                    olusturma_tarihi TEXT,
                    FOREIGN KEY (proje_id) REFERENCES projects(id) ON DELETE CASCADE
                )
            """)
            
            # Taşeron teklifleri tablosu
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS taseron_teklifleri (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    proje_id INTEGER NOT NULL,
                    firma_adi TEXT NOT NULL,
                    kalem_id INTEGER,
                    poz_no TEXT,
                    tanim TEXT,
                    miktar REAL,
                    birim TEXT,
                    fiyat REAL NOT NULL,
                    toplam REAL,
                    teklif_tarihi TEXT,
                    durum TEXT DEFAULT 'beklemede',
                    notlar TEXT,
                    FOREIGN KEY (proje_id) REFERENCES projects(id) ON DELETE CASCADE,
                    FOREIGN KEY (kalem_id) REFERENCES metraj_kalemleri(id) ON DELETE SET NULL
                )
            """)
            
            # Malzemeler tablosu
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS malzemeler (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ad TEXT NOT NULL UNIQUE,
                    birim TEXT NOT NULL,
                    kategori TEXT,
                    aciklama TEXT,
                    birim_fiyat REAL DEFAULT 0,
                    olusturma_tarihi TEXT
                )
            """)
            
            # Mevcut tablolara birim_fiyat sütunu ekle (migration)
            try:
                cursor.execute("ALTER TABLE malzemeler ADD COLUMN birim_fiyat REAL DEFAULT 0")
            except sqlite3.OperationalError:
                # Sütun zaten varsa hata verme
                pass
            
            # Malzeme formülleri tablosu (Poz → Malzeme ilişkileri)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS malzeme_formulleri (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    poz_id INTEGER NOT NULL,
                    malzeme_id INTEGER NOT NULL,
                    miktar REAL NOT NULL,
                    birim TEXT NOT NULL,
                    formul_tipi TEXT DEFAULT 'direkt',
                    aciklama TEXT,
                    FOREIGN KEY (poz_id) REFERENCES pozlar(id) ON DELETE CASCADE,
                    FOREIGN KEY (malzeme_id) REFERENCES malzemeler(id) ON DELETE CASCADE,
                    UNIQUE(poz_id, malzeme_id)
                )
            """)
            
            # Birim dönüşümleri tablosu
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS birim_donusumleri (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    malzeme_id INTEGER,
                    kaynak_birim TEXT NOT NULL,
                    hedef_birim TEXT NOT NULL,
                    donusum_katsayisi REAL NOT NULL,
                    FOREIGN KEY (malzeme_id) REFERENCES malzemeler(id) ON DELETE CASCADE
                )
            """)
            
            # İndeksler
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_projects_durum 
                ON projects(durum)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_metraj_proje 
                ON metraj_kalemleri(proje_id)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_taseron_proje 
                ON taseron_teklifleri(proje_id)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_malzeme_formul_poz 
                ON malzeme_formulleri(poz_id)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_malzeme_formul_malzeme 
                ON malzeme_formulleri(malzeme_id)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_birim_fiyat_poz 
                ON birim_fiyatlar(poz_id)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_birim_fiyat_poz_no 
                ON birim_fiyatlar(poz_no)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_birim_fiyat_tarih 
                ON birim_fiyatlar(tarih)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_ihale_kalem_ihale 
                ON ihale_kalemleri(ihale_id)
            """)
            
            conn.commit()
            
    # Proje İşlemleri
    def create_project(self, ad: str, aciklama: str = "") -> int:
        """
        Yeni proje oluştur.
        
        Args:
            ad: Proje adı
            aciklama: Proje açıklaması
            
        Returns:
            int: Oluşturulan projenin ID'si
        """
        now = datetime.now().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO projects (ad, aciklama, olusturma_tarihi, guncelleme_tarihi)
                VALUES (?, ?, ?, ?)
            """, (ad, aciklama, now, now))
            return cursor.lastrowid
            
    def get_all_projects(self) -> List[Dict[str, Any]]:
        """
        Tüm projeleri getir.
        
        Returns:
            List[Dict]: Proje listesi
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM projects 
                ORDER BY olusturma_tarihi DESC
            """)
            return [dict(row) for row in cursor.fetchall()]
            
    def get_project(self, project_id: int) -> Optional[Dict[str, Any]]:
        """
        Belirli bir projeyi getir.
        
        Args:
            project_id: Proje ID'si
            
        Returns:
            Optional[Dict]: Proje bilgileri veya None
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
            
    def update_project(self, project_id: int, **kwargs) -> bool:
        """
        Projeyi güncelle.
        
        Args:
            project_id: Proje ID'si
            **kwargs: Güncellenecek alanlar
            
        Returns:
            bool: Başarı durumu
        """
        if not kwargs:
            return False
            
        now = datetime.now().isoformat()
        fields = ", ".join([f"{k} = ?" for k in kwargs.keys()])
        fields += ", guncelleme_tarihi = ?"
        values = list(kwargs.values()) + [now, project_id]
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE projects SET {fields} WHERE id = ?", values)
            return cursor.rowcount > 0
            
    def delete_project(self, project_id: int) -> bool:
        """
        Projeyi sil.
        
        Args:
            project_id: Proje ID'si
            
        Returns:
            bool: Başarı durumu
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            return cursor.rowcount > 0
            
    # Poz İşlemleri
    def add_poz(self, poz_no: str, tanim: str, birim: str, 
                resmi_fiyat: float = 0, kategori: str = "", fire_orani: float = 0.05) -> int:
        """
        Yeni poz ekle.
        
        Args:
            poz_no: Poz numarası
            tanim: Poz tanımı
            birim: Birim (m, m², m³, adet, vb.)
            resmi_fiyat: Resmi birim fiyat
            kategori: Poz kategorisi
            fire_orani: Fire/atık oranı (0.05 = %5, varsayılan)
            
        Returns:
            int: Oluşturulan pozun ID'si
        """
        now = datetime.now().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO pozlar (poz_no, tanim, birim, resmi_fiyat, kategori, fire_orani, guncelleme_tarihi)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (poz_no, tanim, birim, resmi_fiyat, kategori, fire_orani, now))
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                # Poz zaten varsa güncelle
                cursor.execute("""
                    UPDATE pozlar 
                    SET tanim = ?, birim = ?, resmi_fiyat = ?, kategori = ?, fire_orani = ?, guncelleme_tarihi = ?
                    WHERE poz_no = ?
                """, (tanim, birim, resmi_fiyat, kategori, fire_orani, now, poz_no))
                cursor.execute("SELECT id FROM pozlar WHERE poz_no = ?", (poz_no,))
                return cursor.fetchone()['id']
                
    def get_poz(self, poz_no: str) -> Optional[Dict[str, Any]]:
        """
        Poz bilgilerini getir.
        
        Args:
            poz_no: Poz numarası
            
        Returns:
            Optional[Dict]: Poz bilgileri veya None
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM pozlar WHERE poz_no = ?", (poz_no,))
            row = cursor.fetchone()
            return dict(row) if row else None
            
    def search_pozlar(self, search_term: str) -> List[Dict[str, Any]]:
        """
        Poz arama.
        
        Args:
            search_term: Arama terimi
            
        Returns:
            List[Dict]: Bulunan pozlar
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM pozlar 
                WHERE poz_no LIKE ? OR tanim LIKE ?
                ORDER BY poz_no
                LIMIT 100
            """, (f"%{search_term}%", f"%{search_term}%"))
            return [dict(row) for row in cursor.fetchall()]
            
    # Metraj Kalemleri İşlemleri
    def add_metraj_kalem(self, proje_id: int, tanim: str, miktar: float,
                         birim: str, birim_fiyat: float = 0, 
                         poz_no: str = "", kategori: str = "") -> int:
        """
        Metraj kalemi ekle.
        
        Args:
            proje_id: Proje ID'si
            tanim: Kalem tanımı
            miktar: Miktar
            birim: Birim
            birim_fiyat: Birim fiyat
            poz_no: Poz numarası (opsiyonel)
            kategori: Kategori
            
        Returns:
            int: Oluşturulan kalemin ID'si
        """
        toplam = miktar * birim_fiyat
        now = datetime.now().isoformat()
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO metraj_kalemleri 
                (proje_id, poz_no, tanim, miktar, birim, birim_fiyat, toplam, kategori, olusturma_tarihi)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (proje_id, poz_no, tanim, miktar, birim, birim_fiyat, toplam, kategori, now))
            
            # Proje toplam maliyetini güncelle
            self._update_project_total(conn, proje_id)
            
            return cursor.lastrowid
            
    def get_project_metraj(self, proje_id: int) -> List[Dict[str, Any]]:
        """
        Projeye ait metraj kalemlerini getir.
        
        Args:
            proje_id: Proje ID'si
            
        Returns:
            List[Dict]: Metraj kalemleri listesi
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM metraj_kalemleri
                WHERE proje_id = ?
                ORDER BY kategori, tanim
            """, (proje_id,))
            return [dict(row) for row in cursor.fetchall()]
            
    def update_metraj_kalem(self, item_id: int, **kwargs) -> bool:
        """
        Metraj kalemini güncelle.
        
        Args:
            item_id: Kalem ID'si
            **kwargs: Güncellenecek alanlar
            
        Returns:
            bool: Başarı durumu
        """
        if not kwargs:
            return False
            
        # Toplam hesapla
        if 'miktar' in kwargs and 'birim_fiyat' in kwargs:
            kwargs['toplam'] = kwargs['miktar'] * kwargs['birim_fiyat']
        elif 'miktar' in kwargs or 'birim_fiyat' in kwargs:
            # Mevcut değerleri al
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT miktar, birim_fiyat FROM metraj_kalemleri WHERE id = ?", (item_id,))
                row = cursor.fetchone()
                if row:
                    miktar = kwargs.get('miktar', row['miktar'])
                    birim_fiyat = kwargs.get('birim_fiyat', row['birim_fiyat'])
                    kwargs['toplam'] = miktar * birim_fiyat
                    
        fields = ", ".join([f"{k} = ?" for k in kwargs.keys()])
        values = list(kwargs.values()) + [item_id]
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE metraj_kalemleri SET {fields} WHERE id = ?", values)
            
            # Proje toplamını güncelle
            cursor.execute("SELECT proje_id FROM metraj_kalemleri WHERE id = ?", (item_id,))
            row = cursor.fetchone()
            if row:
                self._update_project_total(conn, row['proje_id'])
                
            return cursor.rowcount > 0
            
    def delete_item(self, item_id: int) -> bool:
        """
        Metraj kalemini sil.
        
        Args:
            item_id: Kalem ID'si
            
        Returns:
            bool: Başarı durumu
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Önce proje ID'sini al
            cursor.execute("SELECT proje_id FROM metraj_kalemleri WHERE id = ?", (item_id,))
            row = cursor.fetchone()
            
            if row:
                proje_id = row['proje_id']
                # Kalemi sil
                cursor.execute("DELETE FROM metraj_kalemleri WHERE id = ?", (item_id,))
                # Proje toplamını güncelle
                self._update_project_total(conn, proje_id)
                return cursor.rowcount > 0
            return False
            
    def _update_project_total(self, conn: sqlite3.Connection, proje_id: int) -> None:
        """Proje toplam maliyetini güncelle."""
        cursor = conn.cursor()
        cursor.execute("""
            SELECT SUM(toplam) as toplam FROM metraj_kalemleri
            WHERE proje_id = ?
        """, (proje_id,))
        result = cursor.fetchone()
        toplam = result['toplam'] if result['toplam'] else 0
        
        cursor.execute("""
            UPDATE projects SET toplam_maliyet = ? WHERE id = ?
        """, (toplam, proje_id))
        
    # Taşeron Teklifleri İşlemleri
    def add_taseron_teklif(self, proje_id: int, firma_adi: str, 
                           kalem_id: Optional[int], fiyat: float,
                           poz_no: str = "", tanim: str = "",
                           miktar: float = 0, birim: str = "") -> int:
        """
        Taşeron teklifi ekle.
        
        Args:
            proje_id: Proje ID'si
            firma_adi: Firma adı
            kalem_id: Metraj kalemi ID'si (opsiyonel)
            fiyat: Teklif fiyatı
            poz_no: Poz numarası
            tanim: Kalem tanımı
            miktar: Miktar
            birim: Birim
            
        Returns:
            int: Oluşturulan teklifin ID'si
        """
        toplam = miktar * fiyat if miktar > 0 else fiyat
        now = datetime.now().isoformat()
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO taseron_teklifleri
                (proje_id, firma_adi, kalem_id, poz_no, tanim, miktar, birim, fiyat, toplam, teklif_tarihi)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (proje_id, firma_adi, kalem_id, poz_no, tanim, miktar, birim, fiyat, toplam, now))
            return cursor.lastrowid
            
    def get_taseron_teklifleri(self, proje_id: int) -> List[Dict[str, Any]]:
        """
        Projeye ait taşeron tekliflerini getir.
        
        Args:
            proje_id: Proje ID'si
            
        Returns:
            List[Dict]: Taşeron teklifleri listesi
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM taseron_teklifleri
                WHERE proje_id = ?
                ORDER BY firma_adi, tanim
            """, (proje_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def update_taseron_teklif(self, offer_id: int, **kwargs) -> bool:
        """
        Taşeron teklifini güncelle.
        
        Args:
            offer_id: Teklif ID'si
            **kwargs: Güncellenecek alanlar
            
        Returns:
            bool: Başarı durumu
        """
        if not kwargs:
            return False
            
        # Toplam hesapla
        if 'miktar' in kwargs and 'fiyat' in kwargs:
            kwargs['toplam'] = kwargs['miktar'] * kwargs['fiyat']
        elif 'miktar' in kwargs or 'fiyat' in kwargs:
            # Mevcut değerleri al
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT miktar, fiyat FROM taseron_teklifleri WHERE id = ?", (offer_id,))
                row = cursor.fetchone()
                if row:
                    miktar = kwargs.get('miktar', row['miktar'])
                    fiyat = kwargs.get('fiyat', row['fiyat'])
                    kwargs['toplam'] = miktar * fiyat if miktar and fiyat else 0
                    
        fields = ", ".join([f"{k} = ?" for k in kwargs.keys()])
        values = list(kwargs.values()) + [offer_id]
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE taseron_teklifleri SET {fields} WHERE id = ?", values)
            return cursor.rowcount > 0
            
    def delete_taseron_teklif(self, offer_id: int) -> bool:
        """
        Taşeron teklifini sil.
        
        Args:
            offer_id: Teklif ID'si
            
        Returns:
            bool: Başarı durumu
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM taseron_teklifleri WHERE id = ?", (offer_id,))
            return cursor.rowcount > 0
    
    # Malzeme İşlemleri
    def add_malzeme(self, ad: str, birim: str, kategori: str = "", aciklama: str = "", birim_fiyat: float = 0.0) -> int:
        """
        Yeni malzeme ekle.
        
        Args:
            ad: Malzeme adı
            birim: Birim (kg, m³, adet, vb.)
            kategori: Malzeme kategorisi
            aciklama: Açıklama
            birim_fiyat: Birim fiyat (varsayılan 0)
            
        Returns:
            int: Oluşturulan malzemenin ID'si
        """
        now = datetime.now().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO malzemeler (ad, birim, kategori, aciklama, birim_fiyat, olusturma_tarihi)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (ad, birim, kategori, aciklama, birim_fiyat, now))
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                # Malzeme zaten varsa güncelle (birim fiyat hariç)
                cursor.execute("""
                    UPDATE malzemeler 
                    SET birim = ?, kategori = ?, aciklama = ?
                    WHERE ad = ? AND birim_fiyat = 0
                """, (birim, kategori, aciklama, ad))
                cursor.execute("SELECT id FROM malzemeler WHERE ad = ?", (ad,))
                row = cursor.fetchone()
                return row['id'] if row else 0
                
    def get_malzeme(self, malzeme_id: int) -> Optional[Dict[str, Any]]:
        """Malzeme bilgilerini getir."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM malzemeler WHERE id = ?", (malzeme_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
            
    def get_malzeme_by_name(self, ad: str) -> Optional[Dict[str, Any]]:
        """Malzeme adına göre getir."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM malzemeler WHERE ad = ?", (ad,))
            row = cursor.fetchone()
            return dict(row) if row else None
            
    def get_all_malzemeler(self) -> List[Dict[str, Any]]:
        """Tüm malzemeleri getir."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM malzemeler ORDER BY kategori, ad")
            return [dict(row) for row in cursor.fetchall()]
    
    # Malzeme Formülü İşlemleri
    def add_malzeme_formulu(self, poz_id: int, malzeme_id: int, miktar: float, 
                           birim: str, formul_tipi: str = "direkt", aciklama: str = "") -> int:
        """
        Poz için malzeme formülü ekle.
        
        Args:
            poz_id: Poz ID'si
            malzeme_id: Malzeme ID'si
            miktar: Birim poz başına malzeme miktarı
            birim: Malzeme birimi
            formul_tipi: Formül tipi (direkt, harç, beton_karisimi, vb.)
            aciklama: Açıklama
            
        Returns:
            int: Oluşturulan formülün ID'si
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO malzeme_formulleri 
                    (poz_id, malzeme_id, miktar, birim, formul_tipi, aciklama)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (poz_id, malzeme_id, miktar, birim, formul_tipi, aciklama))
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                # Formül zaten varsa güncelle
                cursor.execute("""
                    UPDATE malzeme_formulleri 
                    SET miktar = ?, birim = ?, formul_tipi = ?, aciklama = ?
                    WHERE poz_id = ? AND malzeme_id = ?
                """, (miktar, birim, formul_tipi, aciklama, poz_id, malzeme_id))
                cursor.execute("""
                    SELECT id FROM malzeme_formulleri 
                    WHERE poz_id = ? AND malzeme_id = ?
                """, (poz_id, malzeme_id))
                row = cursor.fetchone()
                return row['id'] if row else 0
                
    def get_poz_formulleri(self, poz_id: int) -> List[Dict[str, Any]]:
        """
        Poz için malzeme formüllerini getir.
        
        Args:
            poz_id: Poz ID'si
            
        Returns:
            List[Dict]: Formül listesi (malzeme bilgileri dahil)
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    mf.id,
                    mf.poz_id,
                    mf.malzeme_id,
                    mf.miktar,
                    mf.birim,
                    mf.formul_tipi,
                    mf.aciklama,
                    m.ad as malzeme_adi,
                    m.birim as malzeme_birim,
                    m.kategori as malzeme_kategori
                FROM malzeme_formulleri mf
                JOIN malzemeler m ON mf.malzeme_id = m.id
                WHERE mf.poz_id = ?
                ORDER BY m.kategori, m.ad
            """, (poz_id,))
            return [dict(row) for row in cursor.fetchall()]
            
    def get_poz_formulleri_by_poz_no(self, poz_no: str) -> List[Dict[str, Any]]:
        """Poz numarasına göre formülleri getir."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    mf.id,
                    mf.poz_id,
                    mf.malzeme_id,
                    mf.miktar,
                    mf.birim,
                    mf.formul_tipi,
                    mf.aciklama,
                    m.ad as malzeme_adi,
                    m.birim as malzeme_birim,
                    m.kategori as malzeme_kategori
                FROM malzeme_formulleri mf
                JOIN malzemeler m ON mf.malzeme_id = m.id
                JOIN pozlar p ON mf.poz_id = p.id
                WHERE p.poz_no = ?
                ORDER BY m.kategori, m.ad
            """, (poz_no,))
            return [dict(row) for row in cursor.fetchall()]
    
    # Birim Dönüşüm İşlemleri
    def add_birim_donusum(self, malzeme_id: Optional[int], kaynak_birim: str, 
                         hedef_birim: str, donusum_katsayisi: float) -> int:
        """Birim dönüşümü ekle."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO birim_donusumleri 
                (malzeme_id, kaynak_birim, hedef_birim, donusum_katsayisi)
                VALUES (?, ?, ?, ?)
            """, (malzeme_id, kaynak_birim, hedef_birim, donusum_katsayisi))
            return cursor.lastrowid
            
    def get_birim_donusum(self, kaynak_birim: str, hedef_birim: str, 
                         malzeme_id: Optional[int] = None) -> Optional[float]:
        """Birim dönüşüm katsayısını getir."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if malzeme_id:
                cursor.execute("""
                    SELECT donusum_katsayisi FROM birim_donusumleri
                    WHERE malzeme_id = ? AND kaynak_birim = ? AND hedef_birim = ?
                """, (malzeme_id, kaynak_birim, hedef_birim))
            else:
                cursor.execute("""
                    SELECT donusum_katsayisi FROM birim_donusumleri
                    WHERE malzeme_id IS NULL AND kaynak_birim = ? AND hedef_birim = ?
                """, (kaynak_birim, hedef_birim))
            row = cursor.fetchone()
            return row['donusum_katsayisi'] if row else None
    
    # Yedekleme ve Geri Yükleme İşlemleri
    def backup_project(self, project_id: int, backup_path: Path) -> bool:
        """
        Projeyi yedekle (JSON formatında).
        
        Args:
            project_id: Yedeklenecek proje ID'si
            backup_path: Yedek dosyasının kaydedileceği yol
            
        Returns:
            bool: Başarılı ise True
        """
        try:
            # Proje bilgilerini al
            project = self.get_project(project_id)
            if not project:
                return False
            
            # Metraj kalemlerini al
            metraj_items = self.get_project_metraj(project_id)
            
            # Taşeron tekliflerini al
            taseron_offers = self.get_taseron_teklifleri(project_id)
            
            # Yedek verisi oluştur
            backup_data = {
                'version': '1.0',
                'backup_date': datetime.now().isoformat(),
                'project': dict(project),
                'metraj_items': [dict(item) for item in metraj_items],
                'taseron_offers': [dict(offer) for offer in taseron_offers],
                'taseron_teklifleri': [dict(offer) for offer in taseron_offers]  # Uyumluluk için
            }
            
            # JSON dosyasına kaydet
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2)
            
            return True
            
        except Exception as e:
            print(f"Yedekleme hatası: {e}")
            return False
    
    def restore_project(self, backup_path: Path, new_project_name: Optional[str] = None) -> Optional[int]:
        """
        Yedekten proje geri yükle.
        
        Args:
            backup_path: Yedek dosyasının yolu
            new_project_name: Yeni proje adı (None ise eski ad kullanılır)
            
        Returns:
            Optional[int]: Geri yüklenen projenin ID'si, hata durumunda None
        """
        try:
            # Yedek dosyasını oku
            with open(backup_path, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)
            
            # Proje bilgilerini al
            project_data = backup_data.get('project', {})
            metraj_items = backup_data.get('metraj_items', [])
            # Uyumluluk için hem 'taseron_offers' hem 'taseron_teklifleri' kontrol et
            taseron_offers = backup_data.get('taseron_offers', backup_data.get('taseron_teklifleri', []))
            
            # Yeni proje oluştur
            project_name = new_project_name or project_data.get('ad', 'Geri Yüklenen Proje')
            project_id = self.create_project(
                ad=project_name,
                aciklama=project_data.get('aciklama', '')
            )
            
            # Metraj kalemlerini geri yükle
            for item in metraj_items:
                try:
                    self.add_item(
                        proje_id=project_id,
                        poz_no=item.get('poz_no', ''),
                        tanim=item.get('tanim', ''),
                        kategori=item.get('kategori', ''),
                        miktar=item.get('miktar', 0),
                        birim=item.get('birim', ''),
                        birim_fiyat=item.get('birim_fiyat', 0),
                        toplam=item.get('toplam', 0)
                    )
                except Exception as e:
                    print(f"Metraj kalemi geri yükleme hatası: {e}")
                    continue
            
            # Taşeron tekliflerini geri yükle
            for offer in taseron_offers:
                try:
                    # Önce kalem ID'sini bul (poz_no'ya göre)
                    kalem_id = None
                    if offer.get('poz_no'):
                        metraj = self.get_project_metraj(project_id)
                        for item in metraj:
                            if item.get('poz_no') == offer.get('poz_no'):
                                kalem_id = item.get('id')
                                break
                    
                    self.add_taseron_teklif(
                        proje_id=project_id,
                        firma_adi=offer.get('firma_adi', ''),
                        kalem_id=kalem_id,
                        fiyat=offer.get('fiyat', 0),
                        poz_no=offer.get('poz_no', ''),
                        tanim=offer.get('tanim', ''),
                        miktar=offer.get('miktar', 0),
                        birim=offer.get('birim', '')
                    )
                except Exception as e:
                    print(f"Taşeron teklifi geri yükleme hatası: {e}")
                    continue
            
            return project_id
            
        except Exception as e:
            print(f"Geri yükleme hatası: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def backup_all_projects(self, backup_path: Path) -> bool:
        """
        Tüm projeleri yedekle.
        
        Args:
            backup_path: Yedek dosyasının kaydedileceği yol
            
        Returns:
            bool: Başarılı ise True
        """
        try:
            projects = self.get_all_projects()
            backup_data = {
                'version': '1.0',
                'backup_date': datetime.now().isoformat(),
                'backup_type': 'all_projects',
                'projects': []
            }
            
            for project in projects:
                project_id = project['id']
                project_backup = {
                    'project': dict(project),
                    'metraj_items': [dict(item) for item in self.get_project_metraj(project_id)],
                    'taseron_offers': [dict(offer) for offer in self.get_taseron_teklifleri(project_id)]
                }
                backup_data['projects'].append(project_backup)
            
            # JSON dosyasına kaydet
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2)
            
            return True
            
        except Exception as e:
            print(f"Tüm projeleri yedekleme hatası: {e}")
            return False
    
    # Şablon İşlemleri
    def create_template(self, ad: str, aciklama: str = "") -> int:
        """
        Yeni şablon oluştur.
        
        Args:
            ad: Şablon adı
            aciklama: Şablon açıklaması
            
        Returns:
            int: Oluşturulan şablonun ID'si
        """
        now = datetime.now().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sablonlar (ad, aciklama, olusturma_tarihi, guncelleme_tarihi)
                VALUES (?, ?, ?, ?)
            """, (ad, aciklama, now, now))
            return cursor.lastrowid
    
    def get_all_templates(self) -> List[Dict[str, Any]]:
        """
        Tüm şablonları getir.
        
        Returns:
            List[Dict]: Şablon listesi
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM sablonlar
                ORDER BY olusturma_tarihi DESC
            """)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_template(self, template_id: int) -> Optional[Dict[str, Any]]:
        """
        Şablon bilgilerini getir.
        
        Args:
            template_id: Şablon ID'si
            
        Returns:
            Optional[Dict]: Şablon bilgileri
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sablonlar WHERE id = ?", (template_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_template_items(self, template_id: int) -> List[Dict[str, Any]]:
        """
        Şablon kalemlerini getir.
        
        Args:
            template_id: Şablon ID'si
            
        Returns:
            List[Dict]: Şablon kalemleri listesi
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM sablon_kalemleri
                WHERE sablon_id = ?
                ORDER BY id
            """, (template_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def add_template_item(self, sablon_id: int, poz_no: str = "", tanim: str = "",
                         kategori: str = "", miktar: float = 0, birim: str = "",
                         birim_fiyat: float = 0, toplam: float = 0) -> int:
        """
        Şablona kalem ekle.
        
        Args:
            sablon_id: Şablon ID'si
            poz_no: Poz numarası
            tanim: Kalem tanımı
            kategori: Kategori
            miktar: Miktar
            birim: Birim
            birim_fiyat: Birim fiyat
            toplam: Toplam
            
        Returns:
            int: Eklenen kalemin ID'si
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sablon_kalemleri 
                (sablon_id, poz_no, tanim, kategori, miktar, birim, birim_fiyat, toplam)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (sablon_id, poz_no, tanim, kategori, miktar, birim, birim_fiyat, toplam))
            return cursor.lastrowid
    
    def create_project_from_template(self, template_id: int, project_name: str, 
                                    project_description: str = "") -> Optional[int]:
        """
        Şablondan proje oluştur.
        
        Args:
            template_id: Şablon ID'si
            project_name: Yeni proje adı
            project_description: Yeni proje açıklaması
            
        Returns:
            Optional[int]: Oluşturulan projenin ID'si
        """
        try:
            # Yeni proje oluştur
            project_id = self.create_project(project_name, project_description)
            
            # Şablon kalemlerini al
            template_items = self.get_template_items(template_id)
            
            # Kalemleri projeye ekle
            for item in template_items:
                self.add_item(
                    proje_id=project_id,
                    poz_no=item.get('poz_no', ''),
                    tanim=item.get('tanim', ''),
                    kategori=item.get('kategori', ''),
                    miktar=item.get('miktar', 0),
                    birim=item.get('birim', ''),
                    birim_fiyat=item.get('birim_fiyat', 0),
                    toplam=item.get('toplam', 0)
                )
            
            return project_id
            
        except Exception as e:
            print(f"Şablondan proje oluşturma hatası: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def create_template_from_project(self, project_id: int, template_name: str, 
                                    template_description: str = "") -> Optional[int]:
        """
        Projeden şablon oluştur.
        
        Args:
            project_id: Proje ID'si
            template_name: Şablon adı
            template_description: Şablon açıklaması
            
        Returns:
            Optional[int]: Oluşturulan şablonun ID'si
        """
        try:
            # Yeni şablon oluştur
            template_id = self.create_template(template_name, template_description)
            
            # Proje kalemlerini al
            project_items = self.get_project_metraj(project_id)
            
            # Kalemleri şablona ekle
            for item in project_items:
                self.add_template_item(
                    sablon_id=template_id,
                    poz_no=item.get('poz_no', ''),
                    tanim=item.get('tanim', ''),
                    kategori=item.get('kategori', ''),
                    miktar=item.get('miktar', 0),
                    birim=item.get('birim', ''),
                    birim_fiyat=item.get('birim_fiyat', 0),
                    toplam=item.get('toplam', 0)
                )
            
            return template_id
            
        except Exception as e:
            print(f"Projeden şablon oluşturma hatası: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def delete_template(self, template_id: int) -> bool:
        """
        Şablonu sil.
        
        Args:
            template_id: Şablon ID'si
            
        Returns:
            bool: Başarı durumu
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM sablonlar WHERE id = ?", (template_id,))
            return cursor.rowcount > 0
    
    def update_template(self, template_id: int, **kwargs) -> bool:
        """
        Şablonu güncelle.
        
        Args:
            template_id: Şablon ID'si
            **kwargs: Güncellenecek alanlar
            
        Returns:
            bool: Başarı durumu
        """
        if not kwargs:
            return False
            
        now = datetime.now().isoformat()
        fields = ", ".join([f"{k} = ?" for k in kwargs.keys()])
        fields += ", guncelleme_tarihi = ?"
        values = list(kwargs.values()) + [now, template_id]
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE sablonlar SET {fields} WHERE id = ?", values)
            return cursor.rowcount > 0
    
    # Birim Fiyat İşlemleri
    def add_birim_fiyat(self, poz_id: Optional[int] = None, poz_no: str = "",
                       birim_fiyat: float = 0, tarih: Optional[str] = None,
                       kaynak: str = "", aciklama: str = "", aktif: bool = True) -> int:
        """
        Birim fiyat ekle.
        
        Args:
            poz_id: Poz ID'si (opsiyonel)
            poz_no: Poz numarası
            birim_fiyat: Birim fiyat
            tarih: Tarih (None ise bugün)
            kaynak: Fiyat kaynağı (ör: "Tedarikçi A", "Resmi Fiyat")
            aciklama: Açıklama
            aktif: Aktif mi (varsayılan: True)
            
        Returns:
            int: Eklenen fiyatın ID'si
        """
        if tarih is None:
            tarih = datetime.now().isoformat()
        
        # Eğer poz_id yoksa ama poz_no varsa, poz_id'yi bul
        if not poz_id and poz_no:
            poz = self.get_poz_by_no(poz_no)
            if poz:
                poz_id = poz['id']
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Yeni fiyat eklendiğinde eski fiyatları pasif yap (aynı poz için)
            if poz_id:
                cursor.execute("""
                    UPDATE birim_fiyatlar SET aktif = 0
                    WHERE poz_id = ? AND aktif = 1
                """, (poz_id,))
            elif poz_no:
                cursor.execute("""
                    UPDATE birim_fiyatlar SET aktif = 0
                    WHERE poz_no = ? AND aktif = 1
                """, (poz_no,))
            
            # Yeni fiyatı ekle
            cursor.execute("""
                INSERT INTO birim_fiyatlar 
                (poz_id, poz_no, birim_fiyat, tarih, kaynak, aciklama, aktif)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (poz_id, poz_no, birim_fiyat, tarih, kaynak, aciklama, 1 if aktif else 0))
            return cursor.lastrowid
    
    def get_birim_fiyat(self, poz_id: Optional[int] = None, poz_no: str = "",
                        aktif_only: bool = True) -> Optional[Dict[str, Any]]:
        """
        Poz için aktif birim fiyatı getir.
        
        Args:
            poz_id: Poz ID'si
            poz_no: Poz numarası
            aktif_only: Sadece aktif fiyatları getir
            
        Returns:
            Optional[Dict]: Birim fiyat bilgisi
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if poz_id:
                if aktif_only:
                    cursor.execute("""
                        SELECT * FROM birim_fiyatlar
                        WHERE poz_id = ? AND aktif = 1
                        ORDER BY tarih DESC
                        LIMIT 1
                    """, (poz_id,))
                else:
                    cursor.execute("""
                        SELECT * FROM birim_fiyatlar
                        WHERE poz_id = ?
                        ORDER BY tarih DESC
                        LIMIT 1
                    """, (poz_id,))
            elif poz_no:
                if aktif_only:
                    cursor.execute("""
                        SELECT * FROM birim_fiyatlar
                        WHERE poz_no = ? AND aktif = 1
                        ORDER BY tarih DESC
                        LIMIT 1
                    """, (poz_no,))
                else:
                    cursor.execute("""
                        SELECT * FROM birim_fiyatlar
                        WHERE poz_no = ?
                        ORDER BY tarih DESC
                        LIMIT 1
                    """, (poz_no,))
            else:
                return None
            
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_birim_fiyat_gecmisi(self, poz_id: Optional[int] = None, poz_no: str = "",
                                limit: int = 50) -> List[Dict[str, Any]]:
        """
        Poz için fiyat geçmişini getir.
        
        Args:
            poz_id: Poz ID'si
            poz_no: Poz numarası
            limit: Maksimum kayıt sayısı
            
        Returns:
            List[Dict]: Fiyat geçmişi listesi
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if poz_id:
                cursor.execute("""
                    SELECT * FROM birim_fiyatlar
                    WHERE poz_id = ?
                    ORDER BY tarih DESC
                    LIMIT ?
                """, (poz_id, limit))
            elif poz_no:
                cursor.execute("""
                    SELECT * FROM birim_fiyatlar
                    WHERE poz_no = ?
                    ORDER BY tarih DESC
                    LIMIT ?
                """, (poz_no, limit))
            else:
                return []
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_all_birim_fiyatlar(self, aktif_only: bool = True) -> List[Dict[str, Any]]:
        """
        Tüm birim fiyatları getir.
        
        Args:
            aktif_only: Sadece aktif fiyatları getir
            
        Returns:
            List[Dict]: Birim fiyat listesi
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if aktif_only:
                cursor.execute("""
                    SELECT bf.*, p.tanim as poz_tanim, p.birim as poz_birim
                    FROM birim_fiyatlar bf
                    LEFT JOIN pozlar p ON bf.poz_id = p.id
                    WHERE bf.aktif = 1
                    ORDER BY bf.tarih DESC
                """)
            else:
                cursor.execute("""
                    SELECT bf.*, p.tanim as poz_tanim, p.birim as poz_birim
                    FROM birim_fiyatlar bf
                    LEFT JOIN pozlar p ON bf.poz_id = p.id
                    ORDER BY bf.tarih DESC
                """)
            return [dict(row) for row in cursor.fetchall()]
    
    def compare_birim_fiyatlar(self, poz_no: str) -> Dict[str, Any]:
        """
        Poz için fiyat karşılaştırması yap.
        
        Args:
            poz_no: Poz numarası
            
        Returns:
            Dict: Karşılaştırma sonuçları (en düşük, en yüksek, ortalama, kaynaklar)
        """
        fiyatlar = self.get_birim_fiyat_gecmisi(poz_no=poz_no, limit=100)
        
        if not fiyatlar:
            return {
                'poz_no': poz_no,
                'fiyat_sayisi': 0,
                'en_dusuk': None,
                'en_yuksek': None,
                'ortalama': None,
                'kaynaklar': []
            }
        
        fiyat_degerleri = [f['birim_fiyat'] for f in fiyatlar if f.get('birim_fiyat')]
        
        if not fiyat_degerleri:
            return {
                'poz_no': poz_no,
                'fiyat_sayisi': 0,
                'en_dusuk': None,
                'en_yuksek': None,
                'ortalama': None,
                'kaynaklar': []
            }
        
        en_dusuk = min(fiyat_degerleri)
        en_yuksek = max(fiyat_degerleri)
        ortalama = sum(fiyat_degerleri) / len(fiyat_degerleri)
        
        # Kaynakları topla
        kaynaklar = {}
        for f in fiyatlar:
            kaynak = f.get('kaynak', 'Belirtilmemiş')
            if kaynak not in kaynaklar:
                kaynaklar[kaynak] = []
            kaynaklar[kaynak].append(f['birim_fiyat'])
        
        return {
            'poz_no': poz_no,
            'fiyat_sayisi': len(fiyatlar),
            'en_dusuk': en_dusuk,
            'en_yuksek': en_yuksek,
            'ortalama': ortalama,
            'kaynaklar': kaynaklar,
            'fiyatlar': fiyatlar
        }
    
    def delete_pdf_imported_data(self) -> Dict[str, int]:
        """
        PDF'den içe aktarılan tüm pozları ve birim fiyatları sil.
        
        Returns:
            Dict: Silinen kayıt sayıları {'pozlar': int, 'birim_fiyatlar': int}
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Önce PDF Import kaynaklı birim fiyatların poz_no'larını topla
            cursor.execute("""
                SELECT DISTINCT poz_no 
                FROM birim_fiyatlar 
                WHERE kaynak = 'PDF Import' AND poz_no IS NOT NULL
            """)
            pdf_poz_nos = [row['poz_no'] for row in cursor.fetchall()]
            
            # 2. Bu poz numaralarına sahip pozları sil (sadece PDF'den eklenenleri)
            # PDF'den eklenen pozlar genellikle tanımında "PDF'den içe aktarıldı" içerir
            # veya sadece PDF Import kaynaklı birim fiyatları vardır
            deleted_poz_count = 0
            for poz_no in pdf_poz_nos:
                # Pozun başka kaynaklı birim fiyatı var mı kontrol et
                cursor.execute("""
                    SELECT COUNT(*) as count 
                    FROM birim_fiyatlar 
                    WHERE poz_no = ? AND (kaynak != 'PDF Import' OR kaynak IS NULL)
                """, (poz_no,))
                other_sources = cursor.fetchone()['count']
                
                # Eğer başka kaynak yoksa, pozun PDF'den eklenmiş olma ihtimali yüksek
                # Pozu sil (tanımı "PDF'den içe aktarıldı" içeriyorsa veya başka kaynak yoksa)
                if other_sources == 0:
                    cursor.execute("""
                        DELETE FROM pozlar 
                        WHERE poz_no = ? 
                        AND (tanim LIKE '%PDF%içe aktarıldı%' OR tanim LIKE '%PDF Import%' OR tanim = '' OR tanim IS NULL)
                    """, (poz_no,))
                    deleted_poz_count += cursor.rowcount
            
            # 3. PDF Import kaynaklı tüm birim fiyatları sil
            cursor.execute("""
                DELETE FROM birim_fiyatlar 
                WHERE kaynak = 'PDF Import'
            """)
            deleted_fiyat_count = cursor.rowcount
            
            return {
                'pozlar': deleted_poz_count,
                'birim_fiyatlar': deleted_fiyat_count
            }
    
    def get_poz_by_no(self, poz_no: str) -> Optional[Dict[str, Any]]:
        """
        Poz numarasına göre poz bilgisini getir.
        
        Args:
            poz_no: Poz numarası
            
        Returns:
            Optional[Dict]: Poz bilgisi
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM pozlar WHERE poz_no = ?", (poz_no,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    # İhale İşlemleri
    def create_ihale(self, ad: str, aciklama: str = "") -> int:
        """
        Yeni ihale oluştur.
        
        Args:
            ad: İhale adı
            aciklama: İhale açıklaması
            
        Returns:
            int: Oluşturulan ihale ID'si
        """
        now = datetime.now().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO ihaleler (ad, aciklama, olusturma_tarihi, guncelleme_tarihi)
                VALUES (?, ?, ?, ?)
            """, (ad, aciklama, now, now))
            return cursor.lastrowid
    
    def get_all_ihaleler(self) -> List[Dict[str, Any]]:
        """Tüm ihaleleri getir"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM ihaleler
                ORDER BY olusturma_tarihi DESC
            """)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_ihale(self, ihale_id: int) -> Optional[Dict[str, Any]]:
        """İhale bilgilerini getir"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM ihaleler WHERE id = ?", (ihale_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_ihale_kalemleri(self, ihale_id: int) -> List[Dict[str, Any]]:
        """İhale kalemlerini getir"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM ihale_kalemleri
                WHERE ihale_id = ?
                ORDER BY sira_no, id
            """, (ihale_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def add_ihale_kalem(self, ihale_id: int, poz_no: str = "", poz_tanim: str = "",
                       kategori: str = "", birim_miktar: float = 0, birim: str = "",
                       birim_fiyat: float = 0, toplam: float = 0, sira_no: Optional[int] = None) -> int:
        """
        İhaleye kalem ekle.
        
        Args:
            ihale_id: İhale ID'si
            poz_no: Poz numarası
            poz_tanim: Poz tanımı
            kategori: Kategori
            birim_miktar: Birim miktar (kullanıcı girer)
            birim: Birim
            birim_fiyat: Birim fiyat (otomatik veya kullanıcı düzenler)
            toplam: Toplam (birim_miktar * birim_fiyat)
            sira_no: Sıra numarası
            
        Returns:
            int: Eklenen kalemin ID'si
        """
        # Sıra numarası yoksa, mevcut maksimum + 1
        if sira_no is None:
            kalemler = self.get_ihale_kalemleri(ihale_id)
            sira_no = len(kalemler) + 1
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO ihale_kalemleri 
                (ihale_id, poz_no, poz_tanim, kategori, birim_miktar, birim, birim_fiyat, toplam, sira_no)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (ihale_id, poz_no, poz_tanim, kategori, birim_miktar, birim, birim_fiyat, toplam, sira_no))
            return cursor.lastrowid
    
    def update_ihale_kalem(self, kalem_id: int, **kwargs) -> bool:
        """İhale kalemini güncelle"""
        if not kwargs:
            return False
        
        fields = ", ".join([f"{k} = ?" for k in kwargs.keys()])
        values = list(kwargs.values()) + [kalem_id]
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE ihale_kalemleri SET {fields} WHERE id = ?", values)
            return cursor.rowcount > 0
    
    def delete_ihale_kalem(self, kalem_id: int) -> bool:
        """İhale kalemini sil"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM ihale_kalemleri WHERE id = ?", (kalem_id,))
            return cursor.rowcount > 0
    
    def delete_ihale(self, ihale_id: int) -> bool:
        """İhaleyi sil (kalemleri de silinir - CASCADE)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM ihaleler WHERE id = ?", (ihale_id,))
            return cursor.rowcount > 0
    
    def search_pozlar(self, search_text: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Poz numarası veya tanımına göre arama yap.
        Poz numarası formatı: 15.250.1011 (nokta ile ayrılmış)
        
        Args:
            search_text: Arama metni
            limit: Maksimum sonuç sayısı
            
        Returns:
            List[Dict]: Bulunan pozlar
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            search_text = search_text.strip()
            
            # Eğer arama metni tam poz numarası formatındaysa (nokta içeriyorsa)
            # önce tam eşleşme dene, sonra kısmi eşleşme
            if '.' in search_text:
                # Tam poz numarası araması - önce tam eşleşme
                cursor.execute("""
                    SELECT * FROM pozlar
                    WHERE poz_no = ?
                    ORDER BY poz_no
                    LIMIT ?
                """, (search_text, limit))
                exact_matches = [dict(row) for row in cursor.fetchall()]
                
                # Eğer tam eşleşme varsa onları döndür
                if exact_matches:
                    return exact_matches
                
                # Tam eşleşme yoksa, başlangıçtan eşleşenleri ara (15.250.1011 -> 15.250 ile başlayanlar)
                search_pattern = f"{search_text}%"
                cursor.execute("""
                    SELECT * FROM pozlar
                    WHERE poz_no LIKE ? OR tanim LIKE ?
                    ORDER BY poz_no
                    LIMIT ?
                """, (search_pattern, f"%{search_text}%", limit))
                return [dict(row) for row in cursor.fetchall()]
            else:
                # Nokta yoksa, normal LIKE araması yap
                search_pattern = f"%{search_text}%"
                cursor.execute("""
                    SELECT * FROM pozlar
                    WHERE poz_no LIKE ? OR tanim LIKE ?
                    ORDER BY poz_no
                    LIMIT ?
                """, (search_pattern, search_pattern, limit))
                return [dict(row) for row in cursor.fetchall()]

