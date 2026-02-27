;;; ============================================================
;;; KALIP-ALAN.lsp  —  Kolon + Kiriş + Döşeme Kalıp Alanı
;;; İnşaat Metraj Pro  |  v1.0  |  2026
;;; ============================================================
;;; KULLANIM:
;;;   AutoCAD komut satırına  c:KALIP-ALAN  yazın.
;;;   Program sırayla soru sorar:
;;;   1) Kolon kesit polyline'ları → ENTER
;;;   2) Kat yüksekliği (m)        → ENTER  [varsayılan: 3.0]
;;;   3) Kiriş eksen çizgileri     → ENTER
;;;   4) Kiriş b (m)               → ENTER  [varsayılan: 0.25]
;;;   5) Kiriş h (m)               → ENTER  [varsayılan: 0.50]
;;;   6) Döşeme polyline'ları      → ENTER
;;;   Sonuç  %TEMP%\imp_metraj.txt  dosyasına yazılır.
;;;
;;; FORMÜLLER (TS 500 / IMO standartları):
;;;   Kolon kalıp  = Σ(çevre × kat_yüksekliği)
;;;   Kiriş kalıp  = Σ uzunluk × (2×h + b)   [yan + alt yüzey]
;;;   Döşeme kalıp = Σ brüt_alan
;;;   TOPLAM       = Kolon + Kiriş + Döşeme
;;; ============================================================

(defun c:KALIP-ALAN ( / ss_kolon ss_kiris ss_doseme
                        i ent uzunluk alan cevre
                        kat_yuk kiris_b kiris_h
                        kolon_kalip kiris_kalip doseme_kalip toplam_kalip
                        dosya sonuc_str sonuc_yolu girdilen)

  ;; Katman değişkenleri (Python override edilebilir)
  (if (not (boundp '*IMP_KATMAN_KOLON*))   (setq *IMP_KATMAN_KOLON*   "KOLON"))
  (if (not (boundp '*IMP_KATMAN_KIRIS*))   (setq *IMP_KATMAN_KIRIS*   "KIRIS"))
  (if (not (boundp '*IMP_KATMAN_DOSEME*))  (setq *IMP_KATMAN_DOSEME*  "DOSEME"))
  (if (not (boundp '*IMP_KAT_YUKSEKLIGI*)) (setq *IMP_KAT_YUKSEKLIGI* 3.0))
  (if (not (boundp '*IMP_KIRIS_B*))        (setq *IMP_KIRIS_B*        0.25))
  (if (not (boundp '*IMP_KIRIS_H*))        (setq *IMP_KIRIS_H*        0.50))

  (setq kolon_kalip  0.0)
  (setq kiris_kalip  0.0)
  (setq doseme_kalip 0.0)

  (prompt "\n╔══════════════════════════════════════════════════╗")
  (prompt "\n║  KALIP-ALAN  —  Kolon + Kiriş + Döşeme Kalıbı  ║")
  (prompt "\n╚══════════════════════════════════════════════════╝")

  ;; ══════════════════════════════════════════
  ;; A) KOLON KALIP ALANI
  ;; ══════════════════════════════════════════
  (prompt (strcat "\n\n─── A) KOLON KALIP ───"
                  "\n► Kolon kesit polyline'larını seçin"
                  "  [Katman: " *IMP_KATMAN_KOLON* "]"
                  "\n  (Atlamak için ENTER): "))
  (setq ss_kolon (ssget))

  (if (not ss_kolon)
    (progn
      (setq ss_kolon (ssget "X"
        (list '(0 . "LWPOLYLINE") (cons 8 *IMP_KATMAN_KOLON*))))))

  ;; Kat yüksekliği
  (setq girdilen
    (getdist (strcat "\n► Kat yüksekliği [" (rtos *IMP_KAT_YUKSEKLIGI* 2 2) " m]: ")))
  (setq kat_yuk (if girdilen (abs girdilen) *IMP_KAT_YUKSEKLIGI*))

  ;; Kolon kalıp: Σ (çevre × kat_yük)
  (if ss_kolon
    (progn
      (setq i 0)
      (while (< i (sslength ss_kolon))
        (setq ent (ssname ss_kolon i))
        (setq cevre
          (if (vl-catch-all-error-p
                (vl-catch-all-apply 'vlax-curve-getLength (list ent)))
            0.0
            (abs (vlax-curve-getLength ent))))
        (setq kolon_kalip (+ kolon_kalip (* cevre kat_yuk)))
        (setq i (1+ i)))
      (prompt (strcat "\n  Kolon Kalıp : " (rtos kolon_kalip 2 3) " m²")))
    (prompt "\n  Kolon seçimi atlandı."))

  ;; ══════════════════════════════════════════
  ;; B) KİRİŞ KALIP ALANI
  ;; ══════════════════════════════════════════
  (prompt (strcat "\n\n─── B) KİRİŞ KALIP ───"
                  "\n► Kiriş eksen çizgilerini seçin"
                  "  [Katman: " *IMP_KATMAN_KIRIS* "]"
                  "\n  (Atlamak için ENTER): "))
  (setq ss_kiris (ssget))

  (if (not ss_kiris)
    (setq ss_kiris (ssget "X"
      (list '(0 . "LINE,LWPOLYLINE") (cons 8 *IMP_KATMAN_KIRIS*)))))

  ;; Kiriş boyutları
  (setq girdilen
    (getdist (strcat "\n► Kiriş genişliği b [" (rtos *IMP_KIRIS_B* 2 2) " m]: ")))
  (setq kiris_b (if girdilen (abs girdilen) *IMP_KIRIS_B*))

  (setq girdilen
    (getdist (strcat "\n► Kiriş yüksekliği h [" (rtos *IMP_KIRIS_H* 2 2) " m]: ")))
  (setq kiris_h (if girdilen (abs girdilen) *IMP_KIRIS_H*))

  ;; Kiriş kalıp: Σ uzunluk × (2h + b)
  ;; 2h = iki yan yüz, b = alt yüz (döşeme altı dahil değil)
  (if ss_kiris
    (progn
      (setq i 0)
      (while (< i (sslength ss_kiris))
        (setq ent (ssname ss_kiris i))
        (setq uzunluk
          (if (vl-catch-all-error-p
                (vl-catch-all-apply 'vlax-curve-getLength (list ent)))
            0.0
            (abs (vlax-curve-getLength ent))))
        (setq kiris_kalip
          (+ kiris_kalip (* uzunluk (+ (* 2 kiris_h) kiris_b))))
        (setq i (1+ i)))
      (prompt (strcat "\n  Kiriş Kalıp : " (rtos kiris_kalip 2 3) " m²")))
    (prompt "\n  Kiriş seçimi atlandı."))

  ;; ══════════════════════════════════════════
  ;; C) DÖŞEME KALIP ALANI
  ;; ══════════════════════════════════════════
  (prompt (strcat "\n\n─── C) DÖŞEME KALIP ───"
                  "\n► Döşeme/plak polyline'larını seçin"
                  "  [Katman: " *IMP_KATMAN_DOSEME* "]"
                  "\n  (Atlamak için ENTER): "))
  (setq ss_doseme (ssget))

  (if (not ss_doseme)
    (setq ss_doseme (ssget "X"
      (list '(0 . "LWPOLYLINE") (cons 8 *IMP_KATMAN_DOSEME*)))))

  (if ss_doseme
    (progn
      (setq i 0)
      (while (< i (sslength ss_doseme))
        (setq ent (ssname ss_doseme i))
        (setq alan
          (if (vl-catch-all-error-p
                (vl-catch-all-apply 'vlax-curve-getArea (list ent)))
            0.0
            (abs (vlax-curve-getArea ent))))
        (setq doseme_kalip (+ doseme_kalip alan))
        (setq i (1+ i)))
      (prompt (strcat "\n  Döşeme Kalıp: " (rtos doseme_kalip 2 3) " m²")))
    (prompt "\n  Döşeme seçimi atlandı."))

  ;; ══════════════════════════════════════════
  ;; D) TOPLAM
  ;; ══════════════════════════════════════════
  (setq toplam_kalip (+ kolon_kalip kiris_kalip doseme_kalip))

  (prompt "\n┌──────────────────────────────────────────────")
  (prompt (strcat "\n│  Kolon Kalıp   : " (rtos kolon_kalip  2 3) " m²"))
  (prompt (strcat "\n│  Kiriş Kalıp   : " (rtos kiris_kalip  2 3) " m²"))
  (prompt (strcat "\n│  Döşeme Kalıp  : " (rtos doseme_kalip 2 3) " m²"))
  (prompt "\n│  ─────────────────────────────────────────")
  (prompt (strcat "\n│  TOPLAM KALIP  : " (rtos toplam_kalip 2 3) " m²  ◄"))
  (prompt "\n└──────────────────────────────────────────────")
  (prompt "\n  Not: TS 500 kiriş kalıbı = 2h+b / döşeme brüt alandan kirişler düşülmez (std).")

  ;; ── Sonucu temp dosyaya yaz ───────────────────────────────
  (setq sonuc_yolu (strcat (getenv "TEMP") "\\imp_metraj.txt"))
  (setq sonuc_str
    (strcat "{"
      "\"tur\":\"kalip_alan\","
      "\"kolon_kalip\":"  (rtos kolon_kalip  2 4) ","
      "\"kiris_kalip\":"  (rtos kiris_kalip  2 4) ","
      "\"doseme_kalip\":" (rtos doseme_kalip 2 4) ","
      "\"toplam\":"       (rtos toplam_kalip 2 4) ","
      "\"kat_yuksekligi\":" (rtos kat_yuk   2 4) ","
      "\"kiris_b\":"      (rtos kiris_b     2 4) ","
      "\"kiris_h\":"      (rtos kiris_h     2 4) ","
      "\"birim\":\"m2\","
      "\"aciklama\":\"Kolon+kiris+doseme kalip alani (TS 500)\""
    "}"))
  (setq dosya (open sonuc_yolu "w"))
  (write-line sonuc_str dosya)
  (close dosya)

  (prompt (strcat "\n✔ Sonuç kaydedildi: " sonuc_yolu))
  (prompt "\n  Uygulamada 'Sonucu Oku' butonuna tıklayın.\n")
  toplam_kalip
)
