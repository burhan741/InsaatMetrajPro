"""Fiyatsız pozları listele"""
import sqlite3
from pathlib import Path

db_path = Path(__file__).parent / "data" / "insaat_metraj.db"

conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

# Fiyatı 0 veya NULL olan pozları bul
cursor.execute("""
    SELECT poz_no, tanim, resmi_fiyat
    FROM pozlar
    WHERE resmi_fiyat IS NULL OR resmi_fiyat = 0 OR resmi_fiyat = ''
    ORDER BY poz_no
""")

rows = cursor.fetchall()

# Sonuçları dosyaya yaz
result_file = Path(__file__).parent / "fiyatsiz_pozlar.txt"
with open(result_file, 'w', encoding='utf-8') as f:
    f.write(f"FIYATSIZ POZLAR LISTESI\n")
    f.write(f"=" * 80 + "\n")
    f.write(f"Toplam fiyatsiz poz sayisi: {len(rows)}\n")
    f.write(f"=" * 80 + "\n\n")

    for row in rows:
        poz_no, tanim, fiyat = row
        tanim_short = (tanim[:60] + '...') if tanim and len(tanim) > 60 else (tanim or '-')
        f.write(f"Poz: {poz_no}\n")
        f.write(f"Tanim: {tanim_short}\n")
        f.write(f"Fiyat: {fiyat}\n")
        f.write("-" * 40 + "\n")

conn.close()

print(f"Toplam fiyatsiz poz: {len(rows)}")
print(f"Liste kaydedildi: {result_file}")
