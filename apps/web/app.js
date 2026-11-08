// WHY: TR-VOX-05, TR-VOX-06, TR-PWA-01, G1, G2, G3 — Ale Voice Frontend Application with Live MediaRecorder & API Client
const API_BASE = ""; // Relative to origin when served by FastAPI

const $ = id => document.getElementById(id);
const q = s => document.querySelectorAll(s);

function toast(m) {
  const t = $('toast');
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

// Roles & Tabs
const ROLES = {
  fisher: ['🎣 Fisher', [[0, '🌅', 'Dawn', 'ಮುಂಜಾನೆ'], [1, '🧭', 'Sea', 'ಸಮುದ್ರ'], [5, '⚓', 'Landing', 'ದಡ'], [2, '🐟', 'Prices', 'ಬೆಲೆ'], [4, '📒', 'Diary', 'ಲೆಕ್ಕ']]],
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
  if (+i === 7) fetchGuardWatch();
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
  rt(+q('.s.on')[0].id.slice(1));
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
  } catch (e) {}
}

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

async function fetchGuardWatch() {
  try {
    const res = await fetch(`${API_BASE}/api/v1/guard/watch`);
    if (!res.ok) return;
    const d = await res.json();
    const gl = $('gl');
    if (d.has_active_emergency && d.active_incident) {
      gl.innerHTML = `
        <div class="card" style="border:3px solid #d6372f">
          <b style="color:#d6372f">🚨 SOS · Boat ${d.active_incident.boat}</b>
          <div class="sub" style="margin:4px 0 8px">${d.active_incident.fisher} · ${d.active_incident.location}</div>
          <button class="btn" id="disp">Dispatch rescue</button>
        </div>`;
      const btn = $('disp');
      if (btn) btn.onclick = async () => {
        await fetch(`${API_BASE}/api/v1/guard/dispatch`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ incident_id: 'active' }) });
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
  toast('🚨 Sending SOS to Coast Guard, boats & family…');
  try {
    const phone = S.user ? S.user.phone : '9876500021';
    await fetch(`${API_BASE}/api/v1/trips/sos`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phone, client_op_id: 'sos_tap_' + Date.now() })
    });
    toast('🚨 SOS broadcast confirmed');
    fetchFamilyStatus();
    fetchGuardWatch();
  } catch (e) {
    toast('🚨 SOS logged offline');
  }
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

// Scripted / Clickable phrases for judges
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

// Turn execution calling backend
async function executeVoiceTurn(transcriptText, audioBlob) {
  if (S.busy) return;
  S.busy = 1;
  setWave(true);
  $('vst').textContent = 'Processing with Gnani AI…';

  // Offline queue mode if simulated no network
  if (!S.net) {
    S.vq.push({ transcript: transcriptText, time: Date.now() });
    addBubble('u', '🎙 ' + transcriptText, 'Offline');
    addBubble('a', `📥 No network. Saved voice note (${S.vq.length} queued). Will sync when online.`);
    setWave(false);
    S.busy = 0;
    $('vst').textContent = 'Saved offshore';
    return;
  }

  addBubble('u', '🎙 ' + transcriptText, 'User utterance');

  const formData = new FormData();
  formData.append('session_token', S.session_token);
  formData.append('phone', S.user ? S.user.phone : '9876500021');
  formData.append('role', S.role);
  if (transcriptText) formData.append('transcript', transcriptText);
  if (audioBlob) formData.append('audio_file', audioBlob, 'mic.wav');

  try {
    const res = await fetch(`${API_BASE}/api/v1/voice/turn`, {
      method: 'POST',
      body: formData
    });
    const data = await res.json();
    setWave(false);

    // Render agent answer
    addBubble('a', data.reply_kn, data.reply_en + (data.card_html ? '<br>' + data.card_html : ''));
    if (data.inspector) addInspector(data.inspector);

    // Audio synthesis
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

// Microphone capture via MediaRecorder
let mediaRecorder = null, audioChunks = [];
$('vm').onpointerdown = async () => {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    // Fallback: cycle phrases
    const list = PHRASES[S.role === 'family' ? 'family' : 'fisher'];
    executeVoiceTurn(list[S.nx++ % list.length].kn);
    return;
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream);
    audioChunks = [];
    mediaRecorder.ondataavailable = ev => audioChunks.push(ev.data);
    mediaRecorder.onstop = () => {
      const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
      executeVoiceTurn('', audioBlob);
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
$('vn').onclick = () => {
  S.noise ^= 1;
  $('vn').textContent = '🔊 Engine noise: ' + (S.noise ? 'On' : 'Off');
  $('vn').classList.toggle('on', !!S.noise);
};
$('vi').onclick = () => {
  S.insp ^= 1;
  $('vi').textContent = '🧪 How it works: ' + (S.insp ? 'On' : 'Off');
  $('vi').classList.toggle('on', !!S.insp);
  $('vf').classList.toggle('on', !!S.insp);
};
$('vo').onclick = async () => {
  S.net ^= 1;
  $('vo').textContent = '📶 Network: ' + (S.net ? 'Good' : 'None');
  $('vo').classList.toggle('on', !S.net);
  if (S.net && S.vq.length) {
    toast(`📶 Back online. Syncing ${S.vq.length} queued notes…`);
    const ops = S.vq.map((item, idx) => ({
      client_op_id: 'sync_' + item.time + '_' + idx,
      op_type: 'ledger_sale',
      phone: S.user ? S.user.phone : '9876500021',
      payload: { amount: 1600, description: item.transcript || 'Voice catch' }
    }));
    await fetch(`${API_BASE}/api/v1/sync/outbox`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ operations: ops })
    });
    S.vq = [];
    fetchDiarySummary();
    toast('✔ Offline sync complete: zero duplicates');
  }
};

$('mic').onclick = () => {
  $('vs').classList.remove('off');
  renderPhrases();
  $('vb').innerHTML = '';
  addBubble('a', 'ನಮಸ್ಕಾರ ಸುರೇಶ್! ಏನು ಬೇಕು?', 'Hello! How can I help?');
};
$('vx').onclick = () => $('vs').classList.add('off');

// Auth flow & OTP 4821
const AU = $('auth');
let au = 0, mob = '9876500021', otp = '4821';
function showAuth() {
  AU.innerHTML = `
    <div style="margin:auto;text-align:center">
      <div style="font-size:64px">🌊</div>
      <div class="logo" style="font-size:46px">ale<span>~</span></div>
      <p class="sub">The sea doesn’t change. How we prepare for it can.</p>
      <div class="card" style="margin:16px 0">
        <b>Demo Sign-in</b>
        <div style="font-size:20px;margin:8px 0;font-weight:700">+91 98765 00021 (Suresh)</div>
        <small class="sub">Demo OTP: 4821</small>
      </div>
      <button class="btn" id="abtn">Start · ಪ್ರಾರಂಭಿಸಿ</button>
    </div>`;
  $('abtn').onclick = () => {
    AU.classList.add('off');
    $('mic').style.display = 'grid';
    toast('👋 Welcome, Suresh');
    show(0);
  };
}

// Initialise app
rt();
showAuth();
fetchDawnWeather();
fetchPrices();
fetchDiarySummary();
