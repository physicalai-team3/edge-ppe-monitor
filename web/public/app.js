// 👤 팀원 4 — 대시보드 (docs/03-contracts.md §7)
const cfg = window.PPE_CONFIG || {};
const db = supabase.createClient(cfg.SUPABASE_URL, cfg.SUPABASE_PUBLISHABLE_KEY);
const BUCKET = cfg.SUPABASE_BUCKET || "violation-images";

const TYPE_LABEL = { no_helmet: "안전모 미착용", no_vest: "조끼 미착용" };
const TZ = "Asia/Seoul";
const seen = new Set();          // 이미 그린 위반 id (조회와 Realtime 중복 제거, §7.2)
const stats = { total: 0, helmet: 0, vest: 0 };

// 한국 시간 오늘 0시를 UTC ISO 문자열로. 예: "2026-11-01T15:00:00.000Z"
function kstMidnightISO() {
  const ymd = new Date().toLocaleDateString("en-CA", { timeZone: TZ });   // "2026-11-02"
  return new Date(`${ymd}T00:00:00+09:00`).toISOString();
}

function formatKST(iso) {
  return new Date(iso).toLocaleString("ko-KR", { timeZone: TZ });
}

async function loadRecent() {
  const { data, error } = await db
    .from("violations")
    .select("*")
    .order("captured_at", { ascending: false })
    .limit(50);
  if (error) return console.error(error);
  data.reverse().forEach(renderCard);   // 오래된 것부터 prepend → 최신이 위
}

async function loadTodayStats() {
  // 피드 50건이 아니라 따로 조회 (§7.1-2)
  const { data, error } = await db
    .from("violations")
    .select("no_helmet_count, no_vest_count")
    .gte("captured_at", kstMidnightISO());
  if (error) return console.error(error);
  stats.total = data.length;
  stats.helmet = data.reduce((s, r) => s + r.no_helmet_count, 0);
  stats.vest = data.reduce((s, r) => s + r.no_vest_count, 0);
  renderStats();
}

function renderStats() {
  document.getElementById("stat-total").textContent = stats.total;
  document.getElementById("stat-helmet").textContent = stats.helmet;
  document.getElementById("stat-vest").textContent = stats.vest;
}

function onNew(row) {
  if (seen.has(row.id)) return;
  if (new Date(row.captured_at) >= new Date(kstMidnightISO())) {
    stats.total += 1;
    stats.helmet += row.no_helmet_count;
    stats.vest += row.no_vest_count;
    renderStats();
  }
  renderCard(row);
  // TODO: 새 위반 알림 (토스트/소리)
}

function subscribe() {
  // 구독을 먼저 시작하고 조회한다 (§7.1-3)
  db.channel("violations-feed")
    .on("postgres_changes", { event: "INSERT", schema: "public", table: "violations" },
        (payload) => onNew(payload.new))
    .subscribe((status) => {
      document.getElementById("conn").textContent = status === "SUBSCRIBED" ? "실시간" : "연결 끊김";
    });
}

async function renderCard(row) {
  if (seen.has(row.id)) return;
  seen.add(row.id);
  const card = document.getElementById("card-tpl").content.firstElementChild.cloneNode(true);
  card.dataset.capturedAt = row.captured_at;
  card.querySelector(".types").textContent = row.violation_types.map((t) => TYPE_LABEL[t] || t).join(" · ");
  card.querySelector(".device").textContent = row.device_id;
  card.querySelector("time").textContent = formatKST(row.captured_at);
  // TODO: captured_at 순서에 맞는 위치에 끼우기 (지금은 항상 맨 위)
  document.getElementById("feed").prepend(card);

  const img = card.querySelector("img");
  const { data, error } = await db.storage.from(BUCKET).createSignedUrl(row.image_path, 3600);
  if (error || !data) {
    img.alt = "사진 없음";   // TODO: "사진 없음" 표시 스타일
    return;
  }
  img.src = data.signedUrl;
}

// TODO (2차): devices 조회 + postgres_changes '*' 구독, 10초마다 last_seen 90초 초과면 오프라인

subscribe();
loadRecent();
loadTodayStats();
