;;; ============================================================
;;; KIRIS-HACIM.lsp  —  Kiriş Beton Hacmi Hesabı
;;; İnşaat Metraj Pro  |  v1.0  |  2026
;;; ============================================================
;;; KULLANIM:
;;;   AutoCAD komut satırına  c:KIRIS-HACIM  yazın.
;;;   1) Kiriş eksen çizgilerini (LINE/LWPOLYLINE) seçin → ENTER
;;;   2) Kiriş genişliğini (b, m) girin → ENTER  [varsayılan: 0.25]
;;;   3) Kiriş yüksekliğini (h, m) girin → ENTER [varsayılan: 0.50]
;;;   Sonuç  %TEMP%\imp_metraj.txt  dosyasına yazılır.
;;;
;;; GEREKSİNİMLER:
;;;   • Kirişler: LINE veya LWPOLYLINE (eksen çizgisi)
;;;   • b ve h Python'dan *IMP_KIRIS_B* ve *IMP_KIRIS_H* ile override edilebilir
;;;   FORMÜL: Hacim = Σ(uzunluk × b × h)
;;;   NOT: Kolon kesimleri (node-to-node) otomatik değildir;
;;;        eksen uzunlukları kullanılır, kolon payı manuel düşün.
;;; ============================================================

(defun c:KIRIS-HACIM ( / ss_kiris i ent uzunluk
                         kiris_b kiris_h toplam_uzunluk brut_hacim
                         dosya sonuc_str sonuc_yolu
                         girdilen)

  ;; Katman ve parametre değişkenleri (Python override edilebilir)
  (if (not (boundp '*IMP_KATMAN_KIRIS*)) (setq *IMP_KATMAN_KIRIS* "KIRIS"))
  (if (not (boundp '*IMP_KIRIS_B*))      (setq *IMP_KIRIS_B*      0.25))
  (if (not (boundp '*IMP_KIRIS_H*))      (setq *IMP_KIRIS_H*      0.50))

  (setq toplam_uzunluk 0.0)
  (setq brut_hacim     0.0)

  (prompt "\n╔══════════════════════════════════════════╗")
  (prompt "\n║  KIRIS-HACIM  —  Kiriş Beton Hacmi      ║")
  (prompt "\n╚══════════════════════════════════════════╝")

  ;; ── 1. Kiriş çizgisi seçimi ──────────────────────────────
  (prompt (strcat "\n► Kiriş eksen çizgilerini seçin (LINE veya LWPOLYLINE)"
                  "  [Katman: " *IMP_KATMAN_KIRIS* "]"
                  "\n  (Otomatik seçim için ENTER): "))
  (setq ss_kiris (ssget))

  (if (not ss_kiris)
    (progn
      (prompt (strcat "\n  → Otomatik: '" *IMP_KATMAN_KIRIS* "' katmanı taranıyor..."))
      (setq ss_kiris (ssget "X"
        (list '(0 . "LINE,LWPOLYLINE") (cons 8 *IMP_KATMAN_KIRIS*))))
      (if (not ss_kiris)
        (setq ss_kiris (ssget "X"
          (list '(0 . "LINE,LWPOLYLINE") '(8 . "BEAM")))))))

  (if (not ss_kiris)
    (progn
      (prompt "\n⚠ Kiriş çizgisi bulunamadı. İşlem iptal.")
      (exit)))

  ;; ── 2. Kiriş boyutlarını al ──────────────────────────────
  ;; b (genişlik)
  (setq girdilen
    (getdist (strcat "\n► Kiriş genişliği b [" (rtos *IMP_KIRIS_B* 2 2) " m]: ")))
  (if girdilen
    (setq kiris_b (abs girdilen))
    (setq kiris_b *IMP_KIRIS_B*))

  ;; h (yükseklik — döşeme dahil ise dikkat)
  (setq girdilen
    (getdist (strcat "\n► Kiriş yüksekliği h [" (rtos *IMP_KIRIS_H* 2 2) " m]: ")))
  (if girdilen
    (setq kiris_h (abs girdilen))
    (setq kiris_h *IMP_KIRIS_H*))

  (prompt (strcat "\n  Boyutlar: b=" (rtos kiris_b 2 3)
                  " m × h=" (rtos kiris_h 2 3) " m"))

  ;; ── 3. Her kiriş için uzunluk al ─────────────────────────
  (setq i 0)
  (while (< i (sslength ss_kiris))
    (setq ent (ssname ss_kiris i))
    (setq uzunluk
      (if (vl-catch-all-error-p
            (vl-catch-all-apply 'vlax-curve-getLength (list ent)))
        0.0
        (abs (vlax-curve-getLength ent))))
    (if (> uzunluk 0)
      (setq toplam_uzunluk (+ toplam_uzunluk uzunluk)))
    (setq i (1+ i)))

  ;; ── 4. Hacim hesabı ──────────────────────────────────────
  (setq brut_hacim (* toplam_uzunluk kiris_b kiris_h))

  ;; ── 5. Konsol çıktısı ────────────────────────────────────
  (prompt "\n┌─────────────────────────────────────")
  (prompt (strcat "\n│  Toplam Uzunluk : " (rtos toplam_uzunluk 2 3) " m"))
  (prompt (strcat "\n│  Kesit b×h      : " (rtos kiris_b 2 3) " × " (rtos kiris_h 2 3) " m"))
  (prompt (strcat "\n│  TOPLAM HACİM   : " (rtos brut_hacim 2 3) " m³  ◄"))
  (prompt "\n└─────────────────────────────────────")
  (prompt "\n  Not: Kolon kesim paylarını (-kolon_eni×sayı×b×h) manuel düşün.")

  ;; ── 6. Sonucu temp dosyaya yaz ────────────────────────────
  (setq sonuc_yolu (strcat (getenv "TEMP") "\\imp_metraj.txt"))
  (setq sonuc_str
    (strcat "{"
      "\"tur\":\"kiris_hacim\","
      "\"toplam_uzunluk\":" (rtos toplam_uzunluk 2 4) ","
      "\"kiris_b\":"        (rtos kiris_b        2 4) ","
      "\"kiris_h\":"        (rtos kiris_h        2 4) ","
      "\"toplam_hacim\":"   (rtos brut_hacim     2 4) ","
      "\"birim\":\"m3\","
      "\"aciklama\":\"Kiris beton hacmi (eksen uzunlugu x b x h)\""
    "}"))
  (setq dosya (open sonuc_yolu "w"))
  (write-line sonuc_str dosya)
  (close dosya)

  (prompt (strcat "\n✔ Sonuç kaydedildi: " sonuc_yolu))
  (prompt "\n  Uygulamada 'Sonucu Oku' butonuna tıklayın.\n")
  brut_hacim
)
