"""
Veritabanı Yöneticisi
SQLite veritabanı bağlantısı ve işlemleri için core modül
"""

import sqlite3
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
                    toplam_maliyet REAL DEFAULT 0
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
                    olusturma_tarihi TEXT
                )
            """)
            
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
    
    # Malzeme İşlemleri
    def add_malzeme(self, ad: str, birim: str, kategori: str = "", aciklama: str = "") -> int:
        """
        Yeni malzeme ekle.
        
        Args:
            ad: Malzeme adı
            birim: Birim (kg, m³, adet, vb.)
            kategori: Malzeme kategorisi
            aciklama: Açıklama
            
        Returns:
            int: Oluşturulan malzemenin ID'si
        """
        now = datetime.now().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO malzemeler (ad, birim, kategori, aciklama, olusturma_tarihi)
                    VALUES (?, ?, ?, ?, ?)
                """, (ad, birim, kategori, aciklama, now))
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                # Malzeme zaten varsa ID'sini döndür
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

