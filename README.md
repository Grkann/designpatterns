# Yemek Sipariş ve Teslimat Sistemi

Tasarım Kalıpları dersi dönem projesi. Bir yemek siparişi sepetten teslimata kadar altı GoF kalıbıyla yönetilir: **Builder** (yaratımsal), **Adapter** ve **Decorator** (yapısal), **Strategy**, **State** ve **Observer** (davranışsal). Proje tarayıcı arayüzüyle ya da konsoldan çalıştırılabilir.

## Hızlı başlangıç

Python 3.10 veya üstü yeterlidir. Yalnızca standart kütüphane kullanılır; uygulama ve arayüz için kurulum gerekmez. Komutlar proje klasöründe çalıştırılır.

```bash
git clone https://github.com/Grkann/designpatterns.git
cd designpatterns

python -m arayuz          # tarayıcı arayüzü: http://127.0.0.1:8000 kendiliğinden açılır (kapatmak: Ctrl+C)
python main.py            # konsol demo senaryosu (3 sipariş akışı)

pip install pytest        # yalnızca testler için
python -m pytest -q       # 85 test
```

8000 portu doluysa başka bir port verilebilir: `python -m arayuz 8080`. Arayüzde sağ üstteki **Sıfırla** tüm siparişleri ve sepeti temizler; her adım serbestçe denenebilir. Bilerek kural dışı işlemler de yapılabilir: kolaya "duble et" eklemek, kurumsal siparişte kupon girmek, yoldaki siparişi iptal etmek gibi. Bu durumlarda ilgili kalıbın verdiği hata ekranda gösterilir.

## Proje yapısı

```
siparis/                  çekirdek: kalıpların uygulandığı kod
  builder.py              Builder  — OrderBuilder, Individual/CorporateOrderBuilder, OrderDirector
  menu.py                 Decorator — MenuItem, Dish, ItemExtra ve ekstralar
  delivery.py             Strategy — DeliveryStrategy, 5 teslimat yöntemi, PriceCalculator
  payment.py              Adapter  — PaymentGateway, KolayPay/GlobalCard adaptörleri, yedekli ödeme
  external/               Adaptee'ler — değiştiremediğimiz dış ödeme servislerini taklit eder
  order_state.py          State    — OrderState ve 7 durum sınıfı
  notifications.py        Observer — OrderSubject, OrderObserver, OrderEvent
  observers.py            Observer — SMS, restoran paneli, kurye, iade, denetim günlüğü, analitik
  order.py, checkout.py   Order (Context/Subject/Product) ve ödeme akışı
arayuz/                   tarayıcı arayüzü (http.server + tek sayfa HTML/JS); yeni kalıp eklemez
main.py                   konsol demo senaryosu
tests/                    85 test
```

## Kullanılan kalıplar ve rollerin karşılandığı tipler

| Kalıp | Grup | Dosya | Roller → Tipler |
|---|---|---|---|
| Builder | Yaratımsal | `siparis/builder.py` | Builder → `OrderBuilder` · ConcreteBuilder → `IndividualOrderBuilder`, `CorporateOrderBuilder` · Director → `OrderDirector` · Product → `Order` |
| Adapter | Yapısal | `siparis/payment.py` | Target → `PaymentGateway` · Adapter → `KolayPayAdapter`, `GlobalCardAdapter` · Adaptee → `KolayPayClient`, `GlobalCardSDK` · Client → `CheckoutService`, `RefundHandler` |
| Decorator | Yapısal | `siparis/menu.py` | Component → `MenuItem` · ConcreteComponent → `Dish` · Decorator → `ItemExtra` · ConcreteDecorator → `ExtraCheese`, `ExtraSauce`, `DoubleMeat`, `LargePortion`, `GlutenFreeBase`, `DrinkUpgrade`, `ExtraDip` |
| Strategy | Davranışsal | `siparis/delivery.py` | Strategy → `DeliveryStrategy` · ConcreteStrategy → `StandardDelivery`, `ExpressDelivery`, `PickupDelivery`, `ScheduledDelivery`, `BadWeatherExpressDelivery` · Context → `PriceCalculator` · Client → `CheckoutService` |
| State | Davranışsal | `siparis/order_state.py` | Context → `Order` · State → `OrderState` · ConcreteState → `AwaitingPaymentState`, `ReceivedState`, `PreparingState`, `OnTheWayState`, `ReadyForPickupState`, `DeliveredState`, `CancelledState` |
| Observer | Davranışsal | `siparis/notifications.py`, `siparis/observers.py` | Subject → `OrderSubject` · ConcreteSubject → `Order` · Observer → `OrderObserver` · ConcreteObserver → `CustomerNotifier`, `RestaurantPanel`, `CourierDispatcher`, `RefundHandler`, `AuditLogObserver`, `AnalyticsObserver` |

Tüm arayüzler `abc.ABC` + `@abstractmethod` ile açıkça tanımlanmıştır. Dile gömülü kalıp karşılığı (lambda vb.) ve kütüphane/çerçeve kalıbı kullanılmamıştır; Observer dahil hepsi elle yazılmıştır.

`FailoverPaymentGateway` (yedekli ödeme) da `PaymentGateway` arayüzünü uygular: birincil sağlayıcı reddederse ikincisine geçer. Bu sayede `CheckoutService` ve `RefundHandler` hiç değişmeden yedekli ödeme desteği kazanır.

## Kalıplar birbirine nasıl bağlanıyor?

```
IndividualOrderBuilder / CorporateOrderBuilder  (+ OrderDirector hazır menüler)
        │ build()
        ▼
      Order  ◄── items: MenuItem (Dish + ItemExtra dekoratörleri)
        │
CheckoutService.checkout(order, DeliveryStrategy)
        │   durum ödeme almaya izin veriyor mu?        (State: çift ödeme engellenir)
        │   PriceCalculator(strategy) → PriceBreakdown  (Strategy: ücret, süre, uygunluk)
        │   PaymentGateway.charge()                     (Adapter)
        │       → KolayPayAdapter / GlobalCardAdapter / FailoverPaymentGateway
        ▼
 order.record_payment() → state.mark_paid() → ReceivedState
        │ accept() / hand_over() / complete() / cancel()   (State)
        ▼
 Order.change_state() → notify(OrderEvent)                 (Observer)
        ├─ CustomerNotifier    (SMS)
        ├─ RestaurantPanel     (aktif siparişler)
        ├─ CourierDispatcher   (kurye ata / serbest bırak / bekleme kuyruğu)
        ├─ RefundHandler       (iptal oranına göre PaymentGateway.refund)
        ├─ AuditLogObserver    (zaman damgalı durum geçmişi)
        └─ AnalyticsObserver   (alınan / teslim / iptal sayıları, ciro)
```

## Kalıp kaldırılırsa ne olur? (gereklilik kontrolü)

- **Builder yok** → 9 parametreli kurucu; kurumsal/bireysel kuralları her çağrı yerinde tekrarlanır, geçersiz sipariş nesnesi oluşabilir.
- **Adapter yok** → `CheckoutService` kuruş/float dönüşümünü, dict/durum kodu yorumlamayı bilmek zorunda kalır; sağlayıcı eklemek ödeme kodunu değiştirir.
- **Decorator yok** → her ekstra kombinasyonu için sınıf ya da `Dish` içinde bayrak listesi + if zinciri. Ekstranın hangi ürüne eklenebileceği (`allowed_categories`) ve tekrar kuralı (`stackable`) da her ekstranın kendi sınıfında durur; `LargePortion` yüzde hesapladığı için sarma sırası fiyatı değiştirir.
- **Strategy yok** → `PriceCalculator` içinde yönteme göre if/elif; yeni teslimat türü çekirdek kodu değiştirir. Ücret, süre ve uygunluk kuralı (`unavailable_reason`: adres zorunluluğu, ekspresin 8 km sınırı) yöntemin kendi sınıfındadır; `CheckoutService` bunları bilmez.
- **State yok** → `Order`'ın her metodunda `if status == ...` kontrolleri; izinli geçişler, iptalde iade oranı ve "ödenmiş siparişten tekrar para çekilmez" kuralı dağınık olur.
- **Observer yok** → `Order`, SMS, panel, kurye, iade, denetim ve analitik servislerini doğrudan çağırır; her yeni dinleyici `Order`'ı değiştirir.

## Arayüz

`arayuz/` klasörü projeyi tarayıcıdan adım adım kullanmayı sağlar. Arayüz yeni bir kalıp eklemez; her adım projedeki sınıfları çağırır ve kullanılan kalıbın rollerini ekranda gösterir:

| Adım | Ekranda ne var | Kalıp |
|---|---|---|
| 1. Sepet | Ekstralar ürünün etrafına katman katman sarılır; fiyat ve `LargePortion(ExtraCheese(Dish(...)))` zinciri canlı görünür. Hazır menüler `OrderDirector` ile kurulur. | Decorator, Builder (Director) |
| 2. Sipariş bilgileri | Bireysel/kurumsal builder seçilir; formdan oluşan `.for_customer().add_item()...build()` zinciri gösterilir, kural ihlalleri builder hatası olarak çıkar. | Builder |
| 3. Teslimat | Beş teslimat stratejisi aynı `PriceCalculator` ile hesaplanır; siparişe uymayanlar nedeniyle birlikte pasif görünür. | Strategy |
| 4. Ödeme | KolayPay, GlobalCard veya yedekli ödeme; adaptörün dış servise yaptığı çağrı (kuruş/float, sözlük/durum kodu) adım adım listelenir. | Adapter |
| 5. Takip | Durum makinesi, izinli/izinsiz geçişler, iptalde iade oranı; sağ panelde dinleyicilerin (SMS, restoran, kurye, iade, analitik) canlı tepkileri. | State, Observer |

Demo için GlobalCard limiti 500 TL tutulmuştur: bu tutarın üstünde GlobalCard reddeder, "Yedekli ödeme" KolayPay'e geçer.

**Sunum modu:** Sağ üstteki "▶ Sunum modu" demoyu sıfırlar ve hazır bir senaryoyu tek tuşla oynatır. Her "İleri" (→ / Boşluk) bir adımı kendisi yapar, ilgili yeri vurgular ve alttaki şeritte kalıbın adını ve kısa açıklamasını gösterir. `N` tuşu prova için konuşma notunu açar/kapatır, `Esc` sunumdan çıkar.

## Testler

| Dosya | Ne test ediliyor |
|---|---|
| `tests/test_menu_and_builder.py` | Decorator, Builder |
| `tests/test_asama1_iyilestirmeler.py` | Builder doğrulamaları, Director, Adapter (yedekli ödeme) |
| `tests/test_delivery_and_payment.py` | Strategy, Adapter |
| `tests/test_asama2_iyilestirmeler.py` | Decorator ve Strategy ek senaryoları |
| `tests/test_strategy_decorator_duzeltmeler.py` | Strategy/Decorator kuralları (uygunluk, kategori, tekrar), yeni sınıf eklemenin başka kodu değiştirmemesi |
| `tests/test_state_and_observer.py`, `test_asama3_4_iyilestirmeler.py` | State geçişleri, iade oranları, Observer dinleyicileri, uçtan uca akış |
| `tests/test_arayuz.py` | Arayüz katmanı ve HTTP uç noktaları (yedekli ödeme, iptalde iade, çift ödeme engeli) |
