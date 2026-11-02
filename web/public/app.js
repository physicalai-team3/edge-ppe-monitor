// 👤 팀원 4 — 대시보드 (docs/03-contracts.md §7)
// 데이터는 Supabase 에서만 읽는다. 쓰는 쪽이 gateway(실제)든 cloud-seed(가짜)든 같은 형식이라 코드는 같다.
const cfg = window.PPE_CONFIG || {};
const BUCKET = cfg.SUPABASE_BUCKET || "violation-images";

const TYPE_LABEL = { no_helmet: "안전모 미착용", no_vest: "조끼 미착용" };
const TZ = "Asia/Seoul";
const FEED_MAX = 50;                 // 피드 카드 수 (§7.1-1)
const SIGNED_URL_S = 3600;           // 서명 URL 1시간 (§7.1-4)
const DEVICE_ONLINE_MS = 90 * 1000;  // last_seen 90초 이내면 온라인 (§7.2)
const ALERT_GAP_MS = 1000;           // 알림은 1초에 한 번까지 (burst 때 묶음)

const $ = (id) => document.getElementById(id);
const seen = new Set();              // 이미 그린 위반 id (조회와 Realtime 중복 제거, §7.2)
const todayRows = new Map();         // 오늘(KST) 위반 id → {device_id, no_helmet_count, no_vest_count}
const devices = new Map();           // device_id → devices 행
let statsDay = kstDate();
let db = null;
let disconnected = false;            // 한 번 끊긴 뒤 다시 SUBSCRIBED 되면 다시 조회
let audio = null;                    // 알림 소리 (브라우저는 클릭 전 소리를 막는다)
const alerts = { last: 0, pending: 0, timer: null };

// ── 시간 ──────────────────────────────────────────────────

// KST 날짜 "2026-11-02"
function kstDate(d = new Date()) {
  return d.toLocaleDateString("en-CA", { timeZone: TZ });
}

// 한국 시간 오늘 0시를 UTC ISO 문자열로. 예: "2026-11-01T15:00:00.000Z"
function kstMidnightISO() {
  return new Date(`${kstDate()}T00:00:00+09:00`).toISOString();
}

function formatKST(iso) {
  return new Date(iso).toLocaleString("ko-KR", { timeZone: TZ });
}

function ago(iso) {
  const s = Math.max(0, Math.round((Date.now() - Date.parse(iso)) / 1000));
  if (s < 60) return `${s}초 전`;
  if (s < 3600) return `${Math.floor(s / 60)}분 전`;
  return `${Math.floor(s / 3600)}시간 전`;
}

// ── 피드 ──────────────────────────────────────────────────

async function loadRecent() {
  const { data, error } = await db
    .from("violations")
    .select("*")
    .order("captured_at", { ascending: false })
    .limit(FEED_MAX);
  if (error) return console.error(error);
  const fresh = data.filter((row) => !seen.has(row.id));
  if (!fresh.length) return;
  // 서명 URL 을 한 번에 받는다 (50번 요청 → 1번)
  const urls = new Map();
  const signed = await db.storage.from(BUCKET).createSignedUrls(fresh.map((r) => r.image_path), SIGNED_URL_S);
  if (signed.error) console.error(signed.error);
  for (const s of signed.data || []) urls.set(s.path, s.signedUrl && !s.error ? s.signedUrl : false);
  for (const row of fresh) renderCard(row, urls.has(row.image_path) ? urls.get(row.image_path) : null);
}

// captured_at 최신이 위. 늦게 도착한 위반(outbox 재시도)도 시간 순서 자리에 들어간다.
function insertByTime(card, capturedAt) {
  const feed = $("feed");
  const t = Date.parse(capturedAt);
  const after = [...feed.children].find((c) => Date.parse(c.dataset.capturedAt) < t);
  feed.insertBefore(card, after || null);
  while (feed.children.length > FEED_MAX) feed.lastElementChild.remove();
}

// signedUrl: 이미 받은 URL, null 이면 이 카드만 따로 발급, false 면 발급 실패로 확정
function renderCard(row, signedUrl = null) {
  if (seen.has(row.id)) return null;
  seen.add(row.id);
  const card = $("card-tpl").content.firstElementChild.cloneNode(true);
  card.dataset.id = row.id;
  card.dataset.capturedAt = row.captured_at;
  card.querySelector(".types").textContent = row.violation_types.map((t) => TYPE_LABEL[t] || t).join(" · ");
  card.querySelector(".device").textContent = row.device_id;
  card.querySelector(".persons").textContent = row.person_count > 1 ? `사람 ${row.person_count}명` : "";
  const time = card.querySelector("time");
  time.dateTime = row.captured_at;
  time.textContent = formatKST(row.captured_at);
  insertByTime(card, row.captured_at);

  const img = card.querySelector("img");
  img.onerror = () => markNoImage(card);        // 만료·삭제된 사진
  card.querySelector(".photo-missing").onclick = () => signImage(card, row);   // 클릭하면 다시 발급
  if (signedUrl) img.src = signedUrl;
  else if (signedUrl === false) markNoImage(card);
  else signImage(card, row);
  return card;
}

async function signImage(card, row) {
  const { data, error } = await db.storage.from(BUCKET).createSignedUrl(row.image_path, SIGNED_URL_S);
  if (error || !data) return markNoImage(card);
  card.classList.remove("no-image");
  card.querySelector("img").src = data.signedUrl;
}

function markNoImage(card) {
  card.classList.add("no-image");
  card.querySelector("img").removeAttribute("src");
}

// ── 오늘 통계 (§7.1-2, 피드 50건과 별도 조회) ──────────────

async function loadTodayStats() {
  const day = kstDate();
  const { data, error } = await db
    .from("violations")
    .select("id, device_id, no_helmet_count, no_vest_count")
    .gte("captured_at", kstMidnightISO());
  if (error) return console.error(error);
  if (day !== statsDay) return;                 // 조회 중 자정이 지났으면 버린다 (다음 tick 이 다시 조회)
  // 조회 도중 Realtime 으로 들어온 행이 결과에 없더라도 지우지 않는다 (덮어쓰기 대신 합치기)
  for (const r of data) todayRows.set(r.id, r);
  renderStats();
}

function countToday(row) {
  if (kstDate(new Date(row.captured_at)) !== statsDay) return;
  todayRows.set(row.id, row);
  renderStats();
}

function renderStats() {
  let helmet = 0, vest = 0;
  const byDevice = new Map();
  for (const r of todayRows.values()) {
    helmet += r.no_helmet_count;
    vest += r.no_vest_count;
    byDevice.set(r.device_id, (byDevice.get(r.device_id) || 0) + 1);
  }
  $("stat-total").textContent = todayRows.size;
  $("stat-helmet").textContent = helmet;
  $("stat-vest").textContent = vest;
  $("stat-devices").textContent = [...byDevice]
    .sort((a, b) => b[1] - a[1])
    .map(([id, n]) => `${id} ${n}건`)
    .join(" · ");
}

// 자정(KST)이 지나면 통계를 비우고 다시 조회
function checkDayChange() {
  const day = kstDate();
  if (day === statsDay) return;
  statsDay = day;
  todayRows.clear();
  renderStats();
  loadTodayStats();
}

// ── 새 위반 알림 ──────────────────────────────────────────

function alertNew(row) {
  const card = document.querySelector(`.card[data-id="${row.id}"]`);
  if (card) {
    card.classList.add("fresh");
    setTimeout(() => card.classList.remove("fresh"), 4000);
  }
  alerts.pending += 1;
  const wait = alerts.last + ALERT_GAP_MS - Date.now();
  if (wait <= 0) return flushAlerts(row);
  if (!alerts.timer) alerts.timer = setTimeout(() => flushAlerts(null), wait);
}

function flushAlerts(row) {
  clearTimeout(alerts.timer);
  alerts.timer = null;
  if (!alerts.pending) return;
  const text = alerts.pending === 1 && row
    ? `새 위반 · ${row.device_id} · ${row.violation_types.map((t) => TYPE_LABEL[t] || t).join(", ")}`
    : `새 위반 ${alerts.pending}건`;
  alerts.pending = 0;
  alerts.last = Date.now();
  showToast(text);
  beep();
}

function showToast(text) {
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.textContent = text;
  $("toasts").prepend(toast);
  setTimeout(() => toast.remove(), 5000);
}

function beep() {
  if (!audio) return;
  const t = audio.currentTime;
  for (const start of [0, 0.2]) {
    const osc = audio.createOscillator();
    const gain = audio.createGain();
    osc.frequency.value = 880;
    gain.gain.setValueAtTime(0.2, t + start);
    gain.gain.exponentialRampToValueAtTime(0.001, t + start + 0.15);
    osc.connect(gain).connect(audio.destination);
    osc.start(t + start);
    osc.stop(t + start + 0.15);
  }
}

function toggleSound() {
  if (audio) {
    audio.close();
    audio = null;
  } else {
    audio = new (window.AudioContext || window.webkitAudioContext)();
    beep();
  }
  $("sound").textContent = audio ? "알림 소리 끄기" : "알림 소리 켜기";
  $("sound").setAttribute("aria-pressed", String(!!audio));
}

// ── 장치 상태 (2차, §7.1-5) ────────────────────────────────

async function loadDevices() {
  const { data, error } = await db.from("devices").select("*");
  if (error) return console.error(error);
  for (const d of data) devices.set(d.device_id, d);
  renderDevices();
}

function onDeviceChange(payload) {
  if (payload.eventType === "DELETE") devices.delete(payload.old.device_id);
  else devices.set(payload.new.device_id, payload.new);
  renderDevices();
}

// 10초마다 다시 그려 90초 기준을 넘은 장치를 오프라인으로 바꾼다
function renderDevices() {
  const box = $("devices");
  box.replaceChildren();
  for (const d of [...devices.values()].sort((a, b) => a.device_id.localeCompare(b.device_id))) {
    const online = Date.now() - Date.parse(d.last_seen) <= DEVICE_ONLINE_MS;
    const chip = document.createElement("span");
    chip.className = `device-chip ${online ? "online" : "offline"}`;
    const extra = online ? (d.rssi != null ? ` · RSSI ${d.rssi}` : "") : ` · ${ago(d.last_seen)}`;
    chip.textContent = `${d.device_id} ${online ? "온라인" : "오프라인"}${extra}`;
    if (d.last_error) chip.title = `마지막 오류: ${d.last_error}`;
    box.append(chip);
  }
  box.hidden = devices.size === 0;
}

// ── Realtime ──────────────────────────────────────────────

function onNew(row) {
  if (seen.has(row.id)) return;
  countToday(row);
  if (renderCard(row)) alertNew(row);
}

function setConn(text, ok) {
  $("conn").textContent = text;
  $("conn").classList.toggle("ok", ok);
}

function subscribe() {
  // 구독을 먼저 시작하고 조회한다 (§7.1-3). outbox 재시도의 UPDATE 이벤트는 구독하지 않는다
  db.channel("violations-feed")
    .on("postgres_changes", { event: "INSERT", schema: "public", table: "violations" }, (p) => onNew(p.new))
    .on("postgres_changes", { event: "*", schema: "public", table: "devices" }, onDeviceChange)
    .subscribe((status) => {
      if (status === "SUBSCRIBED") {
        setConn("실시간", true);
        if (disconnected) {          // 끊긴 동안 놓친 위반을 다시 채운다 (seen 이 중복을 막음)
          disconnected = false;
          loadRecent();
          loadTodayStats();
          loadDevices();
        }
      } else {
        setConn("연결 끊김", false);
        disconnected = true;
      }
    });
}

// ── 시작 ──────────────────────────────────────────────────

function showSetupError(message) {
  setConn("설정 필요", false);
  const p = document.createElement("p");
  p.className = "setup-error";
  p.textContent = message;
  $("feed").replaceWith(p);
}

function start() {
  $("sound").onclick = toggleSound;
  if (!window.supabase) {
    return showSetupError("supabase-js 를 불러오지 못했습니다. 인터넷(cdn.jsdelivr.net) 연결을 확인하세요.");
  }
  if (!cfg.SUPABASE_URL || !cfg.SUPABASE_PUBLISHABLE_KEY) {
    return showSetupError("config.js 에 SUPABASE_URL / SUPABASE_PUBLISHABLE_KEY 가 없습니다. .env 를 채우고 web 을 다시 실행하세요.");
  }
  db = supabase.createClient(cfg.SUPABASE_URL, cfg.SUPABASE_PUBLISHABLE_KEY);
  subscribe();
  loadRecent();
  loadTodayStats();
  loadDevices();
  setInterval(checkDayChange, 60 * 1000);
  setInterval(renderDevices, 10 * 1000);
}

start();
