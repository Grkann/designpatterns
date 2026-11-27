# Yemek Sipariş ve Teslimat Sistemi

Tasarım Kalıpları dersi dönem projesi. Python 3.10+, yalnızca standart kütüphane kullanılır (testler için `pytest`).

```bash
python main.py            # demo senaryosu (3 sipariş akışı)
python -m pytest -q       # 79 test
```

## Kullanılan kalıplar ve rollerin karşılandığı tipler

| Kalıp | Grup | Dosya | Roller → Tipler |
|---|---|---|---|
| Builder | Yaratımsal | `siparis/builder.py` | Builder → `OrderBuilder` · ConcreteBuilder → `IndividualOrderBuilder`, `CorporateOrderBuilder` · Director → `OrderDirector` · Product → `Order` |
| Adapter | Yapısal | `siparis/payment.py` | Target → `PaymentGateway` · Adapter → `KolayPayAdapter`, `GlobalCardAdapter` · Adaptee → `KolayPayClient`, `GlobalCardSDK` · Client → `CheckoutService`, `RefundHandler` |
| Decorator | Yapısal | `siparis/menu.py` | Component → `MenuItem` · ConcreteComponent → `Dish` · Decorator → `ItemExtra` · ConcreteDecorator → `ExtraCheese`, `ExtraSauce`, `DoubleMeat`, `LargePortion`, `GlutenFreeBase`, `DrinkUpgrade`, `ExtraDip` |
| Strategy | Davranışsal | `siparis/delivery.py` | Strategy → `DeliveryStrategy` · ConcreteStrategy → `StandardDelivery`, `ExpressDelivery`, `PickupDelivery`, `ScheduledDelivery`, `BadWeatherExpressDelivery` · Context → `PriceCalculator` · Client → `CheckoutService` |
| State | Davranışsal | `siparis/order_state.py` | Context → `Order` · State → `OrderState` · ConcreteState → `AwaitingPaymentState`, `ReceivedState`, `PreparingState`, `OnTheWayState`, `ReadyForPickupState`, `DeliveredState`, `CancelledState` |
| Observer | Davranışsal | `siparis/notifications.py`, `siparis/observers.py` | Subject → `OrderSubject` · ConcreteSubject → `Order` · Observer → `OrderObserver` · ConcreteObserver → `CustomerNotifier`, `RestaurantPanel`, `CourierDispatcher`, `RefundHandler` |

Tüm arayüzler `abc.ABC` + `@abstractmethod` ile açıkça tanımlanmıştır. Dile gömülü kalıp karşılığı (lambda vb.) ve kütüphane/çerçeve kalıbı kullanılmamıştır; Observer dahil hepsi elle yazılmıştır.

## Kalıplar birbirine nasıl bağlanıyor?

```
IndividualOrderBuilder / CorporateOrderBuilder  (+ OrderDirector hazır menüler)
        │ build()
        ▼
      Order  ◄── items: MenuItem (Dish + ItemExtra dekoratörleri)
        │
CheckoutService.checkout(order, DeliveryStrategy)
        │   PriceCalculator(strategy) → PriceBreakdown
        │   PaymentGateway.charge()  → KolayPayAdapter / GlobalCardAdapter
        ▼
 order.record_payment() → state.mark_paid() → ReceivedState
        │ accept() / hand_over() / complete() / cancel()   (State)
        ▼
 Order._change_state() → _notify(OrderEvent)                (Observer)
        ├─ CustomerNotifier   (SMS)
        ├─ RestaurantPanel    (aktif siparişler)
        ├─ CourierDispatcher  (kurye ata / serbest bırak)
        └─ RefundHandler      (iptal oranına göre PaymentGateway.refund)
```

## Kalıp kaldırılırsa ne olur? (gereklilik kontrolü)

- **Builder yok** → 9 parametreli kurucu; kurumsal/bireysel kuralları her çağrı yerinde tekrarlanır, geçersiz sipariş nesnesi oluşabilir.
- **Adapter yok** → `CheckoutService` kuruş/float dönüşümünü, dict/durum kodu yorumlamayı bilmek zorunda kalır; sağlayıcı eklemek ödeme kodunu değiştirir.
- **Decorator yok** → her ekstra kombinasyonu için sınıf ya da `Dish` içinde bayrak listesi + if zinciri. Ekstranın hangi ürüne eklenebileceği (`allowed_categories`) ve tekrar kuralı (`stackable`) da her ekstranın kendi sınıfında durur; `LargePortion` yüzde hesapladığı için sarma sırası fiyatı değiştirir.
- **Strategy yok** → `PriceCalculator` içinde yönteme göre if/elif; yeni teslimat türü çekirdek kodu değiştirir. Ücret, süre ve uygunluk kuralı (`unavailable_reason`: adres zorunluluğu, ekspresin 8 km sınırı) yöntemin kendi sınıfındadır; `CheckoutService` bunları bilmez.
- **State yok** → `Order`'ın her metodunda `if status == ...` kontrolleri; iade oranı kuralları dağınık.
- **Observer yok** → `Order`, SMS, panel, kurye ve iade servislerini doğrudan çağırır; her yeni dinleyici `Order`'ı değiştirir.
