from siparis.builder import CorporateOrderBuilder, IndividualOrderBuilder, OrderBuildError, OrderDirector
from siparis.checkout import CheckoutService
from siparis.delivery import (
    BadWeatherExpressDelivery,
    ExpressDelivery,
    PickupDelivery,
    ScheduledDelivery,
    StandardDelivery,
)
from siparis.external.globalcard import GlobalCardSDK
from siparis.external.kolaypay import KolayPayClient
from siparis.menu import DoubleMeat, ExtraCheese, ExtraNotApplicableError, ExtraSauce, default_catalog
from siparis.money import fmt
from siparis.observers import CourierDispatcher, CustomerNotifier, RefundHandler, RestaurantPanel
from siparis.order import Customer
from siparis.order_state import InvalidTransitionError
from siparis.payment import GlobalCardAdapter, KolayPayAdapter


def title(text):
    print(f"\n{'=' * 64}\n{text}\n{'=' * 64}")


def watch(order, gateway, panel, couriers):
    order.attach(CustomerNotifier())
    order.attach(panel)
    order.attach(couriers)
    order.attach(RefundHandler(gateway))


def main():
    menu = default_catalog()
    director = OrderDirector(menu)
    panel = RestaurantPanel()
    couriers = CourierDispatcher(["Ahmet", "Zeynep"])
    kolaypay = KolayPayAdapter(KolayPayClient())
    globalcard = GlobalCardAdapter(GlobalCardSDK())

    title("1) Bireysel sipariş — Builder + Decorator + Strategy + KolayPay Adapter")
    ayse = Customer("C-1", "Ayşe Yılmaz", "0555 111 22 33")
    order = (
        IndividualOrderBuilder()
        .for_customer(ayse)
        .add_item(ExtraSauce(DoubleMeat(menu["burger"])))
        .add_item(ExtraCheese(menu["pizza"]))
        .add_item(menu["kola"], quantity=2)
        .deliver_to("Kampüs Yurdu B Blok", distance_km=4.5)
        .with_coupon("OGRENCI15")
        .with_note("Zili çalmayın lütfen")
        .build()
    )
    for item in order.items:
        print(f"  - {item.description():45} {fmt(item.price())}")
    try:
        DoubleMeat(menu["kola"])
    except ExtraNotApplicableError as e:
        print(f"  Beklenen hata: {e}")

    checkout = CheckoutService(kolaypay)
    strategies = [
        StandardDelivery(),
        ExpressDelivery(),
        PickupDelivery(),
        ScheduledDelivery(slot_minutes=90),
        BadWeatherExpressDelivery(),
    ]
    print("\nTeslimat seçenekleri (ucuzdan pahalıya):")
    for q in checkout.quote_options(order, strategies):
        print(f"  {q.method_name:22} ücret {fmt(q.delivery_fee):>10}  toplam {fmt(q.total):>10}  ~{q.estimated_minutes} dk")

    watch(order, kolaypay, panel, couriers)
    print()
    checkout.checkout(order, ExpressDelivery())
    order.accept()
    order.hand_over()
    order.complete()

    title("2) Kurumsal sipariş — Director + GlobalCard Adapter + hazırlıkta iptal")
    corp = CorporateOrderBuilder()
    try:
        corp.with_coupon("OGRENCI15")
    except OrderBuildError as e:
        print(f"  Beklenen hata: {e}")
    corp.for_customer(Customer("C-2", "Mehmet Kaya", "0532 444 55 66"))
    corp.with_invoice("Kaya Yazılım A.Ş.", "1234567890")
    corp.deliver_to("Teknopark No:12", distance_km=1.5)
    director.make_office_lunch(corp, headcount=6)
    office = corp.build()
    print(f"  {len(office.items)} ürün, ara toplam {fmt(office.subtotal())}, fatura: {office.invoice.company_name}")

    watch(office, globalcard, panel, couriers)
    print()
    CheckoutService(globalcard).checkout(office, StandardDelivery())
    office.accept()
    office.cancel("Toplantı iptal oldu")

    title("3) Gel-al sipariş + geçersiz durum geçişi (State)")
    can = Customer("C-3", "Can Demir", "0544 777 88 99")
    b = IndividualOrderBuilder().for_customer(can)
    director.make_pizza_night(b)
    pickup = b.build()
    watch(pickup, kolaypay, panel, couriers)
    CheckoutService(kolaypay).checkout(pickup, PickupDelivery())
    pickup.accept()
    pickup.hand_over()
    pickup.complete()
    try:
        pickup.cancel("Vazgeçtim")
    except InvalidTransitionError as e:
        print(f"  Beklenen hata: {e}")

    print(f"\nRestoran panelinde aktif sipariş: {len(panel.active_orders)}")


if __name__ == "__main__":
    main()
