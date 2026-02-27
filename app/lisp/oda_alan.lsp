;;; ============================================================
;;; ODA-ALAN.lsp  —  Oda Bazlı Net Alan Hesabı
;;; İnşaat Metraj Pro  |  v1.0  |  2026
;;; ============================================================
;;; KULLANIM:
;;;   AutoCAD komut satırına  c:ODA-ALAN  yazın.
;;;   1) Oda/zemin polyline'larını seçin → ENTER
;;;   (yoksa katman filtreli otomatik seçim)
;;;   Sonuç  %TEMP%\imp_metraj.txt  dosyasına yazılır.
;;;
;;; GEREKSİNİMLER:
;;;   • Odalar: kapalı LWPOLYLINE (1:1 ölçekli çizim)
;;;   • Oda adı: polygon içinde TEXT veya MTEXT (opsiyonel)
;;; ============================================================

(defun c:ODA-ALAN ( / ss_oda ss_yazi i j ent obj alan
                      bmin bmax cx cy isim_ent isim_obj isim_str
                      oda_listesi oda_item json_odalar
                      toplam dosya sonuc_str sonuc_yolu
                      tx ty ent_tip)

  ;; Katman değişkenleri (Python override edilebilir)
  (if (not (boundp '*IMP_KATMAN_ODA*))  (setq *IMP_KATMAN_ODA*  "MIMARI"))
  (if (not (boundp '*IMP_KATMAN_YAZI*)) (setq *IMP_KATMAN_YAZI* "YAZI"))

  (setq toplam       0.0)
  (setq oda_listesi  nil)
  (setq i            0)

  (prompt "\n╔══════════════════════════════════════════╗")
  (prompt "\n║  ODA-ALAN  —  Oda Bazlı Alan Hesabı     ║")
  (prompt "\n╚══════════════════════════════════════════╝")

  ;; ── 1. Oda polyline seçimi ────────────────────────────────
  (prompt (strcat "\n► Oda polyline'larını seçin"
                  "  [Katman: " *IMP_KATMAN_ODA* "]"
                  "\n  (Otomatik seçim için ENTER): "))
  (setq ss_oda (ssget))

  (if (not ss_oda)
    (progn
      (prompt (strcat "\n  → Otomatik: '" *IMP_KATMAN_ODA* "' katmanı taranıyor..."))
      ;; Birden fazla katman denemesi
      (setq ss_oda (ssget "X"
        (list '(0 . "LWPOLYLINE") (cons 8 *IMP_KATMAN_ODA*))))
      (if (not ss_oda)
        (setq ss_oda (ssget "X"
          (list '(0 . "LWPOLYLINE") '(8 . "ODA")))))))

  (if (not ss_oda)
    (progn
      (prompt "\n⚠ Oda polyline'ı bulunamadı. İşlem iptal.")
      (exit)))

  ;; ── 2. Her oda için alan + isim bul ──────────────────────
  (setq i 0)
  (while (< i (sslength ss_oda))
    (setq ent (ssname ss_oda i))
    (setq alan
      (if (vl-catch-all-error-p
            (vl-catch-all-apply 'vlax-curve-getArea (list ent)))
        0.0
        (abs (vlax-curve-getArea ent))))

    ;; Bounding box al → merkez koordinat
    (vla-GetBoundingBox
      (vlax-ename->vla-object ent)
      'bmin 'bmax)
    (setq bmin (vlax-safearray->list bmin))
    (setq bmax (vlax-safearray->list bmax))
    (setq cx (* 0.5 (+ (car bmin) (car bmax))))
    (setq cy (* 0.5 (+ (cadr bmin) (cadr bmax))))

    ;; Merkeze yakın TEXT/MTEXT ara (50 birim tolerans)
    (setq isim_str "Oda")
    (setq ss_yazi
      (ssget "C"
        (list (- cx 50) (- cy 50) 0)
        (list (+ cx 50) (+ cy 50) 0)
        (list '(0 . "TEXT,MTEXT"))))

    (if ss_yazi
      (progn
        (setq isim_ent (ssname ss_yazi 0))
        (setq ent_tip (cdr (assoc 0 (entget isim_ent))))
        (setq isim_str
          (if (= ent_tip "MTEXT")
            ;; MTEXT: kod 1
            (cdr (assoc 1 (entget isim_ent)))
            ;; TEXT: kod 1
            (cdr (assoc 1 (entget isim_ent)))))
        ;; MTEXT içindeki RTF kodlarını temizle
        (if (wcmatch isim_str "*\\*")
          (setq isim_str
            (vl-string-subst "" "\\" isim_str)))
      ))

    (if (> alan 0)
      (progn
        (setq oda_item (list (cons "isim" isim_str)
                             (cons "alan" alan)))
        (setq oda_listesi (append oda_listesi (list oda_item)))
        (setq toplam (+ toplam alan))
        (prompt (strcat "\n  " isim_str " : " (rtos alan 2 2) " m²"))))

    (setq i (1+ i)))

  ;; ── 3. Konsol özeti ───────────────────────────────────────
  (prompt "\n┌─────────────────────────────────────")
  (prompt (strcat "\n│  Toplam Oda Sayısı : " (itoa (length oda_listesi))))
  (prompt (strcat "\n│  TOPLAM NET ALAN   : " (rtos toplam 2 3) " m²  ◄"))
  (prompt "\n└─────────────────────────────────────")

  ;; ── 4. JSON oluştur ───────────────────────────────────────
  ;; Oda listesini JSON dizisine çevir
  (setq json_odalar "[")
  (setq j 0)
  (foreach oda oda_listesi
    (setq json_odalar
      (strcat json_odalar
        "{\"isim\":\"" (cdr (assoc "isim" oda)) "\","
        "\"alan\":"   (rtos (cdr (assoc "alan"  oda)) 2 4)
        "}"))
    (setq j (1+ j))
    (if (< j (length oda_listesi))
      (setq json_odalar (strcat json_odalar ","))))
  (setq json_odalar (strcat json_odalar "]"))

  (setq sonuc_str
    (strcat "{"
      "\"tur\":\"oda_alan\","
      "\"odalar\":" json_odalar ","
      "\"toplam\":"  (rtos toplam 2 4) ","
      "\"birim\":\"m2\","
      "\"aciklama\":\"Oda bazli net alan hesabi\""
    "}"))

  ;; ── 5. Temp dosyaya yaz ───────────────────────────────────
  (setq sonuc_yolu (strcat (getenv "TEMP") "\\imp_metraj.txt"))
  (setq dosya (open sonuc_yolu "w"))
  (write-line sonuc_str dosya)
  (close dosya)

  (prompt (strcat "\n✔ Sonuç kaydedildi: " sonuc_yolu))
  (prompt "\n  Uygulamada 'Sonucu Oku' butonuna tıklayın.\n")
  toplam
)
