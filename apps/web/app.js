// WHY: TR-VOX-05, TR-VOX-06, TR-PWA-01, G1, G2, G3, D1-D13 — Ale Voice Frontend Application with Live MediaRecorder & API Client
const API_BASE = ""; // Relative to origin when served by FastAPI

const $ = id => document.getElementById(id);
const q = s => document.querySelectorAll(s);

function toast(m) {
  const t = $('toast');
  if (!t) return;
  t.textContent = m;
  t.classList.add('on');
  clearTimeout(t._t);
  t._t = setTimeout(() => t.classList.remove('on'), 2500);
}

// Global state
const S = {
  sold: 18400, fuel: 5200, log: [], spots: [], bids: [], land: null, sos: false,
  lang: 0, role: 'fisher', user: { role: 'fisher', phone: '9876500021', name: 'Suresh Poojary' },
  saved: null, trip: null, voice: 1, notif: 1, map: 0, perm: {}, zone: 10, crew: 2, ret: 6, overdue: 0,
  noise: 0, net: 1, insp: 1, vq: [], busy: 0, vm: 'fisher', nx: 0,
  session_token: 'sess_' + Math.random().toString(36).substring(2, 10),
  activePending: null
};

const PR = {
  Sardine: [90, 110, '🐟'],
  Mackerel: [140, 170, '🐠'],
  Pomfret: [620, 760, '🐡'],
  Prawns: [380, 450, '🦐']
};
const FN = { Sardine: 'ಬೂತಾಯಿ', Mackerel: 'ಬಂಗುಡೆ', Pomfret: 'ಮಾಂಜಿ', Prawns: 'ಸಿಗಡಿ' };
const inr = n => (n || 0).toLocaleString('en-IN');
const stp = f => (PR[f] && PR[f][1] > 300) ? 20 : 5;
const mid = f => {
  const p = PR[f] || [100, 150];
  const s = stp(f);
  return Math.round((p[0] + p[1]) / 2 / s) * s;
};

// Roles & Tabs (Fix 5: includes Trip [8, '📋', 'Trip', 'ಪ್ರಯಾಣ'])
const ROLES = {
  fisher: ['🎣 Fisher', [
    [0, '🌅', 'Dawn', 'ಮುಂಜಾನೆ'],
    [8, '📋', 'Trip', 'ಪ್ರಯಾಣ'],
    [1, '🧭', 'Sea', 'ಸಮುದ್ರ'],
    [5, '⚓', 'Landing', 'ದಡ'],
    [2, '🐟', 'Prices', 'ಬೆಲೆ'],
    [4, '📒', 'Diary', 'ಲೆಕ್ಕ']
  ]],
  family: ['👩 Family', [[3, '👩', 'Status', 'ಸ್ಥಿತಿ'], [4, '📒', 'Diary', 'ಲೆಕ್ಕ']]],
  buyer: ['🛒 Buyer', [[6, '🛒', 'Incoming', 'ಬರುತ್ತಿದೆ'], [2, '🐟', 'Prices', 'ಬೆಲೆ']]],
  guard: ['🛟 Coast Guard', [[7, '🛟', 'Watch', 'ಕಣ್ಗಾವಲು']]]
};

function show(i) {
  q('.s').forEach(s => s.classList.remove('on'));
  const el = $('s' + i);
  if (el) el.classList.add('on');
  q('.tab').forEach(b => b.classList.toggle('on', +b.dataset.i === +i));
  if (+i === 0) fetchDawnWeather();
  if (+i === 2) fetchPrices();
  if (+i === 3) fetchFamilyStatus();
  if (+i === 4) fetchDiarySummary();
  if (+i === 6) rb();
  if (+i === 7) fetchGuardWatch();
  if (+i === 8) { tp(); tsub(); }
  if (+i === 9) pr();
  if (+i === 10) fetchTrackingHealth();
  fab();
}

function rt(k) {
  const T = ROLES[S.role][1];
  $('tabs').innerHTML = T.map(t => `<button class="tab" data-i="${t[0]}"><b>${t[1]}</b>${t[S.lang ? 3 : 2]}</button>`).join('');
  q('.tab').forEach(b => b.onclick = () => show(b.dataset.i));
  show(k == null ? T[0][0] : k);
}

$('roles').innerHTML = Object.keys(ROLES).map(k => `<button class="chip" data-r="${k}" style="padding:6px 2px;font-size:12px;flex:1;min-height:40px">${ROLES[k][0]}</button>`).join('');
q('#roles .chip').forEach(b => b.onclick = () => {
  S.role = b.dataset.r;
  q('#roles .chip').forEach(x => x.classList.toggle('on', x === b));
  rt();
  if (S.role === 'buyer') rb();
  if (S.role === 'guard') fetchGuardWatch();
  fab();
});

// Night / Glare toggle
let tn = 0;
$('th').onclick = () => {
  tn = (tn + 1) % 3;
  const c = $('ph').classList;
  c.toggle('night', tn === 1);
  c.toggle('glare', tn === 2);
  $('th').textContent = ['☀️ Day', '🌙 Night', '🔆 Glare'][tn];
};
$('xl').onclick = () => $('ph').classList.toggle('xl');

// Language toggle
$('lg').onclick = () => {
  S.lang ^= 1;
  const K = S.lang;
  $('lg').textContent = K ? 'ಕನ್ನಡ' : 'EN';
  $('greet').textContent = K ? 'ಶುಭೋದಯ, ಸುರೇಶ್' : 'Good morning, Suresh';
  $('spk').textContent = K ? '🔊 ಕನ್ನಡದಲ್ಲಿ ಕೇಳಿ' : '🔊 Hear in Kannada';
  $('home').textContent = K ? '🏠 ಮನೆಗೆ ಹೋಗಿ' : '🏠 Head home';
  $('pin').textContent = K ? '🎙 ಮೀನಿನ ಸ್ಥಳ' : '🎙 Fish spot';
  const curScreen = q('.s.on')[0];
  if (curScreen) rt(+curScreen.id.slice(1));
  tp();
  tsub();
};

// --- AUDIO / TTS PLAYBACK ---
function playKannadaVoice(text, audioUrl) {
  if (audioUrl) {
    const a = new Audio(audioUrl);
    a.play().catch(() => playSpeechFallback(text));
  } else {
    playSpeechFallback(text);
  }
}

function playSpeechFallback(text) {
  try {
    const u = new SpeechSynthesisUtterance(text);
    u.lang = 'kn-IN';
    speechSynthesis.cancel();
    speechSynthesis.speak(u);
  } catch (e) {}
}

// Weather simulation state
const W = [
  { c: '#1fa35b', l: 'Go', k: 'ಹೋಗಬಹುದು', w: '12', v: '0.8 m', g: -60 },
  { c: '#f0a020', l: 'Be careful', k: 'ಜಾಗರೂಕರಾಗಿರಿ', w: '28', v: '1.8 m', g: 0 },
  { c: '#d6372f', l: 'Don’t go', k: 'ಹೋಗಬೇಡಿ', w: '45', v: '3.5 m', g: 60 }
];
let wi = 0;
async function applyWeather(idx) {
  wi = idx % 3;
  const d = W[wi];
  $('hero').style.background = d.c;
  $('lbl').textContent = d.l;
  $('kn').textContent = d.k;
  $('needle').style.transform = `rotate(${d.g}deg)`;
  $('w1').textContent = d.w;
  $('w2').textContent = d.v;
  window._lastWeather = {
    verdict: ['go', 'caution', 'no_go'][wi],
    label_en: d.l,
    label_kn: d.k,
    color: d.c,
    wind_kmh: +d.w,
    wave_m: +d.v.replace(' m', ''),
    kn_summary: d.k + '. ಗಾಳಿ ' + d.w + ' ಕಿಲೋಮೀಟರ್, ಅಲೆ ' + d.v + '.',
    en_summary: d.l + '. Wind ' + d.w + ' km/h, waves ' + d.v + '.'
  };
  if (wi === 2) {
    fAlert('🌩 Storm warning: Suresh is advised to stay ashore', 'amber');
  }
  try {
    await fetch(`${API_BASE}/api/v1/weather/simulate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ verdict: ['go', 'caution', 'no_go'][wi] })
    });
  } catch (e) {}
}

// --- REST API CALLS ---
async function fetchDawnWeather() {
  try {
    const res = await fetch(`${API_BASE}/api/v1/weather/dawn?harbour_code=MALPE`);
    if (!res.ok) return;
    const d = await res.json();
    $('hero').style.background = d.color;
    $('lbl').textContent = d.label_en;
    $('kn').textContent = d.label_kn;
    $('needle').style.transform = `rotate(${d.gauge_angle}deg)`;
    $('w1').textContent = d.wind_kmh;
    $('w2').textContent = d.wave_m + ' m';
    window._lastWeather = d;
  } catch (e) {}
}

// Wire Dawn buttons: #spk, #sim, #dv
$('spk').onclick = () => {
  const d = window._lastWeather || W[wi];
  const summary = d.kn_summary || (d.k + '. ಗಾಳಿ ' + d.w + ' ಕಿಲೋಮೀಟರ್');
  playKannadaVoice(summary);
  toast('🔊 ' + (S.lang ? (d.label_kn || d.k) : (d.label_en || d.l)));
};

$('sim').onclick = () => {
  applyWeather((wi + 1) % 3);
  toast('Weather: ' + W[wi].l);
};

if (!$('dv')) {
  $('spk').insertAdjacentHTML('beforebegin', '<button class="btn alt" id="dv" style="margin-bottom:10px">🎙 Ask Ale in Kannada<br><small style="font-weight:400">ಇವತ್ತು ಹೋಗಬಹುದಾ?</small></button>');
}
$('dv').onclick = () => ovs('fisher');

// Wire Sea buttons: #pin, #home, #sos
$('pin').onclick = async () => {
  toast('🎙 Recording spot… speak now');
  const x = 120 + Math.random() * 100;
  const y = 60 + Math.random() * 80;
  S.spots.push({ x, y, note: 'Good catch' });
  $('pins').innerHTML += `<text x="${x}" y="${y}" font-size="18">📍</text>`;
  $('spots').innerHTML = S.spots.map((s, i) => `📍 Spot ${i + 1} · saved privately for crew`).join('<br>');
  try {
    await fetch(`${API_BASE}/api/v1/trips/spots`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phone: S.user ? S.user.phone : '9876500021', lat: 13.35, lon: 74.69, note: 'Good catch' })
    });
  } catch (e) {}
  toast(`📍 Spot ${S.spots.length} saved`);
};

function setFam(i) {
  const steps = q('.step');
  if (steps[i]) steps[i].click();
}
$('home').onclick = async () => {
  setFam(1);
  toast('🏠 Arrow guiding you home · family told');
  try {
    await fetch(`${API_BASE}/api/v1/trips/status`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phone: S.user ? S.user.phone : '9876500021', status: 'returning' })
    });
  } catch (e) {}
};

function fAlert(m, c) {
  const a = $('fal');
  if (!a) return;
  a.textContent = m;
  a.className = 'alertbar on ' + (c || '');
}

// 2-second hold SOS
let tm = null, p = 0;
const ring = $('ring'), sos = $('sos');
function go() {
  p = 0;
  tm = setInterval(() => {
    p += 2;
    ring.style.strokeDashoffset = 496 - 496 * p / 100;
    if (p >= 100) {
      clearInterval(tm);
      sosTrigger();
      ring.style.strokeDashoffset = 496;
    }
  }, 40);
}
function stop() {
  clearInterval(tm);
  ring.style.strokeDashoffset = 496;
}
sos.addEventListener('pointerdown', go);
['pointerup', 'pointerleave', 'pointercancel'].forEach(e => sos.addEventListener(e, stop));

async function sosTrigger() {
  S.sos = true;
  fAlert('🚨 SOS from Suresh. Coast guard and nearby boats alerted.');
  toast('🚨 SOS sent to coast guard, boats and family');
  fetchGuardWatch();
  try {
    const phone = S.user ? S.user.phone : '9876500021';
    await fetch(`${API_BASE}/api/v1/trips/sos`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phone, client_op_id: 'sos_tap_' + Date.now() })
    });
  } catch (e) {}
}

// --- PRICES & OFFER CHECKER ---
async function fetchPrices() {
  try {
    const res = await fetch(`${API_BASE}/api/v1/market/prices`);
    if (!res.ok) return;
    const d = await res.json();
    if (d.prices) {
      $('price-cards').innerHTML = d.prices.map(p => `
        <div class="card fish">
          <div class="e">${p.emoji}</div>
          <div><b>${p.species}</b><br><span class="${p.trend_dir === 'up' ? 'up' : 'dn'}">${p.trend} vs yesterday</span></div>
          <div class="p">${p.display}</div>
        </div>
      `).join('');
    }
  } catch (e) {}
}

let fo = 'Sardine', oq = 100;
function chips(id, cb) {
  const el = $(id);
  if (!el) return;
  el.innerHTML = Object.keys(PR).map((k, i) => `<button class="chip${i ? '' : ' on'}" data-f="${k}">${PR[k][2]} ${k}</button>`).join('');
  el.onclick = e => {
    const b = e.target.closest('.chip');
    if (!b) return;
    el.querySelectorAll('.chip').forEach(x => x.classList.toggle('on', x === b));
    cb(b.dataset.f);
  };
}

async function ck() {
  $('ov').textContent = oq;
  const v = $('vd');
  try {
    const res = await fetch(`${API_BASE}/api/v1/market/offer-check`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ species: fo, offer_per_kg: oq })
    });
    if (res.ok) {
      const d = await res.json();
      v.textContent = d.advice_en || (d.verdict + ` (₹${d.range_min}–${d.range_max})`);
      v.style.background = d.color || (d.verdict === 'great' ? '#1fa35b' : d.verdict === 'low' ? '#d6372f' : '#0a4d7a');
      return;
    }
  } catch (e) {}
  const [lo, hi] = PR[fo] || [90, 110];
  const a = oq < lo ? ['Too low. Ask for more (₹' + lo + '–' + hi + ')', '#d6372f'] : oq > hi ? ['Great offer. Take it! (₹' + lo + '–' + hi + ')', '#1fa35b'] : ['Fair price (₹' + lo + '–' + hi + ')', '#0a4d7a'];
  v.textContent = a[0];
  v.style.background = a[1];
}

chips('oc', f => { fo = f; oq = mid(f); ck(); });
$('omn').onclick = () => { oq -= stp(fo); ck(); };
$('opl').onclick = () => { oq += stp(fo); ck(); };
ck();

// --- DIARY SCREEN ---
async function fetchDiarySummary() {
  try {
    const phone = S.user ? S.user.phone : '9876500021';
    const res = await fetch(`${API_BASE}/api/v1/diary/summary?phone=${phone}`);
    if (!res.ok) return;
    const d = await res.json();
    $('dsold').textContent = d.sold_display;
    $('dfuel').textContent = d.fuel_display;
    $('dkept').textContent = d.kept_display;
    if (d.recent_logs && d.recent_logs.length) {
      $('dlog').innerHTML = '<b>Recent entries</b>' + d.recent_logs.map(l => `<div class="sub" style="margin:4px 0 0">${l}</div>`).join('');
    }
  } catch (e) {
    $('dsold').textContent = '₹' + inr(S.sold);
    $('dfuel').textContent = '₹' + inr(S.fuel);
    $('dkept').textContent = '₹' + inr(S.sold - S.fuel);
    $('dlog').innerHTML = '<b>Recent entries</b>' + (S.log.length ? S.log.slice(0, 4).map(l => `<div class="sub" style="margin:4px 0 0">${l}</div>`).join('') : '<div class="sub" style="margin:4px 0 0">Nothing new yet.</div>');
  }
}

$('add1').onclick = async () => {
  S.sold += 1600;
  S.log.unshift('＋ ₹1,600 · 40 kg sardine');
  try {
    await fetch(`${API_BASE}/api/v1/diary/entries`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        phone: S.user ? S.user.phone : '9876500021',
        entry_type: 'sale',
        amount: 1600,
        description: '40 kg sardine',
        species: 'Sardine',
        quantity_kg: 40,
        client_op_id: 'sale_' + Date.now()
      })
    });
  } catch (e) {}
  fetchDiarySummary();
  toast('＋ Catch added');
};

$('add2').onclick = async () => {
  S.fuel += 1200;
  S.log.unshift('⛽ ₹1,200 · fuel');
  try {
    await fetch(`${API_BASE}/api/v1/diary/entries`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        phone: S.user ? S.user.phone : '9876500021',
        entry_type: 'expense',
        amount: 1200,
        description: 'Fuel',
        client_op_id: 'fuel_' + Date.now()
      })
    });
  } catch (e) {}
  fetchDiarySummary();
  toast('⛽ Fuel added');
};

// --- LANDING & BUYER INCOMING ---
let lf = 'Sardine', kq = 40, bp = 0;
chips('lc', f => lf = f);
$('kmn').onclick = () => { kq = Math.max(5, kq - 5); $('kg').textContent = kq; };
$('kpl').onclick = () => { kq += 5; $('kg').textContent = kq; };

function bidsR() {
  $('bids').innerHTML = S.bids.map((b, i) => `
    <div class="card bid">
      <span style="font-size:28px">${b.e || '🧑‍💼'}</span>
      <div><b>${b.n}</b><br>₹${b.p}/kg · ₹${inr(b.p * b.kg)}</div>
      ${b.done ? '<span class="up">✔ Sold</span>' : `<button data-i="${i}" data-id="${b.id || ''}">Accept</button>`}
    </div>
  `).join('');
}

$('bids').onclick = async e => {
  const btn = e.target.closest('button');
  if (!btn) return;
  const i = btn.dataset.i;
  const bidId = btn.dataset.id;
  if (i == null) return;
  const b = S.bids[i];
  b.done = 1;
  if (bidId) {
    try {
      await fetch(`${API_BASE}/api/v1/market/bids/${bidId}/accept`, { method: 'POST' });
    } catch (err) {}
  }
  S.sold += b.p * b.kg;
  S.log.unshift('＋ ₹' + inr(b.p * b.kg) + ' · ' + b.kg + ' kg ' + b.f + ' to ' + b.n);
  bidsR();
  setFam(2);
  fetchDiarySummary();
  toast('✔ Sold to ' + b.n);
};

$('lnotify').onclick = async () => {
  S.land = { f: lf, kg: kq };
  S.bids = [];
  bp = 0;
  bidsR();
  rb();
  setFam(1);
  toast('📣 12 buyers notified · ETA 40 min');
  let backendBids = null;
  try {
    const res = await fetch(`${API_BASE}/api/v1/market/landings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        phone: S.user ? S.user.phone : '9876500021',
        species: lf,
        quantity_kg: kq,
        eta_min: 40
      })
    });
    if (res.ok) {
      const data = await res.json();
      backendBids = data.bids;
    }
  } catch (e) {}

  if (backendBids && backendBids.length) {
    backendBids.forEach((b, j) => {
      setTimeout(() => {
        S.bids.push({ id: b.id, n: b.buyer_name, e: '🧑‍💼', p: b.bid_price_per_kg, f: lf, kg: kq });
        bidsR();
      }, 1200 * (j + 1));
    });
  } else {
    const [lo, hi] = PR[lf];
    [['Rafiq, Harbour Agent', '🧑‍💼', lo], ['Fish Mart Udupi', '🏪', mid(lf)], ['Hotel Mitra', '🏨', hi]].forEach((x, j) => {
      setTimeout(() => {
        S.bids.push({ id: 'bid_' + Date.now() + '_' + j, n: x[0], e: x[1], p: x[2], f: lf, kg: kq });
        bidsR();
      }, 1200 * (j + 1));
    });
  }
};

function rb() {
  const l = S.land;
  if (l && !bp) bp = mid(l.f);
  const bi = $('bi');
  if (!bi) return;
  bi.innerHTML = l ? `
    <div class="card">
      <div class="fish">
        <div class="e">⛵</div>
        <div><b>Ale-Malpe-07</b><br><span class="sub">${PR[l.f][2]} ${l.f} · ${l.kg} kg · ETA 40 min</span></div>
      </div>
      <div class="stepper" style="margin-top:12px">
        <button id="bm">−</button><b>₹<span id="bq">${bp}</span></b>/kg<button id="bpl">+</button>
      </div>
      <button class="btn" id="bs">Send bid</button>
    </div>` : '<div class="card sub">No boats announced yet. Switch to Fisher, open Landing and tap Notify.</div>';
  if (l) {
    const s = stp(l.f);
    $('bm').onclick = () => { bp -= s; $('bq').textContent = bp; };
    $('bpl').onclick = () => { bp += s; $('bq').textContent = bp; };
    $('bs').onclick = async () => {
      S.bids.push({ id: 'bid_' + Date.now(), n: 'You (Buyer)', e: '🛒', p: bp, f: l.f, kg: l.kg });
      bidsR();
      try {
        await fetch(`${API_BASE}/api/v1/market/landings/active/bids`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ buyer_name: 'You (Buyer)', bid_per_kg: bp, bid_price_per_kg: bp })
        });
      } catch (e) {}
      toast('Bid sent: ₹' + bp + '/kg');
    };
  }
}

// --- COAST GUARD WATCH & BROADCAST ---
async function fetchGuardWatch() {
  try {
    const res = await fetch(`${API_BASE}/api/v1/guard/watch`);
    if (!res.ok) return;
    const d = await res.json();
    const gl = $('gl');
    if ((d.has_active_emergency && d.active_incident) || S.sos) {
      gl.innerHTML = `
        <div class="card" style="border:3px solid #d6372f">
          <b style="color:#d6372f">🚨 SOS · Boat Ale-Malpe-07</b>
          <div class="sub" style="margin:4px 0 8px">Suresh · 4 km offshore · 3 boats nearby</div>
          <button class="btn" id="disp">Dispatch rescue</button>
        </div>`;
      const btn = $('disp');
      if (btn) btn.onclick = async () => {
        S.sos = false;
        fAlert('✅ Rescue dispatched. Stay calm.', 'ok');
        try {
          await fetch(`${API_BASE}/api/v1/guard/dispatch`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ incident_id: 'active' })
          });
        } catch (e) {}
        toast('🛟 Rescue dispatched');
        fetchGuardWatch();
      };
      $('gdot').setAttribute('fill', '#d6372f');
    } else {
      gl.innerHTML = '<div class="card"><b>✅ No active incidents</b><div class="sub" style="margin:4px 0 0">12 boats tracked</div></div>';
      $('gdot').setAttribute('fill', '#3ddc84');
    }
  } catch (e) {}
}

$('gbc').onclick = async () => {
  applyWeather(2);
  fAlert('🌩 Storm warning from Coast Guard. Stay ashore.', 'amber');
  try {
    await fetch(`${API_BASE}/api/v1/guard/broadcast`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message_kn: 'ಮೀನುಗಾರರೇ, ಎಚ್ಚರ! ಇಂದು ಗಾಳಿ ಬಲವಾಗಿದೆ, ಅಲೆ ಮೂರೂವರೆ ಮೀಟರ್. ದಯವಿಟ್ಟು ಸಮುದ್ರಕ್ಕೆ ಹೋಗಬೇಡಿ.',
        alert_level: 'storm'
      })
    });
  } catch (e) {}
  toast('📡 Warning broadcast to all boats');
};

if (!$('vbp')) {
  $('gbc').insertAdjacentHTML('afterend', `
    <div class="card" style="margin-top:12px">
      <b>🔊 Voice broadcast (auto-generated)</b>
      <div class="sub" style="margin:6px 0">ಮೀನುಗಾರರೇ, ಎಚ್ಚರ! ಇಂದು ಗಾಳಿ ಬಲವಾಗಿದೆ, ಅಲೆ ಮೂರೂವರೆ ಮೀಟರ್. ದಯವಿಟ್ಟು ಸಮುದ್ರಕ್ಕೆ ಹೋಗಬೇಡಿ.</div>
      <div class="sub" style="margin:0">Template slots: wind, waves, advice · Kannada first, more languages next</div>
      <button class="btn ghost" id="vbp" style="margin-top:8px">▶ Play (Timbre voice)</button>
    </div>`);
  $('vbp').onclick = () => playKannadaVoice('ಮೀನುಗಾರರೇ, ಎಚ್ಚರ! ಇಂದು ಗಾಳಿ ಬಲವಾಗಿದೆ, ಅಲೆ ಮೂರೂವರೆ ಮೀಟರ್. ದಯವಿಟ್ಟು ಸಮುದ್ರಕ್ಕೆ ಹೋಗಬೇಡಿ.');
}

// --- FAMILY VIEW ---
async function fetchFamilyStatus() {
  try {
    const res = await fetch(`${API_BASE}/api/v1/family/status`);
    if (!res.ok) return;
    const d = await res.json();
    $('fe').textContent = d.emoji;
    $('ft').textContent = d.title;
    $('fs').textContent = d.subtitle;
    q('.step').forEach((x, j) => x.classList.toggle('on', j === d.step_index));
    const al = $('fal');
    if (d.alert_banner) {
      al.textContent = d.alert_banner;
      al.className = 'alertbar on ' + (d.alert_type || '');
    } else {
      al.className = 'alertbar';
    }
  } catch (e) {}
}
q('.step').forEach(s => s.onclick = () => {
  q('.step').forEach(x => x.classList.toggle('on', x === s));
  const i = +s.dataset.i;
  const states = [
    { e: '⛵', t: 'Boat is out at sea', s: 'Safe zone · last seen 2 min ago' },
    { e: '🧭', t: 'Boat is returning', s: 'Heading towards Malpe Harbour · ETA 40 min' },
    { e: '⚓', t: 'Boat has landed', s: 'Safe at Malpe Harbour · trip complete' }
  ];
  $('fe').textContent = states[i].e;
  $('ft').textContent = states[i].t;
  $('fs').textContent = states[i].s;
});
$('call').onclick = () => toast('📞 Calling Suresh: +91 9876500021');
$('fsim').onclick = () => {
  fAlert('⚠ Boat has left the safe zone. Call Suresh or alert the coast guard.', 'amber');
  toast('Alert shown to family');
};

// --- TRIP CHECK-IN SCREEN (#s8) ---
const CK = [
  ['🦺', 'Life jackets for everyone', 'ಎಲ್ಲರಿಗೂ ಲೈಫ್ ಜಾಕೆಟ್'],
  ['⛽', 'Fuel for the trip', 'ಪ್ರಯಾಣಕ್ಕೆ ಇಂಧನ'],
  ['🧊', 'Ice and water', 'ಐಸ್ ಮತ್ತು ನೀರು'],
  ['🔋', 'Phone charged', 'ಫೋನ್ ಚಾರ್ಜ್ ಆಗಿದೆ']
];
let tk = [0, 0, 0, 0];
const ET = h => {
  const m = 355 + h * 60, H = Math.floor(m / 60) % 24;
  return (H % 12 || 12) + ':' + String(m % 60).padStart(2, '0') + ' ' + (H < 12 ? 'AM' : 'PM');
};

function tp() {
  const d = window._lastWeather || W[wi];
  const X = [
    [S.map, '🗺', S.lang ? 'ನಕ್ಷೆ ಸಿದ್ಧ' : 'Offline map ready', 'm'],
    [1, '📡', S.lang ? 'GPS ಸಿದ್ಧ' : 'GPS ready', 'g'],
    [wi < 2, '🌦', (S.lang ? 'ಹವಾಮಾನ: ' : 'Weather: ') + (S.lang ? (d.label_kn || d.k) : (d.label_en || d.l)), 'w']
  ];
  $('tchk').innerHTML = CK.map((c, i) => `
    <div class="chk${tk[i] ? ' on' : ''}" data-t="${i}">
      <span>${c[0]} ${S.lang ? c[2] : c[1]}</span>
      <i>${tk[i] ? '✔' : ''}</i>
    </div>
  `).join('') + X.map(a => `
    <div class="chk${a[0] ? ' on' : ''}" data-t="${a[3]}">
      <span>${a[1]} ${a[2]}</span>
      <i>${a[0] ? '✔' : '!'}</i>
    </div>
  `).join('');
}

function tsub() {
  const T = S.trip;
  $('tgo').textContent = T ? '🏁 ' + (S.lang ? 'ಪ್ರಯಾಣ ಮುಗಿಸಿ' : 'End trip (landed)') : '⛵ ' + (S.lang ? 'ಪ್ರಯಾಣ ಪ್ರಾರಂಭಿಸಿ' : 'Start trip');
  $('tsub').textContent = T ? (S.lang ? 'ಪ್ರಯಾಣ ನಡೆಯುತ್ತಿದೆ · ' + T.eta + ' ಒಳಗೆ ವಾಪಸ್' : 'Trip active · ' + S.crew + ' crew · back by ' + T.eta) : (S.lang ? 'ಹೊರಡುವ ಮುನ್ನ ಪರಿಶೀಲಿಸಿ' : 'Check before you sail');
  $('tod').style.display = T ? 'block' : 'none';
  updateFgNotif();
}

$('tchk').onclick = e => {
  const r = e.target.closest('.chk');
  if (!r) return;
  const i = r.dataset.t;
  if (i === 'm') {
    if (!S.map) {
      toast('⬇ Downloading 48 MB…');
      setTimeout(() => { S.map = 1; sw(); tp(); toast('✔ Offline map ready'); }, 1200);
    }
  } else if (i === 'g' || i === 'w') {
    toast(i === 'g' ? '📡 GPS works offline' : '🌦 Checked automatically from Dawn');
  } else {
    tk[i] ^= 1;
    tp();
  }
};

$('tsos').onclick = () => toast('✔ SOS test OK. Nobody was alerted');
$('cmn').onclick = () => { S.crew = Math.max(1, S.crew - 1); $('cq').textContent = S.crew; };
$('cpl').onclick = () => { S.crew = Math.min(12, S.crew + 1); $('cq').textContent = S.crew; };
$('rmn').onclick = () => { S.ret = Math.max(1, S.ret - 1); $('rq').textContent = S.ret; };
$('rpl').onclick = () => { S.ret = Math.min(24, S.ret + 1); $('rq').textContent = S.ret; };

let force = 0;
$('tgo').onclick = async () => {
  if (S.trip) {
    try {
      await fetch(`${API_BASE}/api/v1/trips/end`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone: S.user ? S.user.phone : '9876500021' })
      });
    } catch (e) {}
    S.trip = null;
    S.overdue = 0;
    setFam(2);
    fAlert('✅ Suresh is home safe', 'ok');
    tk = [0, 0, 0, 0];
    tsub();
    tp();
    fetchGuardWatch();
    return toast('🏁 ' + (S.lang ? 'ಪ್ರಯಾಣ ಮುಗಿಯಿತು' : 'Trip ended. Welcome home!'));
  }
  if (!tk.every(Boolean) || !S.map) return toast('⚠ ' + (S.lang ? 'ಪಟ್ಟಿ ಪೂರ್ಣಗೊಳಿಸಿ' : 'Please finish the checklist'));
  if (wi === 2 && !force) { force = 1; return toast('🌩 Storm warning! Tap again only if you must sail'); }
  force = 0;
  const etaText = ET(S.ret);
  S.trip = { eta: etaText };
  try {
    await fetch(`${API_BASE}/api/v1/trips/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        phone: S.user ? S.user.phone : '9876500021',
        crew_count: S.crew,
        return_in_hours: S.ret,
        checklist: ['life_jackets', 'fuel', 'ice_water', 'phone_charged']
      })
    });
  } catch (e) {}
  setFam(0);
  $('fs').textContent = 'Left 5:55 AM · back by ' + S.trip.eta + ' · ' + S.crew + ' crew';
  $('fal').className = 'alertbar';
  tsub();
  toast('⛵ ' + (S.lang ? 'ಪ್ರಯಾಣ ಪ್ರಾರಂಭ. ಕುಟುಂಬಕ್ಕೆ ತಿಳಿಸಲಾಗಿದೆ' : 'Trip started. Family informed'));
};

$('tod').onclick = async () => {
  S.overdue = 1;
  fAlert('⏰ Overdue: back-by time has passed. Tried calling Suresh.', 'amber');
  try {
    await fetch(`${API_BASE}/api/v1/trips/status`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phone: S.user ? S.user.phone : '9876500021', status: 'overdue' })
    });
  } catch (e) {}
  fetchGuardWatch();
  toast('⏰ Family and coast guard notified');
};

// --- PROFILE SCREEN (#s9) ---
function sw() {
  [['tvo', 'voice'], ['tal', 'notif'], ['tmp', 'map']].forEach(([id, k]) => {
    const el = $(id);
    if (el) {
      el.classList.toggle('on', !!S[k]);
      el.lastElementChild.textContent = S[k] ? '✔' : '';
    }
  });
}
function pr() {
  const u = S.user;
  if (!u) return;
  const RL_AVATAR = { fisher: '🎣', family: '👩', buyer: '🛒', guard: '🛟' };
  $('pav').textContent = RL_AVATAR[u.role] || '👤';
  $('pnm').textContent = u.name;
  $('pdt').textContent = u.role + ' · +91 ' + u.phone + (u.a ? ' · ' + u.a : '');
  $('pec').textContent = '👩 ' + (u.role === 'fisher' ? 'Family +91 ' + (u.c || '9876500012') : 'Family') + ' · 🛟 Coast Guard Malpe';
  q('.fo').forEach(e => e.style.display = u.role === 'fisher' ? '' : 'none');
  sw();
}
$('tvo').onclick = () => { S.voice ^= 1; sw(); if (S.voice) playKannadaVoice('ಧ್ವನಿ ಮಾರ್ಗದರ್ಶನ ಆನ್'); };
$('tal').onclick = () => { S.notif ^= 1; sw(); toast(S.notif ? '🔔 Alerts on' : '🔕 Alerts off'); };
$('tmp').onclick = () => {
  if (S.map) {
    S.map = 0; sw(); tp(); toast('Offline map removed');
  } else {
    toast('⬇ Downloading 48 MB…');
    setTimeout(() => { S.map = 1; sw(); tp(); toast('✔ Offline map ready'); }, 1200);
  }
};
function zn(d) {
  S.zone = Math.min(15, Math.max(5, S.zone + d));
  $('zq').textContent = S.zone;
  $('sz').setAttribute('r', S.zone * 9.2);
}
$('zmn').onclick = () => zn(-1);
$('zpl').onclick = () => zn(1);
$('pf').onclick = () => { if (off()) show(9); };
$('ptour').onclick = () => { rp = 1; au = 7; tr = 0; AU.classList.remove('off'); A(); };
$('pdemo').onclick = () => {
  const r = $('roles');
  r.style.display = r.style.display === 'none' ? 'flex' : 'none';
};
let lgo = 0;
$('plog').onclick = () => {
  if (!lgo) {
    lgo = 1;
    $('plog').textContent = 'Tap again to log out';
    setTimeout(() => { lgo = 0; $('plog').textContent = 'Log out'; }, 3000);
    return;
  }
  lgo = 0;
  $('plog').textContent = 'Log out';
  mob = S.saved ? S.saved.phone : '';
  otp = '';
  au = 3;
  AU.classList.remove('off');
  A();
  toast('👋 Logged out');
};

// --- AUTH / ONBOARDING / OTP MODAL ---
const AU = $('auth'), L = (a, b) => S.lang ? b : a, off = () => AU.classList.contains('off');
let au = 0, mob = '9876500021', otp = '', tr = 0, fv = {}, rp = 0;
const RL = {
  fisher: ['🎣', 'Fisher', 'ಮೀನುಗಾರ', 'Weather, safety and fair prices', 'ಹವಾಮಾನ, ಸುರಕ್ಷತೆ, ನ್ಯಾಯಯುತ ಬೆಲೆ'],
  family: ['👩', 'Family', 'ಕುಟುಂಬ', 'Know your boat is safe', 'ನಿಮ್ಮ ದೋಣಿ ಸುರಕ್ಷಿತವೇ ತಿಳಿಯಿರಿ'],
  buyer: ['🛒', 'Buyer', 'ಖರೀದಿದಾರ', 'See catches and send bids', 'ಮೀನು ನೋಡಿ, ಬಿಡ್ ಕಳುಹಿಸಿ'],
  guard: ['🛟', 'Coast Guard', 'ಕರಾವಳಿ ಕಾವಲು ಪಡೆ', 'Watch the sea and warn boats', 'ಸಮುದ್ರ ಗಮನಿಸಿ, ದೋಣಿಗಳಿಗೆ ಎಚ್ಚರಿಕೆ ನೀಡಿ']
};
const rn = k => RL[k][S.lang ? 2 : 1], HB = ['Malpe', 'Mangaluru', 'Gangolli', 'Honnavar'];
const PF = {
  fisher: [['Your name', 'Suresh Poojary'], ['Boat name or number', 'Ale-Malpe-07'], ['Harbour', HB], ['Family phone', '9876500012']],
  family: [['Your name', 'Lakshmi'], ['Fisher’s phone', '9876500021'], ['Relation', ['Wife', 'Son', 'Daughter', 'Other']]],
  buyer: [['Your name', 'Rafiq'], ['Business', 'Fish Mart Udupi'], ['Harbour', HB]],
  guard: [['Officer name', 'Insp. Naik'], ['Station', 'Malpe Coast Guard'], ['Officer ID', 'CG-0412']]
};
const SM = {
  fisher: ['Suresh Poojary', 'Ale-Malpe-07', 'Malpe', '9876500012'],
  family: ['Lakshmi', '9876500021', 'Wife'],
  buyer: ['Rafiq', 'Fish Mart Udupi', 'Malpe'],
  guard: ['Insp. Naik', 'Malpe Coast Guard', 'CG-0412']
};
const TR = {
  fisher: [
    ['🌅', 'Check the sea', 'Green, amber or red tells you if it is safe to sail.', 'ಸಮುದ್ರ ಪರಿಶೀಲಿಸಿ'],
    ['📋', 'Check before you sail', 'Tick the safety list and tell your family when you will return.', 'ಹೊರಡುವ ಮುನ್ನ ಪರಿಶೀಲಿಸಿ'],
    ['🆘', 'SOS in one hold', 'Hold the red button for 2 seconds. It works offline.', 'ಒಂದೇ ಒತ್ತಿನಲ್ಲಿ SOS'],
    ['🐟', 'Sell at a fair price', 'Tell buyers what you caught and compare bids.', 'ನ್ಯಾಯಯುತ ಬೆಲೆಗೆ ಮಾರಿ']
  ],
  family: [
    ['⛵', 'See your boat', 'Out, Returning or Landed, always on one screen.', 'ನಿಮ್ಮ ದೋಣಿ ನೋಡಿ'],
    ['⚠️', 'Get alerts early', 'Storm, off route, overdue or SOS.', 'ಮುಂಚಿತವಾಗಿ ಎಚ್ಚರಿಕೆ'],
    ['📞', 'Call in one tap', 'Reach your fisher or the coast guard fast.', 'ಒಂದೇ ಒತ್ತಿನಲ್ಲಿ ಕರೆ']
  ],
  buyer: [
    ['🛒', 'See incoming boats', 'Know the fish, quantity and arrival time.', 'ಬರುವ ದೋಣಿಗಳು'],
    ['💰', 'Send your bid', 'Fair price guidance helps both sides.', 'ನಿಮ್ಮ ಬಿಡ್ ಕಳುಹಿಸಿ']
  ],
  guard: [
    ['🗺', 'Watch the sector', 'All boats on one map.', 'ಪ್ರದೇಶ ಗಮನಿಸಿ'],
    ['🚨', 'Act on SOS', 'See incidents and dispatch rescue.', 'SOS ಗೆ ಸ್ಪಂದಿಸಿ'],
    ['📡', 'Warn everyone', 'Broadcast storm warnings to all boats.', 'ಎಲ್ಲರಿಗೂ ಎಚ್ಚರಿಕೆ']
  ]
};
const KP = '<div class="kp">' + [1, 2, 3, 4, 5, 6, 7, 8, 9, '⌫', 0, '✔'].map(k => `<button class="key" data-k="${k}">${k}</button>`).join('') + '</div>';
const dots = (n, t) => '<div class="dots">' + Array.from({ length: t }, (x, i) => `<i class="${i < n ? 'on' : ''}"></i>`).join('') + '</div>';

function A() {
  let h = '';
  if (au === 0) h = `<div style="margin:auto;text-align:center"><div style="font-size:64px">🌊</div><div class="logo" style="font-size:46px">ale<span>~</span></div><p class="sub">The sea doesn’t change. How we prepare for it can.</p><button class="btn" data-a="next" style="margin-top:20px">Get started · ಪ್ರಾರಂಭಿಸಿ</button></div>`;
  else if (au === 1) h = `<h2>Choose your language<br>ಭಾಷೆ ಆಯ್ಕೆಮಾಡಿ</h2><br><div class="card rc" data-l="0"><span style="font-size:28px">A</span>English</div><div class="card rc" data-l="1"><span style="font-size:28px">ಕ</span>ಕನ್ನಡ</div><div class="card rc" style="opacity:.5"><span style="font-size:28px">ತು</span><div>ತುಳು<small>Coming soon</small></div></div>`;
  else if (au === 2) h = `<h2>${L('Who are you?', 'ನೀವು ಯಾರು?')}</h2><br>` + Object.keys(RL).map(k => `<div class="card rc" data-r="${k}"><span style="font-size:34px">${RL[k][0]}</span><div>${rn(k)}<small>${RL[k][S.lang ? 4 : 3]}</small></div></div>`).join('');
  else if (au === 3) h = `<h2>${L('Your mobile number', 'ನಿಮ್ಮ ಮೊಬೈಲ್ ಸಂಖ್ಯೆ')}</h2><p class="sub">${L('We will send a 4-digit code', 'ನಾವು 4 ಅಂಕಿಯ ಕೋಡ್ ಕಳುಹಿಸುತ್ತೇವೆ')}</p><div class="card" style="font-size:26px;font-weight:800;text-align:center;letter-spacing:2px">+91 ${mob.replace(/(\d{5})(\d+)/, '$1 $2') || '<span style="opacity:.3">00000 00000</span>'}</div>${KP}<button class="btn" data-a="send">${L('Send code', 'ಕೋಡ್ ಕಳುಹಿಸಿ')}</button>`;
  else if (au === 4) h = `<h2>${L('Enter the code', 'ಕೋಡ್ ನಮೂದಿಸಿ')}</h2><div class="card" style="font-size:14px">💬 <b>Ale</b> · Your code is 4821</div><div class="boxes">${[0, 1, 2, 3].map(i => `<i class="${i === otp.length ? 'on' : ''}">${otp[i] || ''}</i>`).join('')}</div><div class="row"><button class="btn ghost" data-a="read">🔊 ${L('Read aloud', 'ಓದಿ ಹೇಳಿ')}</button><button class="btn ghost" data-a="fill">${L('Demo: fill code', 'ಡೆಮೊ: ಕೋಡ್ ತುಂಬಿ')}</button></div>${KP}<button class="btn" data-a="verify">${L('Verify', 'ಪರಿಶೀಲಿಸಿ')}</button>`;
  else if (au === 5) h = `<h2>${L('About you', 'ನಿಮ್ಮ ಬಗ್ಗೆ')}</h2>` + PF[S.role].map((f, i) => Array.isArray(f[1]) ? `<b>${f[0]}</b><div class="chips" data-c="${i}">${f[1].map(o => `<button class="chip${fv[i] === o ? ' on' : ''}" data-o="${o}">${o}</button>`).join('')}</div>` : `<b>${f[0]}</b><input class="inp" data-i="${i}" placeholder="${f[1]}" value="${fv[i] || ''}">`).join('') + `<button class="btn ghost" data-a="sample">${L('Fill sample details', 'ಮಾದರಿ ವಿವರ ತುಂಬಿ')}</button><button class="btn" data-a="next">${L('Continue', 'ಮುಂದುವರಿಸಿ')}</button>`;
  else if (au === 6) {
    const P = [['loc', '📍', 'Location', 'Share your boat position for safety'], ['not', '🔔', 'Alerts', 'Weather and SOS warnings'], ['mic', '🎙', 'Microphone', 'Voice notes for fish spots'], ['map', '🗺', 'Offline map · 48 MB', 'Works with no network at sea']].filter(p => S.role === 'fisher' || p[0] === 'not');
    h = `<h2>${L('Allow what Ale needs', 'ಆಲೆಗೆ ಬೇಕಾದ ಅನುಮತಿಗಳು')}</h2><p class="sub">${L('You can change this later in Profile', 'ನಂತರ ಬದಲಾಯಿಸಬಹುದು')}</p>` + P.map(p => `<div class="card rc${S.perm[p[0]] ? ' on' : ''}" data-p="${p[0]}"><span style="font-size:32px">${p[1]}</span><div>${p[2]}<small>${p[3]}</small></div><span style="margin-left:auto;font-size:26px">${S.perm[p[0]] ? '✅' : '⬜'}</span></div>`).join('') + `<button class="btn" data-a="next">${L('Continue', 'ಮುಂದುವರಿಸಿ')}</button>`;
  } else {
    const T = TR[S.role], t = T[tr];
    h = `<div style="margin:auto;text-align:center"><div style="font-size:84px">${t[0]}</div><h2>${S.lang ? t[3] : t[1]}</h2><p class="sub" style="font-size:16px">${t[2]}</p></div>${dots(tr + 1, T.length)}<button class="btn ghost" data-a="tspeak">🔊 ${L('Read aloud', 'ಓದಿ ಹೇಳಿ')}</button><button class="btn" data-a="tnext">${tr === T.length - 1 ? L('Start using Ale', 'ಆಲೆ ಬಳಸಲು ಪ್ರಾರಂಭಿಸಿ') : L('Next', 'ಮುಂದೆ')}</button>`;
  }
  AU.innerHTML = (au > 1 ? '<button class="pill" id="bk" style="align-self:flex-start;margin-bottom:6px">←</button>' : '') + (au ? dots(au, 7) : '') + h;
}

function key(k) {
  if (au === 3) {
    if (k === '⌫') mob = mob.slice(0, -1);
    else if (k === '✔') return act('send');
    else if (mob.length < 10) mob += k;
  } else if (au === 4) {
    if (k === '⌫') otp = otp.slice(0, -1);
    else if (k === '✔') return act('verify');
    else if (otp.length < 4) otp += k;
  }
  A();
  if (au === 4 && otp.length === 4 && k !== '⌫') {
    setTimeout(() => { if (au === 4 && otp.length === 4) act('verify'); }, 400);
  }
}

async function act(a) {
  if (a === 'next') {
    if (au === 5) {
      for (let i = 0; i < PF[S.role].length; i++) {
        if (!(fv[i] || '').trim()) return toast(L('Please fill every box', 'ಎಲ್ಲಾ ಬಾಕ್ಸ್ ತುಂಬಿ'));
      }
      try {
        await fetch(`${API_BASE}/api/v1/auth/verify-otp`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            phone: mob,
            otp: '4821',
            role: S.role,
            name: fv[0],
            boat_name: fv[1],
            emergency_phone: fv[3]
          })
        });
      } catch (e) {}
      au = 6;
    } else {
      au++;
      if (au === 7) tr = 0;
    }
    A();
  } else if (a === 'send') {
    if (mob.length < 10) return toast(L('Enter all 10 digits', '10 ಅಂಕಿ ನಮೂದಿಸಿ'));
    otp = '';
    au = 4;
    A();
    try {
      await fetch(`${API_BASE}/api/v1/auth/send-otp`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone: mob, role: S.role })
      });
    } catch (e) {}
    toast('💬 SMS: Your Ale code is 4821');
  } else if (a === 'verify') {
    if (otp !== '4821') {
      otp = '';
      A();
      return toast(L('Wrong code. Try again', 'ತಪ್ಪು ಕೋಡ್. ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ'));
    }
    try {
      await fetch(`${API_BASE}/api/v1/auth/verify-otp`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone: mob, otp: otp, role: S.role })
      });
    } catch (e) {}
    if (S.saved && S.saved.phone === mob && S.saved.role === S.role) {
      S.user = S.saved;
      finish(1);
    } else {
      au = 5;
      A();
      toast('✅ ' + L('Verified', 'ಪರಿಶೀಲಿಸಲಾಗಿದೆ'));
    }
  } else if (a === 'read') {
    playSpeechFallback(L('Your code is four, eight, two, one', 'ನಿಮ್ಮ ಕೋಡ್ ನಾಲ್ಕು, ಎಂಟು, ಎರಡು, ಒಂದು'));
  } else if (a === 'fill') {
    otp = '4821';
    A();
  } else if (a === 'sample') {
    SM[S.role].forEach((v, i) => fv[i] = v);
    A();
  } else if (a === 'tnext') {
    const T = TR[S.role];
    if (tr < T.length - 1) {
      tr++;
      A();
    } else finish(rp);
  } else if (a === 'tspeak') {
    const t = TR[S.role][tr];
    playSpeechFallback((S.lang ? t[3] : t[1]) + '. ' + t[2]);
  }
}

AU.onclick = e => {
  const t = e.target.closest('[data-a],[data-l],[data-r],[data-k],[data-o],[data-p],#bk');
  if (!t) return;
  const d = t.dataset;
  if (t.id === 'bk') {
    au = au >= 5 ? 3 : au - 1;
    A();
  } else if (d.l != null) {
    if (S.lang !== +d.l) $('lg').click();
    au = 2;
    A();
  } else if (d.r) {
    S.role = d.r;
    au = 3;
    if (S.saved && !mob) mob = S.saved.phone;
    A();
  } else if (d.k != null) {
    key(d.k);
  } else if (d.o) {
    fv[t.parentElement.dataset.c] = d.o;
    A();
  } else if (d.p) {
    const k = d.p;
    S.perm[k] = !S.perm[k];
    if (k === 'map') {
      S.map = S.perm.map ? 1 : 0;
      if (S.map) {
        toast('⬇ 48 MB…');
        setTimeout(() => toast('✔ Offline map ready'), 1200);
      }
    }
    A();
  } else if (d.a) {
    act(d.a);
  }
};

AU.oninput = e => {
  if (e.target.dataset.i != null) fv[e.target.dataset.i] = e.target.value;
};

document.addEventListener('keydown', e => {
  if (off() || (au !== 3 && au !== 4) || !/^(\d|Backspace|Enter)$/.test(e.key)) return;
  key(e.key === 'Backspace' ? '⌫' : e.key === 'Enter' ? '✔' : e.key);
});

function finish(ret) {
  const n = S.role;
  if (!ret) {
    S.user = {
      role: n,
      phone: mob,
      name: fv[0] || (n === 'fisher' ? 'Suresh Poojary' : n === 'family' ? 'Lakshmi' : n === 'buyer' ? 'Rafiq' : 'Insp. Naik'),
      a: fv[1], b: fv[2], c: fv[3]
    };
    S.saved = S.user;
  } else {
    S.user.role = n;
  }
  rp = 0;
  AU.classList.add('off');
  $('roles').style.display = 'none';
  const chipIdx = Object.keys(ROLES).indexOf(n);
  if (chipIdx >= 0) q('#roles .chip')[chipIdx].click();
  gr();
  pr();
  fab();
  toast('👋 ' + L('Welcome, ', 'ಸ್ವಾಗತ, ') + S.user.name.split(' ')[0]);
}

function gr() {
  if (S.user) $('greet').textContent = L('Good morning, ', 'ಶುಭೋದಯ, ') + S.user.name.split(' ')[0];
}

function fab() {
  const r = S.role;
  const m = $('mic');
  if (!m) return;
  m.style.display = (off() && (r === 'fisher' || r === 'family')) ? 'grid' : 'none';
  m.textContent = r === 'family' ? '📞' : '🎙';
}

// --- VOICE SHEET / VOX-1 & VOX-2 INTEGRATION ---
$('ph').insertAdjacentHTML('beforeend', `
<button id="mic">🎙</button>
<div id="vs" class="off">
 <div class="vh"><div><b id="vt">🎙 Talk to Ale</b><div class="sub" id="vsub" style="margin:0;font-size:12px">FastAPI + Gnani Prisma STT & Timbre TTS</div></div><button id="vx">✕</button></div>
 <div class="vtog">
  <button class="chip" id="vn">🔊 Engine noise: Off</button>
  <button class="chip" id="vo">📶 Network: Good</button>
  <button class="chip on" id="vi">🧪 How it works: On</button>
 </div>
 <div class="flow on" id="vf">🎙 Mic → Gnani STT → Intent → Action → Reply → Gnani TTS → 🔊</div>
 <div id="vb"></div>
 <div class="vwave" id="vw">${'<i></i>'.repeat(14)}</div>
 <div id="vc"></div>
 <div class="vmic">
  <button id="vm">🎙</button>
  <small id="vst">Tap phrase or hold mic</small>
 </div>
</div>`);

// Scripted phrases for judges
const PHRASES = {
  fisher: [
    { ic: '⛵', kn: 'ಇವತ್ತು ಸಮುದ್ರಕ್ಕೆ ಹೋಗಬಹುದಾ?', en: 'Can I go to sea today?' },
    { ic: '🐠', kn: 'ಬಂಗುಡೆ ರೇಟ್ ಎಷ್ಟು?', en: 'What is the mackerel rate?' },
    { ic: '💰', kn: 'pomfret ಕೆಜಿಗೆ 600 ಕೊಡ್ತಾರೆ, fair ಆ?', en: 'They offer 600/kg for pomfret. Fair?' },
    { ic: '📒', kn: 'ಇವತ್ತು ನಲವತ್ತು ಕೆಜಿ ಬೂತಾಯಿ ಮಾರಿದೆ, ಕೆಜಿಗೆ ನೂರು, ಡೀಸೆಲ್ ಸಾವಿರದ ಇನ್ನೂರು', en: 'Sold 40 kg sardine at ₹100/kg, diesel ₹1,200' },
    { ic: '📍', kn: 'ಇಲ್ಲಿ ಒಳ್ಳೆ ಬಂಗುಡೆ ಇದೆ, ಗುರುತು ಹಾಕು', en: 'Good mackerel here, mark this spot' },
    { ic: '📋', kn: 'ಲೈಫ್ ಜಾಕೆಟ್ ಇದೆ, ಡೀಸೆಲ್ ಇದೆ', en: 'Life jackets and diesel are ready' },
    { ic: '⚓', kn: 'ನಲವತ್ತು ಕೆಜಿ ಬಂಗುಡೆ ತೀರಕ್ಕೆ ಬರ್ತಿದ್ದೇವೆ, ಖರೀದಿದಾರರಿಗೆ ತಿಳಿಸು', en: 'Bringing 40 kg mackerel to shore, tell buyers' }
  ],
  family: [
    { ic: '📍', kn: 'ಅವರ ದೋಣಿ ಎಲ್ಲಿದೆ?', en: 'Where is his boat?' },
    { ic: '🌦', kn: 'ಇವತ್ತು ಹವಾಮಾನ ಹೇಗಿದೆ?', en: 'How is the weather today?' },
    { ic: '⏰', kn: 'ಅವರು ಯಾವಾಗ ಬರ್ತಾರೆ?', en: 'When will he be back?' }
  ]
};

function setWave(on) {
  $('vw').classList.toggle('on', !!on);
  $('vm').classList.toggle('on', !!on);
}

function addBubble(cls, txt, sub) {
  const vb = $('vb');
  vb.insertAdjacentHTML('beforeend', `<div class="bub ${cls}">${txt}${sub ? `<small>${sub}</small>` : ''}</div>`);
  vb.scrollTop = 1e5;
}

function addInspector(text) {
  if (!S.insp) return;
  const vb = $('vb');
  vb.insertAdjacentHTML('beforeend', `<div class="insp">${text}</div>`);
  vb.scrollTop = 1e5;
}

function renderPhrases() {
  const m = PHRASES[S.role === 'family' ? 'family' : 'fisher'];
  $('vc').innerHTML = m.map((p, i) => `
    <button class="chip sc" data-i="${i}">
      ${p.ic} ${p.en}
      <small>${p.kn}</small>
    </button>
  `).join('');
}

// Audio Resampler & 16 kHz Mono 16-bit PCM WAV Encoder (Fix 3)
async function blobTo16kHzMonoWav(blob) {
  try {
    const arrayBuffer = await blob.arrayBuffer();
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);
    
    const offlineCtx = new OfflineAudioContext(1, Math.ceil(audioBuffer.duration * 16000), 16000);
    const source = offlineCtx.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(offlineCtx.destination);
    source.start(0);
    const rendered = await offlineCtx.startRendering();
    await audioCtx.close();
    
    const samples = rendered.getChannelData(0);
    const buffer = new ArrayBuffer(44 + samples.length * 2);
    const view = new DataView(buffer);
    
    const writeString = (v, offset, str) => {
      for (let i = 0; i < str.length; i++) v.setUint8(offset + i, str.charCodeAt(i));
    };
    
    writeString(view, 0, 'RIFF');
    view.setUint32(4, 36 + samples.length * 2, true);
    writeString(view, 8, 'WAVE');
    writeString(view, 12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true); // PCM
    view.setUint16(22, 1, true); // Mono
    view.setUint32(24, 16000, true); // 16kHz
    view.setUint32(28, 32000, true); // Byte rate (16000 * 2)
    view.setUint16(32, 2, true); // Block align
    view.setUint16(34, 16, true); // 16-bit
    writeString(view, 36, 'data');
    view.setUint32(40, samples.length * 2, true);
    
    let offset = 44;
    for (let i = 0; i < samples.length; i++, offset += 2) {
      const s = Math.max(-1, Math.min(1, samples[i]));
      view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
    }
    return new Blob([buffer], { type: 'audio/wav' });
  } catch (err) {
    return blob; // fallback to original blob
  }
}

// Turn execution calling backend
async function executeVoiceTurn(transcriptText, audioBlob) {
  if (S.busy) return;
  S.busy = 1;
  setWave(true);
  $('vst').textContent = 'Processing with Gnani AI…';

  // Offline queue mode if simulated no network
  if (!S.net) {
    S.vq.push({ transcript: transcriptText, time: Date.now() });
    addBubble('u', '🎙 ' + (transcriptText || 'Offshore recording'), 'Offline');
    addBubble('a', `📥 No network. Saved voice note (${S.vq.length} queued). Will sync when online.`);
    setWave(false);
    S.busy = 0;
    $('vst').textContent = 'Saved offshore';
    return;
  }

  // Only render user bubble upfront if transcript was supplied directly
  if (transcriptText) {
    addBubble('u', '🎙 ' + transcriptText, 'User utterance');
  }

  const formData = new FormData();
  formData.append('session_token', S.session_token);
  formData.append('phone', S.user ? S.user.phone : '9876500021');
  formData.append('role', S.role);
  formData.append('noise', S.noise ? '1' : '0'); // Fix 2
  if (transcriptText) formData.append('transcript', transcriptText);
  if (audioBlob) formData.append('audio_file', audioBlob, 'mic.wav');

  try {
    const res = await fetch(`${API_BASE}/api/v1/voice/turn`, {
      method: 'POST',
      body: formData
    });
    const data = await res.json();
    setWave(false);

    // If recording from mic with empty transcript, render user bubble now (Fix 3)
    if (!transcriptText) {
      addBubble('u', '🎙 ' + (data.transcript || '...'), 'Recorded audio');
    }

    // Render agent answer
    addBubble('a', data.reply_kn, data.reply_en + (data.card_html ? '<br>' + data.card_html : ''));
    if (data.inspector) addInspector(data.inspector);

    // Audio synthesis playback
    playKannadaVoice(data.reply_kn, data.audio_url);

    // Handle confirmations / repair options
    if (data.decision === 'confirm') {
      S.activePending = data.intent;
      $('vc').innerHTML = `
        <div class="row">
          <button class="btn" id="vy">✔ ಹೌದು · Yes</button>
          <button class="btn ghost" id="vn_btn">✖ ಇಲ್ಲ · No</button>
        </div>`;
      $('vy').onclick = () => confirmTurn(true);
      $('vn_btn').onclick = () => confirmTurn(false);
      $('vst').textContent = 'Confirm action';
    } else if (data.decision === 'repair') {
      const opts = data.repair_options || ['Sardine', 'Mackerel'];
      $('vc').innerHTML = opts.map(f => `
        <button class="chip sc" data-rep="${f}">
          ${PR[f] ? PR[f][2] : '🐟'} ${FN[f] || f} <small>${f}</small>
        </button>
      `).join('');
      q('[data-rep]').forEach(b => b.onclick = () => {
        executeVoiceTurn(b.dataset.rep);
      });
      $('vst').textContent = 'Choose option';
    } else {
      if (data.target_screen_id) {
        const sid = data.target_screen_id.replace('#s', '');
        $('vc').innerHTML = `<button class="chip sc on" id="vnav">↗ Open this screen</button>`;
        $('vnav').onclick = () => {
          $('vs').classList.add('off');
          show(sid);
        };
      }
      setTimeout(renderPhrases, 2500);
      $('vst').textContent = 'Tap phrase or hold mic';
    }
  } catch (err) {
    setWave(false);
    addBubble('a', 'ದೋಷ ಸಂಭವಿಸಿದೆ. ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.', 'Error connecting to backend.');
    $('vst').textContent = 'Error';
    setTimeout(renderPhrases, 2000);
  } finally {
    S.busy = 0;
  }
}

async function confirmTurn(confirmed) {
  try {
    const res = await fetch(`${API_BASE}/api/v1/voice/confirm`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_token: S.session_token,
        confirmed: confirmed,
        phone: S.user ? S.user.phone : '9876500021'
      })
    });
    const d = await res.json();
    addBubble('u', confirmed ? 'ಹೌದು · Yes' : 'ಇಲ್ಲ · No', 'Confirmation');
    addBubble('a', d.reply_kn, d.reply_en);
    playKannadaVoice(d.reply_kn, d.audio_url);
    fetchDiarySummary();
    renderPhrases();
  } catch (e) {}
}

// Phrase chip clicks
$('vc').onclick = e => {
  const b = e.target.closest('[data-i]');
  if (!b) return;
  const list = PHRASES[S.role === 'family' ? 'family' : 'fisher'];
  const p = list[+b.dataset.i];
  if (p) executeVoiceTurn(p.kn);
};

// Microphone capture via MediaRecorder (Fix 3)
let mediaRecorder = null, audioChunks = [];
$('vm').onpointerdown = async () => {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    const list = PHRASES[S.role === 'family' ? 'family' : 'fisher'];
    executeVoiceTurn(list[S.nx++ % list.length].kn);
    return;
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream);
    audioChunks = [];
    mediaRecorder.ondataavailable = ev => audioChunks.push(ev.data);
    mediaRecorder.onstop = async () => {
      const rawBlob = new Blob(audioChunks, { type: 'audio/webm' });
      const pcmBlob = await blobTo16kHzMonoWav(rawBlob);
      executeVoiceTurn('', pcmBlob);
      stream.getTracks().forEach(t => t.stop());
    };
    mediaRecorder.start();
    setWave(true);
    $('vst').textContent = 'Recording live mic… release to send';
  } catch (e) {
    const list = PHRASES[S.role === 'family' ? 'family' : 'fisher'];
    executeVoiceTurn(list[S.nx++ % list.length].kn);
  }
};

$('vm').onpointerup = () => {
  if (mediaRecorder && mediaRecorder.state === 'recording') {
    mediaRecorder.stop();
  }
};

// Toggles inside VOX sheet
function tg() {
  $('vn').textContent = '🔊 Engine noise: ' + (S.noise ? 'On' : 'Off');
  $('vn').classList.toggle('on', !!S.noise);
  $('vo').textContent = '📶 Network: ' + (S.net ? 'Good' : 'None');
  $('vo').classList.toggle('on', !S.net);
  $('vi').textContent = '🧪 How it works: ' + (S.insp ? 'On' : 'Off');
  $('vi').classList.toggle('on', !!S.insp);
  $('vf').classList.toggle('on', !!S.insp);
}
$('vn').onclick = () => { S.noise ^= 1; tg(); };
$('vi').onclick = () => { S.insp ^= 1; tg(); };
$('vo').onclick = async () => {
  S.net ^= 1;
  tg();
  if (S.net && S.vq.length) {
    toast(`📶 Back online. Syncing ${S.vq.length} queued notes…`);
    const ops = S.vq.map((item, idx) => ({
      client_op_id: 'sync_' + item.time + '_' + idx,
      op_type: 'ledger_sale',
      phone: S.user ? S.user.phone : '9876500021',
      payload: { amount: 1600, description: item.transcript || 'Voice catch' }
    }));
    try {
      await fetch(`${API_BASE}/api/v1/sync/outbox`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ operations: ops })
      });
      S.vq = [];
      fetchDiarySummary();
      toast('✔ Offline sync complete: zero duplicates');
    } catch (e) {}
  }
};

function ovs(m) {
  S.vm = m;
  S.busy = 0;
  $('vs').classList.remove('off');
  $('vt').textContent = m === 'family' ? '📞 Ale helpline' : '🎙 Talk to Ale';
  $('vsub').textContent = m === 'family' ? 'Works on any phone, no app needed.' : 'FastAPI + Gnani Prisma STT & Timbre TTS';
  $('vn').style.display = $('vo').style.display = m === 'family' ? 'none' : '';
  $('vb').innerHTML = '';
  const n = m === 'family' ? 'ಲಕ್ಷ್ಮಿ' : (S.user ? S.user.name.split(' ')[0] : 'ಸುರೇಶ್');
  addBubble('a', 'ನಮಸ್ಕಾರ ' + n + '! ಏನು ಬೇಕು?', 'Hello! How can I help?');
  renderPhrases();
  tg();
}

$('mic').onclick = () => ovs(S.role === 'family' ? 'family' : 'fisher');
$('vx').onclick = () => {
  $('vs').classList.add('off');
  try { speechSynthesis.cancel(); } catch (e) {}
};

// --- PRO-2 TRACKING HEALTH & FOREGROUND SERVICE (Spec v1.1 D17, FR-SEA-07, TR-CLI-12) ---
function updateFgNotif() {
  const el = $('fg-notif');
  if (!el) return;
  if (S.trip) {
    el.style.display = 'flex';
  } else {
    el.style.display = 'none';
  }
}

async function fetchTrackingHealth() {
  try {
    const res = await fetch(`${API_BASE}/api/v1/devices/health?phone=${S.user ? S.user.phone : '9876500021'}`);
    if (!res.ok) return;
    const d = await res.json();
    renderHealthUI(d);
  } catch (e) {}
}

function renderHealthUI(d) {
  const stateEl = $('h-state');
  const n15Sea = $('sea-n15');
  const isDegraded = d.tracking_state === 'degraded' || d.tracking_state === 'stopped';

  if (stateEl) {
    if (isDegraded) {
      stateEl.style.background = '#f0a02033';
      stateEl.style.color = '#f0a020';
      stateEl.textContent = d.tracking_state === 'degraded' ? '▲ Degraded (N-15 Alert)' : '✕ Stopped';
    } else {
      stateEl.style.background = '#1fa35b22';
      stateEl.style.color = '#1fa35b';
      stateEl.textContent = '● Running (Foreground Service)';
    }
  }

  if (n15Sea) {
    n15Sea.style.display = isDegraded ? 'block' : 'none';
  }

  const fgEl = $('fg-notif');
  if (fgEl) {
    const batEl = $('fg-bat');
    if (batEl) batEl.textContent = (d.battery_pct || 86) + '%';
    if (isDegraded) {
      fgEl.style.borderColor = '#f0a020';
      fgEl.style.color = '#f0a020';
    } else {
      fgEl.style.borderColor = '#1fa35b';
      fgEl.style.color = '#8fd0ff';
    }
  }

  if ($('h-loc')) $('h-loc').textContent = d.location_permission === 'always' ? 'Always allow (granted)' : d.location_permission;
  if ($('h-notif')) $('h-notif').textContent = d.notifications_enabled ? 'Notifications enabled' : 'Disabled';
  if ($('h-bat-opt')) $('h-bat-opt').textContent = d.battery_optimised ? 'Restricted by OS' : 'Whitelisted (No restrictions)';
  if ($('h-dev')) $('h-dev').textContent = d.device_model ? (d.device_model + ' · Android 14') : 'Xiaomi Redmi Note 12 · Android 14';
  if ($('h-oem-guide') && d.oem_guidance) $('h-oem-guide').textContent = d.oem_guidance;
}

if ($('fg-notif')) $('fg-notif').onclick = () => show(10);
if ($('sea-n15')) $('sea-n15').onclick = () => show(10);
if ($('phealth')) $('phealth').onclick = () => show(10);
if ($('hlth-back')) $('hlth-back').onclick = () => show(1);

if ($('h-sim-fail')) {
  $('h-sim-fail').onclick = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/devices/health`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          phone: S.user ? S.user.phone : '9876500021',
          tracking_state: 'degraded',
          reason: 'Battery Saver killed service (N-15)',
          battery_pct: 18,
        })
      });
      if (res.ok) {
        renderHealthUI({
          tracking_state: 'degraded',
          battery_pct: 18,
          location_permission: 'always',
          notifications_enabled: true,
          battery_optimised: true,
        });
        fAlert('⚠ Suresh’s tracking has degraded · Last update 14m ago', 'amber');
        toast('⚠️ N-15: Tracking service killed by battery manager');
      }
    } catch (e) {}
  };
}

if ($('h-fix-resume')) {
  $('h-fix-resume').onclick = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/devices/health`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          phone: S.user ? S.user.phone : '9876500021',
          tracking_state: 'running',
          battery_pct: 86,
          reason: 'Service manually resumed by fisher',
        })
      });
      if (res.ok) {
        renderHealthUI({
          tracking_state: 'running',
          battery_pct: 86,
          location_permission: 'always',
          notifications_enabled: true,
          battery_optimised: false,
        });
        toast('✅ Foreground tracking service restored.');
      }
    } catch (e) {}
  };
}

// Initialise
rt();
A();
fetchDawnWeather();
fetchPrices();
fetchDiarySummary();
fetchTrackingHealth();
updateFgNotif();
fab();
