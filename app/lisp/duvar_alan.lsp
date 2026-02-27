;;; ============================================================
;;; DUVAR-ALAN.lsp  —  Net Duvar Alanı (Menha Düşümlü)
;;; İnşaat Metraj Pro  |  v1.0  |  2026
;;; ============================================================
;;; KULLANIM:
;;;   AutoCAD komut satırına  c:DUVAR-ALAN  yazın.
;;;   1) Duvar polyline'larını seçin → ENTER
;;;   2) Kapı/pencere bloklarını seçin → ENTER (yoksa direkt ENTER)
;;;   Sonuç  %TEMP%\imp_metraj.txt  dosyasına yazılır.
;;;
;;; GEREKSİNİMLER:
;;;   • Duvarlar: kapalı LWPOLYLINE (1:1 ölçekli çizim)
;;;   • Kapı/pencere: INSERT blok, XScale=genişlik(m), YScale=yükseklik(m)
;;; ============================================================

(defun c:DUVAR-ALAN ( / ss_duvar ss_bosluk brut_alan bosluk_alan net_alan
                        i ent obj bx by dosya sonuc_str sonuc_yolu)

  ;; --- Katman adları (Python tarafından *IMP_KATMAN_* değişkenleriyle override edilebilir) ---
  (if (not (boundp '*IMP_KATMAN_DUVAR*))   (setq *IMP_KATMAN_DUVAR*   "DUVAR"))
  (if (not (boundp '*IMP_KATMAN_KAPI*))    (setq *IMP_KATMAN_KAPI*    "KAPI"))
  (if (not (boundp '*IMP_KATMAN_PENCERE*)) (setq *IMP_KATMAN_PENCERE* "PENCERE"))

  (setq brut_alan   0.0)
  (setq bosluk_alan 0.0)
  (setq i 0)

  (prompt "\n╔══════════════════════════════════════════╗")
  (prompt "\n║  DUVAR-ALAN  —  Net Duvar Alanı Hesabı  ║")
  (prompt "\n╚══════════════════════════════════════════╝")

  ;; ── 1. Duvar polyline seçimi ──────────────────────────────
  (prompt (strcat "\n► Duvar polyline'larını seçin"
                  "  [Katman: " *IMP_KATMAN_DUVAR* "]"
                  "\n  (Katman filtreli otomatik seçim için ENTER'a basın): "))
  (setq ss_duvar (ssget))

  ;; Seçim yoksa katmana göre otomatik seç
  (if (not ss_duvar)
    (progn
      (prompt (strcat "\n  → Otomatik: '" *IMP_KATMAN_DUVAR* "' katmanı taranıyor..."))
      (setq ss_duvar (ssget "X"
        (list '(0 . "LWPOLYLINE") (cons 8 *IMP_KATMAN_DUVAR*))))))

  (if (not ss_duvar)
    (progn
      (prompt "\n⚠ Duvar polyline'ı bulunamadı. İşlem iptal.")
      (exit)))

  ;; Brüt alan hesabı (tüm seçili polyline'lar)
  (setq i 0)
  (while (< i (sslength ss_duvar))
    (setq ent (ssname ss_duvar i))
    (if (vl-catch-all-error-p
          (vl-catch-all-apply 'vlax-curve-getArea (list ent)))
      nil  ; hatalı objeyi atla
      (setq brut_alan (+ brut_alan (abs (vlax-curve-getArea ent)))))
    (setq i (1+ i)))

  (prompt (strcat "\n  Brüt Alan: " (rtos brut_alan 2 3) " m²"))

  ;; ── 2. Boşluk (kapı/pencere) seçimi ──────────────────────
  (prompt "\n► Kapı/Pencere bloklarını seçin")
  (prompt "\n  (Seçim yoksa ENTER: otomatik katman tarama): ")
  (setq ss_bosluk (ssget))

  (if (not ss_bosluk)
    (progn
      ;; Katmana göre tüm kapı+pencere INSERT'lerini al
      (setq ss_bosluk
        (ssget "X"
          (list '(0 . "INSERT")
                (cons 8 (strcat *IMP_KATMAN_KAPI* "," *IMP_KATMAN_PENCERE*)))))
      (if ss_bosluk
        (prompt (strcat "\n  → " (itoa (sslength ss_bosluk)) " boşluk bloğu otomatik bulundu."))
        (prompt "\n  → Boşluk bulunamadı, düşüm yapılmayacak."))))

  ;; Boşluk alan hesabı
  (if ss_bosluk
    (progn
      (setq i 0)
      (while (< i (sslength ss_bosluk))
        (setq ent (ssname ss_bosluk i))
        (setq obj (vlax-ename->vla-object ent))
        (setq bx (vl-catch-all-apply 'vlax-get-property (list obj 'XScaleFactor)))
        (setq by (vl-catch-all-apply 'vlax-get-property (list obj 'YScaleFactor)))
        (if (and (not (vl-catch-all-error-p bx))
                 (not (vl-catch-all-error-p by)))
          (setq bosluk_alan (+ bosluk_alan (* (abs bx) (abs by)))))
        (setq i (1+ i)))))

  ;; ── 3. Net alan hesabı ────────────────────────────────────
  (setq net_alan (- brut_alan bosluk_alan))
  (if (< net_alan 0) (setq net_alan 0.0))

  ;; ── 4. Konsol çıktısı ────────────────────────────────────
  (prompt "\n┌─────────────────────────────────────")
  (prompt (strcat "\n│  Brüt Alan  : " (rtos brut_alan   2 3) " m²"))
  (prompt (strcat "\n│  Menha      : " (rtos bosluk_alan 2 3) " m²"))
  (prompt (strcat "\n│  NET Alan   : " (rtos net_alan    2 3) " m²  ◄"))
  (prompt "\n└─────────────────────────────────────")

  ;; ── 5. Sonucu temp dosyaya yaz ────────────────────────────
  (setq sonuc_yolu (strcat (getenv "TEMP") "\\imp_metraj.txt"))
  (setq sonuc_str
    (strcat "{"
      "\"tur\":\"duvar_alan\","
      "\"brut\":" (rtos brut_alan   2 4) ","
      "\"bosluk\":" (rtos bosluk_alan 2 4) ","
      "\"net\":" (rtos net_alan    2 4) ","
      "\"birim\":\"m2\","
      "\"aciklama\":\"Net duvar alani (menha dusumlu)\""
    "}"))
  (setq dosya (open sonuc_yolu "w"))
  (write-line sonuc_str dosya)
  (close dosya)

  (prompt (strcat "\n✔ Sonuç kaydedildi: " sonuc_yolu))
  (prompt "\n  Uygulamada 'Sonucu Oku' butonuna tıklayın.\n")
  net_alan
)
