"""
PDF Import Test Scripti
PDF dosyasını test eder ve sonuçları gösterir
"""

import sys
from pathlib import Path
from app.utils.pdf_importer import PDFBirimFiyatImporter

def test_pdf_import(pdf_path: str):
    """PDF'i test et"""
    pdf_file = Path(pdf_path)
    
    if not pdf_file.exists():
        print(f"❌ Dosya bulunamadı: {pdf_path}")
        return
    
    print(f"📄 PDF işleniyor: {pdf_file.name}")
    print(f"📊 Dosya boyutu: {pdf_file.stat().st_size / 1024 / 1024:.2f} MB")
    print()
    
    try:
        importer = PDFBirimFiyatImporter()
        
        def progress_callback(current, total):
            if current % 50 == 0 or current == total:
                print(f"   Sayfa {current}/{total} işlendi...")
            return True
        
        extracted_data = importer.extract_from_pdf(pdf_file, progress_callback)
        
        print()
        print(f"✅ İşlem tamamlandı!")
        print(f"📊 Bulunan poz/fiyat sayısı: {len(extracted_data)}")
        print()
        
        if extracted_data:
            print("📋 İlk 10 kayıt:")
            print("-" * 80)
            for i, item in enumerate(extracted_data[:10], 1):
                poz_no = item.get('poz_no', '')
                tanim = item.get('tanim', '')[:50]
                fiyat = item.get('birim_fiyat', 0)
                print(f"{i:2d}. Poz: {poz_no:15s} | Fiyat: {fiyat:,.2f} ₺ | {tanim}")
            print("-" * 80)
            
            if len(extracted_data) > 10:
                print(f"\n... ve {len(extracted_data) - 10} kayıt daha")
        else:
            print("⚠️  Hiç poz/fiyat bulunamadı!")
            print("   PDF formatını kontrol edin veya parsing mantığını güncelleyin.")
    
    except Exception as e:
        print(f"❌ Hata: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # PDF dosya yolu
    pdf_path = "2025-yili-b-r-m-f-yatlari-20250117121853.pdf"
    
    # Eğer argüman olarak verilmişse onu kullan
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    
    test_pdf_import(pdf_path)


