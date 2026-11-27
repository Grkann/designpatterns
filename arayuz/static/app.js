"use strict";

// --------------------------------------------------------------- durum
const S = {
  catalog: null,
  data: null,
  step: 1,
  product: "pizza",
  extras: [],
  preview: null,
  qty: 1,
  headcount: 6,
  form: {
    type: "bireysel",
    name: "Ayşe Yılmaz",
    phone: "0555 111 22 33",
    address: "Kampüs Yurdu B Blok",
    distance: "4.5",
    coupon: "OGRENCI15",
    note: "Zili çalmayın lütfen",
    company: "Kaya Yazılım A.Ş.",
    tax_number: "1234567890",
    pickup_only: false,
  },
  orderId: null,
  quotes: null,
  strategy: null,
  slot: 90,
  surge: "1.25",
  gateway: "kolaypay",
  trace: null,
  cancelReason: "Müşteri vazgeçti",
  lastEventN: null,
};

const STEPS = [
  { n: 1, t: "Sepet", p: "Decorator · Director", pills: ["Decorator", "Builder"] },
  { n: 2, t: "Sipariş bilgileri", p: "Builder", pills: ["Builder"] },
  { n: 3, t: "Teslimat", p: "Strategy", pills: ["Strategy"] },
  { n: 4, t: "Ödeme", p: "Adapter", pills: ["Adapter"] },
  { n: 5, t: "Sipariş takibi", p: "State · Observer", pills: ["State", "Observer"] },
];

const SOURCE_LABEL = {
  Order: "Durum",
  CustomerNotifier: "Müşteri SMS",
  RestaurantPanel: "Restoran",
  CourierDispatcher: "Kurye",
  RefundHandler: "İade",
  OrderBuilder: "Builder",
};

// ------------------------------------------------------------ yardımcılar
const $ = (sel, el = document) => el.querySelector(sel);
const esc = (v) =>
  String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const tl = (v) => `${v} TL`;

async function api(path, body) {
  const opt = body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
  const res = await fetch(path, opt);
  const json = await res.json();
  if (!res.ok) {
    const err = new Error(json.error);
    err.kind = json.kind;
    throw err;
  }
  if (body === undefined) return json;
  S.data = json.state;
  renderSide();
  return json.result;
}

async function run(fn) {
  try {
    return await fn();
  } catch (e) {
    toast(e.message, "err", e.kind);
    return undefined;
  }
}

let toastTimer;
function toast(msg, kind = "", detail = "") {
  const el = $("#toast");
  el.className = `toast show ${kind}`;
  el.innerHTML = `${detail ? `<span class="kind">${esc(detail)}</span>` : ""}${esc(msg)}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), 4200);
}

function note(group, pattern, kind, roles, why) {
  const cls = { create: "g-create", struct: "g-struct", behav: "" }[group];
  return `<div class="note ${cls}">
    <div class="h">${pattern}<span>${kind}</span></div>
    <div class="roles">${roles.map(([r, t]) => `<span><b>${r}:</b> <code>${t}</code></span>`).join("")}</div>
    <p>${why}</p>
  </div>`;
}

const currentOrder = () => S.data?.orders.find((o) => o.id === S.orderId) || null;

// ------------------------------------------------------------- iskelet
function goto(n) {
  S.step = n;
  render();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function render() {
  const order = currentOrder();
  $("#stepper").innerHTML = STEPS.map((s) => {
    const done =
      (s.n === 1 && S.orderId) || (s.n === 2 && S.orderId) || ((s.n === 3 || s.n === 4) && order && order.paid);
    return `<button class="step ${S.step === s.n ? "active" : ""} ${done && S.step !== s.n ? "done" : ""}" data-act="goto" data-n="${s.n}">
      <span class="num">${done && S.step !== s.n ? "✓" : s.n}</span>
      <span><span class="t">${s.t}</span><br><span class="p">${s.p}</span></span>
    </button>`;
  }).join("");

  const on = P.on && P.i >= 0 ? beatPills(SCENE[P.i]) : STEPS[S.step - 1].pills;
  document.querySelectorAll(".pill").forEach((p) => p.classList.toggle("on", on.includes(p.dataset.pattern)));

  const views = { 1: viewCart, 2: viewBuilder, 3: viewStrategy, 4: viewPayment, 5: viewTracking };
  $("#main").innerHTML = views[S.step]();
  if (S.step === 2) updateBuilderCode();
}

// ------------------------------------------------------ 1) Decorator: sepet
function viewCart() {
  const c = S.catalog;
  const prod = c.products.find((p) => p.key === S.product);
  const cart = S.data.cart;

  const products = c.products
    .map((p) => `<button class="product ${p.key === S.product ? "sel" : ""}" data-act="pick" data-key="${p.key}">
        <b>${esc(p.name)}</b><span>${tl(p.price)} · ${esc(p.category)}</span></button>`)
    .join("");

  const extras = c.extras
    .map((x) => {
      const na = !x.categories.includes(prod.category);
      return `<button class="chip ${na ? "na" : ""}" data-act="extra" data-key="${x.key}" title="${x.cls}">
        + ${esc(x.label)} ${x.stackable ? "" : "<small>(1 kez)</small>"}</button>`;
    })
    .join("");

  const chain = S.extras.length
    ? S.extras
        .map((k, i) => `<button class="chip chain-chip" data-act="unextra" data-i="${i}">${esc(c.extras.find((x) => x.key === k).label)}</button>`)
        .join("")
    : `<span class="muted small">Henüz ekstra yok — yukarıdan ekleyin.</span>`;

  const lines = cart.lines.length
    ? cart.lines
        .map((l) => `<div class="cart-line">
          <span class="q">${l.qty}×</span>
          <span class="d">${esc(l.description)}<code>${esc(l.code)}</code></span>
          <b>${tl(l.line_total)}</b>
          <button class="x" data-act="remove" data-i="${l.index}" title="Bir adet çıkar">×</button>
        </div>`)
        .join("")
    : `<div class="empty">Sepet boş</div>`;

  const presets = c.presets
    .map((p) => `<button class="btn small" data-act="preset" data-key="${p.key}" title="OrderDirector.${p.method}()">${esc(p.name)}${p.key === "ofis" ? ` (${S.headcount} kişi)` : ""}</button>`)
    .join("");

  return `<div class="cols">
    <div>
      <div class="card">
        <h2>Menü</h2>
        <div class="products">${products}</div>
        <h3>Ekstralar — sırayla sarılır</h3>
        <div class="chips">${extras}</div>
        <h3>Uygulanan sıra</h3>
        <div class="chips">${chain}</div>
        <div class="onion">${onion(S.preview?.layers || [])}</div>
        <div class="spread" style="margin-top:.9rem">
          <div><div class="muted small">Ürün fiyatı</div><div class="price-big">${S.preview ? tl(S.preview.price) : "—"}</div></div>
          <div class="row">
            <input class="inline-input" type="number" min="1" max="50" value="${S.qty}" data-f="qty" style="width:4.5rem" aria-label="Adet">
            <button class="btn primary" data-act="add">Sepete ekle</button>
          </div>
        </div>
        <pre class="code" style="margin-top:.8rem">${S.preview ? codeColor(S.preview.code) : ""}</pre>
      </div>
    </div>
    <div>
      <div class="card cart-card">
        <div class="spread"><h2>Sepet</h2>${cart.count ? `<button class="btn ghost small" data-act="clear">Temizle</button>` : ""}</div>
        ${lines}
        <div class="total-row"><span>Ara toplam (${cart.count} ürün)</span><span>${tl(cart.subtotal)}</span></div>
        <h3>Hazır menüler — <code class="inline">OrderDirector</code></h3>
        <div class="row">${presets}</div>
        <div class="next"><button class="btn primary" data-act="goto" data-n="2" ${cart.count ? "" : "disabled"}>Sipariş bilgileri →</button></div>
      </div>
    </div>
  </div>
  ${note("struct", "Decorator", "Yapısal", [
    ["Component", "MenuItem"], ["ConcreteComponent", "Dish"], ["Decorator", "ItemExtra"],
    ["ConcreteDecorator", "ExtraCheese, DoubleMeat, LargePortion, …"],
  ], "Her ekstra ürünü sarar ve kendisi de bir MenuItem'dır; fiyat ve açıklama katman katman hesaplanır. Ekstra uygun ürün türünü ve tekrar kuralını kendisi denetler (ör. içeceğe “duble et” eklenemez). Hazır menüler Builder kalıbının Director'ı ile kurulur.")}`;
}

function onion(layers) {
  if (!layers.length) return "";
  let html = "";
  layers.forEach((l, i) => {
    const head = `<div class="layer-head"><span><b>${esc(l.cls)}</b> ${esc(l.label)}</span>
      <span class="amt">${l.extra !== null ? `+${tl(l.extra)} → ` : ""}${tl(l.price)}</span></div>`;
    html = `<div class="layer ${i === 0 ? "base" : ""}">${head}${html}</div>`;
  });
  return html;
}

function codeColor(code) {
  return esc(code)
    .replace(/(&quot;[^&]*&quot;)/g, '<span class="s">$1</span>')
    .replace(/\b([A-Z][A-Za-z]+)\(/g, '<span class="k">$1</span>(');
}

async function updatePreview() {
  S.preview = await run(() => api("/api/preview", { product: S.product, extras: S.extras }));
  render();
}

// ---------------------------------------------------- 2) Builder: sipariş
function viewBuilder() {
  const f = S.form;
  const corp = f.type === "kurumsal";
  const cart = S.data.cart;
  const coupons = Object.entries(S.catalog.coupons).map(([k, v]) => `${k} (${v})`).join(", ");
  return `<div class="cols">
    <div class="card">
      <h2>Sipariş bilgileri</h2>
      <div class="seg">
        <button class="${corp ? "" : "on"}" data-act="otype" data-v="bireysel">Bireysel</button>
        <button class="${corp ? "on" : ""}" data-act="otype" data-v="kurumsal">Kurumsal</button>
      </div>
      <div class="fields">
        <label class="f">Ad soyad<input data-f="name" value="${esc(f.name)}"></label>
        <label class="f">Telefon<input data-f="phone" value="${esc(f.phone)}"></label>
        <label class="f full">Adres<input data-f="address" value="${esc(f.address)}" ${f.pickup_only ? "disabled" : ""}></label>
        <label class="f">Mesafe (km)<input data-f="distance" type="number" step="0.5" value="${esc(f.distance)}" ${f.pickup_only ? "disabled" : ""}></label>
        <label class="check" style="align-self:end;padding-bottom:.5rem"><input type="checkbox" data-f="pickup_only" ${f.pickup_only ? "checked" : ""}> Adres yok (gel-al)</label>
        <label class="f">Kupon<input data-f="coupon" value="${esc(f.coupon)}" placeholder="${esc(coupons)}"></label>
        <label class="f">Not<input data-f="note" value="${esc(f.note)}"></label>
        ${corp ? `<label class="f">Şirket ünvanı<input data-f="company" value="${esc(f.company)}"></label>
        <label class="f">Vergi no (10 hane)<input data-f="tax_number" value="${esc(f.tax_number)}"></label>` : ""}
      </div>
      <p class="small muted">${corp ? "Kurumsal: fatura zorunlu, en az 3 ürün, kupon kullanılamaz." : `Geçerli kuponlar: ${esc(coupons)}`}</p>
      <div class="next">
        <button class="btn ghost" data-act="goto" data-n="1">← Sepet</button>
        <button class="btn primary" data-act="build" ${cart.count ? "" : "disabled"}>build() — siparişi oluştur</button>
      </div>
    </div>
    <div class="card">
      <h2>Builder çağrı zinciri</h2>
      <pre class="code" id="builder-code"></pre>
      <p class="small muted">Form değiştikçe hangi adımların çağrılacağı burada güncellenir. Kurallara uymayan adımı builder reddeder; geçersiz bir <code>Order</code> nesnesi hiç oluşmaz.</p>
    </div>
  </div>
  ${note("create", "Builder", "Yaratımsal", [
    ["Builder", "OrderBuilder"], ["ConcreteBuilder", "IndividualOrderBuilder, CorporateOrderBuilder"],
    ["Director", "OrderDirector"], ["Product", "Order"],
  ], "Siparişi adım adım kurar. Bireysel ve kurumsal siparişin kuralları kendi builder'ında durur; 9 parametreli bir kurucu yerine okunur bir zincir çıkar.")}`;
}

function updateBuilderCode() {
  const el = $("#builder-code");
  if (!el) return;
  const f = S.form;
  const corp = f.type === "kurumsal";
  const s = (v) => `<span class="s">"${esc(v)}"</span>`;
  const m = (name) => `  .<span class="m">${name}</span>`;
  const lines = [`<span class="k">${corp ? "CorporateOrderBuilder" : "IndividualOrderBuilder"}</span>()`];
  lines.push(`${m("for_customer")}(<span class="k">Customer</span>(${s(f.name)}, ${s(f.phone)}))`);
  S.data.cart.lines.forEach((l) => {
    lines.push(`${m("add_item")}(${codeColor(l.code)}${l.qty > 1 ? `, quantity=${l.qty}` : ""})`);
  });
  if (!f.pickup_only) lines.push(`${m("deliver_to")}(${s(f.address)}, distance_km=${esc(f.distance)})`);
  if (f.coupon) lines.push(`${m("with_coupon")}(${s(f.coupon)})`);
  if (f.note) lines.push(`${m("with_note")}(${s(f.note)})`);
  if (corp) lines.push(`${m("with_invoice")}(${s(f.company)}, ${s(f.tax_number)})`);
  lines.push(`${m("build")}()   <span class="c"># → Order</span>`);
  el.innerHTML = lines.join("\n");
}

// --------------------------------------------------- 3) Strategy: teslimat
function needOrder() {
  return `<div class="card"><div class="empty">Önce sepeti doldurup sipariş oluşturun.</div>
    <div class="next"><button class="btn primary" data-act="goto" data-n="1">Sepete git</button></div></div>`;
}

function paidNotice(order) {
  return `<div class="card"><div class="banner ok">#${order.id} ödendi: ${esc(order.method)} · ${tl(order.total)} · ${esc(order.provider)}</div>
    <div class="next"><button class="btn primary" data-act="goto" data-n="5">Sipariş takibine geç →</button></div></div>`;
}

function viewStrategy() {
  const order = currentOrder();
  if (!order) return needOrder();
  if (order.paid || order.is_final) return paidNotice(order);
  const q = S.quotes;
  if (!q) return `<div class="card"><div class="empty">Seçenekler hesaplanıyor…</div></div>`;

  const usable = q.options.filter((o) => o.available);
  const minTotal = Math.min(...usable.map((o) => Number(o.total)));
  const minTime = Math.min(...usable.map((o) => o.minutes));
  const cards = q.options
    .map((o) => {
      if (!o.available) {
        return `<div class="opt off"><div class="cls">${o.cls}</div><div class="name">${esc(o.name)}</div>
          <div class="why">${esc(o.reason)}</div></div>`;
      }
      const tags = `${Number(o.total) === minTotal ? `<span class="tag cheap">En ucuz</span>` : ""}${o.minutes === minTime ? `<span class="tag fast">En hızlı</span>` : ""}`;
      return `<button class="opt ${S.strategy === o.key ? "sel" : ""}" data-act="strategy" data-key="${o.key}">
        <div class="cls">${o.cls}</div><div class="name">${esc(o.name)}</div>${tags}
        <div class="tot">${tl(o.total)}</div>
        <div class="meta">Teslimat ücreti ${tl(o.fee)} · ~${o.minutes} dk${o.courier ? "" : " · kurye yok"}</div>
      </button>`;
    })
    .join("");

  const sel = q.options.find((o) => o.key === S.strategy);
  return `<div class="card">
    <h2>Teslimat yöntemi — sipariş #${order.id}</h2>
    <div class="summary">
      <div>Ara toplam<b>${tl(q.subtotal)}</b></div>
      <div>Kupon indirimi<b>${q.discount === "0.00" ? "—" : "−" + tl(q.discount)}</b></div>
      <div>Mesafe<b>${order.address ? `${order.distance} km` : "Adres yok"}</b></div>
    </div>
    <div class="options">${cards}</div>
    <pre class="code" style="margin-top:1rem">calculator = <span class="k">PriceCalculator</span>(...)
calculator.<span class="m">set_strategy</span>(<span class="k">${sel ? sel.cls : "…"}</span>())   <span class="c"># çalışma anında değişir</span>
calculator.<span class="m">calculate</span>(order)       <span class="c"># → ${sel ? `toplam ${sel.total} TL, ~${sel.minutes} dk` : "PriceBreakdown"}</span></pre>
    <div class="next">
      <button class="btn primary" data-act="goto" data-n="4" ${sel ? "" : "disabled"}>Ödemeye geç →</button>
    </div>
  </div>
  ${note("behav", "Strategy", "Davranışsal", [
    ["Strategy", "DeliveryStrategy"], ["ConcreteStrategy", "Standard, Express, Pickup, Scheduled, BadWeatherExpress"],
    ["Context", "PriceCalculator"], ["Client", "CheckoutService"],
  ], "Ücret, süre ve “bu sipariş için uygun mu?” kuralı her yöntemin kendi sınıfında. PriceCalculator yalnızca arayüzü bilir; yeni teslimat türü eklemek hesaplayıcıyı değiştirmez.")}`;
}

async function loadQuotes() {
  if (!S.orderId) return;
  S.quotes = await run(() => api("/api/orders/" + S.orderId + "/quotes", { slot: S.slot, surge: S.surge }));
  if (S.quotes) {
    const ok = S.quotes.options.filter((o) => o.available);
    if (!ok.some((o) => o.key === S.strategy)) S.strategy = null;
  }
  render();
}

// ------------------------------------------------------- 4) Adapter: ödeme
function viewPayment() {
  const order = currentOrder();
  if (!order) return needOrder();
  const sel = S.quotes?.options.find((o) => o.key === S.strategy && o.available);
  if (!order.paid && !sel) {
    return `<div class="card"><div class="empty">Önce teslimat yöntemini seçin.</div>
      <div class="next"><button class="btn primary" data-act="goto" data-n="3">Teslimata git</button></div></div>`;
  }
  const lim = S.catalog.globalcard_limit;
  const gws = [
    ["kolaypay", "KolayPay", "KolayPayAdapter", "Yerli servis: tutarı kuruş (int) ister, sonucu sözlük olarak döner."],
    ["globalcard", "GlobalCard", "GlobalCardAdapter", `Yabancı SDK: tutarı float ve para birimiyle ister, HTTP durum kodu döner. Demo limiti ${lim} TL.`],
    ["yedekli", "Yedekli ödeme", "FailoverPaymentGateway", "Önce GlobalCard'ı dener, reddedilirse KolayPay'e geçer."],
  ]
    .map(([k, n, cls, d]) => `<button class="gw ${S.gateway === k ? "sel" : ""}" data-act="gateway" data-key="${k}" ${order.paid ? "disabled" : ""}>
      <div class="name">${n}</div><div class="cls">${cls}</div><div class="meta">${d}</div></button>`)
    .join("");

  return `<div class="card">
    <h2>Ödeme — sipariş #${order.id}</h2>
    <div class="summary">
      <div>Teslimat<b>${esc(order.paid ? order.method : sel.name)}</b></div>
      <div>Ödenecek tutar<b>${tl(order.paid ? order.total : sel.total)}</b></div>
    </div>
    <div class="gws">${gws}</div>
    <div class="next">
      ${order.paid ? "" : `<button class="btn ghost" data-act="goto" data-n="3">← Teslimat</button>
      <button class="btn primary" data-act="pay">Öde</button>`}
    </div>
    ${traceView(order)}
  </div>
  ${note("struct", "Adapter", "Yapısal", [
    ["Target", "PaymentGateway"], ["Adapter", "KolayPayAdapter, GlobalCardAdapter"],
    ["Adaptee", "KolayPayClient, GlobalCardSDK"], ["Client", "CheckoutService, RefundHandler"],
  ], "CheckoutService her sağlayıcıyla aynı charge() çağrısını yapar. Kuruş/float dönüşümü ve sağlayıcıya özgü yanıtı PaymentResult'a çevirmek adaptörün işidir.")}`;
}

function traceView(order) {
  const t = S.trace;
  if (!t) return "";
  const amount = t.amount || (S.quotes?.options.find((o) => o.key === S.strategy)?.total ?? "");
  let n = 1;
  const items = [
    `<li data-n="${n++}"><div class="role">Client → Target</div>
      <code>CheckoutService → ${esc(t.gateway_cls)}.charge(${esc(amount)} TL, "C-${order.id}")</code></li>`,
  ];
  t.calls.forEach((c) => {
    const ok = /BASARILI|\(200/.test(c.response);
    items.push(`<li data-n="${n++}" class="${ok ? "ok" : "fail"}"><div class="role">Adapter → Adaptee (${esc(c.adaptee)})</div>
      <code>${esc(c.call)}</code><code class="resp">↳ ${esc(c.response)}</code></li>`);
  });
  items.push(`<li data-n="${n++}" class="${t.success ? "ok" : "fail"}"><div class="role">Adapter → Client</div>
    <code>PaymentResult(success=${t.success ? "True" : "False"}${t.transaction_id ? `, transaction_id="${esc(t.transaction_id)}"` : ""})</code></li>`);
  const banner = t.success
    ? `<div class="banner ok">Ödeme alındı · ${esc(t.provider)} · işlem no ${esc(t.transaction_id)}</div>
       <div class="next"><button class="btn primary" data-act="goto" data-n="5">Sipariş takibine geç →</button></div>`
    : `<div class="banner fail">Ödeme reddedildi: ${esc(t.error)} — başka bir sağlayıcı deneyin.</div>`;
  return `<h3>Adapter çevirisi</h3><ol class="trace">${items.join("")}</ol>${banner}`;
}

// ------------------------------------------------- 5) State + Observer
const MAIN_FLOW = [
  ["AwaitingPaymentState", "ÖDEME BEKLİYOR"],
  ["ReceivedState", "ALINDI"],
  ["PreparingState", "HAZIRLANIYOR"],
];
const BRANCH = [
  ["OnTheWayState", "YOLDA"],
  ["ReadyForPickupState", "GEL-AL İÇİN HAZIR"],
];

function viewTracking() {
  const orders = S.data.orders;
  if (!orders.length) return needOrder();
  if (!orders.some((o) => o.id === S.orderId)) S.orderId = orders[orders.length - 1].id;
  const o = currentOrder();

  const tabs = orders
    .map((x) => `<button class="tab ${x.id === o.id ? "on" : ""}" data-act="selorder" data-id="${x.id}">#${x.id} ${esc(x.customer)}<small>${esc(x.state)}</small></button>`)
    .join("");

  const visited = new Set(o.history.flatMap((h) => [h.from, h.to]));
  visited.add("ÖDEME BEKLİYOR");
  const node = ([cls, name], extra = "") => {
    const cur = o.state === name;
    return `<div class="node ${cur ? "current" : visited.has(name) ? "visited" : ""} ${extra}">${name}<small>${cls}</small></div>`;
  };
  const machine = `<div class="machine">
      ${MAIN_FLOW.map((s) => node(s)).join("")}
      <div class="stack">${BRANCH.map((s) => node(s)).join("")}</div>
      ${node(["DeliveredState", "TESLİM EDİLDİ"], "last")}
    </div>
    <div class="cancel-row">${node(["CancelledState", "İPTAL EDİLDİ"], "cancel")}
      <span class="small muted">Ödeme bekliyor · alındı · hazırlanıyor durumlarından iptal edilebilir</span></div>`;

  const acts = S.catalog.actions;
  const buttons = Object.entries(acts)
    .filter(([k]) => k !== "cancel")
    .map(([k, label]) => `<button class="btn ${o.allowed.includes(k) ? "allowed" : ""}" data-act="do" data-a="${k}">${label}<br><code class="small">${k}()</code></button>`)
    .join("");

  const hist = o.history.length
    ? o.history.map((h) => `<li><span class="t">${h.time}</span>${esc(h.from)} → <b>${esc(h.to)}</b></li>`).join("")
    : `<li class="muted">Henüz geçiş yok</li>`;

  const payBtn = !o.paid && !o.is_final
    ? `<button class="btn primary" data-act="goto" data-n="3">Ödemeye devam et</button>` : "";

  return `<div class="card">
    <div class="spread"><h2>Sipariş takibi</h2><button class="btn small" data-act="neworder">+ Yeni sipariş</button></div>
    <div class="tabs">${tabs}</div>
    ${machine}
    <div class="actions">
      ${buttons}
      <span style="flex:1"></span>
      <input class="inline-input" data-f="cancelReason" value="${esc(S.cancelReason)}" style="width:12rem" aria-label="İptal nedeni">
      <button class="btn danger ${o.allowed.includes("cancel") ? "allowed" : ""}" data-act="do" data-a="cancel">İptal et<br><code class="small">cancel()</code></button>
      ${payBtn}
    </div>
    <p class="small muted">${o.refund_if_cancel ? `Şu an iptal edilirse iade oranı: <b>${o.refund_if_cancel}</b> (kural durumun kendi sınıfında). ` : ""}Renkli düğmeler bu durumda izinli işlemlerdir; diğerlerine basınca durum nesnesi isteği reddeder.</p>
  </div>
  <div class="cols even" style="margin-top:1rem">
    <div class="card">
      <h2>Sipariş #${o.id} · ${esc(o.type)}</h2>
      <dl class="kv">
        <dt>Müşteri</dt><dd>${esc(o.customer)}</dd>
        <dt>Ürünler</dt><dd>${o.items.map(esc).join("<br>")}</dd>
        <dt>Teslimat</dt><dd>${o.method ? `${esc(o.method)} · ~${o.minutes} dk` : "—"}</dd>
        <dt>Tutar</dt><dd>${o.total ? tl(o.total) : `${tl(o.subtotal)} (ödenmedi)`}</dd>
        <dt>Ödeme</dt><dd>${o.provider ? `${esc(o.provider)} · ${esc(o.transaction_id)}` : "—"}</dd>
        <dt>Kurye</dt><dd>${o.courier ? esc(o.courier) : o.courier_needed ? "—" : "Gerekmiyor (gel-al)"}</dd>
        ${o.cancel_reason ? `<dt>İptal nedeni</dt><dd>${esc(o.cancel_reason)}</dd>` : ""}
        ${o.refund ? `<dt>İade</dt><dd>${tl(o.refund)}</dd>` : ""}
      </dl>
    </div>
    <div class="card">
      <h2>Durum geçmişi <small class="muted">AuditLogObserver</small></h2>
      <ul class="hist">${hist}</ul>
    </div>
  </div>
  ${note("behav", "State", "Davranışsal", [
    ["Context", "Order"], ["State", "OrderState"],
    ["ConcreteState", "AwaitingPayment, Received, Preparing, OnTheWay, ReadyForPickup, Delivered, Cancelled"],
  ], "Order her isteği o anki durum nesnesine devreder. Hangi geçişin izinli olduğu ve iptalde ne kadar iade yapılacağı durum sınıflarında tanımlı; Order'da if/else zinciri yok.")}
  ${note("behav", "Observer", "Davranışsal", [
    ["Subject", "OrderSubject"], ["ConcreteSubject", "Order"], ["Observer", "OrderObserver"],
    ["ConcreteObserver", "CustomerNotifier, RestaurantPanel, CourierDispatcher, RefundHandler, AuditLog, Analytics"],
  ], "Her durum değişikliğinde Order yalnızca notify() çağırır; SMS, restoran paneli, kurye ataması ve iade sağdaki akışta görünür. Yeni dinleyici eklemek Order'ı değiştirmez — bu ekranın akışı da ayrı bir dinleyicidir.")}`;
}

// ------------------------------------------------------------ yan panel
function renderSide() {
  const d = S.data;
  if (!d) return;
  const prev = S.lastEventN; // null: ilk çizim, vurgulama yok
  const isNew = (e) => prev !== null && e.n > prev;
  const feed = d.events.length
    ? [...d.events]
        .reverse()
        .slice(0, 60)
        .map((e) => `<li class="${isNew(e) ? "new" : ""}">
          <div class="fh"><span class="src ${e.source}">${SOURCE_LABEL[e.source] || e.source}</span><span class="tm">${e.time}</span></div>
          ${esc(e.text.replace(/^\[[^\]]*\]\s*/, ""))}</li>`)
        .join("")
    : `<li class="muted">Henüz bildirim yok. Bir siparişin durumu değişince dinleyiciler burada tepki verir.</li>`;
  if (d.events.some((e) => isNew(e) && e.source !== "OrderBuilder")) {
    const pill = $('.pill[data-pattern="Observer"]');
    pill.classList.remove("ping");
    void pill.offsetWidth;
    pill.classList.add("ping");
  }
  S.lastEventN = d.events.length ? d.events[d.events.length - 1].n : 0;

  const c = d.couriers;
  const busy = Object.entries(c.assignments).map(([id, name]) => `<span class="badge busy">${esc(name)} → #${id}</span>`).join(" ");
  const free = c.available.map((n) => `<span class="badge free">${esc(n)}</span>`).join(" ");
  const a = d.analytics;

  $("#side").innerHTML = `<div class="card">
      <h2>Canlı bildirimler <small>Observer</small></h2>
      <ul class="feed">${feed}</ul>
    </div>
    <div class="card mini">
      <h2>Restoran paneli <small>RestaurantPanel</small></h2>
      <div>${d.panel.length ? d.panel.map((id) => `<span class="badge">#${id}</span>`).join(" ") : `<span class="muted">Aktif sipariş yok</span>`}</div>
      <h2 style="margin-top:.9rem">Kuryeler <small>CourierDispatcher</small></h2>
      <div class="row">${free || ""}${busy}${!free && !busy ? `<span class="muted">—</span>` : ""}</div>
      ${c.queue.length ? `<div class="muted small" style="margin-top:.3rem">Sırada: ${c.queue.map((x) => "#" + x).join(", ")}</div>` : ""}
      <h2 style="margin-top:.9rem">Özet <small>AnalyticsObserver</small></h2>
      <div class="stats">
        <div><b>${a.received}</b><span>Alınan</span></div>
        <div><b>${a.delivered}</b><span>Teslim</span></div>
        <div><b>${a.cancelled}</b><span>İptal</span></div>
        <div><b>${a.revenue}</b><span>Ciro TL</span></div>
      </div>
    </div>`;
}

// ---------------------------------------------------------- sunum modu
// Her "İleri" bir adımı oynatır: işlemi yapar, ilgili yeri vurgular, altta kalıbı ve kısa açıklamayı gösterir.
// "say" satırları anlatım metnidir; N tuşuyla prova sırasında görünür olur.
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const GROUP = { Builder: "g-create", Decorator: "g-struct", Adapter: "g-struct", Strategy: "g-behav", State: "g-behav", Observer: "g-behav" };

const SCENE = [
  {
    pattern: "Giriş", pills: ["Builder", "Adapter", "Decorator", "Strategy", "State", "Observer"],
    title: "Yemek sipariş ve teslimat sistemi",
    cap: "6 GoF kalıbı: Builder · Adapter, Decorator · Strategy, State, Observer",
    say: "Merhaba. Projemiz bir yemek sipariş ve teslimat sistemi. Altı GoF kalıbı kullandık: yaratımsal grupta Builder, yapısal grupta Adapter ve Decorator, davranışsal grupta Strategy, State ve Observer. Tek bir siparişi baştan sona vererek hepsini göstereceğim.",
    run: async () => { await resetDemo(true); },
  },
  {
    pattern: "Decorator", title: "Sade ürün", cap: "<code>Dish(\"Klasik Burger\")</code> — henüz ekstra yok",
    say: "İlk kalıp Decorator. Klasik Burger'i seçiyorum; bu sade bir Dish nesnesi.",
    run: async () => { S.product = "burger"; S.extras = []; await updatePreview(); },
    spot: ".onion",
  },
  {
    pattern: "Decorator", title: "+ duble et", cap: "<code>DoubleMeat</code> ürünü sarar, kendisi de bir <code>MenuItem</code>",
    say: "Duble et eklediğimde burger bir dekoratörle sarılıyor. Dekoratör de bir MenuItem olduğu için fiyat ve açıklama katman katman hesaplanıyor.",
    run: () => ACTS.extra({ key: "duble_et" }), spot: ".onion",
  },
  {
    pattern: "Decorator", title: "+ acı sos, + büyük boy", cap: "Her ekstra bir katman daha · <code>LargePortion</code> fiyatın %30'unu ekler",
    say: "Acı sos ve büyük boy iki katman daha ekliyor. Büyük boy fiyatın yüzde otuzunu eklediği için sarma sırası fiyatı değiştiriyor.",
    run: () => ACTS.extra({ key: "aci_sos" }),
    then: () => ACTS.extra({ key: "buyuk_boy" }), thenDelay: 350,
    spot: ".onion",
  },
  {
    pattern: "Decorator", title: "Kural: içeceğe et eklenmez", cap: "Ekstra, eklenebileceği ürün türünü kendisi denetler",
    say: "Burgeri sepete ekliyorum. Her ekstra hangi ürüne eklenebileceğini kendisi denetliyor: kolaya duble et eklemeye çalışınca reddediliyor.",
    run: () => ACTS.add(),
    then: async () => {
      S.product = "kola"; S.extras = [];
      await updatePreview();
      await wait(600);
      await ACTS.extra({ key: "duble_et" });
    },
    thenDelay: 500,
    spot: ".products .sel",
  },
  {
    pattern: "Builder", title: "Director: hazır menü", cap: "<code>OrderDirector.make_student_menu()</code> sepeti tek adımda doldurur",
    say: "Hazır menüler Builder kalıbının Director'ı ile kuruluyor; öğrenci menüsü tek tıkla sepete geldi.",
    run: () => ACTS.preset({ key: "ogrenci" }), spot: ".cart-card",
  },
  {
    pattern: "Builder", title: "Sipariş adım adım kurulur", cap: "<code>IndividualOrderBuilder</code> · müşteri → ürünler → adres → kupon → <code>build()</code>",
    say: "İkinci kalıp Builder. Siparişi adım adım kuruyoruz: müşteri, ürünler, adres ve kupon. Bireysel ve kurumsal siparişin kuralları kendi builder sınıflarında duruyor.",
    run: async () => { goto(2); }, spot: "#builder-code",
  },
  {
    pattern: "Builder", title: "build() → Order", cap: "Kurallara uyan bir <code>Order</code> nesnesi oluştu",
    say: "Build dediğimde kurallara uyan bir Order nesnesi oluşuyor; geçersiz bir sipariş hiç oluşamıyor.",
    run: () => ACTS.build(), spot: ".summary",
  },
  {
    pattern: "Strategy", title: "Beş teslimat stratejisi", cap: "Her yöntem ücreti, süreyi ve uygunluğu kendisi hesaplar",
    say: "Üçüncü kalıp Strategy. Beş teslimat yönteminin her biri ayrı bir sınıf; ücreti, süreyi ve siparişe uygun olup olmadığını kendisi hesaplıyor.",
    run: async () => {}, spot: ".options",
  },
  {
    pattern: "Strategy", title: "Ekspres seçildi", cap: "<code>PriceCalculator.set_strategy(ExpressDelivery())</code> — hesaplayıcının kodu değişmez",
    say: "Ekspresi seçiyorum. PriceCalculator yalnızca stratejiyi değiştiriyor, kendi kodu hiç değişmiyor. Yeni bir teslimat türü eklemek tek bir sınıf yazmak demek.",
    run: () => ACTS.strategy({ key: "ekspres" }), spot: ".opt.sel",
  },
  {
    pattern: "Adapter", title: "Ödeme servisleri farklı dil konuşur", cap: "KolayPay: kuruş + sözlük · GlobalCard: ondalık tutar + durum kodu",
    say: "Dördüncü kalıp Adapter. İki ödeme servisimiz farklı arayüzler kullanıyor: biri kuruş ve sözlük, diğeri ondalık tutar ve durum kodu. Adaptörler ikisini de aynı PaymentGateway arayüzüne çeviriyor.",
    run: async () => { goto(4); ACTS.gateway({ key: "yedekli" }); }, spot: ".gws",
  },
  {
    pattern: "Adapter", title: "Öde", cap: "GlobalCard reddetti → aynı arayüzle KolayPay'e geçildi",
    say: "Yedekli ödemeyle ödüyorum: GlobalCard limit yüzünden reddediyor, sistem aynı arayüz üzerinden KolayPay'e geçiyor ve ödeme alınıyor.",
    run: () => ACTS.pay(), spot: ".trace",
  },
  {
    pattern: "State", title: "Durum: ALINDI", cap: "<code>Order</code> her isteği o anki durum nesnesine devreder",
    say: "Son iki kalıp State ve Observer. Sipariş şimdi Alındı durumunda; her durum hangi işleme izin verdiğini kendisi biliyor.",
    run: async () => { goto(5); }, spot: ".machine",
  },
  {
    pattern: "Observer", pills: ["State", "Observer"], title: "Restoran onayladı → HAZIRLANIYOR",
    cap: "Order yalnızca <code>notify()</code> der: SMS gitti, kurye atandı",
    say: "Restoran onaylayınca sipariş Hazırlanıyor durumuna geçiyor. Sağ panelde Observer'ı görüyoruz: müşteriye SMS gitti, kurye otomatik atandı.",
    run: () => ACTS.do({ a: "accept" }), spot: "#side .feed",
  },
  {
    pattern: "State", title: "Yoldaki sipariş iptal edilemez", cap: "<code>OnTheWayState</code> iptal isteğini reddeder — if/else zinciri yok",
    say: "Teslimata çıkınca durum Yolda oluyor. Bu durumda iptal etmeye çalışırsam durum nesnesi isteği reddediyor.",
    run: () => ACTS.do({ a: "hand_over" }),
    then: () => ACTS.do({ a: "cancel" }), thenDelay: 900,
    spot: ".machine",
  },
  {
    pattern: "Observer", pills: ["State", "Observer"], title: "Teslim edildi",
    cap: "Restoran paneli kapandı · kurye boşa çıktı · analitik güncellendi",
    say: "Teslim edildiğinde restoran paneli siparişi kapatıyor, kurye boşa çıkıyor, analitik ciroyu güncelliyor. Order bu dinleyicilerin hiçbirini tanımıyor.",
    run: () => ACTS.do({ a: "complete" }), spot: "#side",
  },
  {
    pattern: "Özet", pills: ["Builder", "Adapter", "Decorator", "Strategy", "State", "Observer"],
    title: "Her kalıp gerçek bir sorunu çözüyor",
    cap: "Yeni ekstra, teslimat türü, ödeme servisi ya da dinleyici: mevcut koda dokunmadan eklenir",
    say: "Özetle her kalıp gerçek bir sorunu çözüyor. Yeni bir ekstra, teslimat türü, ödeme servisi ya da dinleyici eklemek mevcut kodu değiştirmeden mümkün. Dinlediğiniz için teşekkürler.",
    run: async () => {},
  },
];

const P = { on: false, i: -1, busy: false, notes: false };

function beatPills(beat) {
  return beat.pills || [beat.pattern];
}

function renderPresent() {
  const bar = $("#present");
  bar.hidden = !P.on;
  document.body.classList.toggle("presenting", P.on);
  $("#present-toggle").textContent = P.on ? "■ Sunumdan çık" : "▶ Sunum modu";
  if (!P.on) return;
  const beat = SCENE[P.i];
  bar.classList.toggle("notes", P.notes);
  const chip = $("#pp-pattern");
  chip.textContent = beat.pattern;
  chip.className = `present-pattern ${GROUP[beat.pattern] || ""}`;
  $("#pp-count").textContent = `${P.i + 1} / ${SCENE.length}`;
  $("#pp-title").textContent = beat.title;
  $("#pp-cap").innerHTML = beat.cap;
  $("#pp-say").textContent = beat.say;
  $("#pp-bar").style.width = `${((P.i + 1) / SCENE.length) * 100}%`;
  const last = P.i === SCENE.length - 1;
  const next = $("#pp-next");
  next.textContent = last ? "Bitir" : "İleri →";
  next.disabled = P.busy;
}

function applySpot() {
  document.querySelectorAll(".spot").forEach((el) => el.classList.remove("spot"));
  const beat = P.on ? SCENE[P.i] : null;
  if (!beat) return;
  const on = beatPills(beat);
  document.querySelectorAll(".pill").forEach((p) => p.classList.toggle("on", on.includes(p.dataset.pattern)));
  if (!beat.spot) return;
  const el = $(beat.spot);
  if (!el) return;
  el.classList.add("spot");
  const r = el.getBoundingClientRect();
  const barTop = window.innerHeight - $("#present").offsetHeight;
  if (r.top < 0 || r.bottom > barTop) el.scrollIntoView({ block: "center", behavior: "smooth" });
}

// thenAt: kayıt modunda ikinci hareketin adım başından itibaren kaçıncı ms'de olacağı (konuşmaya göre).
async function playBeat(i, thenAt = null) {
  const beat = SCENE[i];
  const start = performance.now();
  P.i = i;
  P.busy = true;
  $("#toast").classList.remove("show");
  renderPresent();
  const step = async (fn) => {
    try {
      await fn();
    } catch (e) {
      toast(e.message, "err", e.kind);
    }
    await wait(80);
    applySpot();
  };
  await step(beat.run);
  if (beat.then) {
    await wait(thenAt === null ? beat.thenDelay ?? 900 : Math.max(0, thenAt - (performance.now() - start)));
    await step(beat.then);
  }
  P.busy = false;
  renderPresent();
}

// Video kaydı için: adımlar, anlatım sesinin zamanlarına göre kendiliğinden oynar.
// plan = { beats: [{ at: ms, then?: ms }, ...] }  — at: videonun başından, then: adımın başından.
window.__play = (plan) => {
  const startWall = Date.now();
  const t0 = performance.now();
  P.on = true;
  document.body.classList.add("auto");
  (async () => {
    for (let i = 0; i < plan.beats.length; i++) {
      const b = plan.beats[i];
      await wait(Math.max(0, b.at - (performance.now() - t0)));
      await playBeat(i, b.then ?? null);
    }
    window.__done = true;
  })();
  return startWall;
};

async function startPresentation() {
  P.on = true;
  await playBeat(0);
}

function stopPresentation() {
  P.on = false;
  P.i = -1;
  renderPresent();
  document.querySelectorAll(".spot").forEach((el) => el.classList.remove("spot"));
  render();
}

async function resetDemo(silent = false) {
  await run(() => api("/api/reset", {}));
  Object.assign(S, { orderId: null, quotes: null, strategy: null, trace: null, extras: [], product: "pizza" });
  await updatePreview();
  goto(1);
  if (!silent) toast("Demo sıfırlandı", "ok");
}

document.addEventListener("keydown", (e) => {
  if (!P.on || ["INPUT", "SELECT", "TEXTAREA"].includes(e.target.tagName)) return;
  if (["ArrowRight", " ", "PageDown", "Enter"].includes(e.key)) {
    e.preventDefault();
    ACTS.presentNext();
  } else if (e.key === "n" || e.key === "N") {
    P.notes = !P.notes;
    renderPresent();
  } else if (e.key === "Escape") {
    stopPresentation();
  }
});

// ------------------------------------------------------------ olaylar
const ACTS = {
  presentToggle: () => (P.on ? stopPresentation() : startPresentation()),
  presentRestart: () => startPresentation(),
  presentNext: () => {
    document.activeElement?.blur();
    if (P.busy) return;
    if (P.i >= SCENE.length - 1) return stopPresentation();
    playBeat(P.i + 1);
  },
  goto: (d) => {
    const n = Number(d.n);
    goto(n);
    if (n === 3) loadQuotes();
  },
  reset: () => resetDemo(),
  pick: (d) => {
    S.product = d.key;
    S.extras = [];
    updatePreview();
  },
  async extra(d) {
    const next = [...S.extras, d.key];
    const res = await run(() => api("/api/preview", { product: S.product, extras: next }));
    if (res) {
      S.extras = next;
      S.preview = res;
      render();
    }
  },
  unextra: (d) => {
    S.extras.splice(Number(d.i), 1);
    updatePreview();
  },
  async add() {
    const ok = await run(() => api("/api/cart/add", { product: S.product, extras: S.extras, qty: S.qty }));
    if (ok !== undefined) {
      toast(`Sepete eklendi: ${S.qty}× ${S.preview.description}`, "ok");
      render();
    }
  },
  async remove(d) {
    await run(() => api("/api/cart/remove", { index: Number(d.i) }));
    render();
  },
  async clear() {
    await run(() => api("/api/cart/clear", {}));
    render();
  },
  async preset(d) {
    const ok = await run(() => api("/api/cart/preset", { key: d.key, headcount: S.headcount }));
    if (ok !== undefined) render();
  },
  otype: (d) => {
    S.form.type = d.v;
    if (d.v === "kurumsal") S.form.name = S.form.name === "Ayşe Yılmaz" ? "Mehmet Kaya" : S.form.name;
    render();
  },
  async build() {
    const id = await run(() => api("/api/orders", S.form));
    if (id !== undefined) {
      Object.assign(S, { orderId: id, quotes: null, strategy: null, trace: null });
      toast(`Sipariş #${id} oluşturuldu`, "ok");
      goto(3);
      await loadQuotes();
    }
  },
  strategy: (d) => {
    S.strategy = d.key;
    render();
  },
  gateway: (d) => {
    S.gateway = d.key;
    S.trace = null;
    render();
  },
  async pay() {
    const res = await run(() =>
      api(`/api/orders/${S.orderId}/checkout`, { strategy: S.strategy, gateway: S.gateway, slot: S.slot, surge: S.surge }),
    );
    if (res) {
      S.trace = res;
      render();
    }
  },
  selorder: (d) => {
    S.orderId = Number(d.id);
    S.trace = null;
    render();
  },
  async do(d) {
    const before = currentOrder()?.state;
    const ok = await run(() => api(`/api/orders/${S.orderId}/action`, { action: d.a, reason: S.cancelReason }));
    if (ok !== undefined) {
      const after = currentOrder()?.state;
      if (before !== after) toast(`${before} → ${after}`, "ok", "Durum değişti");
      render();
    }
  },
  neworder: () => {
    Object.assign(S, { orderId: null, quotes: null, strategy: null, trace: null });
    goto(1);
  },
};

document.addEventListener("click", (e) => {
  const el = e.target.closest("[data-act]");
  if (!el || el.disabled) return;
  const fn = ACTS[el.dataset.act];
  if (fn) fn(el.dataset, el);
});

function onField(e) {
  const el = e.target;
  const f = el.dataset.f;
  if (!f) return;
  const val = el.type === "checkbox" ? el.checked : el.value;
  if (f in S.form) {
    S.form[f] = val;
    if (f === "pickup_only") return render();
    updateBuilderCode();
  } else if (f === "qty" || f === "headcount") {
    S[f] = Math.max(1, parseInt(val, 10) || 1);
  } else if (f === "slot" || f === "surge") {
    S[f] = f === "slot" ? Number(val) : val;
    loadQuotes();
  } else {
    S[f] = val;
  }
}
document.addEventListener("input", (e) => {
  if (e.target.tagName !== "SELECT" && e.target.type !== "checkbox") onField(e);
});
document.addEventListener("change", (e) => {
  if (e.target.tagName === "SELECT" || e.target.type === "checkbox") onField(e);
});

// ------------------------------------------------------------ başlangıç
(async function init() {
  try {
    S.catalog = await api("/api/catalog");
    S.data = await api("/api/state");
  } catch (e) {
    document.body.innerHTML = `<p style="padding:2rem">Sunucuya bağlanılamadı: ${esc(e.message)}</p>`;
    return;
  }
  renderSide();
  await updatePreview();
})();
