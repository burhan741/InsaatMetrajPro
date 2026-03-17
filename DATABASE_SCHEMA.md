# Veritabanı Şeması - DatabaseManager

## Genel Bilgi

**Dosya:** `app/core/database.py`  
**Sınıf:** `DatabaseManager`  
**Toplam Metodlar:** 45  
**Veritabanı:** SQLite3 (WAL mode)  
**Tablolar:** 9  

---

## Tablo Tanımları

### 1. **projects** - Proje Yönetimi
```sql
CREATE TABLE projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ad TEXT NOT NULL UNIQUE,
    aciklama TEXT,
    olusturma_tarihi TEXT,
    guncelleme_tarihi TEXT,
    durum TEXT DEFAULT 'aktif',  -- aktif, pasif, tamamlandı
    toplam_maliyet REAL DEFAULT 0,
    notlar TEXT
)
```
**Index:** `idx_projects_ad` (ad sütununda)

---

### 2. **tedarikcilar** - Tedarikçi/Taşeron Yönetimi
```sql
CREATE TABLE tedarikcilar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ad TEXT NOT NULL,
    telefon TEXT,
    email TEXT,
    adres TEXT,
    notlar TEXT,
    olusturma_tarihi TEXT,
    guncelleme_tarihi TEXT
)
```
**Index:** `idx_tedarikcilar_ad` (ad sütununda)

---

### 3. **sablonlar** - Metraj Şablonları
```sql
CREATE TABLE sablonlar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ad TEXT NOT NULL UNIQUE,
    aciklama TEXT,
    olusturma_tarihi TEXT,
    guncelleme_tarihi TEXT
)
```
**Index:** `idx_sablonlar_ad` (ad sütununda)

---

### 4. **sablon_kalemleri** - Şablon Alt Kalemleri
```sql
CREATE TABLE sablon_kalemleri (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sablon_id INTEGER NOT NULL,
    poz_no TEXT,
    tanim TEXT,
    kategori TEXT,
    miktar REAL,
    birim TEXT,
    birim_fiyat REAL,
    toplam REAL,
    FOREIGN KEY (sablon_id) REFERENCES sablonlar(id) ON DELETE CASCADE
)
```
**Index:** `idx_sablon_kalemleri_sablon_id` (sablon_id sütununda)

---

### 5. **ayarlar** - Uygulama Ayarları (Key-Value)
```sql
CREATE TABLE ayarlar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    anahtar TEXT NOT NULL UNIQUE,
    deger TEXT,
    olusturma_tarihi TEXT,
    guncelleme_tarihi TEXT
)
```
**Tipik Anahtarlar:**
- `pozlar_yuklendi` - Poz veritabanı yüklendi mi?
- `malzemeler_yuklendi` - Malzeme veritabanı yüklendi mi?
- `son_guncelleme` - Son güncelleme tarihi
- `tema` - Uygulama teması

---

### 6. **ihaleler** - İhale/Teklife ve Bütçeler
```sql
CREATE TABLE ihaleler (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ad TEXT NOT NULL,
    aciklama TEXT,
    olusturma_tarihi TEXT,
    guncelleme_tarihi TEXT,
    durum TEXT DEFAULT 'tasarı'  -- tasarı, sunulan, kabul, reddedildi
)
```
**Index:** `idx_ihaleler_ad` (ad sütununda)

---

### 7. **ihale_kalemleri** - İhale Alt Kalemleri
```sql
CREATE TABLE ihale_kalemleri (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ihale_id INTEGER NOT NULL,
    poz_no TEXT,
    poz_tanim TEXT,
    kategori TEXT,
    birim_miktar REAL,
    birim TEXT,
    birim_fiyat REAL,
    toplam REAL,
    sira_no INTEGER,
    FOREIGN KEY (ihale_id) REFERENCES ihaleler(id) ON DELETE CASCADE
)
```
**Index:** `idx_ihale_kalemleri_ihale_id` (ihale_id sütununda)

---

### 8. **birim_fiyatlar** - Bütçe Birim Fiyatları
```sql
CREATE TABLE birim_fiyatlar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    poz_id INTEGER,
    poz_no TEXT NOT NULL,
    birim_fiyat REAL,
    tarih TEXT,
    kaynak TEXT,  -- 'manuel', 'ithalatci', 'resmi'
    aciklama TEXT,
    aktif INTEGER DEFAULT 1,
    FOREIGN KEY (poz_id) REFERENCES pozlar(id) ON DELETE SET NULL
)
```
**Index:** 
- `idx_birim_fiyatlar_poz_no` (poz_no sütununda)
- `idx_birim_fiyatlar_aktif` (aktif sütununda)

---

### 9. **pozlar** - İş Kalem Veritabanı
```sql
CREATE TABLE pozlar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    poz_no TEXT NOT NULL UNIQUE,
    tanim TEXT,
    birim TEXT,
    resmi_fiyat REAL,
    kategori TEXT,
    aciklama TEXT,
    fire_orani REAL DEFAULT 0,
    guncelleme_tarihi TEXT
)
```
**Index:** `idx_pozlar_poz_no` (poz_no sütununda)

---

## Metodlar (45 Toplam)

### Genel CRUD İşlemleri (6 Metod)

```python
def execute(query: str, params: list = None) -> List[Any]
def execute_single(query: str, params: list = None) -> Optional[Any]
def insert(table: str, data: Dict[str, Any]) -> int  # lastrowid döner
def update(table: str, data: Dict[str, Any], where: Dict[str, Any]) -> int  # rowcount döner
def delete(table: str, where: Dict[str, Any]) -> int  # rowcount döner
@contextmanager
def get_connection() -> sqlite3.Connection
```

---

### Proje Yönetimi (5 Metod)

```python
def get_all_projects() -> List[Dict[str, Any]]
def get_project(project_id: int) -> Optional[Dict[str, Any]]
def create_project(ad: str, aciklama: str = "", notlar: str = "") -> int
def update_project(project_id: int, **kwargs) -> bool
def delete_project(project_id: int) -> bool
```

---

### Tedarikçi Yönetimi (5 Metod)

```python
def get_tedarikci_listesi() -> List[Dict[str, Any]]
def get_tedarikci(tedarikci_id: int) -> Optional[Dict[str, Any]]
def create_tedarikci(ad: str, telefon: str = "", email: str = "", adres: str = "", notlar: str = "") -> int
def update_tedarikci(tedarikci_id: int, **kwargs) -> bool
def delete_tedarikci(tedarikci_id: int) -> bool
```

---

### Ayarlar Yönetimi (4 Metod)

```python
def get_ayar(anahtar: str, varsayilan: str = "") -> str
def set_ayar(anahtar: str, deger: str) -> bool
def delete_ayar(anahtar: str) -> bool
def get_tum_ayarlar() -> Dict[str, str]
```

---

### İhale Yönetimi (8 Metod)

```python
def get_all_ihaleler() -> List[Dict[str, Any]]
def get_ihale(ihale_id: int) -> Optional[Dict[str, Any]]
def create_ihale(ad: str, aciklama: str = "") -> int
def update_ihale(ihale_id: int, **kwargs) -> bool
def delete_ihale(ihale_id: int) -> bool
def get_ihale_kalemleri(ihale_id: int) -> List[Dict[str, Any]]
def add_ihale_kalemi(ihale_id: int, poz_no: str, poz_tanim: str, kategori: str, 
                     birim_miktar: float, birim: str, birim_fiyat: float, sira_no: int = 0) -> int
def delete_ihale_kalemi(kalem_id: int) -> bool
```

---

### Birim Fiyat Yönetimi (7 Metod)

```python
def get_all_birim_fiyatlar(aktif_only: bool = True) -> List[Dict[str, Any]]
def get_birim_fiyat(fiyat_id: int) -> Optional[Dict[str, Any]]
def get_poz_birim_fiyatlar(poz_no: str) -> List[Dict[str, Any]]
def create_birim_fiyat(poz_no: str, birim_fiyat: float, tarih: str = None, 
                       kaynak: str = "manuel", aciklama: str = "") -> int
def update_birim_fiyat(fiyat_id: int, **kwargs) -> bool
def delete_birim_fiyat(fiyat_id: int) -> bool
def deaktif_et_birim_fiyat(fiyat_id: int) -> bool
```

---

### Şablon Yönetimi (10 Metod)

```python
def get_all_templates() -> List[Dict[str, Any]]
def get_template(template_id: int) -> Optional[Dict[str, Any]]
def create_template(ad: str, aciklama: str = "") -> int
def update_template(template_id: int, **kwargs) -> bool
def delete_template(template_id: int) -> bool
def get_template_items(template_id: int) -> List[Dict[str, Any]]  # Alias
def get_template_kalemleri(template_id: int) -> List[Dict[str, Any]]
def add_template_kalemi(template_id: int, poz_no: str, tanim: str, kategori: str, 
                        miktar: float, birim: str, birim_fiyat: float) -> int
def update_template_kalemi(kalem_id: int, **kwargs) -> bool
def delete_template_kalemi(kalem_id: int) -> bool
```

---

## Özellikleri

### ✅ Güvenlik
- **Foreign Key Constraints:** Referans bütünlüğü sağlanır
- **CASCADE DELETE:** Anahtarlı tablolarda otomatik silme
- **Context Manager:** Otomatik bağlantı yönetimi

### ✅ Performans
- **WAL Mode:** Write-Ahead Logging (eşzamanlı okuma-yazma)
- **PRAGMA Optimizasyonları:**
  - `journal_mode=WAL`
  - `synchronous=NORMAL` (hız ve güvenlik dengesi)
  - `cache_size=-64000` (64MB cache)
  - `FOREIGN_KEYS=ON`
- **Indexes:** Sık kullanılan sütunlarda hızlı erişim

### ✅ Veri Bütünlüğü
- **Type Hints:** Tüm metodlarda Python type annotations
- **Error Handling:** Try-except blokları ile güvenli işlemler
- **Default Values:** Null değerler yerine uygun defaults

---

## Veritabanı Dosyası

**Konumu:** `data/insaat_metraj.db` (proje kök dizininde)

```python
db_manager = DatabaseManager()  # Varsayılan konumda
db_manager = DatabaseManager(db_path="/custom/path/database.db")  # Özel konum
```

---

## Örnek Kullanımlar

### Proje Oluşturma
```python
db = DatabaseManager()
project_id = db.create_project(
    ad="Ankara Rezidans",
    aciklama="15 katlı modern apartman",
    notlar="Bitiş tarihi: Aralık 2024"
)
```

### Tedarikçi Ekleme
```python
tedarikci_id = db.create_tedarikci(
    ad="Ahmet İnşaat Ltd.",
    telefon="0312 234 5678",
    email="info@ahmet.com.tr",
    adres="Ankara, Çankaya"
)
```

### İhale Oluşturma ve Kalem Ekleme
```python
ihale_id = db.create_ihale(
    ad="2024 Yıllık İhale",
    aciklama="Genel inşaat işleri"
)

# Kalem ekle
db.add_ihale_kalemi(
    ihale_id=ihale_id,
    poz_no="01.01.001",
    poz_tanim="İnşaat Alanı Hazırlama",
    kategori="İnşaat",
    birim_miktar=1500,
    birim="m2",
    birim_fiyat=25.50,
    sira_no=1
)
```

### Şablon Oluşturma
```python
template_id = db.create_template(
    ad="Standart Konut Şablonu",
    aciklama="100m2 konut için standart metraj şablonu"
)

db.add_template_kalemi(
    template_id=template_id,
    poz_no="02.01.001",
    tanim="Perdeleme",
    kategori="Dış Cephe",
    miktar=120,
    birim="m2",
    birim_fiyat=18.50
)
```

---

## Veritabanı Bakımı

### Yedekleme
```python
import shutil
from pathlib import Path

db_path = Path("data/insaat_metraj.db")
backup_path = Path("backups") / f"insaat_metraj_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
backup_path.parent.mkdir(exist_ok=True)
shutil.copy(db_path, backup_path)
```

### Cache Temizleme
```bash
# PowerShell
Get-ChildItem -Path .venv -Include __pycache__ -Recurse | Remove-Item -Recurse
Get-ChildItem -Path app -Include __pycache__ -Recurse | Remove-Item -Recurse
```

---

## İstatistikler

| Kategori | Sayı |
|----------|------|
| Toplam Metodlar | 45 |
| CRUD İşlemleri | 6 |
| Proje Metodları | 5 |
| Tedarikçi Metodları | 5 |
| Ayar Metodları | 4 |
| İhale Metodları | 8 |
| Birim Fiyat Metodları | 7 |
| Şablon Metodları | 10 |
| Tablolar | 9 |
| Indexes | 7 |

---

**Son Güncelleme:** 2024  
**Durum:** ✅ Üretim Hazır
