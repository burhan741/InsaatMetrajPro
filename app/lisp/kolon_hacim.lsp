;;; ============================================================
;;; KOLON-HACIM.lsp  —  Kolon Beton Hacmi Hesabı
;;; İnşaat Metraj Pro  |  v1.0  |  2026
;;; ============================================================
;;; KULLANIM:
;;;   AutoCAD komut satırına  c:KOLON-HACIM  yazın.
;;;   1) Kolon polyline'larını seçin → ENTER
;;;   2) Kat yüksekliğini girin (m) → ENTER  [varsayılan: 3.0]
;;;   Sonuç  %TEMP%\imp_metraj.txt  dosyasına yazılır.
;;;
;;; GEREKSİNİMLER:
;;;   • Kolonlar: kapalı LWPOLYLINE (kolon enkesiti, 1:1 ölçekli)
;;;   • Kat yüksekliği: kullanıcıdan istenir veya Python'dan *IMP_KAT_YUKSEKLIGI*
;;;   FORMÜL: Hacim = Σ(enkesit_alanı × kat_yüksekliği)
;;; ============================================================

(defun c:KOLON-HACIM ( / ss_kolon i ent alan
                         kat_yuk kolon_sayisi brut_hacim
                         dosya sonuc_str sonuc_yolu
                         girdilen_yuk)

  ;; Katman ve parametre değişkenleri (Python override edilebilir)
  (if (not (boundp '*IMP_KATMAN_KOLON*))    (setq *IMP_KATMAN_KOLON*    "KOLON"))
  (if (not (boundp '*IMP_KAT_YUKSEKLIGI*))  (setq *IMP_KAT_YUKSEKLIGI*  3.0))

  (setq brut_hacim  0.0)
  (setq kolon_sayisi 0)

  (prompt "\n╔══════════════════════════════════════════╗")
  (prompt "\n║  KOLON-HACIM  —  Kolon Beton Hacmi      ║")
  (prompt "\n╚══════════════════════════════════════════╝")

  ;; ── 1. Kolon polyline seçimi ──────────────────────────────
  (prompt (strcat "\n► Kolon kesit polyline'larını seçin"
                  "  [Katman: " *IMP_KATMAN_KOLON* "]"
                  "\n  (Otomatik seçim için ENTER): "))
  (setq ss_kolon (ssget))

  (if (not ss_kolon)
    (progn
      (prompt (strcat "\n  → Otomatik: '" *IMP_KATMAN_KOLON* "' katmanı taranıyor..."))
      (setq ss_kolon (ssget "X"
        (list '(0 . "LWPOLYLINE") (cons 8 *IMP_KATMAN_KOLON*))))
      (if (not ss_kolon)
        (setq ss_kolon (ssget "X"
          (list '(0 . "LWPOLYLINE") '(8 . "COLUMN")))))))

  (if (not ss_kolon)
    (progn
      (prompt "\n⚠ Kolon polyline'ı bulunamadı. İşlem iptal.")
      (exit)))

  ;; ── 2. Kat yüksekliği ────────────────────────────────────
  (if (= *IMP_KAT_YUKSEKLIGI* 0.0)
    ;; Python'dan sıfır geldiyse kullanıcıdan iste
    (progn
      (setq girdilen_yuk
        (getdist (strcat "\n► Kat yüksekliğini girin [" (rtos 3.0 2 2) " m]: ")))
      (if (not girdilen_yuk)
        (setq kat_yuk 3.0)
        (setq kat_yuk (abs girdilen_yuk))))
    ;; Python'dan geldi
    (setq kat_yuk *IMP_KAT_YUKSEKLIGI*))

  ;; Kullanıcı doğrudan kat yüksekliği girmek istiyorsa:
  (if (and (= kat_yuk 3.0)
           (/= *IMP_KAT_YUKSEKLIGI* 3.0))
    (progn
      (setq girdilen_yuk
        (getdist (strcat "\n► Kat yüksekliğini girin [" (rtos *IMP_KAT_YUKSEKLIGI* 2 2) " m]: ")))
      (if girdilen_yuk
        (setq kat_yuk (abs girdilen_yuk)))))

  ;; Kullanıcı hiç girmemişse varsayılan
  (if (or (not kat_yuk) (= kat_yuk 0))
    (setq kat_yuk *IMP_KAT_YUKSEKLIGI*))

  (prompt (strcat "\n  Kat Yüksekliği: " (rtos kat_yuk 2 2) " m"))

  ;; ── 3. Her kolon için enkesit alanı hesapla ───────────────
  (setq i 0)
  (while (< i (sslength ss_kolon))
    (setq ent (ssname ss_kolon i))
    (setq alan
      (if (vl-catch-all-error-p
            (vl-catch-all-apply 'vlax-curve-getArea (list ent)))
        0.0
        (abs (vlax-curve-getArea ent))))
    (if (> alan 0)
      (progn
        (setq brut_hacim (+ brut_hacim (* alan kat_yuk)))
        (setq kolon_sayisi (1+ kolon_sayisi))
        (prompt (strcat "\n  Kolon " (itoa kolon_sayisi)
                        " : " (rtos alan 2 4) " m² × "
                        (rtos kat_yuk 2 2) " m = "
                        (rtos (* alan kat_yuk) 2 4) " m³"))))
    (setq i (1+ i)))

  ;; ── 4. Konsol çıktısı ────────────────────────────────────
  (prompt "\n┌─────────────────────────────────────")
  (prompt (strcat "\n│  Kolon Sayısı  : " (itoa kolon_sayisi)))
  (prompt (strcat "\n│  Kat Yüksekliği: " (rtos kat_yuk 2 2) " m"))
  (prompt (strcat "\n│  TOPLAM HACİM  : " (rtos brut_hacim 2 3) " m³  ◄"))
  (prompt "\n└─────────────────────────────────────")
  (prompt "\n  Not: Kirişlerle kesişim (bindirme) düşümü manuel yapın.")

  ;; ── 5. Sonucu temp dosyaya yaz ────────────────────────────
  (setq sonuc_yolu (strcat (getenv "TEMP") "\\imp_metraj.txt"))
  (setq sonuc_str
    (strcat "{"
      "\"tur\":\"kolon_hacim\","
      "\"kolon_sayisi\":" (itoa kolon_sayisi) ","
      "\"kat_yuksekligi\":" (rtos kat_yuk 2 4) ","
      "\"toplam_hacim\":" (rtos brut_hacim 2 4) ","
      "\"birim\":\"m3\","
      "\"aciklama\":\"Kolon beton hacmi (enkesit x kat yuksekligi)\""
    "}"))
  (setq dosya (open sonuc_yolu "w"))
  (write-line sonuc_str dosya)
  (close dosya)

  (prompt (strcat "\n✔ Sonuç kaydedildi: " sonuc_yolu))
  (prompt "\n  Uygulamada 'Sonucu Oku' butonuna tıklayın.\n")
  brut_hacim
)
