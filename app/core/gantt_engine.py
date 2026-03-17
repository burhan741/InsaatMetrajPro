"""
Gantt Chart ve CPM (Critical Path Method) Modülü
Proje is programi, kritik yol analizi ve zaman yonetimi

Ozellikler:
- CPM algoritması (Kahn topolojik siralama, Forward/Backward Pass, Float hesabi)
- Resmi tatil destegi (Turkiye)
- Baseline karsilastirma
- WBS (Work Breakdown Structure) hiyerarsisi
- Kaynak cakisma kontrolu ve otomatik dengeleme
- S-Curve (Kazanilmis Deger) analizi
- What-If senaryo simulasyonu
- Drag & Drop gorev tasima
- SQLite veritabani kayit/yukleme
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Tuple, Set
import logging
from collections import defaultdict, deque
import uuid

logger = logging.getLogger(__name__)


# ==================== TURKIYE RESMI TATILLERI ====================

TURKIYE_RESMI_TATILLER_SABIT = [
    (1,  1,  "Yilbasi"),
    (4,  23, "Ulusal Egemenlik ve Cocuk Bayrami"),
    (5,  1,  "Emek ve Dayanisma Gunu"),
    (5,  19, "Ataturk'u Anma, Genclik ve Spor Bayrami"),
    (7,  15, "Demokrasi ve Milli Birlik Gunu"),
    (8,  30, "Zafer Bayrami"),
    (10, 29, "Cumhuriyet Bayrami"),
]

RAMAZAN_BAYRAMI_TARIHLERI = {
    2024: [(4, 10), (4, 11), (4, 12)],
    2025: [(3, 30), (3, 31), (4, 1)],
    2026: [(3, 20), (3, 21), (3, 22)],
    2027: [(3, 9),  (3, 10), (3, 11)],
    2028: [(2, 26), (2, 27), (2, 28)],
    2029: [(2, 14), (2, 15), (2, 16)],
    2030: [(2, 4),  (2, 5),  (2, 6)],
}

KURBAN_BAYRAMI_TARIHLERI = {
    2024: [(6, 16), (6, 17), (6, 18), (6, 19)],
    2025: [(6, 6),  (6, 7),  (6, 8),  (6, 9)],
    2026: [(5, 27), (5, 28), (5, 29), (5, 30)],
    2027: [(5, 16), (5, 17), (5, 18), (5, 19)],
    2028: [(5, 5),  (5, 6),  (5, 7),  (5, 8)],
    2029: [(4, 24), (4, 25), (4, 26), (4, 27)],
    2030: [(4, 13), (4, 14), (4, 15), (4, 16)],
}


# ==================== MEVSIMSEL KISIT ====================

class MevsimselKisit:
    """
    Mevsimsel ve hava kosulu kisitlari yonetimi.

    Turkiye insaatinda kis doneminde (Aralik-Subat) beton dokumu,
    siva, boya gibi isler donma riski nedeniyle yapilamaz.
    (TS 500 md.5.6 referansi)
    """

    def __init__(self):
        self.aktif: bool = False
        self.kisit_aylari: List[int] = []
        self.kisit_aciklama: str = "Mevsimsel Insaat Kisiti"
        self.ozel_kisit_donemler: List[Tuple[datetime, datetime, str]] = []

    def set_kis_donemi_kisit(self, aktif: bool = True) -> None:
        """Kis donemi kisitini ayarla (Aralik, Ocak, Subat)."""
        self.aktif = aktif
        if aktif:
            self.kisit_aylari = [12, 1, 2]
            self.kisit_aciklama = "Kis Donemi Kisiti (Donma Riski - TS 500 md.5.6)"
        else:
            self.kisit_aylari = []

    def donem_ekle(self, baslangic: datetime, bitis: datetime, aciklama: str = "") -> None:
        """Ozel kisit donemi ekle."""
        self.ozel_kisit_donemler.append(
            (baslangic, bitis, aciklama or self.kisit_aciklama)
        )

    def donem_sil(self, baslangic: datetime) -> None:
        """Baslangic tarihine gore ozel kisit donemini sil."""
        self.ozel_kisit_donemler = [
            (b, e, a) for b, e, a in self.ozel_kisit_donemler
            if b.date() != baslangic.date()
        ]

    def kisit_mi(self, tarih: datetime) -> Tuple[bool, str]:
        """Verilen tarihte kisit var mi kontrol et."""
        if self.aktif and tarih.month in self.kisit_aylari:
            return True, self.kisit_aciklama
        for b, e, a in self.ozel_kisit_donemler:
            if b.date() <= tarih.date() <= e.date():
                return True, a
        return False, ""

    def get_kisit_ozet(self) -> Dict[str, Any]:
        """Kisit ozetini dondur."""
        return {
            'aktif': self.aktif,
            'kisit_aylari': self.kisit_aylari,
            'aciklama': self.kisit_aciklama,
            'ozel_donem_sayisi': len(self.ozel_kisit_donemler),
        }


# ==================== TASK (IS KALEMI) ====================

class Task:
    """Is kalemi (Task) veri sinifi."""

    def __init__(
        self,
        task_id: int,
        ad: str,
        sure_gun: int,
        baslangic_tarihi: Optional[datetime] = None,
        bitis_tarihi: Optional[datetime] = None,
        ilerleme: float = 0.0,
        metraj_kalem_id: Optional[int] = None,
        aciklama: str = "",
        milestone: bool = False,
        kaynak: str = "",
        wbs_kodu: str = "",
        parent_id: Optional[int] = None,
        renk: str = "#3498db",
    ):
        self.task_id = task_id
        self.ad = ad
        self.sure_gun = sure_gun
        self.baslangic_tarihi = baslangic_tarihi
        self.bitis_tarihi = bitis_tarihi
        self.ilerleme = ilerleme          # 0-100 arasi
        self.metraj_kalem_id = metraj_kalem_id
        self.aciklama = aciklama
        self.milestone = milestone
        self.kaynak = kaynak
        self.renk = renk

        # WBS (Work Breakdown Structure)
        self.wbs_kodu = wbs_kodu          # Orn: "1.1.2"
        self.parent_id = parent_id
        self.children: List[int] = []
        self.seviye = 0                   # 0=ana, 1=alt, 2=alt-alt...

        # CPM hesaplamalari
        self.early_start: Optional[datetime] = None
        self.early_finish: Optional[datetime] = None
        self.late_start: Optional[datetime] = None
        self.late_finish: Optional[datetime] = None
        self.float_gun: int = 0
        self.kritik: bool = False

        # Baseline degerleri
        self.baseline_baslangic: Optional[datetime] = None
        self.baseline_bitis: Optional[datetime] = None
        self.baseline_sure_gun: Optional[int] = None

        # Gerceklesen degerler
        self.gercek_baslangic: Optional[datetime] = None
        self.gercek_bitis: Optional[datetime] = None

        # Maliyet ve Hakedis alanlari
        self.butce: float = 0.0            # Planlanan butce (TL)
        self.gercek_maliyet: float = 0.0   # Gerceklesen maliyet (TL)
        self.birim_fiyat: float = 0.0      # Birim fiyat (TL/birim)

        # Bagimliliklar
        self.predecessors: List[Tuple[int, str, int]] = []  # (task_id, dep_type, lag)
        self.successors: List[Tuple[int, str, int]] = []    # (task_id, dep_type, lag)

    def hesapla_bitis_tarihi(self) -> Optional[datetime]:
        """Baslangic tarihinden bitis tarihini hesapla (hafta sonu haric)."""
        if self.baslangic_tarihi and self.sure_gun > 0:
            gun_sayaci = 0
            tarih = self.baslangic_tarihi
            while gun_sayaci < self.sure_gun:
                tarih += timedelta(days=1)
                if tarih.weekday() < 5:
                    gun_sayaci += 1
            return tarih
        return None

    def hesapla_sure(self) -> int:
        """Baslangic ve bitis tarihinden sureyi hesapla (is gunu)."""
        if self.baslangic_tarihi and self.bitis_tarihi:
            gun_sayaci = 0
            tarih = self.baslangic_tarihi
            while tarih < self.bitis_tarihi:
                tarih += timedelta(days=1)
                if tarih.weekday() < 5:
                    gun_sayaci += 1
            return gun_sayaci
        return 0

    def get_durum(self) -> str:
        """Is durumunu dondur."""
        if self.ilerleme >= 100:
            return "tamamlandi"
        elif self.ilerleme > 0:
            return "devam_ediyor"
        elif self.baslangic_tarihi and datetime.now() > self.baslangic_tarihi:
            return "gecikmis"
        return "baslanmadi"

    def get_durum_rengi(self) -> str:
        """Durum rengini dondur."""
        return {
            'tamamlandi':   '#27ae60',
            'devam_ediyor': '#3498db',
            'gecikmis':     '#e74c3c',
            'baslanmadi':   '#95a5a6',
        }.get(self.get_durum(), '#95a5a6')

    def set_baseline(self):
        """Mevcut plani baseline olarak kaydet."""
        if self.early_start is not None:
            self.baseline_baslangic = self.early_start
        if self.early_finish is not None:
            self.baseline_bitis = self.early_finish
        self.baseline_sure_gun = self.sure_gun

    def get_sapma_gun(self) -> Dict[str, int]:
        """Baseline'dan sapma hesapla (gun cinsinden)."""
        sapma = {'baslangic_sapma': 0, 'bitis_sapma': 0, 'sure_sapma': 0}
        if self.baseline_baslangic and self.early_start:
            sapma['baslangic_sapma'] = (self.early_start - self.baseline_baslangic).days
        if self.baseline_bitis and self.early_finish:
            sapma['bitis_sapma'] = (self.early_finish - self.baseline_bitis).days
        if self.baseline_sure_gun:
            sapma['sure_sapma'] = self.sure_gun - self.baseline_sure_gun
        return sapma

    def get_tamamlanma_yuzdesi(self) -> float:
        """Zaman bazli tamamlanma yuzdesi hesapla."""
        if not self.early_start or not self.early_finish:
            return 0.0
        bugun = datetime.now()
        if bugun < self.early_start:
            return 0.0
        elif bugun >= self.early_finish:
            return 100.0
        toplam = (self.early_finish - self.early_start).days
        gecen = (bugun - self.early_start).days
        return (gecen / toplam * 100) if toplam > 0 else 0.0

    def __repr__(self):
        return f"Task({self.task_id}: {self.ad}, {self.sure_gun} gun, WBS: {self.wbs_kodu})"


# ==================== TATIL YONETICISI ====================

class TatilYoneticisi:
    """Resmi tatil, ozel tatil ve mevsimsel kisit yonetimi."""

    def __init__(self):
        self.ozel_tatiller: List[Tuple[datetime, str]] = []
        self.hafta_sonu_calisma = False
        self.cumartesi_yarim_gun = False
        self.mevsimsel_kisit: Optional[MevsimselKisit] = None

    def get_yil_tatilleri(self, yil: int) -> List[Tuple[datetime, str]]:
        """Belirli bir yilin tum tatillerini getir."""
        tatiller = []
        for ay, gun, aciklama in TURKIYE_RESMI_TATILLER_SABIT:
            tatiller.append((datetime(yil, ay, gun), aciklama))
        if yil in RAMAZAN_BAYRAMI_TARIHLERI:
            for ay, gun in RAMAZAN_BAYRAMI_TARIHLERI[yil]:
                tatiller.append((datetime(yil, ay, gun), "Ramazan Bayrami"))
        if yil in KURBAN_BAYRAMI_TARIHLERI:
            for ay, gun in KURBAN_BAYRAMI_TARIHLERI[yil]:
                tatiller.append((datetime(yil, ay, gun), "Kurban Bayrami"))
        for tarih, aciklama in self.ozel_tatiller:
            if tarih.year == yil:
                tatiller.append((tarih, aciklama))
        return sorted(tatiller, key=lambda x: x[0])

    def tatil_mi(self, tarih: datetime) -> Tuple[bool, str]:
        """Verilen tarih tatil mi kontrol et."""
        if tarih.weekday() == 6:
            return True, "Pazar"
        if tarih.weekday() == 5 and not self.hafta_sonu_calisma:
            return True, "Cumartesi"
        for tatil_tarihi, aciklama in self.get_yil_tatilleri(tarih.year):
            if tarih.date() == tatil_tarihi.date():
                return True, aciklama
        if self.mevsimsel_kisit:
            kisit, kisit_aciklama = self.mevsimsel_kisit.kisit_mi(tarih)
            if kisit:
                return True, kisit_aciklama
        return False, ""

    def ekle_ozel_tatil(self, tarih: datetime, aciklama: str):
        """Ozel tatil ekle."""
        self.ozel_tatiller.append((tarih, aciklama))

    def sil_ozel_tatil(self, tarih: datetime):
        """Ozel tatil sil."""
        self.ozel_tatiller = [
            (t, a) for t, a in self.ozel_tatiller
            if t.date() != tarih.date()
        ]

    def get_donem_tatil_sayisi(self, baslangic: datetime, bitis: datetime) -> int:
        """Iki tarih arasindaki tatil sayisini hesapla."""
        tatil_sayisi = 0
        tarih = baslangic
        while tarih <= bitis:
            tatil, _ = self.tatil_mi(tarih)
            if tatil:
                tatil_sayisi += 1
            tarih += timedelta(days=1)
        return tatil_sayisi


# ==================== GANTT ENGINE (ANA MOTOR) ====================

class GanttEngine:
    """
    Gantt Chart ve CPM (Critical Path Method) motoru.

    Desteklenen ozellikler:
    - Is programi olusturma (CPM - Kahn topolojik siralama)
    - Kritik yol analizi (Forward/Backward Pass, Float hesabi)
    - Bagimlilık yonetimi (FS, SS, FF, SF + lag destegi)
    - Ilerleme takibi ve gecikme analizi
    - Milestone yonetimi
    - Resmi tatil destegi (Turkiye)
    - Baseline karsilastirma
    - WBS (Work Breakdown Structure) hiyerarsisi
    - Kaynak cakisma kontrolu ve otomatik dengeleme
    - S-Curve analizi (Planned Value / Earned Value)
    - What-If senaryo simulasyonu
    - Drag & Drop gorev tasima + cascade
    - SQLite veritabani kayit/yukleme
    """

    DEPENDENCY_TYPES = {
        'FS': 'Finish-to-Start',   # A bitsin, B baslasın (en yaygin)
        'SS': 'Start-to-Start',    # A baslasın, B baslasın
        'FF': 'Finish-to-Finish',  # A bitsin, B bitsin
        'SF': 'Start-to-Finish',   # A baslasın, B bitsin (nadir)
    }

    TASK_COLORS = {
        'normal':     '#3498db',  # Mavi
        'kritik':     '#e74c3c',  # Kirmizi
        'tamamlandi': '#27ae60',  # Yesil
        'gecikme':    '#e67e22',  # Turuncu
        'milestone':  '#9b59b6',  # Mor
        'ozet':       '#34495e',  # Koyu gri (summary task)
    }

    def __init__(self, db_manager=None):
        """
        Gantt motoru baslat.

        Args:
            db_manager: DatabaseManager instance (opsiyonel)
        """
        self.db = db_manager
        self.tasks: Dict[int, Task] = {}
        self.proje_baslangic: Optional[datetime] = None
        self.proje_bitis: Optional[datetime] = None
        self.kritik_yol: List[int] = []

        self.tatil_yoneticisi = TatilYoneticisi()
        self.baseline_kayitli = False
        self.baseline_tarihi: Optional[datetime] = None

        self.wbs_sayac: Dict[int, int] = {}
        self.kaynaklar: Dict[str, Dict[str, Any]] = {}
        self._scenarios: Dict[str, Any] = {}

    # ==================== GOREV YONETIMI ====================

    def add_task(self, task: Task) -> None:
        """Is kalemi ekle."""
        self.tasks[task.task_id] = task

    def add_dependency(
        self,
        predecessor_id: int,
        successor_id: int,
        dep_type: str = 'FS',
        lag_days: int = 0,
    ) -> bool:
        """
        Bagimlilık ekle.

        Args:
            predecessor_id: Onceki is ID
            successor_id: Sonraki is ID
            dep_type: Bagimlilık turu (FS, SS, FF, SF)
            lag_days: Gecikme (pozitif) veya one alma (negatif) gun sayisi

        Returns:
            Basari durumu
        """
        if predecessor_id not in self.tasks or successor_id not in self.tasks:
            logger.error(
                f"Bagimlilık kurulamadi: {predecessor_id} veya {successor_id} "
                "numarali is kalemi WBS agacinda bulunamadi."
            )
            return False

        if dep_type not in self.DEPENDENCY_TYPES:
            logger.error(f"Tanimsiz bagimlilık tipi '{dep_type}'. Gecerli tipler: FS, SS, FF, SF.")
            return False

        if self._creates_cycle(predecessor_id, successor_id):
            logger.error(
                "Dongüsel bagimlilık: CPM hesabi durdu. "
                "WBS hiyerarsisini ve oncul-ardul iliskilerini kontrol edin."
            )
            return False

        self.tasks[predecessor_id].successors.append((successor_id, dep_type, lag_days))
        self.tasks[successor_id].predecessors.append((predecessor_id, dep_type, lag_days))
        return True

    def _creates_cycle(self, from_id: int, to_id: int) -> bool:
        """Dongüsel bagimlilık kontrolu (DFS)."""
        visited: Set[int] = set()

        def dfs(task_id: int) -> bool:
            if task_id == from_id:
                return True
            if task_id in visited:
                return False
            visited.add(task_id)
            task = self.tasks.get(task_id)
            if not task:
                return False
            return any(dfs(succ_id) for succ_id, _, _ in task.successors)

        return dfs(to_id)

    # ==================== CPM HESAPLAMA ====================

    def calculate_schedule(self, proje_baslangic: datetime) -> Dict[str, Any]:
        """
        Is programini hesapla (CPM algoritmasi).

        Args:
            proje_baslangic: Proje baslangic tarihi

        Returns:
            Hesaplama sonuclari
        """
        self.proje_baslangic = proje_baslangic

        topo_order = self._topological_sort()
        if not topo_order:
            return {'error': 'Dongüsel bagimlilık tespit edildi!'}

        self._forward_pass(topo_order)
        self._backward_pass(topo_order)
        self._calculate_float()

        self.proje_bitis = max(
            (task.early_finish for task in self.tasks.values() if task.early_finish),
            default=proje_baslangic,
        )
        self.kritik_yol = self._find_critical_path()

        toplam_is = len(self.tasks)
        kritik_is_sayisi = len(self.kritik_yol)
        ortalama_float = (
            sum(t.float_gun for t in self.tasks.values()) / toplam_is
            if toplam_is > 0 else 0
        )

        return {
            'success': True,
            'proje_baslangic': proje_baslangic,
            'proje_bitis': self.proje_bitis,
            'toplam_sure_gun': self._calculate_working_days(proje_baslangic, self.proje_bitis),
            'toplam_is': toplam_is,
            'kritik_is_sayisi': kritik_is_sayisi,
            'kritik_yol': self.kritik_yol,
            'ortalama_float': round(ortalama_float, 1),
            'kritik_yuzde': round(kritik_is_sayisi / toplam_is * 100, 1) if toplam_is > 0 else 0,
        }

    def _topological_sort(self) -> List[int]:
        """Topolojik siralama (Kahn's algoritmasi)."""
        in_degree = {task_id: 0 for task_id in self.tasks}
        for task in self.tasks.values():
            for succ_id, _, _ in task.successors:
                in_degree[succ_id] += 1

        queue = deque([tid for tid, deg in in_degree.items() if deg == 0])
        result = []

        while queue:
            task_id = queue.popleft()
            result.append(task_id)
            for succ_id, _, _ in self.tasks[task_id].successors:
                in_degree[succ_id] -= 1
                if in_degree[succ_id] == 0:
                    queue.append(succ_id)

        if len(result) != len(self.tasks):
            logger.error("Topolojik siralama basarisiz: DAG kosulu ihlal edildi.")
            return []
        return result

    def _forward_pass(self, topo_order: List[int]) -> None:
        """Forward Pass - Early Start/Finish hesaplama."""
        for task_id in topo_order:
            task = self.tasks[task_id]
            if not task.predecessors:
                task.early_start = self.proje_baslangic
            else:
                max_early_finish = self.proje_baslangic
                for pred_id, dep_type, lag_days in task.predecessors:
                    pred = self.tasks[pred_id]
                    if dep_type == 'FS':
                        candidate = self._offset_working_days(pred.early_finish, lag_days)
                    elif dep_type == 'SS':
                        candidate = self._offset_working_days(pred.early_start, lag_days)
                    elif dep_type == 'FF':
                        ff_bitis = self._offset_working_days(pred.early_finish, lag_days)
                        candidate = self._subtract_working_days(ff_bitis, task.sure_gun)
                    elif dep_type == 'SF':
                        sf_bitis = self._offset_working_days(pred.early_start, lag_days)
                        candidate = self._subtract_working_days(sf_bitis, task.sure_gun)
                    else:
                        candidate = pred.early_finish
                    if candidate > max_early_finish:
                        max_early_finish = candidate
                task.early_start = max_early_finish
            task.early_finish = self._add_working_days(task.early_start, task.sure_gun)

    def _backward_pass(self, topo_order: List[int]) -> None:
        """Backward Pass - Late Start/Finish hesaplama."""
        for task_id in reversed(topo_order):
            task = self.tasks[task_id]
            if not task.successors:
                task.late_finish = task.early_finish
            else:
                min_late_start = datetime.max
                for succ_id, dep_type, lag_days in task.successors:
                    succ = self.tasks[succ_id]
                    if dep_type == 'FS':
                        candidate = self._offset_working_days(succ.late_start, -lag_days)
                    elif dep_type == 'SS':
                        ss_b = self._offset_working_days(succ.late_start, -lag_days)
                        candidate = self._add_working_days(ss_b, task.sure_gun)
                    elif dep_type == 'FF':
                        candidate = self._offset_working_days(succ.late_finish, -lag_days)
                    elif dep_type == 'SF':
                        sf_b = self._offset_working_days(succ.late_finish, -lag_days)
                        candidate = self._add_working_days(sf_b, task.sure_gun)
                    else:
                        candidate = succ.late_start
                    if candidate < min_late_start:
                        min_late_start = candidate
                task.late_finish = min_late_start
            task.late_start = self._subtract_working_days(task.late_finish, task.sure_gun)

    def _calculate_float(self) -> None:
        """Float (esneklik) hesapla ve kritik task'lari isaretler."""
        for task in self.tasks.values():
            if task.late_start and task.early_start:
                task.float_gun = self._calculate_working_days(task.early_start, task.late_start)
            task.kritik = (task.float_gun == 0)

    def _find_critical_path(self) -> List[int]:
        """Kritik yolu bul (float=0 olan task'lar, baslangic sirasina gore)."""
        kritik_tasks = [tid for tid, task in self.tasks.items() if task.kritik]
        kritik_tasks.sort(key=lambda tid: self.tasks[tid].early_start or datetime.min)
        return kritik_tasks

    # ==================== IS GUNU HESAPLAMA ====================

    def _add_working_days(self, start_date: datetime, days: int) -> datetime:
        """Is gunu ekle (tatiller ve hafta sonu haric)."""
        current = start_date
        added = 0
        while added < days:
            current += timedelta(days=1)
            tatil, _ = self.tatil_yoneticisi.tatil_mi(current)
            if not tatil:
                added += 1
        return current

    def _subtract_working_days(self, end_date: datetime, days: int) -> datetime:
        """Is gunu cikar (tatiller ve hafta sonu haric)."""
        current = end_date
        subtracted = 0
        while subtracted < days:
            current -= timedelta(days=1)
            tatil, _ = self.tatil_yoneticisi.tatil_mi(current)
            if not tatil:
                subtracted += 1
        return current

    def _offset_working_days(self, date: datetime, days: int) -> datetime:
        """Is gunu ekle veya cikar (pozitif/negatif gun)."""
        if days == 0:
            return date
        if days > 0:
            return self._add_working_days(date, days)
        return self._subtract_working_days(date, abs(days))

    def _calculate_working_days(self, start_date: datetime, end_date: datetime) -> int:
        """Iki tarih arasi is gunu sayisi (tatiller haric)."""
        if not start_date or not end_date:
            return 0
        days = 0
        current = start_date
        while current < end_date:
            current += timedelta(days=1)
            tatil, _ = self.tatil_yoneticisi.tatil_mi(current)
            if not tatil:
                days += 1
        return days

    # ==================== WBS YONETIMI ====================

    def add_task_with_wbs(self, task: Task, parent_id: Optional[int] = None) -> str:
        """WBS kodu ile is kalemi ekle."""
        if parent_id is None:
            self.wbs_sayac.setdefault(0, 0)
            self.wbs_sayac[0] += 1
            task.wbs_kodu = str(self.wbs_sayac[0])
            task.seviye = 0
        else:
            if parent_id not in self.tasks:
                raise ValueError(f"Parent task bulunamadi: {parent_id}")
            parent = self.tasks[parent_id]
            self.wbs_sayac.setdefault(parent_id, 0)
            self.wbs_sayac[parent_id] += 1
            task.wbs_kodu = f"{parent.wbs_kodu}.{self.wbs_sayac[parent_id]}"
            task.parent_id = parent_id
            task.seviye = parent.seviye + 1
            parent.children.append(task.task_id)
        self.tasks[task.task_id] = task
        return task.wbs_kodu

    def get_wbs_tree(self) -> List[Dict[str, Any]]:
        """WBS agac yapisini getir."""
        def build_tree(parent_id: Optional[int] = None) -> List[Dict[str, Any]]:
            tree = []
            for task_id, task in self.tasks.items():
                if task.parent_id == parent_id:
                    node = {
                        'task_id': task_id,
                        'ad': task.ad,
                        'wbs_kodu': task.wbs_kodu,
                        'seviye': task.seviye,
                        'sure_gun': task.sure_gun,
                        'ilerleme': task.ilerleme,
                        'children': build_tree(task_id),
                    }
                    tree.append(node)
            return sorted(tree, key=lambda x: x['wbs_kodu'])
        return build_tree(None)

    def get_summary_task_progress(self, parent_id: int) -> float:
        """Ozet gorev ilerleme yuzdesi (recursive, agirlikli ortalama)."""
        if parent_id not in self.tasks:
            return 0.0
        parent = self.tasks[parent_id]
        if not parent.children:
            return parent.ilerleme
        toplam_sure = 0
        toplam_ilerleme = 0.0
        for child_id in parent.children:
            if child_id not in self.tasks:
                continue
            child = self.tasks[child_id]
            child_ilerleme = (
                self.get_summary_task_progress(child_id)
                if child.children else child.ilerleme
            )
            toplam_sure += child.sure_gun
            toplam_ilerleme += child.sure_gun * child_ilerleme
        return (toplam_ilerleme / toplam_sure) if toplam_sure > 0 else 0.0

    # ==================== BASELINE YONETIMI ====================

    def save_baseline(self) -> Dict[str, Any]:
        """Mevcut plani baseline olarak kaydet."""
        if not self.tasks:
            return {'success': False, 'error': 'Kaydedilecek gorev yok'}
        for task in self.tasks.values():
            task.set_baseline()
        self.baseline_kayitli = True
        self.baseline_tarihi = datetime.now()
        return {'success': True, 'tarih': self.baseline_tarihi, 'gorev_sayisi': len(self.tasks)}

    def get_baseline_comparison(self) -> List[Dict[str, Any]]:
        """Baseline ile mevcut durum karsilastirmasi."""
        if not self.baseline_kayitli:
            return []
        karsilastirma = []
        for task_id, task in self.tasks.items():
            sapma = task.get_sapma_gun()
            karsilastirma.append({
                'task_id': task_id,
                'ad': task.ad,
                'wbs_kodu': task.wbs_kodu,
                'baseline_baslangic': task.baseline_baslangic,
                'baseline_bitis': task.baseline_bitis,
                'baseline_sure': task.baseline_sure_gun,
                'mevcut_baslangic': task.early_start,
                'mevcut_bitis': task.early_finish,
                'mevcut_sure': task.sure_gun,
                'baslangic_sapma': sapma['baslangic_sapma'],
                'bitis_sapma': sapma['bitis_sapma'],
                'sure_sapma': sapma['sure_sapma'],
                'gecikme_var': sapma['bitis_sapma'] > 0,
                'kritik': task.kritik,
            })
        return karsilastirma

    def get_baseline_summary(self) -> Dict[str, Any]:
        """Baseline ozet raporu."""
        if not self.baseline_kayitli:
            return {'baseline_var': False}
        karsilastirma = self.get_baseline_comparison()
        geciken_sayisi = sum(1 for k in karsilastirma if k['gecikme_var'])
        toplam_gecikme = sum(k['bitis_sapma'] for k in karsilastirma if k['bitis_sapma'] > 0)
        kritik_geciken = sum(1 for k in karsilastirma if k['gecikme_var'] and k['kritik'])
        return {
            'baseline_var': True,
            'baseline_tarihi': self.baseline_tarihi,
            'toplam_gorev': len(karsilastirma),
            'geciken_gorev': geciken_sayisi,
            'zamaninda_gorev': len(karsilastirma) - geciken_sayisi,
            'toplam_gecikme_gun': toplam_gecikme,
            'kritik_geciken': kritik_geciken,
            'proje_sapmasi': karsilastirma[-1]['bitis_sapma'] if karsilastirma else 0,
        }

    # ==================== KAYNAK YONETIMI ====================

    def add_kaynak(self, kaynak_adi: str, kapasite: int = 1, maliyet_gun: float = 0) -> None:
        """Kaynak (ekip/isci) ekle."""
        self.kaynaklar[kaynak_adi] = {
            'kapasite': kapasite,
            'maliyet_gun': maliyet_gun,
            'atamalar': [],
        }

    def atama_kaynak(self, task_id: int, kaynak_adi: str) -> bool:
        """Goreve kaynak ata."""
        if task_id not in self.tasks:
            return False
        if kaynak_adi not in self.kaynaklar:
            self.add_kaynak(kaynak_adi)
        self.tasks[task_id].kaynak = kaynak_adi
        self.kaynaklar[kaynak_adi]['atamalar'].append(task_id)
        return True

    def check_kaynak_cakisma(self) -> List[Dict[str, Any]]:
        """Kaynak cakismalarini tespit et."""
        cakismalar = []
        for kaynak_adi, kaynak_bilgi in self.kaynaklar.items():
            atamalar = kaynak_bilgi['atamalar']
            kapasite = kaynak_bilgi['kapasite']
            if len(atamalar) < 2:
                continue
            tarih_gorevler: Dict[str, List[int]] = defaultdict(list)
            for task_id in atamalar:
                if task_id not in self.tasks:
                    continue
                task = self.tasks[task_id]
                if not task.early_start or not task.early_finish:
                    continue
                tarih = task.early_start
                while tarih <= task.early_finish:
                    tatil, _ = self.tatil_yoneticisi.tatil_mi(tarih)
                    if not tatil:
                        tarih_gorevler[tarih.strftime('%Y-%m-%d')].append(task_id)
                    tarih += timedelta(days=1)
            for tarih_str, gorevler in tarih_gorevler.items():
                if len(gorevler) > kapasite:
                    cakismalar.append({
                        'kaynak': kaynak_adi,
                        'tarih': tarih_str,
                        'gorev_sayisi': len(gorevler),
                        'kapasite': kapasite,
                        'asim': len(gorevler) - kapasite,
                        'gorevler': [
                            self.tasks[tid].ad for tid in gorevler if tid in self.tasks
                        ],
                    })
        return cakismalar

    def get_kaynak_yukleme(self, kaynak_adi: str) -> Dict[str, float]:
        """Kaynagın gunluk yukleme oranini hesapla."""
        if kaynak_adi not in self.kaynaklar:
            return {}
        yukleme: Dict[str, float] = {}
        kaynak_bilgi = self.kaynaklar[kaynak_adi]
        for task_id in kaynak_bilgi['atamalar']:
            if task_id not in self.tasks:
                continue
            task = self.tasks[task_id]
            if not task.early_start or not task.early_finish:
                continue
            tarih = task.early_start
            while tarih <= task.early_finish:
                tatil, _ = self.tatil_yoneticisi.tatil_mi(tarih)
                if not tatil:
                    tarih_str = tarih.strftime('%Y-%m-%d')
                    yukleme[tarih_str] = yukleme.get(tarih_str, 0) + 1
                tarih += timedelta(days=1)
        kapasite = kaynak_bilgi['kapasite']
        for tarih_str in yukleme:
            yukleme[tarih_str] = (yukleme[tarih_str] / kapasite) * 100
        return yukleme

    # ==================== MALIYET HESABI ====================

    def calculate_kaynak_maliyet(self) -> Dict[str, Any]:
        """Kaynak bazli toplam maliyet hesapla."""
        kaynak_maliyetler: Dict[str, Any] = {}
        toplam_maliyet = 0.0
        toplam_is_gunu = 0

        for kaynak_adi, kaynak_bilgi in self.kaynaklar.items():
            maliyet_gun = kaynak_bilgi.get('maliyet_gun', 0)
            atamalar = kaynak_bilgi.get('atamalar', [])
            kaynak_toplam_gun = 0
            atanan_gorevler = []

            for task_id in atamalar:
                if task_id not in self.tasks:
                    continue
                task = self.tasks[task_id]
                gorev_maliyet = task.sure_gun * maliyet_gun
                kaynak_toplam_gun += task.sure_gun
                atanan_gorevler.append({
                    'task_id': task_id,
                    'ad': task.ad,
                    'sure_gun': task.sure_gun,
                    'birim_maliyet': maliyet_gun,
                    'toplam_maliyet': gorev_maliyet,
                    'kritik': task.kritik,
                })

            kaynak_toplam = kaynak_toplam_gun * maliyet_gun
            toplam_maliyet += kaynak_toplam
            toplam_is_gunu += kaynak_toplam_gun

            kaynak_maliyetler[kaynak_adi] = {
                'maliyet_gun': maliyet_gun,
                'kapasite': kaynak_bilgi.get('kapasite', 1),
                'toplam_gun': kaynak_toplam_gun,
                'toplam_maliyet': kaynak_toplam,
                'gorev_sayisi': len(atanan_gorevler),
                'gorevler': atanan_gorevler,
            }

        return {
            'toplam_maliyet': toplam_maliyet,
            'para_birimi': 'TL',
            'kaynaklar': kaynak_maliyetler,
            'ozet': {
                'toplam_is_gunu': toplam_is_gunu,
                'kaynak_sayisi': len(self.kaynaklar),
                'ortalama_gun_maliyet': toplam_maliyet / toplam_is_gunu if toplam_is_gunu > 0 else 0,
            },
        }

    def get_maliyet_raporu(self) -> str:
        """Metin formatinda maliyet raporu."""
        rapor = self.calculate_kaynak_maliyet()
        satirlar = ["=" * 60, "KAYNAK MALIYET RAPORU", f"Para Birimi: {rapor['para_birimi']}", "=" * 60]
        for kaynak_adi, bilgi in rapor['kaynaklar'].items():
            satirlar.append(
                f"\n{kaynak_adi}:"
                f"\n  Gunluk Maliyet: {bilgi['maliyet_gun']:,.0f} TL"
                f"\n  Toplam Gun:     {bilgi['toplam_gun']}"
                f"\n  Toplam Maliyet: {bilgi['toplam_maliyet']:,.0f} TL"
            )
        satirlar += ["=" * 60, f"TOPLAM MALIYET: {rapor['toplam_maliyet']:,.0f} TL", "=" * 60]
        return "\n".join(satirlar)

    def calculate_hakedis(self) -> Dict[str, Any]:
        """
        Hakedis hesabi: her gorev icin ilerleme% x birim_fiyat x miktar.

        Returns:
            Gorev bazli hakedis listesi ve toplam tutar.
        """
        kalemler = []
        toplam_hakedis = 0.0
        toplam_butce = 0.0

        for task in sorted(self.tasks.values(), key=lambda t: t.wbs_kodu or ''):
            if task.milestone:
                continue
            hak_edilen = (task.ilerleme / 100.0) * task.butce
            kalemler.append({
                'task_id': task.task_id,
                'wbs_kodu': task.wbs_kodu,
                'ad': task.ad,
                'ilerleme': task.ilerleme,
                'butce': task.butce,
                'birim_fiyat': task.birim_fiyat,
                'hak_edilen': round(hak_edilen, 2),
                'kalan': round(task.butce - hak_edilen, 2),
                'kritik': task.kritik,
                'baslangic': task.early_start.strftime('%d.%m.%Y') if task.early_start else '',
                'bitis': task.early_finish.strftime('%d.%m.%Y') if task.early_finish else '',
            })
            toplam_hakedis += hak_edilen
            toplam_butce += task.butce

        tamamlanma_yuzdesi = (toplam_hakedis / toplam_butce * 100) if toplam_butce > 0 else 0.0
        return {
            'kalemler': kalemler,
            'toplam_hakedis': round(toplam_hakedis, 2),
            'toplam_butce': round(toplam_butce, 2),
            'kalan_butce': round(toplam_butce - toplam_hakedis, 2),
            'tamamlanma_yuzdesi': round(tamamlanma_yuzdesi, 1),
            'para_birimi': 'TL',
        }

    def calculate_maliyet_performans(self) -> Dict[str, Any]:
        """
        EVM (Earned Value Management) - Maliyet performans analizi.

        BAC = Tum butcelerin toplami
        PV  = Planlanan Deger (zaman bazli butce harcama orani)
        EV  = Kazanilmis Deger (ilerleme% x BAC)
        AC  = Gercek Maliyet (gerceklesen harcamalar toplami)
        CPI = EV / AC  (>1 iyi, <1 butce asimi)
        SPI = EV / PV  (>1 iyi, <1 gecikme)
        ETC = (BAC - EV) / CPI  - Tahmini kalan maliyet
        EAC = AC + ETC           - Tahmini toplam maliyet
        """
        bac = sum(t.butce for t in self.tasks.values() if not t.milestone)
        ev = sum((t.ilerleme / 100.0) * t.butce for t in self.tasks.values() if not t.milestone)
        ac = sum(t.gercek_maliyet for t in self.tasks.values() if not t.milestone)

        # PV: bugun itibaриyla tamamlanmasi gereken butce orani
        bugun = datetime.now()
        pv = 0.0
        for task in self.tasks.values():
            if task.milestone or not task.early_start or not task.early_finish:
                continue
            if bugun <= task.early_start:
                pv += 0.0
            elif bugun >= task.early_finish:
                pv += task.butce
            else:
                toplam_gun = (task.early_finish - task.early_start).days or 1
                gecen_gun = (bugun - task.early_start).days
                pv += task.butce * (gecen_gun / toplam_gun)

        cpi = (ev / ac) if ac > 0 else 1.0
        spi = (ev / pv) if pv > 0 else 1.0
        etc = ((bac - ev) / cpi) if cpi > 0 else (bac - ev)
        eac = ac + etc
        sapma_maliyet = ev - ac        # CV: pozitif = tasarruf, negatif = asim
        sapma_zaman = ev - pv          # SV: pozitif = onde, negatif = geride

        gorev_detaylari = []
        for task in sorted(self.tasks.values(), key=lambda t: t.wbs_kodu or ''):
            if task.milestone:
                continue
            gorev_ev = (task.ilerleme / 100.0) * task.butce
            gorev_cv = gorev_ev - task.gercek_maliyet
            gorev_detaylari.append({
                'task_id': task.task_id,
                'ad': task.ad,
                'wbs_kodu': task.wbs_kodu,
                'butce': task.butce,
                'gercek_maliyet': task.gercek_maliyet,
                'ev': round(gorev_ev, 2),
                'cv': round(gorev_cv, 2),
                'ilerleme': task.ilerleme,
                'butce_durumu': 'normal' if gorev_cv >= 0 else 'asim',
            })

        durum = 'iyi'
        if cpi < 0.9 or spi < 0.9:
            durum = 'kritik'
        elif cpi < 1.0 or spi < 1.0:
            durum = 'uyari'

        return {
            'bac': round(bac, 2),
            'pv': round(pv, 2),
            'ev': round(ev, 2),
            'ac': round(ac, 2),
            'cpi': round(cpi, 3),
            'spi': round(spi, 3),
            'etc': round(etc, 2),
            'eac': round(eac, 2),
            'sapma_maliyet': round(sapma_maliyet, 2),
            'sapma_zaman': round(sapma_zaman, 2),
            'durum': durum,
            'para_birimi': 'TL',
            'gorev_detaylari': gorev_detaylari,
        }

    # ==================== EXPORT ====================

    def export_to_dict(self) -> Dict[str, Any]:
        """Tum veriyi dictionary olarak export et."""
        return {
            'proje_baslangic': self.proje_baslangic.isoformat() if self.proje_baslangic else None,
            'proje_bitis': self.proje_bitis.isoformat() if self.proje_bitis else None,
            'baseline_kayitli': self.baseline_kayitli,
            'baseline_tarihi': self.baseline_tarihi.isoformat() if self.baseline_tarihi else None,
            'tasks': [
                {
                    'task_id': t.task_id,
                    'ad': t.ad,
                    'wbs_kodu': t.wbs_kodu,
                    'sure_gun': t.sure_gun,
                    'ilerleme': t.ilerleme,
                    'kaynak': t.kaynak,
                    'kritik': t.kritik,
                    'float_gun': t.float_gun,
                    'early_start': t.early_start.isoformat() if t.early_start else None,
                    'early_finish': t.early_finish.isoformat() if t.early_finish else None,
                    'baseline_baslangic': t.baseline_baslangic.isoformat() if t.baseline_baslangic else None,
                    'baseline_bitis': t.baseline_bitis.isoformat() if t.baseline_bitis else None,
                }
                for t in self.tasks.values()
            ],
            'kritik_yol': self.kritik_yol,
            'kaynaklar': self.kaynaklar,
        }

    def export_to_excel_data(self) -> List[Dict[str, Any]]:
        """Excel export icin veri hazirla."""
        data = []
        for task in sorted(self.tasks.values(), key=lambda t: t.wbs_kodu or ''):
            sapma = (
                task.get_sapma_gun() if self.baseline_kayitli
                else {'baslangic_sapma': 0, 'bitis_sapma': 0, 'sure_sapma': 0}
            )
            data.append({
                'WBS': task.wbs_kodu,
                'Is Adi': task.ad,
                'Sure (Gun)': task.sure_gun,
                'Baslangic': task.early_start.strftime('%d.%m.%Y') if task.early_start else '',
                'Bitis': task.early_finish.strftime('%d.%m.%Y') if task.early_finish else '',
                'Ilerleme (%)': task.ilerleme,
                'Float (Gun)': task.float_gun,
                'Kritik': 'Evet' if task.kritik else 'Hayir',
                'Kaynak': task.kaynak,
                'Baseline Baslangic': task.baseline_baslangic.strftime('%d.%m.%Y') if task.baseline_baslangic else '',
                'Baseline Bitis': task.baseline_bitis.strftime('%d.%m.%Y') if task.baseline_bitis else '',
                'Baslangic Sapma (Gun)': sapma['baslangic_sapma'],
                'Bitis Sapma (Gun)': sapma['bitis_sapma'],
            })
        return data

    # ==================== GORSEL VERI ====================

    def get_gantt_chart_data(self) -> Dict[str, Any]:
        """Gorsel Gantt chart icin veri hazirla."""
        if not self.proje_baslangic or not self.proje_bitis:
            return {'error': 'Once is programini hesaplayin'}

        toplam_gun = (self.proje_bitis - self.proje_baslangic).days + 1
        haftalar, aylar, gunler = [], [], []
        tarih = self.proje_baslangic
        mevcut_ay = mevcut_hafta = None

        while tarih <= self.proje_bitis:
            gunler.append(tarih)
            ay_str = tarih.strftime('%B %Y')
            if ay_str != mevcut_ay:
                aylar.append({'tarih': tarih, 'ad': ay_str, 'baslangic_index': len(gunler) - 1})
                mevcut_ay = ay_str
            hafta_no = tarih.isocalendar()[1]
            if hafta_no != mevcut_hafta:
                haftalar.append({'tarih': tarih, 'hafta_no': hafta_no, 'baslangic_index': len(gunler) - 1})
                mevcut_hafta = hafta_no
            tarih += timedelta(days=1)

        cubuklar = []
        for task in sorted(self.tasks.values(), key=lambda t: (t.seviye, t.wbs_kodu or '')):
            if not task.early_start or not task.early_finish:
                continue
            baslangic_index = (task.early_start - self.proje_baslangic).days
            bitis_index = (task.early_finish - self.proje_baslangic).days
            if task.milestone:
                renk = self.TASK_COLORS['milestone']
            elif task.kritik:
                renk = self.TASK_COLORS['kritik']
            elif task.ilerleme >= 100:
                renk = self.TASK_COLORS['tamamlandi']
            elif task.children:
                renk = self.TASK_COLORS['ozet']
            else:
                renk = task.renk or self.TASK_COLORS['normal']

            cubuklar.append({
                'task_id': task.task_id,
                'ad': task.ad,
                'wbs_kodu': task.wbs_kodu,
                'seviye': task.seviye,
                'baslangic_index': baslangic_index,
                'bitis_index': bitis_index,
                'uzunluk': bitis_index - baslangic_index + 1,
                'ilerleme': task.ilerleme,
                'renk': renk,
                'kritik': task.kritik,
                'milestone': task.milestone,
                'float_gun': task.float_gun,
                'kaynak': task.kaynak,
                'baseline_baslangic_index': (
                    (task.baseline_baslangic - self.proje_baslangic).days
                    if task.baseline_baslangic else None
                ),
                'baseline_bitis_index': (
                    (task.baseline_bitis - self.proje_baslangic).days
                    if task.baseline_bitis else None
                ),
            })

        tatil_gunleri = []
        for i, gun in enumerate(gunler):
            tatil, aciklama = self.tatil_yoneticisi.tatil_mi(gun)
            if tatil:
                tatil_gunleri.append({'index': i, 'tarih': gun, 'aciklama': aciklama})

        return {
            'proje_baslangic': self.proje_baslangic,
            'proje_bitis': self.proje_bitis,
            'toplam_gun': toplam_gun,
            'gunler': gunler,
            'haftalar': haftalar,
            'aylar': aylar,
            'cubuklar': cubuklar,
            'tatil_gunleri': tatil_gunleri,
            'kritik_yol': self.kritik_yol,
            'baseline_var': self.baseline_kayitli,
        }

    def get_timeline_data(self) -> List[Dict[str, Any]]:
        """Gantt chart icin timeline verisi."""
        timeline = []
        for task_id, task in self.tasks.items():
            if not task.early_start or not task.early_finish:
                continue
            timeline.append({
                'task_id': task_id,
                'ad': task.ad,
                'baslangic': task.early_start,
                'bitis': task.early_finish,
                'sure_gun': task.sure_gun,
                'ilerleme': task.ilerleme,
                'durum': task.get_durum(),
                'renk': task.get_durum_rengi(),
                'kritik': task.kritik,
                'float_gun': task.float_gun,
                'milestone': task.milestone,
                'kaynak': task.kaynak,
            })
        timeline.sort(key=lambda x: x['baslangic'])
        return timeline

    def get_critical_path_info(self) -> Dict[str, Any]:
        """Kritik yol bilgilerini getir."""
        if not self.kritik_yol:
            return {'error': 'Kritik yol hesaplanmamis'}
        kritik_tasks = [self.tasks[tid] for tid in self.kritik_yol]
        return {
            'toplam_is': len(kritik_tasks),
            'toplam_sure_gun': sum(t.sure_gun for t in kritik_tasks),
            'baslangic': kritik_tasks[0].early_start if kritik_tasks else None,
            'bitis': kritik_tasks[-1].early_finish if kritik_tasks else None,
            'tasks': [
                {
                    'task_id': t.task_id,
                    'ad': t.ad,
                    'sure_gun': t.sure_gun,
                    'baslangic': t.early_start,
                    'bitis': t.early_finish,
                    'ilerleme': t.ilerleme,
                }
                for t in kritik_tasks
            ],
        }

    def analyze_delays(self, bugun: Optional[datetime] = None) -> Dict[str, Any]:
        """Gecikme analizi yap."""
        if not bugun:
            bugun = datetime.now()
        gecikmis_tasks = []
        risk_tasks = []

        for task_id, task in self.tasks.items():
            if not task.early_start or not task.early_finish:
                continue
            if task.early_start <= bugun < task.early_finish:
                gecen_gun = self._calculate_working_days(task.early_start, bugun)
                beklenen_ilerleme = (
                    gecen_gun / task.sure_gun * 100 if task.sure_gun > 0 else 0
                )
                if task.ilerleme < beklenen_ilerleme - 10:  # %10 tolerans
                    gecikmis_tasks.append({
                        'task_id': task_id,
                        'ad': task.ad,
                        'beklenen_ilerleme': round(beklenen_ilerleme, 1),
                        'gercek_ilerleme': task.ilerleme,
                        'fark': round(beklenen_ilerleme - task.ilerleme, 1),
                        'kritik': task.kritik,
                    })
            if task.kritik and task.early_start < bugun and task.ilerleme == 0:
                risk_tasks.append({
                    'task_id': task_id,
                    'ad': task.ad,
                    'baslamali': task.early_start,
                    'gecikme_gun': self._calculate_working_days(task.early_start, bugun),
                })

        return {
            'bugun': bugun,
            'gecikmis_is_sayisi': len(gecikmis_tasks),
            'riskli_is_sayisi': len(risk_tasks),
            'gecikmis_tasks': gecikmis_tasks,
            'riskli_tasks': risk_tasks,
            'genel_durum': (
                'kritik' if any(t['kritik'] for t in gecikmis_tasks)
                else 'dikkat' if gecikmis_tasks
                else 'normal'
            ),
        }

    def update_progress(self, task_id: int, ilerleme: float) -> bool:
        """Is ilerleme guncelle."""
        if task_id not in self.tasks:
            return False
        self.tasks[task_id].ilerleme = max(0, min(100, ilerleme))
        return True

    def get_task_info(self, task_id: int) -> Optional[Dict[str, Any]]:
        """Is detay bilgisi."""
        if task_id not in self.tasks:
            return None
        task = self.tasks[task_id]
        return {
            'task_id': task.task_id,
            'ad': task.ad,
            'sure_gun': task.sure_gun,
            'baslangic': task.early_start,
            'bitis': task.early_finish,
            'ilerleme': task.ilerleme,
            'durum': task.get_durum(),
            'kritik': task.kritik,
            'float_gun': task.float_gun,
            'early_start': task.early_start,
            'early_finish': task.early_finish,
            'late_start': task.late_start,
            'late_finish': task.late_finish,
            'milestone': task.milestone,
            'kaynak': task.kaynak,
            'predecessors': [
                {
                    'task_id': pred_id,
                    'ad': self.tasks[pred_id].ad if pred_id in self.tasks else f'#{pred_id}',
                    'tip': dep_type,
                    'lag': lag,
                }
                for pred_id, dep_type, lag in task.predecessors
            ],
            'successors': [
                {
                    'task_id': succ_id,
                    'ad': self.tasks[succ_id].ad if succ_id in self.tasks else f'#{succ_id}',
                    'tip': dep_type,
                    'lag': lag,
                }
                for succ_id, dep_type, lag in task.successors
            ],
        }

    # ==================== VERITABANI ====================

    def save_to_database(self, proje_id: int) -> Dict[str, Any]:
        """Is programini veritabanina kaydet."""
        if not self.db:
            return {'success': False, 'error': 'Veritabani baglantisi yok'}
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO is_programi (
                        proje_id, baslangic_tarihi, bitis_tarihi,
                        toplam_sure_gun, kritik_yol_sure_gun, olusturma_tarihi
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    proje_id,
                    self.proje_baslangic.strftime('%Y-%m-%d') if self.proje_baslangic else None,
                    self.proje_bitis.strftime('%Y-%m-%d') if self.proje_bitis else None,
                    self._calculate_working_days(self.proje_baslangic, self.proje_bitis)
                    if self.proje_baslangic and self.proje_bitis else 0,
                    sum(self.tasks[tid].sure_gun for tid in self.kritik_yol),
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                ))
                program_id = cursor.lastrowid

                for task in self.tasks.values():
                    cursor.execute("""
                        INSERT INTO is_programi_kalemleri (
                            program_id, ad, sure_gun, baslangic_tarihi, bitis_tarihi,
                            early_start, early_finish, late_start, late_finish,
                            float_gun, kritik, ilerleme, milestone, kaynak,
                            metraj_kalem_id, aciklama
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        program_id, task.ad, task.sure_gun,
                        task.early_start.strftime('%Y-%m-%d') if task.early_start else None,
                        task.early_finish.strftime('%Y-%m-%d') if task.early_finish else None,
                        task.early_start.strftime('%Y-%m-%d') if task.early_start else None,
                        task.early_finish.strftime('%Y-%m-%d') if task.early_finish else None,
                        task.late_start.strftime('%Y-%m-%d') if task.late_start else None,
                        task.late_finish.strftime('%Y-%m-%d') if task.late_finish else None,
                        task.float_gun, 1 if task.kritik else 0, task.ilerleme,
                        1 if task.milestone else 0, task.kaynak,
                        task.metraj_kalem_id, task.aciklama,
                    ))
                    for succ_id, dep_type, lag in task.successors:
                        cursor.execute("""
                            INSERT INTO is_programi_bagimliliklar (
                                program_id, onceki_is_id, sonraki_is_id,
                                bagimliluk_tipi, lag_gun
                            ) VALUES (?, ?, ?, ?, ?)
                        """, (program_id, task.task_id, succ_id, dep_type, lag))

                conn.commit()
                return {'success': True, 'program_id': program_id, 'mesaj': 'Is programi kaydedildi'}
        except Exception as e:
            logger.error(f"Is programi SQLite'a yazilamadi (proje_id={proje_id}): {e}")
            return {'success': False, 'error': str(e)}

    def load_from_database(self, proje_id: int) -> Dict[str, Any]:
        """Veritabanindan is programini yukle."""
        if not self.db:
            return {'success': False, 'error': 'Veritabani baglantisi yok'}
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM is_programi
                    WHERE proje_id = ?
                    ORDER BY olusturma_tarihi DESC LIMIT 1
                """, (proje_id,))
                program = cursor.fetchone()
                if not program:
                    return {'success': False, 'error': 'Is programi bulunamadi'}

                program_id = program['id']
                self.proje_baslangic = (
                    datetime.strptime(program['baslangic_tarihi'], '%Y-%m-%d')
                    if program['baslangic_tarihi'] else None
                )
                self.proje_bitis = (
                    datetime.strptime(program['bitis_tarihi'], '%Y-%m-%d')
                    if program['bitis_tarihi'] else None
                )

                cursor.execute(
                    "SELECT * FROM is_programi_kalemleri WHERE program_id = ?",
                    (program_id,)
                )
                self.tasks.clear()
                for row in cursor.fetchall():
                    task = Task(
                        task_id=row['id'],
                        ad=row['ad'],
                        sure_gun=row['sure_gun'],
                        baslangic_tarihi=(
                            datetime.strptime(row['baslangic_tarihi'], '%Y-%m-%d')
                            if row['baslangic_tarihi'] else None
                        ),
                        bitis_tarihi=(
                            datetime.strptime(row['bitis_tarihi'], '%Y-%m-%d')
                            if row['bitis_tarihi'] else None
                        ),
                        ilerleme=row['ilerleme'],
                        metraj_kalem_id=row['metraj_kalem_id'],
                        aciklama=row['aciklama'] or '',
                        milestone=bool(row['milestone']),
                        kaynak=row['kaynak'] or '',
                    )
                    task.early_start = (
                        datetime.strptime(row['early_start'], '%Y-%m-%d')
                        if row['early_start'] else None
                    )
                    task.early_finish = (
                        datetime.strptime(row['early_finish'], '%Y-%m-%d')
                        if row['early_finish'] else None
                    )
                    task.late_start = (
                        datetime.strptime(row['late_start'], '%Y-%m-%d')
                        if row['late_start'] else None
                    )
                    task.late_finish = (
                        datetime.strptime(row['late_finish'], '%Y-%m-%d')
                        if row['late_finish'] else None
                    )
                    task.float_gun = row['float_gun']
                    task.kritik = bool(row['kritik'])
                    self.tasks[task.task_id] = task

                cursor.execute(
                    "SELECT * FROM is_programi_bagimliliklar WHERE program_id = ?",
                    (program_id,)
                )
                for dep in cursor.fetchall():
                    pred_id = dep['onceki_is_id']
                    succ_id = dep['sonraki_is_id']
                    if pred_id in self.tasks and succ_id in self.tasks:
                        self.tasks[pred_id].successors.append(
                            (succ_id, dep['bagimliluk_tipi'], dep['lag_gun'])
                        )
                        self.tasks[succ_id].predecessors.append(
                            (pred_id, dep['bagimliluk_tipi'], dep['lag_gun'])
                        )

                self.kritik_yol = [tid for tid, t in self.tasks.items() if t.kritik]
                return {
                    'success': True,
                    'program_id': program_id,
                    'toplam_is': len(self.tasks),
                    'mesaj': 'Is programi yuklendi',
                }
        except Exception as e:
            logger.error(f"Is programi SQLite'dan okunamadi: {e}")
            return {'success': False, 'error': str(e)}

    # ==================== S-CURVE ANALIZI ====================

    def get_s_curve_data(self) -> Dict[str, Any]:
        """
        S-Curve (S Egrisi) verisi hesapla.

        Planlanan (PV - Planned Value) ve Gerceklesen (EV - Earned Value) ilerleme.
        """
        if not self.proje_baslangic or not self.proje_bitis or not self.tasks:
            return {'error': 'Once is programini hesaplayin'}

        toplam_is_gunu = sum(t.sure_gun for t in self.tasks.values())
        if toplam_is_gunu == 0:
            return {'error': 'Toplam is gunu sifir'}

        tarihler, planlanan, gerceklesen = [], [], []
        bugun = datetime.now()
        tarih = self.proje_baslangic
        kumulatif_planlanan = 0.0
        kumulatif_gerceklesen = 0.0

        while tarih <= self.proje_bitis:
            tarihler.append(tarih)
            gunluk_planlanan = 0.0
            gunluk_gerceklesen = 0.0

            for task in self.tasks.values():
                if not task.early_start or not task.early_finish:
                    continue
                gorev_agirligi = task.sure_gun / toplam_is_gunu * 100
                if task.early_start <= tarih <= task.early_finish and task.sure_gun > 0:
                    gunluk_planlanan += gorev_agirligi / task.sure_gun
                if tarih <= bugun and task.early_start <= tarih <= task.early_finish and task.sure_gun > 0:
                    gunluk_gerceklesen += gorev_agirligi / task.sure_gun * (task.ilerleme / 100)

            kumulatif_planlanan += gunluk_planlanan
            kumulatif_gerceklesen += gunluk_gerceklesen
            planlanan.append(min(100, kumulatif_planlanan))
            gerceklesen.append(min(100, kumulatif_gerceklesen) if tarih <= bugun else None)
            tarih += timedelta(days=1)

        return {
            'tarihler': tarihler,
            'planlanan': planlanan,
            'gerceklesen': gerceklesen,
            'proje_baslangic': self.proje_baslangic,
            'proje_bitis': self.proje_bitis,
            'bugun': bugun,
            'toplam_is_gunu': toplam_is_gunu,
        }

    # ==================== KAYNAK DENGELEME ====================

    def resource_leveling(self) -> Dict[str, Any]:
        """
        Otomatik kaynak dengeleme.

        Kaynak cakismalarini tespit edip kritik olmayan gorevleri float icinde kaydirır.
        """
        if not self.tasks:
            return {'success': False, 'error': 'Gorev yok'}

        cakismalar = self.check_kaynak_cakisma()
        if not cakismalar:
            return {
                'success': True, 'degisiklikler': [],
                'cozulen_cakisma': 0, 'kalan_cakisma': 0,
                'mesaj': 'Kaynak cakismasi yok',
            }

        degisiklikler = []
        cozulen_cakisma = 0

        for cakisma in cakismalar:
            kaynak = cakisma['kaynak']
            tarih = datetime.strptime(cakisma['tarih'], '%Y-%m-%d')
            kapasite = cakisma['kapasite']

            atanan_gorevler = [
                task for task in self.tasks.values()
                if task.kaynak == kaynak and task.early_start
                and task.early_start <= tarih <= (task.early_finish or tarih)
            ]
            non_kritik = sorted(
                [t for t in atanan_gorevler if not t.kritik and t.float_gun > 0],
                key=lambda t: -t.float_gun,
            )
            asim = len(atanan_gorevler) - kapasite

            for i, task in enumerate(non_kritik):
                if i >= asim:
                    break
                if task.float_gun > 0:
                    eski_baslangic = task.early_start
                    yeni_baslangic = self._add_working_days(task.early_start, 1)
                    task.early_start = yeni_baslangic
                    task.early_finish = self._add_working_days(yeni_baslangic, task.sure_gun)
                    task.float_gun -= 1
                    degisiklikler.append({
                        'task_id': task.task_id,
                        'ad': task.ad,
                        'eski_baslangic': eski_baslangic.strftime('%d.%m.%Y'),
                        'yeni_baslangic': yeni_baslangic.strftime('%d.%m.%Y'),
                        'kaydirma_gun': 1,
                        'kalan_float': task.float_gun,
                    })
                    cozulen_cakisma += 1

        kalan_cakismalar = self.check_kaynak_cakisma()
        return {
            'success': True,
            'degisiklikler': degisiklikler,
            'cozulen_cakisma': cozulen_cakisma,
            'kalan_cakisma': len(kalan_cakismalar),
            'mesaj': f'{cozulen_cakisma} cakisma cozuldu' if cozulen_cakisma > 0 else 'Cozülebilecek cakisma yok',
        }

    # ==================== WHAT-IF SENARYO ANALIZI ====================

    def what_if_analysis(self, task_id: int, gecikme_gun: int) -> Dict[str, Any]:
        """
        What-If senaryo analizi.

        Belirli bir gorevin X gun gecikmesi durumunda projeye etkisini simule et.
        Simulasyon sonrasi orijinal degerler geri yuklenir (non-destructive).
        """
        if task_id not in self.tasks:
            return {'error': f'Gorev bulunamadi: {task_id}'}
        if gecikme_gun <= 0:
            return {'error': 'Gecikme 1 veya daha fazla gun olmali'}

        scenario_id = str(uuid.uuid4())[:8]
        eski_proje_bitis = self.proje_bitis
        eski_kritik_yol = self.kritik_yol.copy()

        # Orijinal degerleri sakla
        original_tasks = {
            tid: {
                'early_start': t.early_start,
                'early_finish': t.early_finish,
                'late_start': t.late_start,
                'late_finish': t.late_finish,
                'float_gun': t.float_gun,
                'kritik': t.kritik,
            }
            for tid, t in self.tasks.items()
        }

        hedef_task = self.tasks[task_id]
        etkilenen_gorevler = []

        if hedef_task.early_start:
            eski_baslangic = hedef_task.early_start
            eski_bitis = hedef_task.early_finish
            yeni_baslangic = self._add_working_days(hedef_task.early_start, gecikme_gun)
            hedef_task.early_start = yeni_baslangic
            hedef_task.early_finish = self._add_working_days(yeni_baslangic, hedef_task.sure_gun)

            etkilenen_gorevler.append({
                'task_id': task_id,
                'ad': hedef_task.ad,
                'eski_baslangic': eski_baslangic.strftime('%d.%m.%Y') if eski_baslangic else '-',
                'yeni_baslangic': hedef_task.early_start.strftime('%d.%m.%Y'),
                'eski_bitis': eski_bitis.strftime('%d.%m.%Y') if eski_bitis else '-',
                'yeni_bitis': hedef_task.early_finish.strftime('%d.%m.%Y'),
                'sebep': 'Dogrudan gecikme',
            })

            def update_successors(tid: int):
                task = self.tasks[tid]
                for succ_id, dep_type, lag_days in task.successors:
                    if succ_id not in self.tasks:
                        continue
                    succ = self.tasks[succ_id]
                    eski_b = succ.early_start
                    eski_f = succ.early_finish
                    if dep_type in ('FS', 'FF'):
                        yeni_succ_b = task.early_finish + timedelta(days=lag_days)
                    else:
                        yeni_succ_b = task.early_start + timedelta(days=lag_days)
                    if succ.early_start and yeni_succ_b > succ.early_start:
                        succ.early_start = yeni_succ_b
                        succ.early_finish = self._add_working_days(yeni_succ_b, succ.sure_gun)
                        etkilenen_gorevler.append({
                            'task_id': succ_id,
                            'ad': succ.ad,
                            'eski_baslangic': eski_b.strftime('%d.%m.%Y') if eski_b else '-',
                            'yeni_baslangic': succ.early_start.strftime('%d.%m.%Y'),
                            'eski_bitis': eski_f.strftime('%d.%m.%Y') if eski_f else '-',
                            'yeni_bitis': succ.early_finish.strftime('%d.%m.%Y'),
                            'sebep': f"Bagimlı: {hedef_task.ad}",
                        })
                        update_successors(succ_id)

            update_successors(task_id)

        yeni_proje_bitis = max(
            (task.early_finish for task in self.tasks.values() if task.early_finish),
            default=self.proje_baslangic,
        )
        topo = self._topological_sort()
        if topo:
            self._backward_pass(topo)
            self._calculate_float()

        yeni_kritik_yol = [tid for tid, t in self.tasks.items() if t.kritik]
        kritik_yol_degisti = set(yeni_kritik_yol) != set(eski_kritik_yol)
        proje_gecikme = (
            self._calculate_working_days(eski_proje_bitis, yeni_proje_bitis)
            if eski_proje_bitis and yeni_proje_bitis else 0
        )

        sonuc = {
            'scenario_id': scenario_id,
            'geciktirilen_gorev': hedef_task.ad,
            'gecikme_gun': gecikme_gun,
            'etkilenen_gorevler': etkilenen_gorevler,
            'etkilenen_gorev_sayisi': len(etkilenen_gorevler),
            'eski_proje_bitis': eski_proje_bitis.strftime('%d.%m.%Y') if eski_proje_bitis else '-',
            'yeni_proje_bitis': yeni_proje_bitis.strftime('%d.%m.%Y') if yeni_proje_bitis else '-',
            'proje_gecikme_gun': proje_gecikme,
            'kritik_yol_degisti': kritik_yol_degisti,
            'yeni_kritik_yol': yeni_kritik_yol,
        }

        # Orijinal degerleri geri yukle (simulasyon geri alinir)
        for tid, orig in original_tasks.items():
            task = self.tasks[tid]
            task.early_start = orig['early_start']
            task.early_finish = orig['early_finish']
            task.late_start = orig['late_start']
            task.late_finish = orig['late_finish']
            task.float_gun = orig['float_gun']
            task.kritik = orig['kritik']
        self.proje_bitis = eski_proje_bitis
        self.kritik_yol = eski_kritik_yol

        self._scenarios[scenario_id] = {
            'task_id': task_id,
            'gecikme_gun': gecikme_gun,
            'sonuc': sonuc,
        }
        return sonuc

    def apply_scenario(self, scenario_id: str) -> bool:
        """Kaydedilmis senaryoyu uygula."""
        if scenario_id not in self._scenarios:
            return False
        scenario = self._scenarios[scenario_id]
        task_id = scenario['task_id']
        if task_id not in self.tasks:
            return False
        task = self.tasks[task_id]
        if task.early_start:
            task.early_start = self._add_working_days(task.early_start, scenario['gecikme_gun'])
            task.early_finish = self._add_working_days(task.early_start, task.sure_gun)
        self.calculate_schedule(self.proje_baslangic)
        return True

    # ==================== UYARILAR ====================

    def get_alerts(self) -> List[Dict[str, Any]]:
        """Aktif uyarilari getir (Kritik, Uyari, Bilgi, Kaynak)."""
        alerts = []
        bugun = datetime.now()
        yarin = bugun + timedelta(days=1)

        for task_id, task in self.tasks.items():
            if not task.early_start or not task.early_finish:
                continue

            if task.kritik and task.ilerleme < 100:
                if task.early_start < bugun and task.ilerleme == 0:
                    gecikme = self._calculate_working_days(task.early_start, bugun)
                    alerts.append({
                        'tip': 'KRITIK', 'renk': '#e74c3c', 'icon': '',
                        'baslik': f'Kritik gorev baslamadi: {task.ad}',
                        'aciklama': f'Baslamasi gereken: {task.early_start.strftime("%d.%m.%Y")}, Gecikme: {gecikme} gun',
                        'task_id': task_id, 'oncelik': 1,
                    })
                elif task.early_start <= bugun < task.early_finish:
                    gecen_gun = self._calculate_working_days(task.early_start, bugun)
                    beklenen = (gecen_gun / task.sure_gun * 100) if task.sure_gun > 0 else 0
                    if task.ilerleme < beklenen - 15:
                        alerts.append({
                            'tip': 'KRITIK', 'renk': '#e74c3c', 'icon': '',
                            'baslik': f'Kritik gorev geride: {task.ad}',
                            'aciklama': f'Beklenen: %{beklenen:.0f}, Gercek: %{task.ilerleme:.0f} (Fark: %{round(beklenen - task.ilerleme, 1)})',
                            'task_id': task_id, 'oncelik': 1,
                        })

            elif not task.kritik and task.ilerleme < 100:
                if task.early_start < bugun and task.ilerleme == 0:
                    gecikme = self._calculate_working_days(task.early_start, bugun)
                    alerts.append({
                        'tip': 'UYARI', 'renk': '#e67e22', 'icon': '',
                        'baslik': f'Gorev baslamadi: {task.ad}',
                        'aciklama': f'Baslamasi gereken: {task.early_start.strftime("%d.%m.%Y")}, Gecikme: {gecikme} gun',
                        'task_id': task_id, 'oncelik': 2,
                    })
                elif task.early_start <= bugun < task.early_finish:
                    gecen_gun = self._calculate_working_days(task.early_start, bugun)
                    beklenen = (gecen_gun / task.sure_gun * 100) if task.sure_gun > 0 else 0
                    if task.ilerleme < beklenen - 20:
                        alerts.append({
                            'tip': 'UYARI', 'renk': '#e67e22', 'icon': '',
                            'baslik': f'Gorev geride: {task.ad}',
                            'aciklama': f'Beklenen: %{beklenen:.0f}, Gercek: %{task.ilerleme:.0f}',
                            'task_id': task_id, 'oncelik': 2,
                        })

            if task.early_start and task.early_start.date() == yarin.date() and task.ilerleme == 0:
                alerts.append({
                    'tip': 'BILGI', 'renk': '#f1c40f', 'icon': '',
                    'baslik': f'Yarin baslayacak: {task.ad}',
                    'aciklama': f'Kaynak: {task.kaynak or "Atanmamis"}, Sure: {task.sure_gun} gun',
                    'task_id': task_id, 'oncelik': 3,
                })

            if task.milestone and task.early_finish:
                kalan_gun = self._calculate_working_days(bugun, task.early_finish)
                if 0 < kalan_gun <= 3:
                    alerts.append({
                        'tip': 'BILGI', 'renk': '#f1c40f', 'icon': '',
                        'baslik': f'Milestone yaklasıyor: {task.ad}',
                        'aciklama': f'{kalan_gun} gun kaldi ({task.early_finish.strftime("%d.%m.%Y")})',
                        'task_id': task_id, 'oncelik': 3,
                    })

        for cakisma in self.check_kaynak_cakisma()[:5]:
            alerts.append({
                'tip': 'KAYNAK', 'renk': '#3498db', 'icon': '',
                'baslik': f'Kaynak asiri yuku: {cakisma["kaynak"]}',
                'aciklama': f'{cakisma["tarih"]}: {cakisma["gorev_sayisi"]} gorev (kapasite: {cakisma["kapasite"]})',
                'task_id': None, 'oncelik': 2,
            })

        alerts.sort(key=lambda x: (x['oncelik'], x['baslik']))
        return alerts

    def get_alert_summary(self) -> Dict[str, Any]:
        """Uyari ozeti."""
        alerts = self.get_alerts()
        return {
            'toplam': len(alerts),
            'kritik': sum(1 for a in alerts if a['tip'] == 'KRITIK'),
            'uyari': sum(1 for a in alerts if a['tip'] == 'UYARI'),
            'bilgi': sum(1 for a in alerts if a['tip'] == 'BILGI'),
            'kaynak': sum(1 for a in alerts if a['tip'] == 'KAYNAK'),
        }

    # ==================== SABLON YUKLEME ====================

    def load_template(self, template_id: str, baslangic_tarihi: datetime) -> Dict[str, Any]:
        """Sablondan gorevleri yukle."""
        try:
            from app.data.gantt_templates import get_template, get_template_tasks
        except ImportError:
            return {'success': False, 'error': 'Sablon modulu bulunamadi'}

        template = get_template(template_id)
        if not template:
            return {'success': False, 'error': f'Sablon bulunamadi: {template_id}'}

        gorevler = get_template_tasks(template_id)
        if not gorevler:
            return {'success': False, 'error': 'Sablonda gorev yok'}

        max_id = max(self.tasks.keys()) if self.tasks else 0
        sira_to_task_id: Dict[int, int] = {}

        for gorev in gorevler:
            sira = gorev['sira']
            max_id += 1
            sira_to_task_id[sira] = max_id
            task = Task(
                task_id=max_id,
                ad=gorev['ad'],
                sure_gun=gorev['sure'],
                kaynak=gorev.get('kaynak', ''),
                milestone=gorev.get('milestone', False),
                renk=template.get('renk', '#3498db'),
            )
            self.tasks[max_id] = task

        for gorev in gorevler:
            if 'bagimlilık' not in gorev:
                continue
            task_id = sira_to_task_id.get(gorev['sira'])
            if not task_id:
                continue
            for bag_sira in gorev['bagimlilık']:
                pred_id = sira_to_task_id.get(bag_sira)
                if pred_id:
                    self.add_dependency(pred_id, task_id, 'FS', 0)

        return {
            'success': True,
            'eklenen_gorev': len(gorevler),
            'sablon_adi': template['ad'],
            'mesaj': f"{template['ad']} sablonundan {len(gorevler)} gorev eklendi",
        }

    # ==================== DRAG & DROP DESTEK ====================

    def move_task(self, task_id: int, yeni_baslangic: datetime) -> Dict[str, Any]:
        """Gorevi yeni tarihe tasI (Drag & Drop icin)."""
        if task_id not in self.tasks:
            return {'success': False, 'error': 'Gorev bulunamadi'}

        task = self.tasks[task_id]
        eski_baslangic = task.early_start

        # Tatil/hafta sonu kontrolu - ilk is gunune kaydir
        tatil, _ = self.tatil_yoneticisi.tatil_mi(yeni_baslangic)
        while tatil:
            yeni_baslangic += timedelta(days=1)
            tatil, _ = self.tatil_yoneticisi.tatil_mi(yeni_baslangic)

        uyari = None
        for pred_id, dep_type, lag in task.predecessors:
            if pred_id in self.tasks:
                pred = self.tasks[pred_id]
                if pred.early_finish and yeni_baslangic < pred.early_finish:
                    uyari = f"Uyari: {pred.ad} gorevinin bitisinden once baslıyorsunuz!"
        if task.kritik:
            uyari = "Uyari: Kritik yoldaki bir gorevi tasiyorsunuz! Proje bitis tarihi degisebilir."

        task.early_start = yeni_baslangic
        task.early_finish = self._add_working_days(yeni_baslangic, task.sure_gun)
        if task.late_start:
            task.float_gun = self._calculate_working_days(task.early_start, task.late_start)

        return {
            'success': True,
            'eski_baslangic': eski_baslangic,
            'yeni_baslangic': yeni_baslangic,
            'yeni_bitis': task.early_finish,
            'yeni_float': task.float_gun,
            'uyari': uyari,
        }

    def cascade_dependents(self, task_id: int, gun_farki: int) -> Dict[str, Any]:
        """Gorev tasindiginda bagimlı gorevleri de otomatik kaydir."""
        if task_id not in self.tasks:
            return {'success': False, 'error': 'Gorev bulunamadi'}

        kaydirilan_gorevler = []
        islenecek = [task_id]
        islenmis: Set[int] = set()

        while islenecek:
            current_id = islenecek.pop(0)
            if current_id in islenmis:
                continue
            islenmis.add(current_id)

            for other_id, other_task in self.tasks.items():
                if other_id in islenmis:
                    continue
                for pred_id, dep_type, lag in other_task.predecessors:
                    if pred_id == current_id and other_task.early_start:
                        yeni_baslangic = other_task.early_start + timedelta(days=gun_farki)
                        tatil, _ = self.tatil_yoneticisi.tatil_mi(yeni_baslangic)
                        while tatil:
                            yeni_baslangic += timedelta(days=1)
                            tatil, _ = self.tatil_yoneticisi.tatil_mi(yeni_baslangic)
                        other_task.early_start = yeni_baslangic
                        other_task.early_finish = self._add_working_days(yeni_baslangic, other_task.sure_gun)
                        kaydirilan_gorevler.append({
                            'task_id': other_id,
                            'ad': other_task.ad,
                            'yeni_baslangic': yeni_baslangic,
                        })
                        islenecek.append(other_id)
                        break

        return {
            'success': True,
            'kaydirilan_sayisi': len(kaydirilan_gorevler),
            'kaydirilan_gorevler': kaydirilan_gorevler,
        }
