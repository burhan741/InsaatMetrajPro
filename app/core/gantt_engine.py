"""
Gantt Chart ve CPM (Critical Path Method) Modülü
Proje iş programı, kritik yol analizi ve zaman yönetimi

Özellikler:
- CPM (Critical Path Method) algoritması
- Resmi tatil desteği (Türkiye)
- Baseline karşılaştırma
- WBS (Work Breakdown Structure) hiyerarşisi
- Kaynak çakışma kontrolü
- PDF/Excel export desteği
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Tuple, Set
import logging
from collections import defaultdict, deque
import json
import os
import copy
import uuid

logger = logging.getLogger(__name__)


# Türkiye Resmi Tatilleri (Sabit tarihli)
TURKIYE_RESMI_TATILLER_SABIT = [
    (1, 1, "Yılbaşı"),
    (4, 23, "Ulusal Egemenlik ve Çocuk Bayramı"),
    (5, 1, "Emek ve Dayanışma Günü"),
    (5, 19, "Atatürk'ü Anma, Gençlik ve Spor Bayramı"),
    (7, 15, "Demokrasi ve Milli Birlik Günü"),
    (8, 30, "Zafer Bayramı"),
    (10, 29, "Cumhuriyet Bayramı"),
]

# Dini bayramlar (2024-2030 arası yaklaşık tarihler)
# Gerçek uygulamada Diyanet API'si kullanılabilir
RAMAZAN_BAYRAMI_TARIHLERI = {
    2024: [(4, 10), (4, 11), (4, 12)],
    2025: [(3, 30), (3, 31), (4, 1)],
    2026: [(3, 20), (3, 21), (3, 22)],
    2027: [(3, 9), (3, 10), (3, 11)],
    2028: [(2, 26), (2, 27), (2, 28)],
    2029: [(2, 14), (2, 15), (2, 16)],
    2030: [(2, 4), (2, 5), (2, 6)],
}

KURBAN_BAYRAMI_TARIHLERI = {
    2024: [(6, 16), (6, 17), (6, 18), (6, 19)],
    2025: [(6, 6), (6, 7), (6, 8), (6, 9)],
    2026: [(5, 27), (5, 28), (5, 29), (5, 30)],
    2027: [(5, 16), (5, 17), (5, 18), (5, 19)],
    2028: [(5, 5), (5, 6), (5, 7), (5, 8)],
    2029: [(4, 24), (4, 25), (4, 26), (4, 27)],
    2030: [(4, 13), (4, 14), (4, 15), (4, 16)],
}


class Task:
    """İş kalemi (Task) sınıfı"""

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
        renk: str = "#3498db"
    ):
        self.task_id = task_id
        self.ad = ad
        self.sure_gun = sure_gun
        self.baslangic_tarihi = baslangic_tarihi
        self.bitis_tarihi = bitis_tarihi
        self.ilerleme = ilerleme  # 0-100 arası
        self.metraj_kalem_id = metraj_kalem_id
        self.aciklama = aciklama
        self.milestone = milestone
        self.kaynak = kaynak
        self.renk = renk  # Çubuk rengi

        # WBS (Work Breakdown Structure)
        self.wbs_kodu = wbs_kodu  # Örn: "1.1.2"
        self.parent_id = parent_id  # Üst görev ID'si
        self.children: List[int] = []  # Alt görev ID'leri
        self.seviye = 0  # Hiyerarşi seviyesi (0=ana, 1=alt, 2=alt-alt...)

        # CPM hesaplamaları için
        self.early_start: Optional[datetime] = None
        self.early_finish: Optional[datetime] = None
        self.late_start: Optional[datetime] = None
        self.late_finish: Optional[datetime] = None
        self.float_gun: int = 0  # Esneklik (gün)
        self.kritik: bool = False

        # Baseline (Planlanan) değerler
        self.baseline_baslangic: Optional[datetime] = None
        self.baseline_bitis: Optional[datetime] = None
        self.baseline_sure_gun: Optional[int] = None

        # Gerçekleşen değerler
        self.gercek_baslangic: Optional[datetime] = None
        self.gercek_bitis: Optional[datetime] = None

        # Bağımlılıklar
        self.predecessors: List[Tuple[int, str, int]] = []  # (task_id, dependency_type, lag)
        self.successors: List[Tuple[int, str, int]] = []  # (task_id, dependency_type, lag)

    def hesapla_bitis_tarihi(self) -> Optional[datetime]:
        """Başlangıç tarihinden bitiş tarihini hesapla"""
        if self.baslangic_tarihi and self.sure_gun > 0:
            # Sadece iş günleri say (Cumartesi-Pazar hariç)
            gun_sayaci = 0
            tarih = self.baslangic_tarihi

            while gun_sayaci < self.sure_gun:
                tarih += timedelta(days=1)
                # Hafta sonu değilse say
                if tarih.weekday() < 5:  # 0-4: Pazartesi-Cuma
                    gun_sayaci += 1

            return tarih
        return None

    def hesapla_sure(self) -> int:
        """Başlangıç ve bitiş tarihinden süreyi hesapla (iş günü)"""
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
        """İş durumunu döndür"""
        if self.ilerleme >= 100:
            return "tamamlandi"
        elif self.ilerleme > 0:
            return "devam_ediyor"
        elif self.baslangic_tarihi and datetime.now() > self.baslangic_tarihi:
            return "gecikmis"
        else:
            return "baslanmadi"

    def get_durum_rengi(self) -> str:
        """Durum rengini döndür"""
        durum = self.get_durum()
        return {
            'tamamlandi': '#27ae60',      # Yeşil
            'devam_ediyor': '#3498db',    # Mavi
            'gecikmis': '#e74c3c',        # Kırmızı
            'baslanmadi': '#95a5a6'       # Gri
        }.get(durum, '#95a5a6')

    def set_baseline(self):
        """Mevcut planı baseline olarak kaydet"""
        self.baseline_baslangic = self.early_start
        self.baseline_bitis = self.early_finish
        self.baseline_sure_gun = self.sure_gun

    def get_sapma_gun(self) -> Dict[str, int]:
        """Baseline'dan sapma hesapla (gün cinsinden)"""
        sapma = {
            'baslangic_sapma': 0,
            'bitis_sapma': 0,
            'sure_sapma': 0
        }

        if self.baseline_baslangic and self.early_start:
            sapma['baslangic_sapma'] = (self.early_start - self.baseline_baslangic).days

        if self.baseline_bitis and self.early_finish:
            sapma['bitis_sapma'] = (self.early_finish - self.baseline_bitis).days

        if self.baseline_sure_gun:
            sapma['sure_sapma'] = self.sure_gun - self.baseline_sure_gun

        return sapma

    def get_tamamlanma_yuzdesi(self) -> float:
        """Zaman bazlı tamamlanma yüzdesi hesapla"""
        if not self.early_start or not self.early_finish:
            return 0.0

        bugun = datetime.now()

        if bugun < self.early_start:
            return 0.0
        elif bugun >= self.early_finish:
            return 100.0
        else:
            toplam = (self.early_finish - self.early_start).days
            gecen = (bugun - self.early_start).days
            return (gecen / toplam * 100) if toplam > 0 else 0.0

    def __repr__(self):
        return f"Task({self.task_id}: {self.ad}, {self.sure_gun} gün, WBS: {self.wbs_kodu})"


class TatilYoneticisi:
    """Resmi tatil ve özel tatil yönetimi"""

    def __init__(self):
        self.ozel_tatiller: List[Tuple[datetime, str]] = []  # (tarih, açıklama)
        self.hafta_sonu_calisma = False  # Cumartesi çalışılıyor mu?
        self.cumartesi_yarim_gun = False  # Cumartesi yarım gün mü?

    def get_yil_tatilleri(self, yil: int) -> List[Tuple[datetime, str]]:
        """Belirli bir yılın tüm tatillerini getir"""
        tatiller = []

        # Sabit tatiller
        for ay, gun, aciklama in TURKIYE_RESMI_TATILLER_SABIT:
            tatiller.append((datetime(yil, ay, gun), aciklama))

        # Ramazan Bayramı
        if yil in RAMAZAN_BAYRAMI_TARIHLERI:
            for ay, gun in RAMAZAN_BAYRAMI_TARIHLERI[yil]:
                tatiller.append((datetime(yil, ay, gun), "Ramazan Bayramı"))

        # Kurban Bayramı
        if yil in KURBAN_BAYRAMI_TARIHLERI:
            for ay, gun in KURBAN_BAYRAMI_TARIHLERI[yil]:
                tatiller.append((datetime(yil, ay, gun), "Kurban Bayramı"))

        # Özel tatiller
        for tarih, aciklama in self.ozel_tatiller:
            if tarih.year == yil:
                tatiller.append((tarih, aciklama))

        return sorted(tatiller, key=lambda x: x[0])

    def tatil_mi(self, tarih: datetime) -> Tuple[bool, str]:
        """Verilen tarih tatil mi kontrol et"""
        # Pazar her zaman tatil
        if tarih.weekday() == 6:
            return True, "Pazar"

        # Cumartesi kontrolü
        if tarih.weekday() == 5 and not self.hafta_sonu_calisma:
            return True, "Cumartesi"

        # Resmi tatil kontrolü
        tatiller = self.get_yil_tatilleri(tarih.year)
        for tatil_tarihi, aciklama in tatiller:
            if tarih.date() == tatil_tarihi.date():
                return True, aciklama

        return False, ""

    def ekle_ozel_tatil(self, tarih: datetime, aciklama: str):
        """Özel tatil ekle"""
        self.ozel_tatiller.append((tarih, aciklama))

    def sil_ozel_tatil(self, tarih: datetime):
        """Özel tatil sil"""
        self.ozel_tatiller = [(t, a) for t, a in self.ozel_tatiller if t.date() != tarih.date()]

    def get_donem_tatil_sayisi(self, baslangic: datetime, bitis: datetime) -> int:
        """İki tarih arasındaki tatil sayısını hesapla"""
        tatil_sayisi = 0
        tarih = baslangic

        while tarih <= bitis:
            tatil, _ = self.tatil_mi(tarih)
            if tatil:
                tatil_sayisi += 1
            tarih += timedelta(days=1)

        return tatil_sayisi


class GanttEngine:
    """
    Gantt Chart ve CPM (Critical Path Method) motoru.

    Özellikler:
    - İş programı oluşturma
    - Kritik yol analizi (CPM)
    - Bağımlılık yönetimi (FS, SS, FF, SF)
    - İlerleme takibi
    - Milestone yönetimi
    - Gecikme analizi
    - Resmi tatil desteği
    - Baseline karşılaştırma
    - WBS (Work Breakdown Structure)
    - Kaynak çakışma kontrolü
    """

    # Bağımlılık türleri
    DEPENDENCY_TYPES = {
        'FS': 'Finish-to-Start',    # A bitsin, B başlasın (en yaygın)
        'SS': 'Start-to-Start',     # A başlasın, B başlasın
        'FF': 'Finish-to-Finish',   # A bitsin, B bitsin
        'SF': 'Start-to-Finish'     # A başlasın, B bitsin (nadir)
    }

    # Varsayılan çubuk renkleri
    TASK_COLORS = {
        'normal': '#3498db',      # Mavi
        'kritik': '#e74c3c',      # Kırmızı
        'tamamlandi': '#27ae60',  # Yeşil
        'gecikme': '#e67e22',     # Turuncu
        'milestone': '#9b59b6',   # Mor
        'ozet': '#34495e'         # Koyu gri (summary task)
    }

    def __init__(self, db_manager=None):
        """
        Gantt motoru başlat.

        Args:
            db_manager: DatabaseManager instance (opsiyonel)
        """
        self.db = db_manager
        self.tasks: Dict[int, Task] = {}  # task_id -> Task
        self.proje_baslangic: Optional[datetime] = None
        self.proje_bitis: Optional[datetime] = None
        self.kritik_yol: List[int] = []  # Kritik yoldaki task ID'leri

        # Yeni özellikler
        self.tatil_yoneticisi = TatilYoneticisi()
        self.baseline_kayitli = False
        self.baseline_tarihi: Optional[datetime] = None

        # WBS sayaçları
        self.wbs_sayac: Dict[int, int] = {}  # parent_id -> son_numara

        # Kaynak listesi
        self.kaynaklar: Dict[str, Dict[str, Any]] = {}  # kaynak_adi -> bilgiler

    def add_task(self, task: Task) -> None:
        """İş kalemi ekle"""
        self.tasks[task.task_id] = task

    def add_dependency(
        self,
        predecessor_id: int,
        successor_id: int,
        dep_type: str = 'FS',
        lag_days: int = 0
    ) -> bool:
        """
        Bağımlılık ekle.

        Args:
            predecessor_id: Önceki iş ID
            successor_id: Sonraki iş ID
            dep_type: Bağımlılık türü (FS, SS, FF, SF)
            lag_days: Gecikme (pozitif) veya öne alma (negatif) gün sayısı

        Returns:
            Başarı durumu
        """
        if predecessor_id not in self.tasks or successor_id not in self.tasks:
            logger.error(f"Geçersiz task ID: {predecessor_id} veya {successor_id}")
            return False

        if dep_type not in self.DEPENDENCY_TYPES:
            logger.error(f"Geçersiz bağımlılık türü: {dep_type}")
            return False

        # Döngüsel bağımlılık kontrolü
        if self._creates_cycle(predecessor_id, successor_id):
            logger.error("Döngüsel bağımlılık tespit edildi!")
            return False

        # Bağımlılık ekle
        self.tasks[predecessor_id].successors.append((successor_id, dep_type, lag_days))
        self.tasks[successor_id].predecessors.append((predecessor_id, dep_type, lag_days))

        return True

    def _creates_cycle(self, from_id: int, to_id: int) -> bool:
        """Döngüsel bağımlılık kontrolü (DFS ile)"""
        visited = set()

        def dfs(task_id: int) -> bool:
            if task_id == from_id:
                return True
            if task_id in visited:
                return False

            visited.add(task_id)

            task = self.tasks.get(task_id)
            if not task:
                return False

            for succ_id, _, _ in task.successors:
                if dfs(succ_id):
                    return True

            return False

        return dfs(to_id)

    def calculate_schedule(self, proje_baslangic: datetime) -> Dict[str, Any]:
        """
        İş programını hesapla (CPM algoritması).

        Args:
            proje_baslangic: Proje başlangıç tarihi

        Returns:
            Hesaplama sonuçları
        """
        self.proje_baslangic = proje_baslangic

        # 1. Topolojik sıralama (bağımlılık sırası)
        topo_order = self._topological_sort()
        if not topo_order:
            return {'error': 'Döngüsel bağımlılık tespit edildi!'}

        # 2. Forward Pass (Early Start/Finish hesaplama)
        self._forward_pass(topo_order)

        # 3. Backward Pass (Late Start/Finish hesaplama)
        self._backward_pass(topo_order)

        # 4. Float hesaplama ve kritik yol belirleme
        self._calculate_float()

        # 5. Proje bitiş tarihi
        self.proje_bitis = max(
            (task.early_finish for task in self.tasks.values() if task.early_finish),
            default=proje_baslangic
        )

        # 6. Kritik yolu bul
        self.kritik_yol = self._find_critical_path()

        # İstatistikler
        toplam_is = len(self.tasks)
        kritik_is_sayisi = len(self.kritik_yol)
        ortalama_float = sum(t.float_gun for t in self.tasks.values()) / toplam_is if toplam_is > 0 else 0

        return {
            'success': True,
            'proje_baslangic': proje_baslangic,
            'proje_bitis': self.proje_bitis,
            'toplam_sure_gun': self._calculate_working_days(proje_baslangic, self.proje_bitis),
            'toplam_is': toplam_is,
            'kritik_is_sayisi': kritik_is_sayisi,
            'kritik_yol': self.kritik_yol,
            'ortalama_float': round(ortalama_float, 1),
            'kritik_yuzde': round((kritik_is_sayisi / toplam_is * 100), 1) if toplam_is > 0 else 0
        }

    def _topological_sort(self) -> List[int]:
        """Topolojik sıralama (Kahn's algoritması)"""
        # Giriş derecesi (in-degree) hesapla
        in_degree = {task_id: 0 for task_id in self.tasks}

        for task in self.tasks.values():
            for succ_id, _, _ in task.successors:
                in_degree[succ_id] += 1

        # Giriş derecesi 0 olan task'ları queue'ya ekle
        queue = deque([task_id for task_id, degree in in_degree.items() if degree == 0])
        result = []

        while queue:
            task_id = queue.popleft()
            result.append(task_id)

            task = self.tasks[task_id]
            for succ_id, _, _ in task.successors:
                in_degree[succ_id] -= 1
                if in_degree[succ_id] == 0:
                    queue.append(succ_id)

        # Tüm task'lar işlendiyse döngü yok
        if len(result) != len(self.tasks):
            logger.error("Topolojik sıralama başarısız - döngüsel bağımlılık!")
            return []

        return result

    def _forward_pass(self, topo_order: List[int]) -> None:
        """Forward Pass - Early Start/Finish hesaplama"""
        for task_id in topo_order:
            task = self.tasks[task_id]

            if not task.predecessors:
                # Başlangıç task'ı
                task.early_start = self.proje_baslangic
            else:
                # Predecessor'ların en geç bitişini bul
                max_early_finish = self.proje_baslangic

                for pred_id, dep_type, lag_days in task.predecessors:
                    pred = self.tasks[pred_id]

                    if dep_type == 'FS':  # Finish-to-Start
                        candidate = pred.early_finish + timedelta(days=lag_days)
                    elif dep_type == 'SS':  # Start-to-Start
                        candidate = pred.early_start + timedelta(days=lag_days)
                    elif dep_type == 'FF':  # Finish-to-Finish
                        # FF için önce süreyi hesapla, sonra geriye git
                        candidate = pred.early_finish + timedelta(days=lag_days) - timedelta(days=task.sure_gun)
                    elif dep_type == 'SF':  # Start-to-Finish
                        candidate = pred.early_start + timedelta(days=lag_days) - timedelta(days=task.sure_gun)
                    else:
                        candidate = pred.early_finish

                    if candidate > max_early_finish:
                        max_early_finish = candidate

                task.early_start = max_early_finish

            # Early Finish hesapla
            task.early_finish = self._add_working_days(task.early_start, task.sure_gun)

    def _backward_pass(self, topo_order: List[int]) -> None:
        """Backward Pass - Late Start/Finish hesaplama"""
        # Tersten işle
        for task_id in reversed(topo_order):
            task = self.tasks[task_id]

            if not task.successors:
                # Son task - proje bitiş tarihi
                task.late_finish = task.early_finish
            else:
                # Successor'ların en erken başlangıcını bul
                min_late_start = datetime.max

                for succ_id, dep_type, lag_days in task.successors:
                    succ = self.tasks[succ_id]

                    if dep_type == 'FS':  # Finish-to-Start
                        candidate = succ.late_start - timedelta(days=lag_days)
                    elif dep_type == 'SS':  # Start-to-Start
                        candidate = succ.late_start - timedelta(days=lag_days) + timedelta(days=task.sure_gun)
                    elif dep_type == 'FF':  # Finish-to-Finish
                        candidate = succ.late_finish - timedelta(days=lag_days)
                    elif dep_type == 'SF':  # Start-to-Finish
                        candidate = succ.late_finish - timedelta(days=lag_days) + timedelta(days=task.sure_gun)
                    else:
                        candidate = succ.late_start

                    if candidate < min_late_start:
                        min_late_start = candidate

                task.late_finish = min_late_start

            # Late Start hesapla
            task.late_start = self._subtract_working_days(task.late_finish, task.sure_gun)

    def _calculate_float(self) -> None:
        """Float (esneklik) hesapla ve kritik task'ları işaretle"""
        for task in self.tasks.values():
            if task.late_start and task.early_start:
                # Float = Late Start - Early Start (gün cinsinden)
                task.float_gun = self._calculate_working_days(task.early_start, task.late_start)

                # Float = 0 ise kritik
                task.kritik = (task.float_gun == 0)

    def _find_critical_path(self) -> List[int]:
        """Kritik yolu bul (float=0 olan task'lar)"""
        kritik_tasks = [task_id for task_id, task in self.tasks.items() if task.kritik]

        # Kritik yolu sırala (başlangıçtan bitişe)
        kritik_tasks.sort(key=lambda tid: self.tasks[tid].early_start or datetime.min)

        return kritik_tasks

    def _add_working_days(self, start_date: datetime, days: int) -> datetime:
        """İş günü ekle (tatiller ve hafta sonu hariç)"""
        current_date = start_date
        added_days = 0

        while added_days < days:
            current_date += timedelta(days=1)
            tatil, _ = self.tatil_yoneticisi.tatil_mi(current_date)
            if not tatil:
                added_days += 1

        return current_date

    def _subtract_working_days(self, end_date: datetime, days: int) -> datetime:
        """İş günü çıkar (tatiller ve hafta sonu hariç)"""
        current_date = end_date
        subtracted_days = 0

        while subtracted_days < days:
            current_date -= timedelta(days=1)
            tatil, _ = self.tatil_yoneticisi.tatil_mi(current_date)
            if not tatil:
                subtracted_days += 1

        return current_date

    def _calculate_working_days(self, start_date: datetime, end_date: datetime) -> int:
        """İki tarih arası iş günü sayısı (tatiller hariç)"""
        if not start_date or not end_date:
            return 0

        days = 0
        current_date = start_date

        while current_date < end_date:
            current_date += timedelta(days=1)
            tatil, _ = self.tatil_yoneticisi.tatil_mi(current_date)
            if not tatil:
                days += 1

        return days

    # ==================== WBS YÖNETİMİ ====================

    def add_task_with_wbs(self, task: Task, parent_id: Optional[int] = None) -> str:
        """WBS kodu ile iş kalemi ekle"""
        if parent_id is None:
            # Ana seviye görev
            if 0 not in self.wbs_sayac:
                self.wbs_sayac[0] = 0
            self.wbs_sayac[0] += 1
            task.wbs_kodu = str(self.wbs_sayac[0])
            task.seviye = 0
        else:
            # Alt seviye görev
            if parent_id not in self.tasks:
                raise ValueError(f"Parent task bulunamadı: {parent_id}")

            parent = self.tasks[parent_id]

            if parent_id not in self.wbs_sayac:
                self.wbs_sayac[parent_id] = 0
            self.wbs_sayac[parent_id] += 1

            task.wbs_kodu = f"{parent.wbs_kodu}.{self.wbs_sayac[parent_id]}"
            task.parent_id = parent_id
            task.seviye = parent.seviye + 1

            # Parent'a child ekle
            parent.children.append(task.task_id)

        self.tasks[task.task_id] = task
        return task.wbs_kodu

    def get_wbs_tree(self) -> List[Dict[str, Any]]:
        """WBS ağaç yapısını getir"""
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
                        'children': build_tree(task_id)
                    }
                    tree.append(node)
            return sorted(tree, key=lambda x: x['wbs_kodu'])

        return build_tree(None)

    def get_summary_task_progress(self, parent_id: int) -> float:
        """Özet görevin ilerleme yüzdesini hesapla (alt görevlerden)"""
        if parent_id not in self.tasks:
            return 0.0

        parent = self.tasks[parent_id]
        if not parent.children:
            return parent.ilerleme

        toplam_sure = 0
        toplam_ilerleme = 0

        for child_id in parent.children:
            if child_id in self.tasks:
                child = self.tasks[child_id]
                toplam_sure += child.sure_gun
                toplam_ilerleme += child.sure_gun * child.ilerleme

        return (toplam_ilerleme / toplam_sure) if toplam_sure > 0 else 0.0

    # ==================== BASELINE YÖNETİMİ ====================

    def save_baseline(self) -> Dict[str, Any]:
        """Mevcut planı baseline olarak kaydet"""
        if not self.tasks:
            return {'success': False, 'error': 'Kaydedilecek görev yok'}

        for task in self.tasks.values():
            task.set_baseline()

        self.baseline_kayitli = True
        self.baseline_tarihi = datetime.now()

        return {
            'success': True,
            'tarih': self.baseline_tarihi,
            'gorev_sayisi': len(self.tasks)
        }

    def get_baseline_comparison(self) -> List[Dict[str, Any]]:
        """Baseline ile mevcut durum karşılaştırması"""
        if not self.baseline_kayitli:
            return []

        karsilastirma = []

        for task_id, task in self.tasks.items():
            sapma = task.get_sapma_gun()

            karsilastirma.append({
                'task_id': task_id,
                'ad': task.ad,
                'wbs_kodu': task.wbs_kodu,
                # Baseline değerler
                'baseline_baslangic': task.baseline_baslangic,
                'baseline_bitis': task.baseline_bitis,
                'baseline_sure': task.baseline_sure_gun,
                # Mevcut değerler
                'mevcut_baslangic': task.early_start,
                'mevcut_bitis': task.early_finish,
                'mevcut_sure': task.sure_gun,
                # Sapmalar
                'baslangic_sapma': sapma['baslangic_sapma'],
                'bitis_sapma': sapma['bitis_sapma'],
                'sure_sapma': sapma['sure_sapma'],
                # Durum
                'gecikme_var': sapma['bitis_sapma'] > 0,
                'kritik': task.kritik
            })

        return karsilastirma

    def get_baseline_summary(self) -> Dict[str, Any]:
        """Baseline özet raporu"""
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
            'proje_sapmasi': karsilastirma[-1]['bitis_sapma'] if karsilastirma else 0
        }

    # ==================== KAYNAK YÖNETİMİ ====================

    def add_kaynak(self, kaynak_adi: str, kapasite: int = 1, maliyet_gun: float = 0) -> None:
        """Kaynak (ekip/işçi) ekle"""
        self.kaynaklar[kaynak_adi] = {
            'kapasite': kapasite,  # Aynı anda kaç işte çalışabilir
            'maliyet_gun': maliyet_gun,  # Günlük maliyet
            'atamalar': []  # Atandığı task ID'leri
        }

    def atama_kaynak(self, task_id: int, kaynak_adi: str) -> bool:
        """Göreve kaynak ata"""
        if task_id not in self.tasks:
            return False

        if kaynak_adi not in self.kaynaklar:
            self.add_kaynak(kaynak_adi)

        self.tasks[task_id].kaynak = kaynak_adi
        self.kaynaklar[kaynak_adi]['atamalar'].append(task_id)
        return True

    def check_kaynak_cakisma(self) -> List[Dict[str, Any]]:
        """Kaynak çakışmalarını tespit et"""
        cakismalar = []

        for kaynak_adi, kaynak_bilgi in self.kaynaklar.items():
            atamalar = kaynak_bilgi['atamalar']
            kapasite = kaynak_bilgi['kapasite']

            if len(atamalar) < 2:
                continue

            # Her gün için aynı kaynağa atanan görevleri kontrol et
            tarih_gorevler: Dict[str, List[int]] = defaultdict(list)

            for task_id in atamalar:
                if task_id not in self.tasks:
                    continue

                task = self.tasks[task_id]
                if not task.early_start or not task.early_finish:
                    continue

                tarih = task.early_start
                while tarih <= task.early_finish:
                    tarih_str = tarih.strftime('%Y-%m-%d')
                    tarih_gorevler[tarih_str].append(task_id)
                    tarih += timedelta(days=1)

            # Kapasite aşımı kontrolü
            for tarih_str, gorevler in tarih_gorevler.items():
                if len(gorevler) > kapasite:
                    cakismalar.append({
                        'kaynak': kaynak_adi,
                        'tarih': tarih_str,
                        'gorev_sayisi': len(gorevler),
                        'kapasite': kapasite,
                        'asim': len(gorevler) - kapasite,
                        'gorevler': [self.tasks[tid].ad for tid in gorevler if tid in self.tasks]
                    })

        return cakismalar

    def get_kaynak_yukleme(self, kaynak_adi: str) -> Dict[str, float]:
        """Kaynağın günlük yükleme oranını hesapla"""
        if kaynak_adi not in self.kaynaklar:
            return {}

        yukleme = {}
        kaynak_bilgi = self.kaynaklar[kaynak_adi]

        for task_id in kaynak_bilgi['atamalar']:
            if task_id not in self.tasks:
                continue

            task = self.tasks[task_id]
            if not task.early_start or not task.early_finish:
                continue

            tarih = task.early_start
            while tarih <= task.early_finish:
                tarih_str = tarih.strftime('%Y-%m-%d')
                yukleme[tarih_str] = yukleme.get(tarih_str, 0) + 1
                tarih += timedelta(days=1)

        # Yüzdeye çevir (kapasite bazlı)
        kapasite = kaynak_bilgi['kapasite']
        for tarih_str in yukleme:
            yukleme[tarih_str] = (yukleme[tarih_str] / kapasite) * 100

        return yukleme

    # ==================== EXPORT FONKSİYONLARI ====================

    def export_to_dict(self) -> Dict[str, Any]:
        """Tüm veriyi dictionary olarak export et"""
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
            'kaynaklar': self.kaynaklar
        }

    def export_to_excel_data(self) -> List[Dict[str, Any]]:
        """Excel export için veri hazırla"""
        data = []

        for task in sorted(self.tasks.values(), key=lambda t: t.wbs_kodu or ''):
            sapma = task.get_sapma_gun() if self.baseline_kayitli else {'baslangic_sapma': 0, 'bitis_sapma': 0, 'sure_sapma': 0}

            data.append({
                'WBS': task.wbs_kodu,
                'İş Adı': task.ad,
                'Süre (Gün)': task.sure_gun,
                'Başlangıç': task.early_start.strftime('%d.%m.%Y') if task.early_start else '',
                'Bitiş': task.early_finish.strftime('%d.%m.%Y') if task.early_finish else '',
                'İlerleme (%)': task.ilerleme,
                'Float (Gün)': task.float_gun,
                'Kritik': 'Evet' if task.kritik else 'Hayır',
                'Kaynak': task.kaynak,
                'Baseline Başlangıç': task.baseline_baslangic.strftime('%d.%m.%Y') if task.baseline_baslangic else '',
                'Baseline Bitiş': task.baseline_bitis.strftime('%d.%m.%Y') if task.baseline_bitis else '',
                'Başlangıç Sapma (Gün)': sapma['baslangic_sapma'],
                'Bitiş Sapma (Gün)': sapma['bitis_sapma'],
            })

        return data

    def get_gantt_chart_data(self) -> Dict[str, Any]:
        """Görsel Gantt chart için veri hazırla"""
        if not self.proje_baslangic or not self.proje_bitis:
            return {'error': 'Önce iş programını hesaplayın'}

        # Tarih aralığı
        toplam_gun = (self.proje_bitis - self.proje_baslangic).days + 1

        # Hafta ve ay başlıkları
        haftalar = []
        aylar = []
        gunler = []

        tarih = self.proje_baslangic
        mevcut_ay = None
        mevcut_hafta = None

        while tarih <= self.proje_bitis:
            gunler.append(tarih)

            # Ay değişimi
            ay_str = tarih.strftime('%B %Y')
            if ay_str != mevcut_ay:
                aylar.append({'tarih': tarih, 'ad': ay_str, 'baslangic_index': len(gunler) - 1})
                mevcut_ay = ay_str

            # Hafta değişimi
            hafta_no = tarih.isocalendar()[1]
            if hafta_no != mevcut_hafta:
                haftalar.append({'tarih': tarih, 'hafta_no': hafta_no, 'baslangic_index': len(gunler) - 1})
                mevcut_hafta = hafta_no

            tarih += timedelta(days=1)

        # Görev çubukları
        cubuklar = []
        for task in sorted(self.tasks.values(), key=lambda t: (t.seviye, t.wbs_kodu or '')):
            if not task.early_start or not task.early_finish:
                continue

            baslangic_index = (task.early_start - self.proje_baslangic).days
            bitis_index = (task.early_finish - self.proje_baslangic).days

            # Renk belirle
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

            cubuk = {
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
                # Baseline varsa
                'baseline_baslangic_index': (task.baseline_baslangic - self.proje_baslangic).days if task.baseline_baslangic else None,
                'baseline_bitis_index': (task.baseline_bitis - self.proje_baslangic).days if task.baseline_bitis else None,
            }
            cubuklar.append(cubuk)

        # Tatil günleri
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
            'baseline_var': self.baseline_kayitli
        }

    def get_timeline_data(self) -> List[Dict[str, Any]]:
        """Gantt chart için timeline verisi"""
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
                'kaynak': task.kaynak
            })

        # Başlangıç tarihine göre sırala
        timeline.sort(key=lambda x: x['baslangic'])

        return timeline

    def get_critical_path_info(self) -> Dict[str, Any]:
        """Kritik yol bilgilerini getir"""
        if not self.kritik_yol:
            return {'error': 'Kritik yol hesaplanmamış'}

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
                    'ilerleme': t.ilerleme
                }
                for t in kritik_tasks
            ]
        }

    def analyze_delays(self, bugun: Optional[datetime] = None) -> Dict[str, Any]:
        """Gecikme analizi yap"""
        if not bugun:
            bugun = datetime.now()

        gecikmis_tasks = []
        risk_tasks = []

        for task_id, task in self.tasks.items():
            if not task.early_start or not task.early_finish:
                continue

            # Başlamış ama tamamlanmamış
            if task.early_start <= bugun < task.early_finish:
                # Beklenen ilerleme hesapla
                gecen_gun = self._calculate_working_days(task.early_start, bugun)
                beklenen_ilerleme = (gecen_gun / task.sure_gun * 100) if task.sure_gun > 0 else 0

                # Gerçek ilerleme düşükse
                if task.ilerleme < beklenen_ilerleme - 10:  # %10 tolerans
                    gecikmis_tasks.append({
                        'task_id': task_id,
                        'ad': task.ad,
                        'beklenen_ilerleme': round(beklenen_ilerleme, 1),
                        'gercek_ilerleme': task.ilerleme,
                        'fark': round(beklenen_ilerleme - task.ilerleme, 1),
                        'kritik': task.kritik
                    })

            # Kritik yolda ve henüz başlamamış ama başlaması gerekiyor
            if task.kritik and task.early_start < bugun and task.ilerleme == 0:
                risk_tasks.append({
                    'task_id': task_id,
                    'ad': task.ad,
                    'baslamali': task.early_start,
                    'gecikme_gun': self._calculate_working_days(task.early_start, bugun)
                })

        return {
            'bugun': bugun,
            'gecikmis_is_sayisi': len(gecikmis_tasks),
            'riskli_is_sayisi': len(risk_tasks),
            'gecikmis_tasks': gecikmis_tasks,
            'riskli_tasks': risk_tasks,
            'genel_durum': 'kritik' if any(t['kritik'] for t in gecikmis_tasks) else
                           'dikkat' if gecikmis_tasks else 'normal'
        }

    def update_progress(self, task_id: int, ilerleme: float) -> bool:
        """İş ilerleme güncelle"""
        if task_id not in self.tasks:
            return False

        self.tasks[task_id].ilerleme = max(0, min(100, ilerleme))
        return True

    def get_task_info(self, task_id: int) -> Optional[Dict[str, Any]]:
        """İş detay bilgisi"""
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
                    'ad': self.tasks[pred_id].ad,
                    'tip': dep_type,
                    'lag': lag
                }
                for pred_id, dep_type, lag in task.predecessors
            ],
            'successors': [
                {
                    'task_id': succ_id,
                    'ad': self.tasks[succ_id].ad,
                    'tip': dep_type,
                    'lag': lag
                }
                for succ_id, dep_type, lag in task.successors
            ]
        }

    def save_to_database(self, proje_id: int) -> Dict[str, Any]:
        """İş programını veritabanına kaydet"""
        if not self.db:
            return {'success': False, 'error': 'Veritabanı bağlantısı yok'}

        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                # İş programı header
                cursor.execute("""
                    INSERT INTO is_programi (
                        proje_id, baslangic_tarihi, bitis_tarihi,
                        toplam_sure_gun, kritik_yol_sure_gun, olusturma_tarihi
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    proje_id,
                    self.proje_baslangic.strftime('%Y-%m-%d') if self.proje_baslangic else None,
                    self.proje_bitis.strftime('%Y-%m-%d') if self.proje_bitis else None,
                    self._calculate_working_days(self.proje_baslangic, self.proje_bitis) if self.proje_baslangic and self.proje_bitis else 0,
                    sum(self.tasks[tid].sure_gun for tid in self.kritik_yol),
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ))

                program_id = cursor.lastrowid

                # Task'ları kaydet
                for task in self.tasks.values():
                    cursor.execute("""
                        INSERT INTO is_programi_kalemleri (
                            program_id, ad, sure_gun, baslangic_tarihi, bitis_tarihi,
                            early_start, early_finish, late_start, late_finish,
                            float_gun, kritik, ilerleme, milestone, kaynak,
                            metraj_kalem_id, aciklama
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        program_id,
                        task.ad,
                        task.sure_gun,
                        task.early_start.strftime('%Y-%m-%d') if task.early_start else None,
                        task.early_finish.strftime('%Y-%m-%d') if task.early_finish else None,
                        task.early_start.strftime('%Y-%m-%d') if task.early_start else None,
                        task.early_finish.strftime('%Y-%m-%d') if task.early_finish else None,
                        task.late_start.strftime('%Y-%m-%d') if task.late_start else None,
                        task.late_finish.strftime('%Y-%m-%d') if task.late_finish else None,
                        task.float_gun,
                        1 if task.kritik else 0,
                        task.ilerleme,
                        1 if task.milestone else 0,
                        task.kaynak,
                        task.metraj_kalem_id,
                        task.aciklama
                    ))

                    task_db_id = cursor.lastrowid

                    # Bağımlılıkları kaydet
                    for succ_id, dep_type, lag in task.successors:
                        cursor.execute("""
                            INSERT INTO is_programi_bagimliliklar (
                                program_id, onceki_is_id, sonraki_is_id,
                                bagimliluk_tipi, lag_gun
                            ) VALUES (?, ?, ?, ?, ?)
                        """, (
                            program_id,
                            task.task_id,
                            succ_id,
                            dep_type,
                            lag
                        ))

                conn.commit()

                return {
                    'success': True,
                    'program_id': program_id,
                    'mesaj': 'İş programı kaydedildi'
                }

        except Exception as e:
            logger.error(f"İş programı kayıt hatası: {e}")
            return {'success': False, 'error': str(e)}

    def load_from_database(self, proje_id: int) -> Dict[str, Any]:
        """Veritabanından iş programını yükle"""
        if not self.db:
            return {'success': False, 'error': 'Veritabanı bağlantısı yok'}

        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                # Son iş programını al
                cursor.execute("""
                    SELECT * FROM is_programi
                    WHERE proje_id = ?
                    ORDER BY olusturma_tarihi DESC
                    LIMIT 1
                """, (proje_id,))

                program = cursor.fetchone()
                if not program:
                    return {'success': False, 'error': 'İş programı bulunamadı'}

                program_id = program['id']
                self.proje_baslangic = datetime.strptime(program['baslangic_tarihi'], '%Y-%m-%d') if program['baslangic_tarihi'] else None
                self.proje_bitis = datetime.strptime(program['bitis_tarihi'], '%Y-%m-%d') if program['bitis_tarihi'] else None

                # Task'ları yükle
                cursor.execute("""
                    SELECT * FROM is_programi_kalemleri
                    WHERE program_id = ?
                """, (program_id,))

                tasks = cursor.fetchall()
                self.tasks.clear()

                for task_row in tasks:
                    task = Task(
                        task_id=task_row['id'],
                        ad=task_row['ad'],
                        sure_gun=task_row['sure_gun'],
                        baslangic_tarihi=datetime.strptime(task_row['baslangic_tarihi'], '%Y-%m-%d') if task_row['baslangic_tarihi'] else None,
                        bitis_tarihi=datetime.strptime(task_row['bitis_tarihi'], '%Y-%m-%d') if task_row['bitis_tarihi'] else None,
                        ilerleme=task_row['ilerleme'],
                        metraj_kalem_id=task_row['metraj_kalem_id'],
                        aciklama=task_row['aciklama'] or '',
                        milestone=bool(task_row['milestone']),
                        kaynak=task_row['kaynak'] or ''
                    )

                    task.early_start = datetime.strptime(task_row['early_start'], '%Y-%m-%d') if task_row['early_start'] else None
                    task.early_finish = datetime.strptime(task_row['early_finish'], '%Y-%m-%d') if task_row['early_finish'] else None
                    task.late_start = datetime.strptime(task_row['late_start'], '%Y-%m-%d') if task_row['late_start'] else None
                    task.late_finish = datetime.strptime(task_row['late_finish'], '%Y-%m-%d') if task_row['late_finish'] else None
                    task.float_gun = task_row['float_gun']
                    task.kritik = bool(task_row['kritik'])

                    self.tasks[task.task_id] = task

                # Bağımlılıkları yükle
                cursor.execute("""
                    SELECT * FROM is_programi_bagimliliklar
                    WHERE program_id = ?
                """, (program_id,))

                deps = cursor.fetchall()
                for dep in deps:
                    pred_id = dep['onceki_is_id']
                    succ_id = dep['sonraki_is_id']
                    dep_type = dep['bagimliluk_tipi']
                    lag = dep['lag_gun']

                    if pred_id in self.tasks and succ_id in self.tasks:
                        self.tasks[pred_id].successors.append((succ_id, dep_type, lag))
                        self.tasks[succ_id].predecessors.append((pred_id, dep_type, lag))

                # Kritik yolu bul
                self.kritik_yol = [tid for tid, task in self.tasks.items() if task.kritik]

                return {
                    'success': True,
                    'program_id': program_id,
                    'toplam_is': len(self.tasks),
                    'mesaj': 'İş programı yüklendi'
                }

        except Exception as e:
            logger.error(f"İş programı yükleme hatası: {e}")
            return {'success': False, 'error': str(e)}

    # ==================== S-CURVE ANALİZİ ====================

    def get_s_curve_data(self) -> Dict[str, Any]:
        """
        S-Curve (S Eğrisi) verisi hesapla.
        Planlanan (PV - Planned Value) ve Gerçekleşen (EV - Earned Value) ilerleme.

        Returns:
            Dict: {
                'tarihler': [...],
                'planlanan': [...],  # Kümülatif planlanan %
                'gerceklesen': [...],  # Kümülatif gerçekleşen %
                'proje_baslangic': datetime,
                'proje_bitis': datetime,
                'bugun': datetime,
                'toplam_is_gunu': int
            }
        """
        if not self.proje_baslangic or not self.proje_bitis or not self.tasks:
            return {'error': 'Önce iş programını hesaplayın'}

        tarihler = []
        planlanan = []
        gerceklesen = []

        bugun = datetime.now()

        # Toplam iş (süre bazlı ağırlık)
        toplam_is_gunu = sum(t.sure_gun for t in self.tasks.values())

        if toplam_is_gunu == 0:
            return {'error': 'Toplam iş günü sıfır'}

        # Her gün için kümülatif değerleri hesapla
        tarih = self.proje_baslangic
        kumulatif_planlanan = 0.0
        kumulatif_gerceklesen = 0.0

        while tarih <= self.proje_bitis:
            tarihler.append(tarih)

            # O güne kadar planlanan iş
            gunluk_planlanan = 0.0
            gunluk_gerceklesen = 0.0

            for task in self.tasks.values():
                if not task.early_start or not task.early_finish:
                    continue

                # Bu görevin süre ağırlığı
                gorev_agirligi = task.sure_gun / toplam_is_gunu * 100

                # Planlanan: Görev başlamış ve bu tarih görev içindeyse
                if task.early_start <= tarih <= task.early_finish:
                    # Görev içindeki günlük ilerleme
                    if task.sure_gun > 0:
                        gunluk_planlanan += gorev_agirligi / task.sure_gun

                # Gerçekleşen: İlerleme yüzdesi bazlı
                if tarih <= bugun:
                    if task.early_start <= tarih <= task.early_finish:
                        # Görev içindeki günlük gerçekleşen
                        if task.sure_gun > 0:
                            gerceklesen_oran = task.ilerleme / 100
                            gunluk_gerceklesen += gorev_agirligi / task.sure_gun * gerceklesen_oran

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
            'toplam_is_gunu': toplam_is_gunu
        }

    # ==================== KAYNAK DENGELEME (RESOURCE LEVELING) ====================

    def resource_leveling(self) -> Dict[str, Any]:
        """
        Otomatik kaynak dengeleme algoritması.
        Kaynak çakışmalarını tespit edip, kritik olmayan görevleri float içinde kaydırır.

        Returns:
            Dict: {
                'success': bool,
                'degisiklikler': [...],  # Yapılan değişiklikler
                'cozulen_cakisma': int,
                'kalan_cakisma': int
            }
        """
        if not self.tasks:
            return {'success': False, 'error': 'Görev yok'}

        degisiklikler = []
        cozulen_cakisma = 0

        # 1. Çakışmaları tespit et
        cakismalar = self.check_kaynak_cakisma()

        if not cakismalar:
            return {
                'success': True,
                'degisiklikler': [],
                'cozulen_cakisma': 0,
                'kalan_cakisma': 0,
                'mesaj': 'Kaynak çakışması yok'
            }

        # 2. Her çakışma için çözüm dene
        for cakisma in cakismalar:
            kaynak = cakisma['kaynak']
            tarih_str = cakisma['tarih']
            kapasite = cakisma['kapasite']

            # O kaynağa atanmış görevleri bul
            atanan_gorevler = []
            for task_id, task in self.tasks.items():
                if task.kaynak == kaynak and task.early_start and task.early_finish:
                    tarih = datetime.strptime(tarih_str, '%Y-%m-%d')
                    if task.early_start <= tarih <= task.early_finish:
                        atanan_gorevler.append(task)

            # Kritik olmayan görevleri float içinde kaydır
            non_kritik = [t for t in atanan_gorevler if not t.kritik and t.float_gun > 0]
            non_kritik.sort(key=lambda t: -t.float_gun)  # En esnek olanı önce

            # Kapasite aşımı kadar görevi kaydır
            asim = len(atanan_gorevler) - kapasite

            for i, task in enumerate(non_kritik):
                if i >= asim:
                    break

                # Görevi float içinde 1 gün ileri kaydır
                if task.float_gun > 0:
                    eski_baslangic = task.early_start
                    yeni_baslangic = self._add_working_days(task.early_start, 1)

                    # Early Start/Finish güncelle
                    task.early_start = yeni_baslangic
                    task.early_finish = self._add_working_days(yeni_baslangic, task.sure_gun)
                    task.float_gun -= 1

                    degisiklikler.append({
                        'task_id': task.task_id,
                        'ad': task.ad,
                        'eski_baslangic': eski_baslangic.strftime('%d.%m.%Y'),
                        'yeni_baslangic': yeni_baslangic.strftime('%d.%m.%Y'),
                        'kaydirma_gun': 1,
                        'kalan_float': task.float_gun
                    })
                    cozulen_cakisma += 1

        # 3. Kalan çakışmaları kontrol et
        kalan_cakismalar = self.check_kaynak_cakisma()

        return {
            'success': True,
            'degisiklikler': degisiklikler,
            'cozulen_cakisma': cozulen_cakisma,
            'kalan_cakisma': len(kalan_cakismalar),
            'mesaj': f'{cozulen_cakisma} çakışma çözüldü' if cozulen_cakisma > 0 else 'Çözülebilecek çakışma yok'
        }

    # ==================== WHAT-IF SENARYO ANALİZİ ====================

    def what_if_analysis(self, task_id: int, gecikme_gun: int) -> Dict[str, Any]:
        """
        What-If (Ya Şöyle Olsaydı) senaryo analizi.
        Belirli bir görevin X gün gecikmesi durumunda projeye etkisini simüle et.

        Args:
            task_id: Gecikecek görev ID'si
            gecikme_gun: Gecikme gün sayısı (pozitif değer)

        Returns:
            Dict: {
                'scenario_id': str,
                'etkilenen_gorevler': [...],
                'eski_proje_bitis': datetime,
                'yeni_proje_bitis': datetime,
                'proje_gecikme_gun': int,
                'kritik_yol_degisti': bool
            }
        """
        if task_id not in self.tasks:
            return {'error': f'Görev bulunamadı: {task_id}'}

        if gecikme_gun <= 0:
            return {'error': 'Gecikme 1 veya daha fazla gün olmalı'}

        # Senaryo ID oluştur
        scenario_id = str(uuid.uuid4())[:8]

        # Eski değerleri sakla
        eski_proje_bitis = self.proje_bitis
        eski_kritik_yol = self.kritik_yol.copy()

        # Deep copy ile görevleri kopyala
        original_tasks = {}
        for tid, task in self.tasks.items():
            original_tasks[tid] = {
                'early_start': task.early_start,
                'early_finish': task.early_finish,
                'late_start': task.late_start,
                'late_finish': task.late_finish,
                'float_gun': task.float_gun,
                'kritik': task.kritik
            }

        # Seçilen görevi geciktir
        hedef_task = self.tasks[task_id]
        etkilenen_gorevler = []

        # Gecikmeyi uygula
        yeni_baslangic = self._add_working_days(hedef_task.early_start, gecikme_gun) if hedef_task.early_start else None

        if yeni_baslangic:
            eski_baslangic = hedef_task.early_start
            eski_bitis = hedef_task.early_finish

            hedef_task.early_start = yeni_baslangic
            hedef_task.early_finish = self._add_working_days(yeni_baslangic, hedef_task.sure_gun)

            etkilenen_gorevler.append({
                'task_id': task_id,
                'ad': hedef_task.ad,
                'eski_baslangic': eski_baslangic.strftime('%d.%m.%Y') if eski_baslangic else '-',
                'yeni_baslangic': hedef_task.early_start.strftime('%d.%m.%Y'),
                'eski_bitis': eski_bitis.strftime('%d.%m.%Y') if eski_bitis else '-',
                'yeni_bitis': hedef_task.early_finish.strftime('%d.%m.%Y'),
                'sebep': 'Doğrudan gecikme'
            })

        # Bağımlı görevleri güncelle (Forward Pass)
        def update_successors(tid):
            task = self.tasks[tid]
            for succ_id, dep_type, lag_days in task.successors:
                if succ_id not in self.tasks:
                    continue

                succ = self.tasks[succ_id]
                eski_baslangic = succ.early_start
                eski_bitis = succ.early_finish

                # Yeni başlangıç hesapla
                if dep_type == 'FS':
                    yeni_succ_baslangic = task.early_finish + timedelta(days=lag_days)
                elif dep_type == 'SS':
                    yeni_succ_baslangic = task.early_start + timedelta(days=lag_days)
                else:
                    yeni_succ_baslangic = task.early_finish + timedelta(days=lag_days)

                # Sadece ileri taşınacaksa güncelle
                if succ.early_start and yeni_succ_baslangic > succ.early_start:
                    succ.early_start = yeni_succ_baslangic
                    succ.early_finish = self._add_working_days(yeni_succ_baslangic, succ.sure_gun)

                    etkilenen_gorevler.append({
                        'task_id': succ_id,
                        'ad': succ.ad,
                        'eski_baslangic': eski_baslangic.strftime('%d.%m.%Y') if eski_baslangic else '-',
                        'yeni_baslangic': succ.early_start.strftime('%d.%m.%Y'),
                        'eski_bitis': eski_bitis.strftime('%d.%m.%Y') if eski_bitis else '-',
                        'yeni_bitis': succ.early_finish.strftime('%d.%m.%Y'),
                        'sebep': f"Bağımlı: {hedef_task.ad}"
                    })

                    # Recursive olarak devam et
                    update_successors(succ_id)

        # Successors'ları güncelle
        update_successors(task_id)

        # Yeni proje bitiş tarihi
        yeni_proje_bitis = max(
            (task.early_finish for task in self.tasks.values() if task.early_finish),
            default=self.proje_baslangic
        )

        # Float yeniden hesapla
        self._backward_pass(self._topological_sort())
        self._calculate_float()

        yeni_kritik_yol = [tid for tid, task in self.tasks.items() if task.kritik]
        kritik_yol_degisti = set(yeni_kritik_yol) != set(eski_kritik_yol)

        # Proje gecikme hesapla
        proje_gecikme = 0
        if eski_proje_bitis and yeni_proje_bitis:
            proje_gecikme = self._calculate_working_days(eski_proje_bitis, yeni_proje_bitis)

        # Sonucu oluştur
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
            'yeni_kritik_yol': yeni_kritik_yol
        }

        # Orijinal değerleri geri yükle (simülasyon)
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

        # Senaryoyu sakla (opsiyonel uygulama için)
        if not hasattr(self, '_scenarios'):
            self._scenarios = {}
        self._scenarios[scenario_id] = {
            'task_id': task_id,
            'gecikme_gun': gecikme_gun,
            'sonuc': sonuc
        }

        return sonuc

    def apply_scenario(self, scenario_id: str) -> bool:
        """
        Kaydedilmiş senaryoyu uygula.

        Args:
            scenario_id: Senaryo ID'si

        Returns:
            bool: Başarı durumu
        """
        if not hasattr(self, '_scenarios') or scenario_id not in self._scenarios:
            return False

        scenario = self._scenarios[scenario_id]
        task_id = scenario['task_id']
        gecikme_gun = scenario['gecikme_gun']

        if task_id not in self.tasks:
            return False

        # Görevi geciktir
        task = self.tasks[task_id]
        if task.early_start:
            task.early_start = self._add_working_days(task.early_start, gecikme_gun)
            task.early_finish = self._add_working_days(task.early_start, task.sure_gun)

        # Yeniden hesapla
        self.calculate_schedule(self.proje_baslangic)

        return True

    # ==================== OTOMATİK BİLDİRİMLER/UYARILAR ====================

    def get_alerts(self) -> List[Dict[str, Any]]:
        """
        Aktif uyarıları getir.

        Uyarı Tipleri:
        - KRITIK (kirmizi): Kritik görev gecikti
        - UYARI (turuncu): Non-kritik görev gecikti
        - BILGI (sari): Yarın başlayacak görev
        - KAYNAK (mavi): Kaynak aşırı yükü

        Returns:
            List[Dict]: Uyarı listesi
        """
        alerts = []
        bugun = datetime.now()
        yarin = bugun + timedelta(days=1)

        for task_id, task in self.tasks.items():
            if not task.early_start or not task.early_finish:
                continue

            # 1. Kritik görev gecikti
            if task.kritik and task.ilerleme < 100:
                if task.early_start < bugun and task.ilerleme == 0:
                    gecikme = self._calculate_working_days(task.early_start, bugun)
                    alerts.append({
                        'tip': 'KRITIK',
                        'renk': '#e74c3c',
                        'icon': '🔴',
                        'baslik': f'Kritik görev başlamadı: {task.ad}',
                        'aciklama': f'Başlaması gereken: {task.early_start.strftime("%d.%m.%Y")}, Gecikme: {gecikme} gün',
                        'task_id': task_id,
                        'oncelik': 1
                    })
                elif task.early_start <= bugun < task.early_finish:
                    # Beklenen vs gerçek ilerleme kontrolü
                    gecen_gun = self._calculate_working_days(task.early_start, bugun)
                    beklenen = (gecen_gun / task.sure_gun * 100) if task.sure_gun > 0 else 0
                    if task.ilerleme < beklenen - 15:  # %15 tolerans
                        fark = round(beklenen - task.ilerleme, 1)
                        alerts.append({
                            'tip': 'KRITIK',
                            'renk': '#e74c3c',
                            'icon': '🔴',
                            'baslik': f'Kritik görev geride: {task.ad}',
                            'aciklama': f'Beklenen: %{beklenen:.0f}, Gerçek: %{task.ilerleme:.0f} (Fark: %{fark})',
                            'task_id': task_id,
                            'oncelik': 1
                        })

            # 2. Non-kritik görev gecikti
            elif not task.kritik and task.ilerleme < 100:
                if task.early_start < bugun and task.ilerleme == 0:
                    gecikme = self._calculate_working_days(task.early_start, bugun)
                    alerts.append({
                        'tip': 'UYARI',
                        'renk': '#e67e22',
                        'icon': '🟠',
                        'baslik': f'Görev başlamadı: {task.ad}',
                        'aciklama': f'Başlaması gereken: {task.early_start.strftime("%d.%m.%Y")}, Gecikme: {gecikme} gün',
                        'task_id': task_id,
                        'oncelik': 2
                    })
                elif task.early_start <= bugun < task.early_finish:
                    gecen_gun = self._calculate_working_days(task.early_start, bugun)
                    beklenen = (gecen_gun / task.sure_gun * 100) if task.sure_gun > 0 else 0
                    if task.ilerleme < beklenen - 20:  # %20 tolerans
                        alerts.append({
                            'tip': 'UYARI',
                            'renk': '#e67e22',
                            'icon': '🟠',
                            'baslik': f'Görev geride: {task.ad}',
                            'aciklama': f'Beklenen: %{beklenen:.0f}, Gerçek: %{task.ilerleme:.0f}',
                            'task_id': task_id,
                            'oncelik': 2
                        })

            # 3. Yarın başlayacak görev
            if task.early_start and task.early_start.date() == yarin.date() and task.ilerleme == 0:
                alerts.append({
                    'tip': 'BILGI',
                    'renk': '#f1c40f',
                    'icon': '🟡',
                    'baslik': f'Yarın başlayacak: {task.ad}',
                    'aciklama': f'Kaynak: {task.kaynak or "Atanmamış"}, Süre: {task.sure_gun} gün',
                    'task_id': task_id,
                    'oncelik': 3
                })

            # 4. Milestone yaklaşıyor
            if task.milestone and task.early_finish:
                kalan_gun = self._calculate_working_days(bugun, task.early_finish)
                if 0 < kalan_gun <= 3:
                    alerts.append({
                        'tip': 'BILGI',
                        'renk': '#f1c40f',
                        'icon': '⭐',
                        'baslik': f'Milestone yaklaşıyor: {task.ad}',
                        'aciklama': f'{kalan_gun} gün kaldı ({task.early_finish.strftime("%d.%m.%Y")})',
                        'task_id': task_id,
                        'oncelik': 3
                    })

        # 5. Kaynak aşırı yükü
        cakismalar = self.check_kaynak_cakisma()
        for cakisma in cakismalar[:5]:  # İlk 5
            alerts.append({
                'tip': 'KAYNAK',
                'renk': '#3498db',
                'icon': '🔵',
                'baslik': f'Kaynak aşırı yükü: {cakisma["kaynak"]}',
                'aciklama': f'{cakisma["tarih"]}: {cakisma["gorev_sayisi"]} görev (kapasite: {cakisma["kapasite"]})',
                'task_id': None,
                'oncelik': 2
            })

        # Önceliğe göre sırala
        alerts.sort(key=lambda x: (x['oncelik'], x['baslik']))

        return alerts

    def get_alert_summary(self) -> Dict[str, Any]:
        """
        Uyarı özeti.

        Returns:
            Dict: {
                'toplam': int,
                'kritik': int,
                'uyari': int,
                'bilgi': int,
                'kaynak': int
            }
        """
        alerts = self.get_alerts()

        return {
            'toplam': len(alerts),
            'kritik': sum(1 for a in alerts if a['tip'] == 'KRITIK'),
            'uyari': sum(1 for a in alerts if a['tip'] == 'UYARI'),
            'bilgi': sum(1 for a in alerts if a['tip'] == 'BILGI'),
            'kaynak': sum(1 for a in alerts if a['tip'] == 'KAYNAK')
        }

    # ==================== GÖREV ŞABLONLARI ====================

    def load_template(self, template_id: str, baslangic_tarihi: datetime) -> Dict[str, Any]:
        """
        Şablondan görevleri yükle.

        Args:
            template_id: Şablon ID'si (örn: 'temel_insaat')
            baslangic_tarihi: Şablon başlangıç tarihi

        Returns:
            Dict: {
                'success': bool,
                'eklenen_gorev': int,
                'mesaj': str
            }
        """
        try:
            from app.data.gantt_templates import get_template, get_template_tasks
        except ImportError:
            return {'success': False, 'error': 'Şablon modülü bulunamadı'}

        template = get_template(template_id)
        if not template:
            return {'success': False, 'error': f'Şablon bulunamadı: {template_id}'}

        gorevler = get_template_tasks(template_id)
        if not gorevler:
            return {'success': False, 'error': 'Şablonda görev yok'}

        # Mevcut en yüksek task_id
        max_id = max(self.tasks.keys()) if self.tasks else 0

        # Şablon görevleri için ID eşleştirme (sıra -> task_id)
        sira_to_task_id = {}
        eklenen_gorevler = []

        # Görevleri ekle
        for gorev in gorevler:
            sira = gorev['sira']
            max_id += 1
            task_id = max_id
            sira_to_task_id[sira] = task_id

            task = Task(
                task_id=task_id,
                ad=gorev['ad'],
                sure_gun=gorev['sure'],
                kaynak=gorev.get('kaynak', ''),
                milestone=gorev.get('milestone', False),
                renk=template.get('renk', '#3498db')
            )

            self.tasks[task_id] = task
            eklenen_gorevler.append(task_id)

        # Bağımlılıkları ekle
        for gorev in gorevler:
            if 'bagimlilık' not in gorev:
                continue

            sira = gorev['sira']
            task_id = sira_to_task_id.get(sira)

            if not task_id:
                continue

            for bag_sira in gorev['bagimlilık']:
                pred_id = sira_to_task_id.get(bag_sira)
                if pred_id:
                    self.add_dependency(pred_id, task_id, 'FS', 0)

        return {
            'success': True,
            'eklenen_gorev': len(eklenen_gorevler),
            'sablon_adi': template['ad'],
            'mesaj': f"{template['ad']} şablonundan {len(eklenen_gorevler)} görev eklendi"
        }

    # ==================== DRAG & DROP DESTEK ====================

    def move_task(self, task_id: int, yeni_baslangic: datetime) -> Dict[str, Any]:
        """
        Görevi yeni tarihe taşı (Drag & Drop için).

        Args:
            task_id: Taşınacak görev ID
            yeni_baslangic: Yeni başlangıç tarihi

        Returns:
            Dict: {
                'success': bool,
                'eski_baslangic': datetime,
                'yeni_baslangic': datetime,
                'uyari': str (varsa)
            }
        """
        if task_id not in self.tasks:
            return {'success': False, 'error': 'Görev bulunamadı'}

        task = self.tasks[task_id]
        eski_baslangic = task.early_start

        # Tatil/hafta sonu kontrolü
        tatil, aciklama = self.tatil_yoneticisi.tatil_mi(yeni_baslangic)
        if tatil:
            # İlk iş gününe kaydır
            while tatil:
                yeni_baslangic += timedelta(days=1)
                tatil, _ = self.tatil_yoneticisi.tatil_mi(yeni_baslangic)

        # Bağımlılık kontrolü
        uyari = None
        for pred_id, dep_type, lag in task.predecessors:
            if pred_id in self.tasks:
                pred = self.tasks[pred_id]
                if pred.early_finish and yeni_baslangic < pred.early_finish:
                    uyari = f"Uyarı: {pred.ad} görevinin bitişinden önce başlatıyorsunuz!"

        # Kritik görev uyarısı
        if task.kritik:
            uyari = "Uyarı: Kritik yoldaki bir görevi taşıyorsunuz! Proje bitiş tarihi değişebilir."

        # Tarihleri güncelle
        task.early_start = yeni_baslangic
        task.early_finish = self._add_working_days(yeni_baslangic, task.sure_gun)

        # Float değişimi
        if task.late_start:
            task.float_gun = self._calculate_working_days(task.early_start, task.late_start)

        return {
            'success': True,
            'eski_baslangic': eski_baslangic,
            'yeni_baslangic': yeni_baslangic,
            'yeni_bitis': task.early_finish,
            'yeni_float': task.float_gun,
            'uyari': uyari
        }

    def cascade_dependents(self, task_id: int, gun_farki: int) -> Dict[str, Any]:
        """
        Görev taşındığında bağımlı görevleri de otomatik kaydır.

        Args:
            task_id: Taşınan görev ID
            gun_farki: Kaydırma miktarı (gün)

        Returns:
            Dict: Kaydırılan görevler listesi
        """
        if task_id not in self.tasks:
            return {'success': False, 'error': 'Görev bulunamadı'}

        kaydirilan_gorevler = []
        islenecek = [task_id]
        islenmis = set()

        while islenecek:
            current_id = islenecek.pop(0)
            if current_id in islenmis:
                continue
            islenmis.add(current_id)

            current_task = self.tasks.get(current_id)
            if not current_task:
                continue

            # Bu görevin successorlarını bul
            for other_id, other_task in self.tasks.items():
                if other_id in islenmis:
                    continue

                # other_task, current_task'a bağımlı mı?
                for pred_id, dep_type, lag in other_task.predecessors:
                    if pred_id == current_id:
                        # Bağımlı görevi kaydır
                        if other_task.early_start:
                            yeni_baslangic = other_task.early_start + timedelta(days=gun_farki)

                            # Tatil kontrolü
                            tatil, _ = self.tatil_yoneticisi.tatil_mi(yeni_baslangic)
                            while tatil:
                                yeni_baslangic += timedelta(days=1)
                                tatil, _ = self.tatil_yoneticisi.tatil_mi(yeni_baslangic)

                            other_task.early_start = yeni_baslangic
                            other_task.early_finish = self._add_working_days(yeni_baslangic, other_task.sure_gun)

                            kaydirilan_gorevler.append({
                                'task_id': other_id,
                                'ad': other_task.ad,
                                'yeni_baslangic': yeni_baslangic
                            })

                            # Bu görevi de işleneceklere ekle (zincirleme)
                            islenecek.append(other_id)
                        break

        return {
            'success': True,
            'kaydirilan_sayisi': len(kaydirilan_gorevler),
            'kaydirilan_gorevler': kaydirilan_gorevler
        }
