"""
Kolon filiz parse test scripti - Detaylı analiz
"""

import sys
import re
from pathlib import Path

# Encoding düzeltmesi
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, str(Path(__file__).parent))

from app.core.kolon_donati_parser import KolonDonatiParser, TextEntity

if __name__ == "__main__":
    dxf_path = r"C:\Users\USER\Desktop\İdari Bina Statik Projesi (1).dxf"
    
    print("="*80)
    print("FILIZ PARSE DETAYLI ANALIZ")
    print("="*80)
    print(f"\nDosya: {dxf_path}\n")
    
    parser = KolonDonatiParser(dxf_path)
    
    # Text'leri çıkar
    all_texts = parser._extract_texts()
    print(f"Toplam text sayisi: {len(all_texts)}\n")
    
    # Kolon başlığını bul
    kolon_baslik_pattern = re.compile(
        r"KOLON\s+APLIKASYON\s+(PLANI|CIZIMI)", 
        re.IGNORECASE
    )
    
    kolon_baslik = None
    for t in all_texts:
        if kolon_baslik_pattern.search(t.content):
            kolon_baslik = t
            print(f"[OK] Kolon basligi bulundu: '{t.content}' (x={t.x:.1f}, y={t.y:.1f})\n")
            break
    
    # Kolon bölümündeki text'leri filtrele
    if kolon_baslik:
        kolon_texts = []
        for t in all_texts:
            if t.y < kolon_baslik.y and abs(t.x - kolon_baslik.x) <= 10000.0:
                kolon_texts.append(t)
        print(f"[OK] Kolon bolumunden {len(kolon_texts)} text filtrelendi\n")
    else:
        kolon_texts = all_texts
        print("[WARN] Kolon basligi bulunamadi, tum text'ler kullaniliyor\n")
    
    # KOLON DETAYI başlıklarını bul - farklı pattern'ler dene
    print("="*80)
    print("KOLON DETAYI BASLIKLARI")
    print("="*80)
    
    # Farklı pattern'ler dene
    detay_patterns = [
        (r'(S\d{3})\s*\(\d+/\d+\)\s*KOLON\s*DETAYI', "S001 (1/2) KOLON DETAYI"),
        (r'(S\d{3})\s*KOLON\s*DETAYI', "S001 KOLON DETAYI"),
        (r'KOLON\s*DETAYI\s*(S\d{3})', "KOLON DETAYI S001"),
        (r'(S\d{3})\s*DETAY', "S001 DETAY"),
        (r'^(S\d{3})$', "S001 (sadece kolon ismi)"),
    ]
    
    detaylar = []
    for pattern, desc in detay_patterns:
        for t in kolon_texts:
            match = re.search(pattern, t.content, re.IGNORECASE)
            if match:
                kolon_adi = match.group(1) if match.lastindex >= 1 else match.group(0)
                detaylar.append({
                    'ana_kolon': kolon_adi,
                    'x': t.x,
                    'y': t.y,
                    'text': t.content,
                    'pattern': desc
                })
        if detaylar:
            break
    
    # Sadece kolon isimlerini bul (S001, S002, vb.)
    if not detaylar:
        print("\nKolon detay basligi bulunamadi, kolon isimlerini ariyorum...")
        kolon_isimleri = []
        kolon_pattern = r'^S\d{3}$'
        for t in kolon_texts:
            if re.match(kolon_pattern, t.content.strip()):
                kolon_isimleri.append({
                    'ana_kolon': t.content.strip(),
                    'x': t.x,
                    'y': t.y,
                    'text': t.content
                })
        
        # Tekrarları kaldır ve sırala
        seen = set()
        for k in kolon_isimleri:
            if k['ana_kolon'] not in seen:
                detaylar.append(k)
                seen.add(k['ana_kolon'])
        
        print(f"  {len(detaylar)} farkli kolon ismi bulundu")
    
    print(f"\nToplam {len(detaylar)} kolon detay/isim bulundu:\n")
    for i, d in enumerate(detaylar[:20], 1):  # İlk 20'sini göster
        print(f"  {i}. {d['ana_kolon']}: '{d['text']}' (x={d['x']:.1f}, y={d['y']:.1f})")
    if len(detaylar) > 20:
        print(f"  ... ve {len(detaylar) - 20} tane daha")
    
    # Filiz ile ilgili text'leri bul
    print("\n" + "="*80)
    print("FILIZ ILE ILGILI TEXT'LER")
    print("="*80)
    
    # Mevcut pattern
    filiz_bilgi_pattern = r'^(\d+).(\d+)\s*l\s*=\s*(\d+)$'
    
    filiz_benzeri = []
    for t in kolon_texts:
        if 'Etr' not in t.content and 'etr' not in t.content:
            match = re.match(filiz_bilgi_pattern, t.content)
            if match:
                adet = int(match.group(1))
                cap = int(match.group(2))
                boy = int(match.group(3))
                if cap >= 10:
                    filiz_benzeri.append({
                        'text': t.content,
                        'adet': adet,
                        'cap': cap,
                        'boy': boy,
                        'x': t.x,
                        'y': t.y
                    })
    
    if filiz_benzeri:
        print(f"\n[OK] Mevcut pattern ile {len(filiz_benzeri)} filiz bulundu:\n")
        for i, f in enumerate(filiz_benzeri, 1):
            print(f"  {i}. '{f['text']}' -> {f['adet']}O{f['cap']} l={f['boy']}cm (x={f['x']:.1f}, y={f['y']:.1f})")
    else:
        print("\n[FAIL] Mevcut pattern ile filiz bulunamadi!")
    
    # Alternatif pattern'ler dene
    print("\n" + "="*80)
    print("ALTERNATIF PATTERN'LER")
    print("="*80)
    
    alt_patterns = [
        (r'(\d+)\s*[ØΦφ∅ƒf]\s*(\d+)\s*l\s*=\s*(\d+)', "12Ø16 l=372"),
        (r'(\d+)\s*[ØΦφ∅ƒf]\s*(\d+)\s*L\s*=\s*(\d+)', "12Ø16 L=372"),
        (r'(\d+)\s*[ØΦφ∅ƒf]\s*(\d+)\s*=\s*(\d+)', "12Ø16=372"),
        (r'(\d+)\s*[ØΦφ∅ƒf]\s*(\d+)\s*/\s*(\d+)', "12Ø16/372"),
        (r'(\d+)\s*[ØΦφ∅ƒf]\s*(\d+)\s*,\s*(\d+)', "12Ø16,372"),
    ]
    
    for pattern, desc in alt_patterns:
        matches = []
        for t in kolon_texts:
            if 'Etr' not in t.content and 'etr' not in t.content:
                match = re.search(pattern, t.content, re.IGNORECASE)
                if match:
                    try:
                        adet = int(match.group(1))
                        cap = int(match.group(2))
                        boy = int(match.group(3))
                        if cap >= 10 and boy > 100:  # Filiz çapı 10+ ve boy 100+ cm
                            matches.append({
                                'text': t.content,
                                'adet': adet,
                                'cap': cap,
                                'boy': boy,
                                'x': t.x,
                                'y': t.y
                            })
                    except:
                        pass
        
        if matches:
            print(f"\n[OK] Pattern '{desc}' ile {len(matches)} eslesme bulundu:")
            for i, m in enumerate(matches[:10], 1):
                print(f"  {i}. '{m['text']}' -> {m['adet']}O{m['cap']} l={m['boy']}cm (x={m['x']:.1f}, y={m['y']:.1f})")
            if len(matches) > 10:
                print(f"  ... ve {len(matches) - 10} tane daha")
            break
    
    # Kolon detaylarının yakınındaki text'leri incele
    print("\n" + "="*80)
    print("KOLON DETAYLARININ YAKININDAKI TEXT'LER")
    print("="*80)
    
    for detay in detaylar[:3]:  # İlk 3 detayı incele
        print(f"\n{detay['ana_kolon']} detayı yakınındaki text'ler (x={detay['x']:.1f}, y={detay['y']:.1f}):")
        yakin_texts = []
        for t in kolon_texts:
            # Detayın altında ve yakınında (y < detay.y, x toleransı 200 cm)
            if t.y < detay['y'] and abs(t.x - detay['x']) < 200:
                yakin_texts.append(t)
        
        # Y koordinatına göre sırala (yukarıdan aşağıya)
        yakin_texts = sorted(yakin_texts, key=lambda t: t.y, reverse=True)
        
        print(f"  {len(yakin_texts)} text bulundu:")
        for i, t in enumerate(yakin_texts[:15], 1):  # İlk 15'ini göster
            print(f"    {i}. '{t.content}' (x={t.x:.1f}, y={t.y:.1f})")

