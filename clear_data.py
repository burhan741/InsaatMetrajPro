"""Tüm pozları ve birim fiyatları temizle"""
import sqlite3
from pathlib import Path

result_file = Path(__file__).parent / "clear_result.txt"
db_path = Path(__file__).parent / "data" / "insaat_metraj.db"

results = []
results.append(f"Veritabani: {db_path}")
results.append(f"Mevcut: {db_path.exists()}")

if not db_path.exists():
    results.append("HATA: Veritabani dosyasi bulunamadi!")
    result_file.write_text("\n".join(results), encoding="utf-8")
    exit(1)

conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

# Mevcut kayit sayilarini goster
cursor.execute('SELECT COUNT(*) FROM pozlar')
poz_count = cursor.fetchone()[0]
results.append(f"Mevcut poz sayisi: {poz_count}")

cursor.execute('SELECT COUNT(*) FROM birim_fiyatlar')
fiyat_count = cursor.fetchone()[0]
results.append(f"Mevcut birim fiyat sayisi: {fiyat_count}")

# Tablolari temizle
cursor.execute('DELETE FROM birim_fiyatlar')
deleted_fiyat = cursor.rowcount
results.append(f"Silinen birim fiyat: {deleted_fiyat}")

cursor.execute('DELETE FROM pozlar')
deleted_poz = cursor.rowcount
results.append(f"Silinen poz: {deleted_poz}")

conn.commit()
conn.close()

results.append("")
results.append("BASARILI: Tum pozlar ve birim fiyatlar temizlendi!")

# Sonucu dosyaya yaz
result_file.write_text("\n".join(results), encoding="utf-8")
