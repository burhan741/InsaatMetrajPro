"""Fiyatsız pozları oku ve analiz et"""
import pandas as pd
from pathlib import Path

excel_path = r"C:\Users\USER\Desktop\fiyatsiz_pozlar.xlsx"
output_path = Path(__file__).parent / "fiyatsiz_analiz.txt"

try:
    df = pd.read_excel(excel_path)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(f"FIYATSIZ POZLAR ANALİZİ\n")
        f.write(f"=" * 80 + "\n")
        f.write(f"Toplam fiyatsız poz sayısı: {len(df)}\n")
        f.write(f"Sütunlar: {list(df.columns)}\n")
        f.write(f"=" * 80 + "\n\n")

        # İlk 50 pozu göster
        f.write("İLK 50 FIYATSIZ POZ:\n")
        f.write("-" * 80 + "\n")
        for idx, row in df.head(50).iterrows():
            poz_no = row.get('Poz No', row.iloc[0] if len(row) > 0 else '')
            tanim = row.get('Tanım', row.iloc[1] if len(row) > 1 else '')
            tanim_short = str(tanim)[:60] if tanim else ''
            f.write(f"{poz_no} | {tanim_short}\n")

        f.write("\n" + "=" * 80 + "\n")

        # Poz numarası desenlerini analiz et
        f.write("\nPOZ NUMARASI DESENLERİ:\n")
        f.write("-" * 80 + "\n")

        poz_col = df.columns[0]  # İlk sütun poz no
        poz_prefixes = {}
        for poz in df[poz_col]:
            if pd.notna(poz):
                prefix = str(poz).split('.')[0] if '.' in str(poz) else str(poz)[:2]
                poz_prefixes[prefix] = poz_prefixes.get(prefix, 0) + 1

        for prefix, count in sorted(poz_prefixes.items(), key=lambda x: -x[1]):
            f.write(f"  {prefix}.xxx.xxxx: {count} adet\n")

    print(f"Analiz kaydedildi: {output_path}")

except Exception as e:
    print(f"Hata: {e}")
    import traceback
    traceback.print_exc()
