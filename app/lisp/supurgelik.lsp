;;; ============================================================
;;; SUPURGELIK.lsp  —  Süpürgelik / Karkas Uzunluğu Hesabı
;;; İnşaat Metraj Pro  |  v1.0  |  2026
;;; ============================================================
;;; KULLANIM:
;;;   AutoCAD komut satırına  c:SUPURGELIK  yazın.
;;;   1) Oda/zemin polyline'larını seçin → ENTER
;;;   2) Çıkarılacak kapı genişliklerini (bloklar) seçin → ENTER
;;;   Sonuç  %TEMP%\imp_metraj.txt  dosyasına yazılır.
;;;
;;; GEREKSİNİMLER:
;;;   • Odalar: kapalı LWPOLYLINE (perimeter = süpürgelik uzunluğu)
;;;   • Kapılar: INSERT blok, XScale = kapı genişliği (m)
;;;   NOT: Pencere altı süpürgelik genellikle ÇIKARILMAZ,
;;;        bu sebeple sadece kapılar menha edilir.
;;; ============================================================

(defun c:SUPURGELIK ( / ss_oda ss_kapi i ent obj
                        brut_uzunluk kapi_toplam net_uzunluk
                        kx bx dosya sonuc_str sonuc_yolu)

  ;; Katman değişkenleri (Python override edilebilir)
  (if (not (boundp '*IMP_KATMAN_ODA*))  (setq *IMP_KATMAN_ODA*  "MIMARI"))
  (if (not (boundp '*IMP_KATMAN_KAPI*)) (setq *IMP_KATMAN_KAPI* "KAPI"))

  (setq brut_uzunluk  0.0)
  (setq kapi_toplam   0.0)
  (setq i             0)

  (prompt "\n╔══════════════════════════════════════════╗")
  (prompt "\n║  SUPURGELIK  —  Süpürgelik Uzunluğu     ║")
  (prompt "\n╚══════════════════════════════════════════╝")

  ;; ── 1. Oda polyline seçimi ────────────────────────────────
  (prompt (strcat "\n► Oda polyline'larını seçin (çevre = süpürgelik)"
                  "  [Katman: " *IMP_KATMAN_ODA* "]"
                  "\n  (Otomatik seçim için ENTER): "))
  (setq ss_oda (ssget))

  (if (not ss_oda)
    (progn
      (prompt (strcat "\n  → Otomatik: '" *IMP_KATMAN_ODA* "' katmanı..."))
      (setq ss_oda (ssget "X"
        (list '(0 . "LWPOLYLINE") (cons 8 *IMP_KATMAN_ODA*))))
      (if (not ss_oda)
        (setq ss_oda (ssget "X"
          (list '(0 . "LWPOLYLINE") '(8 . "ODA")))))))

  (if (not ss_oda)
    (progn
      (prompt "\n⚠ Oda polyline'ı bulunamadı. İşlem iptal.")
      (exit)))

  ;; Brüt çevre toplamı (vlax-curve-getLength)
  (setq i 0)
  (while (< i (sslength ss_oda))
    (setq ent (ssname ss_oda i))
    (if (not (vl-catch-all-error-p
               (vl-catch-all-apply 'vlax-curve-getLength (list ent))))
      (setq brut_uzunluk
        (+ brut_uzunluk (abs (vlax-curve-getLength ent)))))
    (setq i (1+ i)))

  (prompt (strcat "\n  Brüt Çevre : " (rtos brut_uzunluk 2 3) " m"))

  ;; ── 2. Kapı blokları (menha) ──────────────────────────────
  (prompt "\n► Kapı bloklarını seçin (süpürgelik kesintisi)")
  (prompt "\n  (Otomatik katman tarama için ENTER): ")
  (setq ss_kapi (ssget))

  (if (not ss_kapi)
    (progn
      (setq ss_kapi (ssget "X"
        (list '(0 . "INSERT") (cons 8 *IMP_KATMAN_KAPI*))))
      (if ss_kapi
        (prompt (strcat "\n  → " (itoa (sslength ss_kapi)) " kapı bloğu bulundu."))
        (prompt "\n  → Kapı bulunamadı, menha yapılmayacak."))))

  ;; Kapı genişliklerini XScale'den oku
  (if ss_kapi
    (progn
      (setq i 0)
      (while (< i (sslength ss_kapi))
        (setq ent (ssname ss_kapi i))
        (setq obj (vlax-ename->vla-object ent))
        (setq bx (vl-catch-all-apply 'vlax-get-property (list obj 'XScaleFactor)))
        (if (not (vl-catch-all-error-p bx))
          (setq kapi_toplam (+ kapi_toplam (abs bx))))
        (setq i (1+ i)))))

  ;; ── 3. Net uzunluk ────────────────────────────────────────
  (setq net_uzunluk (- brut_uzunluk kapi_toplam))
  (if (< net_uzunluk 0) (setq net_uzunluk 0.0))

  ;; ── 4. Konsol çıktısı ────────────────────────────────────
  (prompt "\n┌─────────────────────────────────────")
  (prompt (strcat "\n│  Brüt Çevre   : " (rtos brut_uzunluk 2 3) " m"))
  (prompt (strcat "\n│  Kapı Menha   : " (rtos kapi_toplam   2 3) " m"))
  (prompt (strcat "\n│  NET Uzunluk  : " (rtos net_uzunluk   2 3) " m  ◄"))
  (prompt "\n└─────────────────────────────────────")
  (prompt "\n  Not: Pencere altı genellikle menha edilmez.")

  ;; ── 5. Sonucu temp dosyaya yaz ────────────────────────────
  (setq sonuc_yolu (strcat (getenv "TEMP") "\\imp_metraj.txt"))
  (setq sonuc_str
    (strcat "{"
      "\"tur\":\"supurgelik\","
      "\"brut\":"    (rtos brut_uzunluk 2 4) ","
      "\"kapi_menha\":" (rtos kapi_toplam 2 4) ","
      "\"net\":"     (rtos net_uzunluk   2 4) ","
      "\"birim\":\"m\","
      "\"aciklama\":\"Supurgelik/karkas net uzunlugu\""
    "}"))
  (setq dosya (open sonuc_yolu "w"))
  (write-line sonuc_str dosya)
  (close dosya)

  (prompt (strcat "\n✔ Sonuç kaydedildi: " sonuc_yolu))
  (prompt "\n  Uygulamada 'Sonucu Oku' butonuna tıklayın.\n")
  net_uzunluk
)
