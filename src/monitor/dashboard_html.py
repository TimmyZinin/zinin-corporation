"""
Zinin Corp — Monitoring Dashboard HTML Template

Single-page dark-theme dashboard with embedded CSS/JS.
Connects to /api/stream (SSE) for live updates.
"""


def render_dashboard_html() -> str:
    """Generate complete HTML dashboard."""
    return _TEMPLATE


_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Zinin Corp Monitor</title>
<style>
:root {
  --bg: #0a0a12;
  --card: #12121e;
  --border: #1e1e30;
  --text: #e0e0f0;
  --text-dim: #7878a0;
  --green: #3dff8a;
  --yellow: #ffd23d;
  --red: #ff5c5c;
  --purple: #9d5cff;
  --blue: #3dd8ff;
  --pink: #ff5caa;
  --orange: #f39c12;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  background: var(--bg);
  color: var(--text);
  font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace;
  font-size: 14px;
  line-height: 1.5;
  padding: 16px;
  max-width: 1200px;
  margin: 0 auto;
}

/* Header */
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 12px;
  margin-bottom: 16px;
}
.header h1 {
  font-size: 18px;
  font-weight: 600;
  background: linear-gradient(135deg, var(--purple), var(--blue));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}
.clock {
  color: var(--text-dim);
  font-size: 13px;
}
.conn-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--red);
  transition: background 0.3s;
}
.conn-dot.connected {
  background: var(--green);
  box-shadow: 0 0 8px var(--green);
}
.conn-dot.reconnecting {
  background: var(--yellow);
  animation: pulse 1s infinite;
}

/* Agent cards grid */
.agents-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}
.agent-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 14px;
  transition: border-color 0.3s, box-shadow 0.3s;
  min-height: 140px;
}
.agent-card.working {
  border-color: var(--green);
  box-shadow: 0 0 12px rgba(61, 255, 138, 0.15);
}
.agent-card.queued {
  border-color: var(--yellow);
}
.agent-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.agent-icon {
  font-size: 22px;
}
.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--text-dim);
}
.status-dot.working {
  background: var(--green);
  box-shadow: 0 0 6px var(--green);
  animation: pulse 2s infinite;
}
.status-dot.queued {
  background: var(--yellow);
}
.agent-name {
  font-weight: 600;
  font-size: 14px;
  margin-bottom: 2px;
}
.agent-role {
  color: var(--text-dim);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 1px;
  margin-bottom: 8px;
}
.progress-bar {
  height: 4px;
  background: var(--border);
  border-radius: 2px;
  margin-bottom: 6px;
  overflow: hidden;
  display: none;
}
.progress-bar.active { display: block; }
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--green), var(--blue));
  border-radius: 2px;
  transition: width 0.5s;
}
.agent-task {
  font-size: 11px;
  color: var(--text-dim);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.agent-task.active {
  color: var(--text);
}
.agent-time {
  font-size: 10px;
  color: var(--text-dim);
  margin-top: 2px;
}
.agent-stats {
  font-size: 10px;
  color: var(--text-dim);
  margin-top: 4px;
}

/* Info panels */
.panels {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 12px;
  margin-bottom: 16px;
}
.panel {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 14px;
}
.panel-title {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: var(--text-dim);
  margin-bottom: 8px;
}
.panel-value {
  font-size: 20px;
  font-weight: 700;
}
.panel-sub {
  font-size: 11px;
  color: var(--text-dim);
  margin-top: 4px;
}
.panel-row {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  padding: 3px 0;
  border-bottom: 1px solid var(--border);
}
.panel-row:last-child { border-bottom: none; }

/* Live feed */
.feed {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 14px;
}
.feed-title {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: var(--text-dim);
  margin-bottom: 10px;
}
.feed-list {
  max-height: 300px;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: var(--border) transparent;
}
.feed-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 6px 0;
  border-bottom: 1px solid rgba(30, 30, 48, 0.5);
  font-size: 12px;
  animation: fadeIn 0.3s ease-in;
}
.feed-item:last-child { border-bottom: none; }
.feed-time {
  color: var(--text-dim);
  font-size: 11px;
  white-space: nowrap;
  min-width: 60px;
}
.feed-icon { font-size: 14px; min-width: 20px; }
.feed-text { flex: 1; }
.feed-text .agent-ref { color: var(--purple); font-weight: 500; }
.feed-text .task-ref { color: var(--blue); }
.feed-text .success { color: var(--green); }
.feed-text .duration { color: var(--text-dim); }

/* Animations */
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(-4px); }
  to { opacity: 1; transform: translateY(0); }
}

/* Responsive */
@media (max-width: 768px) {
  .agents-grid { grid-template-columns: repeat(2, 1fr); }
  .panels { grid-template-columns: 1fr; }
  body { padding: 8px; }
}
@media (max-width: 480px) {
  .agents-grid { grid-template-columns: 1fr; }
}
</style>
</head>
<body>

<div class="header">
  <h1>ZININ CORP MONITOR</h1>
  <div class="header-right">
    <span class="clock" id="clock">--:--:--</span>
    <div class="conn-dot" id="conn-dot" title="SSE connection"></div>
  </div>
</div>

<div class="agents-grid" id="agents-grid">
  <!-- Filled by JS -->
</div>

<div class="panels">
  <div class="panel" id="panel-pool">
    <div class="panel-title">Task Pool</div>
    <div id="pool-content">--</div>
  </div>
  <div class="panel" id="panel-api">
    <div class="panel-title">API Usage (1h)</div>
    <div id="api-content">--</div>
  </div>
  <div class="panel" id="panel-quality">
    <div class="panel-title">Quality (7d)</div>
    <div id="quality-content">--</div>
  </div>
</div>

<div class="feed">
  <div class="feed-title">Live Activity Feed</div>
  <div class="feed-list" id="feed-list">
    <div class="feed-item">
      <span class="feed-time">--:--</span>
      <span class="feed-text">Connecting...</span>
    </div>
  </div>
</div>

<script>
const AGENTS = {
  manager:    {name:"Алексей",  icon:"👑", role:"CEO",    color:"#9d5cff", flag:"🇷🇺"},
  accountant: {name:"Маттиас",  icon:"🏦", role:"CFO",    color:"#f39c12", flag:"🇨🇭"},
  automator:  {name:"Мартин",   icon:"⚙️",  role:"CTO",    color:"#3dd8ff", flag:"🇦🇷"},
  smm:        {name:"Юки",      icon:"📱", role:"SMM",    color:"#ff5caa", flag:"🇰🇷"},
  designer:   {name:"Райан",    icon:"🎨", role:"Design", color:"#ffd23d", flag:"🇺🇸"},
  cpo:        {name:"Софи",     icon:"📋", role:"CPO",    color:"#3dff8a", flag:"🇩🇰"},
};

const AGENT_ORDER = ["manager","accountant","automator","smm","designer","cpo"];

const EVENT_ICONS = {
  task_start: "▶️",
  task_end: "✅",
  communication: "💬",
  delegation: "📨",
  quality_score: "⭐",
};

let STATE = {agents:{}, events:[], quality:{}, api_usage:{}, task_pool:{}, active_tasks:[], alerts:[]};

// ── Clock ──
function updateClock() {
  const now = new Date();
  document.getElementById("clock").textContent =
    now.toLocaleTimeString("ru-RU", {hour:"2-digit", minute:"2-digit", second:"2-digit"});
}
setInterval(updateClock, 1000);
updateClock();

// ── Init ──
async function init() {
  try {
    const resp = await fetch("/api/snapshot");
    const data = await resp.json();
    applySnapshot(data);
  } catch(e) {
    console.error("Initial fetch failed:", e);
  }
  connectSSE();
}

// ── SSE ──
function connectSSE() {
  const dot = document.getElementById("conn-dot");
  const es = new EventSource("/api/stream");

  es.addEventListener("update", (e) => {
    try {
      const data = JSON.parse(e.data);
      applySnapshot(data);
    } catch(err) { console.error("SSE parse error:", err); }
  });

  es.onopen = () => {
    dot.className = "conn-dot connected";
    dot.title = "Connected";
  };

  es.onerror = () => {
    dot.className = "conn-dot reconnecting";
    dot.title = "Reconnecting...";
  };
}

// ── Apply snapshot ──
function applySnapshot(data) {
  STATE.agents = data.agents || {};
  STATE.events = data.events || [];
  STATE.quality = data.quality || {};
  STATE.api_usage = data.api_usage || {};
  STATE.task_pool = data.task_pool || {};
  STATE.active_tasks = data.active_tasks || [];
  STATE.alerts = data.alerts || [];

  renderAgentCards();
  renderFeed();
  renderPoolPanel();
  renderApiPanel();
  renderQualityPanel();
}

// ── Agent Cards ──
function renderAgentCards() {
  const grid = document.getElementById("agents-grid");
  let html = "";

  for (const key of AGENT_ORDER) {
    const meta = AGENTS[key];
    const s = STATE.agents[key] || {};
    const status = s.status || "idle";
    const task = s.task || "";
    const progress = s.progress;
    const tasks24h = s.tasks_24h || 0;
    const startedAt = s.started_at || "";

    let elapsed = "";
    if (status === "working" && startedAt) {
      const sec = Math.floor((Date.now() - new Date(startedAt).getTime()) / 1000);
      elapsed = sec >= 60 ? Math.floor(sec/60) + "m " + (sec%60) + "s" : sec + "s";
    }

    const lastInfo = s.last_task
      ? `Last: ${truncate(s.last_task, 25)}` + (s.last_task_duration_sec ? ` (${s.last_task_duration_sec}s)` : "")
      : "";

    html += `
      <div class="agent-card ${status}">
        <div class="agent-top">
          <span class="agent-icon">${meta.icon}</span>
          <span class="status-dot ${status}"></span>
        </div>
        <div class="agent-name">${meta.name} ${meta.flag}</div>
        <div class="agent-role">${meta.role}</div>
        <div class="progress-bar ${status === 'working' && progress != null ? 'active' : ''}">
          <div class="progress-fill" style="width:${progress != null ? Math.round(progress*100) : 0}%"></div>
        </div>
        <div class="agent-task ${status === 'working' ? 'active' : ''}">${
          status === "working" ? truncate(task, 30) : (status === "idle" ? "idle" : status)
        }</div>
        ${elapsed ? `<div class="agent-time">${elapsed}</div>` : ""}
        <div class="agent-stats">${lastInfo}</div>
      </div>`;
  }
  grid.innerHTML = html;
}

// ── Feed ──
function renderFeed() {
  const list = document.getElementById("feed-list");
  if (!STATE.events.length) {
    list.innerHTML = '<div class="feed-item"><span class="feed-text" style="color:var(--text-dim)">No events yet</span></div>';
    return;
  }

  let html = "";
  // Events are newest-first (already sorted by activity_tracker)
  const events = STATE.events.slice(0, 50);

  for (const ev of events) {
    const time = formatTime(ev.timestamp);
    const type = ev.type || "unknown";
    const icon = EVENT_ICONS[type] || "📌";
    const agentKey = ev.agent || "";
    const agentMeta = AGENTS[agentKey] || {};
    const agentName = agentMeta.name || agentKey;

    let text = "";
    if (type === "task_start") {
      text = `<span class="agent-ref">${agentName}</span> started <span class="task-ref">"${truncate(ev.task || ev.description || "", 40)}"</span>`;
    } else if (type === "task_end") {
      const dur = ev.duration_sec ? ` <span class="duration">(${ev.duration_sec}s)</span>` : "";
      const ok = ev.success !== false ? ' <span class="success">OK</span>' : ' <span style="color:var(--red)">FAIL</span>';
      text = `<span class="agent-ref">${agentName}</span> completed <span class="task-ref">"${truncate(ev.task || ev.description || "", 35)}"</span>${dur}${ok}`;
    } else if (type === "communication") {
      const toMeta = AGENTS[ev.to_agent || ""] || {};
      text = `<span class="agent-ref">${agentName}</span> → <span class="agent-ref">${toMeta.name || ev.to_agent || "?"}</span> ${truncate(ev.description || "", 35)}`;
    } else if (type === "delegation") {
      const toMeta = AGENTS[ev.to_agent || ""] || {};
      text = `<span class="agent-ref">${agentName}</span> delegated to <span class="agent-ref">${toMeta.name || ev.to_agent || "?"}</span>: <span class="task-ref">"${truncate(ev.task || ev.description || "", 30)}"</span>`;
    } else if (type === "quality_score") {
      const score = ev.score != null ? ev.score.toFixed(2) : "?";
      text = `<span class="agent-ref">${agentName}</span> quality: ${score} for "${truncate(ev.task || "", 30)}"`;
    } else {
      text = `<span class="agent-ref">${agentName}</span> ${truncate(ev.description || type, 40)}`;
    }

    html += `<div class="feed-item"><span class="feed-time">${time}</span><span class="feed-icon">${icon}</span><span class="feed-text">${text}</span></div>`;
  }
  list.innerHTML = html;
}

// ── Task Pool Panel ──
function renderPoolPanel() {
  const el = document.getElementById("pool-content");
  const p = STATE.task_pool;
  if (!p || !p.total) {
    el.innerHTML = '<span style="color:var(--text-dim)">Empty</span>';
    return;
  }

  const todo = p.TODO || 0;
  const prog = p.IN_PROGRESS || 0;
  const blocked = p.BLOCKED || 0;
  const done = p.DONE || 0;
  const assigned = p.ASSIGNED || 0;

  el.innerHTML = `
    <div class="panel-value">${p.total}</div>
    <div class="panel-sub">tasks total</div>
    <div style="margin-top:8px">
      <div class="panel-row"><span>TODO</span><span>${todo}</span></div>
      <div class="panel-row"><span>ASSIGNED</span><span>${assigned}</span></div>
      <div class="panel-row"><span>IN PROGRESS</span><span style="color:var(--blue)">${prog}</span></div>
      <div class="panel-row"><span>BLOCKED</span><span style="color:var(--yellow)">${blocked}</span></div>
      <div class="panel-row"><span>DONE</span><span style="color:var(--green)">${done}</span></div>
    </div>`;
}

// ── API Panel ──
function renderApiPanel() {
  const el = document.getElementById("api-content");
  const u = STATE.api_usage;
  if (!u || !Object.keys(u).length) {
    el.innerHTML = '<span style="color:var(--text-dim)">No data</span>';
    return;
  }

  let totalCalls = 0;
  let totalCost = 0;
  let rows = "";

  const COST = {openrouter:0.003, elevenlabs:0.015, openai:0.002, coingecko:0, groq:0};

  for (const [provider, data] of Object.entries(u)) {
    const count = data.count || 0;
    const avgMs = data.avg_latency_ms || 0;
    totalCalls += count;
    totalCost += count * (COST[provider] || 0);
    if (count > 0) {
      rows += `<div class="panel-row"><span>${provider}</span><span>${count} / ${Math.round(avgMs)}ms</span></div>`;
    }
  }

  el.innerHTML = `
    <div class="panel-value">${totalCalls}</div>
    <div class="panel-sub">calls ~$${totalCost.toFixed(3)}</div>
    <div style="margin-top:8px">${rows || '<div class="panel-row"><span>No calls</span><span>-</span></div>'}</div>`;
}

// ── Quality Panel ──
function renderQualityPanel() {
  const el = document.getElementById("quality-content");
  const q = STATE.quality;
  if (!q || !q.count) {
    el.innerHTML = '<span style="color:var(--text-dim)">No scores yet</span>';
    return;
  }

  const avg = q.avg != null ? q.avg.toFixed(2) : "?";
  const passed = q.passed_pct != null ? Math.round(q.passed_pct) : "?";
  const count = q.count || 0;

  let agentRows = "";
  if (q.by_agent) {
    for (const [key, data] of Object.entries(q.by_agent)) {
      const meta = AGENTS[key] || {};
      agentRows += `<div class="panel-row"><span>${meta.icon || ""} ${meta.name || key}</span><span>${data.avg != null ? data.avg.toFixed(2) : "?"}</span></div>`;
    }
  }

  el.innerHTML = `
    <div class="panel-value">${avg}</div>
    <div class="panel-sub">${count} scores, ${passed}% passed</div>
    <div style="margin-top:8px">${agentRows}</div>`;
}

// ── Helpers ──
function truncate(s, n) {
  if (!s) return "";
  return s.length > n ? s.slice(0, n) + "..." : s;
}

function formatTime(ts) {
  if (!ts) return "--:--";
  try {
    const d = new Date(ts);
    return d.toLocaleTimeString("ru-RU", {hour:"2-digit", minute:"2-digit", second:"2-digit"});
  } catch(e) { return ts.slice(11, 19) || "--:--"; }
}

// ── Start ──
init();
</script>
</body>
</html>"""
