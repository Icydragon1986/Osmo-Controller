"use strict";

const APP_VERSION = "build 11";
console.log("Osmo Controller —", APP_VERSION);

const STATE_LABELS = {
  connected: "Connectée",
  connecting: "Connexion…",
  reconnecting: "Reconnexion…",
  disconnected: "Déconnectée",
  closed: "Fermée",
};

const PENDING_TIMEOUT_MS = 5000;   // au-delà, on considère la commande échouée
const STALE_AFTER_S = 3;           // pas de statut depuis 3 s => chiffres grisés

const grid = document.getElementById("grid");
const emptyMsg = document.getElementById("empty");
const summary = document.getElementById("summary");
const connDot = document.getElementById("conn-dot");
const connText = document.getElementById("conn-text");
const quitBtn = document.getElementById("quit");
const whoamiEl = document.getElementById("whoami");

const cards = new Map();           // nom -> élément DOM
const lastData = new Map();        // nom -> dernier état serveur connu
const pending = new Map();         // nom -> { target: bool, since: ms }
const notConnSince = new Map();    // nom -> ms où la caméra a cessé d'être connectée
const HELP_AFTER_MS = 8000;        // délai avant d'afficher l'aide de connexion

// --- suivi des alertes ---
const recPrev = new Map();         // nom -> dernier is_recording connu
const interruptedCams = new Set(); // caméras dont l'enr. s'est arrêté tout seul
const userStoppedRecently = new Set(); // caméras qu'on vient d'arrêter volontairement
let critPrev = new Set();          // caméras en alerte critique au dernier tour (pour le son)

function markUserStop(name) {
  userStoppedRecently.add(name);
  setTimeout(() => userStoppedRecently.delete(name), 6000);
}

// Bip d'alerte (Web Audio, aucun fichier externe). Débloqué au 1er clic.
let audioCtx = null;
document.addEventListener("click", () => {
  try {
    audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
    if (audioCtx.state === "suspended") audioCtx.resume();
  } catch (e) { /* audio indispo : tant pis, le visuel suffit */ }
}, { once: false });

function beep() {
  if (!audioCtx) return;
  try {
    const o = audioCtx.createOscillator();
    const g = audioCtx.createGain();
    o.connect(g); g.connect(audioCtx.destination);
    o.type = "sine";
    o.frequency.value = 880;
    g.gain.setValueAtTime(0.25, audioCtx.currentTime);
    g.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.5);
    o.start();
    o.stop(audioCtx.currentTime + 0.5);
  } catch (e) { /* rien */ }
}

// Alertes d'une caméra, la plus grave en premier. sev: "crit" | "warn".
function cameraAlerts(c) {
  const out = [];
  if (interruptedCams.has(c.name)) {
    out.push({ sev: "crit", msg: "l'enregistrement s'est ARRÊTÉ tout seul" });
  }
  const t = c.temperature || "";
  if (t.includes("surchauffe") || t.includes("stop")) {
    out.push({ sev: "crit", msg: "surchauffe — la caméra risque de couper" });
  } else if (t.includes("élevée")) {
    out.push({ sev: "warn", msg: "température élevée" });
  }
  if (c.connected && typeof c.battery_pct === "number") {
    if (c.battery_pct <= 10) out.push({ sev: "crit", msg: `batterie faible (${c.battery_pct} %)` });
    else if (c.battery_pct <= 20) out.push({ sev: "warn", msg: `batterie basse (${c.battery_pct} %)` });
  }
  if (c.is_recording && typeof c.remain_time_s === "number") {
    if (c.remain_time_s <= 120) out.push({ sev: "crit", msg: "carte SD presque pleine" });
    else if (c.remain_time_s <= 600) out.push({ sev: "warn", msg: "carte SD bientôt pleine" });
  }
  return out;
}

// --- helpers -------------------------------------------------------- //
function fmtDuration(s) {
  if (s == null) return "—";
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = Math.floor(s % 60);
  const pad = (n) => String(n).padStart(2, "0");
  return h > 0 ? `${h}:${pad(m)}:${pad(sec)}` : `${pad(m)}:${pad(sec)}`;
}

function fmtCapacity(mb) {
  if (mb == null) return "—";
  return mb >= 1000 ? `${(mb / 1000).toFixed(1)} Go` : `${mb} Mo`;
}

function batteryClass(pct) {
  if (pct == null) return "";
  if (pct <= 15) return "crit";
  if (pct <= 35) return "low";
  return "";
}

function tempClass(t) {
  if (!t) return "";
  if (t.includes("surchauffe") || t.includes("stop")) return "bad";
  if (t.includes("élevée")) return "warn";
  return "";
}

async function postCommand(action, camera) {
  try {
    const r = await fetch("/api/command", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, camera }),
    });
    if (r.status === 401) { window.location.href = "/login"; return; }
  } catch (e) {
    console.error("commande échouée", e);
  }
  refresh();
}

// --- création d'une carte (une seule fois) -------------------------- //
function createCard(name) {
  const card = document.createElement("div");
  card.className = "card";
  card.innerHTML = `
    <div class="card-head">
      <div>
        <div class="card-name"></div>
        <div class="card-model"></div>
      </div>
      <span class="badge"><span class="dot"></span><span class="state-label"></span></span>
    </div>

    <div class="card-alert" hidden></div>

    <div class="rec-flag">
      <span class="dot"></span><span class="rec-label"></span>
    </div>

    <div class="live-body">
      <div class="battery">
        <div class="bar"><div class="fill"></div></div>
        <div class="pct"></div>
      </div>

      <div class="stats">
        <div class="stat"><div class="k">Durée d'enr.</div><div class="v" data-f="rec_time"></div></div>
        <div class="stat"><div class="k">Temps restant</div><div class="v" data-f="remain_time"></div></div>
        <div class="stat"><div class="k">Carte SD libre</div><div class="v" data-f="sd"></div></div>
        <div class="stat"><div class="k">Température</div><div class="v" data-f="temp"></div></div>
      </div>
    </div>

    <div class="card-actions">
      <button class="btn btn-rec">⬤ Démarrer</button>
      <button class="btn btn-stop">◼ Arrêter</button>
    </div>
    <button class="btn btn-preview" disabled>🎯 Vérifier le cadrage <span class="soon-badge">à venir</span></button>

    <div class="conn-hint" hidden></div>
    <button class="btn btn-reset" hidden>⟳ Réessayer la connexion</button>
  `;

  card._refs = {
    name: card.querySelector(".card-name"),
    model: card.querySelector(".card-model"),
    badge: card.querySelector(".badge"),
    stateLabel: card.querySelector(".state-label"),
    recFlag: card.querySelector(".rec-flag"),
    recLabel: card.querySelector(".rec-label"),
    fill: card.querySelector(".battery .fill"),
    pct: card.querySelector(".battery .pct"),
    recTime: card.querySelector('[data-f="rec_time"]'),
    remainTime: card.querySelector('[data-f="remain_time"]'),
    sd: card.querySelector('[data-f="sd"]'),
    temp: card.querySelector('[data-f="temp"]'),
    startBtn: card.querySelector(".btn-rec"),
    stopBtn: card.querySelector(".btn-stop"),
    actions: card.querySelector(".card-actions"),
    liveBody: card.querySelector(".live-body"),
    connHint: card.querySelector(".conn-hint"),
    resetBtn: card.querySelector(".btn-reset"),
    cardAlert: card.querySelector(".card-alert"),
  };

  card._refs.startBtn.addEventListener("click", () => sendRec(name, true));
  card._refs.stopBtn.addEventListener("click", () => sendRec(name, false));
  card._refs.resetBtn.addEventListener("click", () => {
    card._refs.resetBtn.disabled = true;
    postCommand("reset_camera", name);
  });

  cards.set(name, card);
  grid.appendChild(card);
  return card;
}

// Marque une caméra "en cours…" et rafraîchit son affichage tout de suite.
function markPending(name, target) {
  pending.set(name, { target, since: Date.now() });
  const data = lastData.get(name);
  if (data) renderCard(name, data);   // bascule visuelle immédiate
}

// Une seule caméra.
function sendRec(name, target) {
  markPending(name, target);
  if (!target) markUserStop(name);          // arrêt volontaire -> pas une alerte
  postCommand(target ? "start_rec" : "stop_rec", name);
}

// Toutes les caméras connectées, en une seule commande groupée.
function sendRecAll(target) {
  for (const [name, data] of lastData) {
    if (data.connected) {
      markPending(name, target);
      if (!target) markUserStop(name);
    }
  }
  postCommand(target ? "start_rec_all" : "stop_rec_all");
}

// --- rendu d'une carte à partir de l'état serveur ------------------- //
function renderCard(name, c) {
  const card = cards.get(name) || createCard(name);
  const r = card._refs;

  const state = c.state || "disconnected";

  // Gestion de l'état "en cours…" : on garde l'affichage sur la cible voulue
  // tant que la caméra n'a pas confirmé (ou jusqu'au timeout = échec).
  let recording = c.is_recording;
  let isPending = false;
  const p = pending.get(name);
  if (p) {
    if (c.is_recording === p.target) {
      pending.delete(name);                 // confirmé par la caméra
    } else if (Date.now() - p.since > PENDING_TIMEOUT_MS) {
      pending.delete(name);                 // jamais confirmé => échec
      flash(card, "cmd-failed");
    } else {
      recording = p.target;                 // on affiche la cible en attendant
      isPending = true;
    }
  }

  // Périmé : connecté mais plus de statut frais (lien fragile).
  const stale = !c.connected ||
    (c.status_age_s != null && c.status_age_s > STALE_AFTER_S);

  card.classList.toggle("recording", !!recording);
  card.classList.toggle("pending", isPending);
  card.classList.toggle("stale", !!stale);

  r.name.textContent = c.name;
  r.model.textContent = c.model || "";
  r.badge.className = "badge " + state;
  r.stateLabel.textContent = STATE_LABELS[state] || state;

  r.recFlag.className = "rec-flag" + (recording ? "" : " idle");
  r.recLabel.textContent = isPending
    ? (recording ? "Démarrage…" : "Arrêt…")
    : (recording ? "ENREGISTRE" : "Enregistrement arrêté");

  const batt = c.battery_pct;
  const battW = batt == null ? 0 : Math.max(0, Math.min(100, batt));
  r.fill.className = "fill " + batteryClass(batt);
  r.fill.style.width = battW + "%";
  r.pct.textContent = batt == null ? "—" : batt + " %";

  r.recTime.textContent = fmtDuration(c.record_time_s);
  r.remainTime.textContent = fmtDuration(c.remain_time_s);
  r.sd.textContent = fmtCapacity(c.remain_capacity_mb);
  r.temp.textContent = c.temperature || "—";
  r.temp.className = "v " + tempClass(c.temperature);

  // Pendant l'attente, on désactive les deux boutons pour éviter le double-clic.
  r.startBtn.disabled = isPending || !(c.connected && !recording);
  r.stopBtn.disabled = isPending || !(c.connected && recording);

  // --- guidage si la caméra ne se connecte pas ---
  if (c.connected) {
    notConnSince.delete(name);
  } else if (!notConnSince.has(name)) {
    notConnSince.set(name, Date.now());
  }
  const downMs = c.connected ? 0 : Date.now() - notConnSince.get(name);
  const showHelp = !c.connected && downMs > HELP_AFTER_MS;
  r.connHint.hidden = !showHelp;
  r.resetBtn.hidden = !showHelp;
  if (showHelp) {
    r.connHint.innerHTML =
      "Caméra introuvable. Vérifie&nbsp;: <b>allumée</b> · <b>à portée</b> · " +
      "<b>Bluetooth du téléphone coupé</b>. Sinon, éteins puis rallume la caméra.";
  } else {
    r.resetBtn.disabled = false;   // réactive le bouton une fois reconnecté
  }

  // --- alerte de la carte (surchauffe / batterie / SD / arrêt inattendu) ---
  const alerts = cameraAlerts(c);
  if (alerts.length) {
    const worst = alerts.some((a) => a.sev === "crit") ? "crit" : "warn";
    r.cardAlert.className = "card-alert " + worst;
    r.cardAlert.innerHTML = alerts
      .map((a) => `${a.sev === "crit" ? "🔴" : "🟠"} ${a.msg}`)
      .join("<br>");
    r.cardAlert.hidden = false;
    card.classList.toggle("has-crit", worst === "crit");
  } else {
    r.cardAlert.hidden = true;
    card.classList.remove("has-crit");
  }
}

function flash(card, cls) {
  card.classList.add(cls);
  setTimeout(() => card.classList.remove(cls), 1200);
}

// Détecte un enregistrement qui s'est arrêté SANS action de l'utilisateur.
function detectInterruptions(cameras) {
  for (const c of cameras) {
    const was = recPrev.get(c.name);
    if (c.connected && was && !c.is_recording && !userStoppedRecently.has(c.name)) {
      interruptedCams.add(c.name);
    }
    if (c.is_recording) interruptedCams.delete(c.name);   // re-enregistre -> alerte levée
    recPrev.set(c.name, !!c.is_recording);
  }
}

// Bandeau de santé global + bip sur nouvelle alerte critique.
function updateHealthBanner(cameras) {
  const problems = [];
  const critNow = new Set();
  for (const c of cameras) {
    for (const a of cameraAlerts(c)) {
      problems.push({ name: c.name, sev: a.sev, msg: a.msg });
      if (a.sev === "crit") critNow.add(c.name);
    }
  }
  for (const name of critNow) {
    if (!critPrev.has(name)) { beep(); break; }   // une caméra vient de passer critique
  }
  critPrev = critNow;

  const banner = document.getElementById("health");
  if (!problems.length) { banner.hidden = true; return; }
  problems.sort((a, b) => (a.sev === b.sev ? 0 : a.sev === "crit" ? -1 : 1));
  const hasCrit = problems.some((p) => p.sev === "crit");
  banner.className = "health " + (hasCrit ? "crit" : "warn");
  banner.hidden = false;
  const items = problems
    .map((p) => `<span class="hp"><b>${p.name}</b> — ${p.msg}</span>`)
    .join("");
  banner.innerHTML =
    `<div class="health-title">${hasCrit ? "🔴" : "🟠"} ` +
    `${problems.length} point(s) à vérifier</div>` +
    `<div class="health-items">${items}</div>`;
}

function render(cameras) {
  emptyMsg.hidden = cameras.length > 0;
  detectInterruptions(cameras);
  const seen = new Set();
  for (const c of cameras) {
    lastData.set(c.name, c);
    try {
      renderCard(c.name, c);          // une carte en erreur ne fige pas le reste
    } catch (e) {
      console.error("rendu de carte échoué", c.name, e);
    }
    seen.add(c.name);
  }
  for (const name of [...cards.keys()]) {
    if (!seen.has(name)) {
      cards.get(name).remove();
      cards.delete(name);
      lastData.delete(name);
      pending.delete(name);
      recPrev.delete(name);
      interruptedCams.delete(name);
    }
  }

  updateHealthBanner(cameras);

  const connected = cameras.filter((c) => c.connected).length;
  const recording = cameras.filter((c) => c.is_recording).length;
  summary.textContent =
    `${connected}/${cameras.length} connectées · ${recording} en enregistrement`;
}

// --- boucle de rafraîchissement ------------------------------------ //
let refreshing = false;
async function refresh() {
  if (refreshing) return;
  refreshing = true;
  try {
    const r = await fetch("/api/state");
    if (r.status === 401) { window.location.href = "/login"; return; }
    const data = await r.json();
    render(data.cameras || []);
    if (data.version && versionEl) versionEl.textContent = "v" + data.version + " · " + APP_VERSION;
    manageBtn.hidden = !data.manageable;
    quitBtn.hidden = data.role !== "admin";   // quitter ferme l'app pour tout le monde : admin seulement
    if (whoamiEl && data.username) whoamiEl.textContent = `${data.username} (${data.role})`;
    if (!modal.hidden) renderManageList();     // garde la liste de la modale à jour
    connDot.classList.add("ok");
    connText.textContent = "Serveur connecté";
  } catch (e) {
    connDot.classList.remove("ok");
    connText.textContent = "Serveur injoignable…";
  } finally {
    refreshing = false;
  }
}

document.getElementById("recAll").addEventListener("click", () => sendRecAll(true));
document.getElementById("stopAll").addEventListener("click", () => sendRecAll(false));

// --- gestion des caméras (modale) ---------------------------------- //
const modal = document.getElementById("manage-modal");
const manageBtn = document.getElementById("manage");

manageBtn.addEventListener("click", openManage);
document.getElementById("manage-close").addEventListener("click", () => (modal.hidden = true));
modal.addEventListener("click", (e) => { if (e.target === modal) modal.hidden = true; });
document.getElementById("scan").addEventListener("click", doScan);

function openManage() {
  modal.hidden = false;
  document.getElementById("scan-results").innerHTML = "";
  renderManageList();
}

function renderManageList() {
  const list = document.getElementById("manage-list");
  const cams = [...lastData.values()];
  if (!cams.length) {
    list.innerHTML = '<div class="manage-empty">Aucune caméra enregistrée.</div>';
    return;
  }
  list.innerHTML = "";
  for (const c of cams) {
    const el = document.createElement("div");
    el.className = "manage-item";
    el.innerHTML = `<div class="info"><span class="n">${c.name}</span>` +
      `<span class="a">${STATE_LABELS[c.state] || c.state}</span></div>`;
    const btn = document.createElement("button");
    btn.className = "btn btn-remove";
    btn.textContent = "Retirer";
    btn.addEventListener("click", async () => {
      btn.disabled = true;
      await postCommand("remove_camera", c.name);
      renderManageList();
    });
    el.appendChild(btn);
    list.appendChild(el);
  }
}

async function doScan() {
  const results = document.getElementById("scan-results");
  const btn = document.getElementById("scan");
  btn.disabled = true;
  results.innerHTML = '<div class="spin">Recherche en cours… (quelques secondes)</div>';
  try {
    const r = await fetch("/api/command", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "scan" }),
    });
    const data = await r.json();
    if (!data.ok) { results.innerHTML = `<div class="spin">Erreur : ${data.error}</div>`; return; }
    renderScan(data.result || []);
  } catch (e) {
    results.innerHTML = '<div class="spin">Recherche échouée.</div>';
  } finally {
    btn.disabled = false;
  }
}

function renderScan(devices) {
  const results = document.getElementById("scan-results");
  results.innerHTML = "";
  const candidates = devices.filter((d) => d.candidate);
  if (!candidates.length) {
    results.innerHTML = '<div class="spin">Aucune caméra trouvée. Vérifie qu\'elle est ' +
      'allumée et que le Bluetooth du téléphone est coupé.</div>';
    return;
  }
  let terrainN = lastData.size + 1;
  for (const d of candidates) {
    const el = document.createElement("div");
    el.className = "scan-item cand";
    const sig = d.rssi != null ? `${d.rssi} dBm` : "";
    el.innerHTML = `<span class="sig">${sig}</span>` +
      `<div class="id"><div class="n">${d.name}</div><div class="a">${d.address}</div></div>`;
    if (d.added) {
      const tag = document.createElement("span");
      tag.className = "muted";
      tag.textContent = "déjà ajoutée";
      el.appendChild(tag);
    } else {
      const input = document.createElement("input");
      input.value = `Terrain ${terrainN++}`;
      const add = document.createElement("button");
      add.className = "btn btn-add";
      add.textContent = "Ajouter";
      add.addEventListener("click", async () => {
        add.disabled = true;
        add.textContent = "…";
        const res = await fetch("/api/command", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action: "add_camera", name: input.value, address: d.address }),
        });
        const j = await res.json();
        if (!j.ok) { add.disabled = false; add.textContent = "Ajouter"; alert("Erreur : " + j.error); return; }
        el.remove();
        refresh();
        renderManageList();
      });
      el.appendChild(input);
      el.appendChild(add);
    }
    results.appendChild(el);
  }
}

// --- déconnexion ----------------------------------------------------- //
document.getElementById("logout").addEventListener("click", async () => {
  try {
    await fetch("/api/logout", { method: "POST" });
  } catch (e) { /* on redirige quand même */ }
  window.location.href = "/login";
});

// --- bouton Quitter (arrêt propre) --------------------------------- //
document.getElementById("quit").addEventListener("click", async () => {
  if (!confirm("Fermer Osmo Controller ?\nLes caméras seront déconnectées proprement.")) return;
  try {
    await fetch("/api/command", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "quit" }),
    });
  } catch (e) { /* le serveur se ferme : normal que la requête coupe */ }
  clearInterval(pollTimer);
  document.getElementById("quit-overlay").hidden = false;
});

const versionEl = document.getElementById("version");
if (versionEl) versionEl.textContent = APP_VERSION;

refresh();
const pollTimer = setInterval(refresh, 500);
