class KolayPayClient:
    def __init__(self, islem_limiti_kurus=1_000_000):
        self.limit = islem_limiti_kurus
        self.sayac = 0
        self.islemler = {}

    def odeme_al(self, tutar_kurus, musteri_no):
        if tutar_kurus <= 0 or tutar_kurus > self.limit:
            return {"durum": "RED", "aciklama": "İşlem limiti aşıldı"}
        self.sayac += 1
        islem_no = f"KP-{self.sayac:05d}"
        self.islemler[islem_no] = tutar_kurus
        return {"durum": "BASARILI", "islem_no": islem_no}

    def iade_et(self, islem_no, tutar_kurus):
        kalan = self.islemler.get(islem_no)
        if kalan is None or tutar_kurus <= 0 or tutar_kurus > kalan:
            return {"durum": "RED", "aciklama": "Geçersiz iade talebi"}
        self.islemler[islem_no] = kalan - tutar_kurus
        return {"durum": "BASARILI", "islem_no": islem_no + "-IADE"}
