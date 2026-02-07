"""
🎮 Zinin Corp — Agent Dashboard
Interactive visualization of multi-agent system behavior and task tracking.
Generates self-contained HTML/CSS/JS dashboard for Streamlit embedding.
"""

import json


def generate_dashboard_html(completed_count=0, agent_statuses=None, recent_events=None):
    """Generate self-contained HTML dashboard.

    Args:
        completed_count: Initial completed tasks counter.
        agent_statuses: Dict of agent statuses from activity_tracker (optional).
        recent_events: List of recent events from activity_tracker (optional).

    Returns:
        Complete HTML string ready for st_components.html().
    """
    initial_data = json.dumps({
        "completedCount": completed_count,
        "agentStatuses": agent_statuses or {},
        "recentEvents": recent_events or [],
    }, default=str, ensure_ascii=False)
    return _HTML_TEMPLATE.replace("__INITIAL_DATA__", initial_data)


_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#08080d;color:#e8e8f0;font-family:'Segoe UI',system-ui,-apple-system,sans-serif;overflow:hidden}

/* ── Header ── */
.dash-header{padding:14px 20px 10px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;border-bottom:1px solid #1a1a26}
.dash-header-left{display:flex;align-items:center;gap:12px}
.dash-title{font-size:20px;font-weight:800;letter-spacing:-0.5px}
.dash-title .gradient{background:linear-gradient(135deg,#9d5cff,#3dd8ff);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.scenario-badge{background:#12121a;border:1px solid #2a2a3a;border-radius:6px;padding:3px 10px;font-size:11px;color:#9d5cff;font-weight:600}
.dash-controls{display:flex;gap:8px;align-items:center}
.completed-label{font-size:12px;color:#555}
.completed-val{color:#3dff8a;font-weight:700}
.ctrl-btn{border-radius:6px;padding:4px 12px;font-size:12px;font-weight:600;cursor:pointer;border:1px solid;transition:all .2s}
.ctrl-btn:hover{filter:brightness(1.2)}
.toggle-btn-run{background:rgba(255,64,87,.1);border-color:#ff405733;color:#ff4057}
.toggle-btn-pause{background:rgba(61,255,138,.1);border-color:#3dff8a33;color:#3dff8a}
.scenario-btn{background:transparent;border:1px solid #2a2a3a;color:#555;border-radius:6px;padding:4px 10px;font-size:11px;cursor:pointer;font-weight:500;transition:all .2s}
.scenario-btn:hover{border-color:#9d5cff44;color:#9d5cff}
.scenario-btn.active{background:rgba(157,92,255,.12);border-color:#9d5cff44;color:#9d5cff}

/* ── Layout ── */
.dash-body{display:flex;height:calc(100vh - 50px)}
.dash-canvas{flex:1;position:relative;padding:24px 20px 20px;overflow:hidden}
.dash-sidebar{width:300px;border-left:1px solid #1a1a26;display:flex;flex-direction:column;overflow:hidden;flex-shrink:0}

/* ── Agent cards row ── */
.agents-row{display:flex;gap:14px;justify-content:center;flex-wrap:wrap;position:relative;z-index:10}
.agent-col{display:flex;flex-direction:column;align-items:center;gap:0}

/* Task label floating above */
.task-label-container{min-height:44px;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;margin-bottom:6px;transition:opacity .3s;opacity:0}
.task-label{border-radius:8px;padding:5px 12px;display:flex;align-items:center;gap:6px;animation:floatLabel 2s ease infinite}
.task-label-line{width:1px;height:8px}

/* Agent card */
.agent-card{background:#0f0f18;border:1.5px solid #1e1e2e;border-radius:16px;padding:18px 16px 14px;width:170px;text-align:center;position:relative;transition:border-color .4s,box-shadow .4s}
.status-dot{position:absolute;top:10px;right:10px;width:9px;height:9px;border-radius:50%;background:#555;transition:all .3s}
.agent-avatar{width:52px;height:52px;border-radius:14px;display:flex;align-items:center;justify-content:center;font-size:26px;margin:0 auto 8px;transition:transform .3s}
.agent-name{font-size:14px;font-weight:700;margin-bottom:1px}
.agent-role{font-size:10px;color:#555;margin-bottom:8px}
.status-badge{display:inline-flex;align-items:center;gap:4px;border-radius:100px;padding:2px 9px;font-size:10px;font-weight:500;background:rgba(85,85,85,.1);border:1px solid rgba(85,85,85,.13);color:#555;transition:all .3s}

/* Progress bar inside card */
.progress-container{margin-top:10px;display:none}
.progress-header{display:flex;justify-content:space-between;margin-bottom:3px}
.progress-label{font-size:9px;color:#555}
.progress-pct{font-size:9px;font-weight:700;font-family:monospace;color:#555}
.progress-track{height:4px;border-radius:2px;background:#1a1a26;overflow:hidden}
.progress-bar-fill{height:100%;border-radius:2px;width:0%;transition:width .15s linear}

/* ── SVG trails ── */
.trails-svg{position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:50}

/* ── Balls container ── */
.balls-container{position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:100}

/* ── Sidebar ── */
.sidebar-section{padding:16px;border-bottom:1px solid #1a1a26}
.sidebar-title{font-size:10px;font-weight:700;color:#555;letter-spacing:2px;text-transform:uppercase;margin-bottom:12px}
.sidebar-agents{display:flex;flex-direction:column;gap:8px}
.sidebar-agent{background:#0c0c14;border:1px solid #1a1a26;border-radius:10px;padding:10px 12px;transition:all .3s}
.sidebar-agent-header{display:flex;align-items:center;justify-content:space-between}
.sidebar-agent-left{display:flex;align-items:center;gap:8px}
.sidebar-agent-icon{font-size:18px}
.sidebar-agent-name{font-size:12px;font-weight:700;line-height:1.2}
.sidebar-agent-info{font-size:10px;color:#444}
.sidebar-agent-pct{display:none;font-size:14px;font-weight:800;font-family:monospace;min-width:40px;text-align:right}
.sidebar-agent-dot{width:8px;height:8px;border-radius:50%;background:#333}
.sidebar-agent-bar{display:none;margin-top:6px;height:4px;border-radius:2px;background:#1a1a26;overflow:hidden}
.sidebar-bar-fill{height:100%;border-radius:2px;width:0%;transition:width .15s linear}

/* Task legend */
.legend-row{display:flex;flex-wrap:wrap;gap:4px}
.legend-item{display:inline-flex;align-items:center;gap:3px;border-radius:5px;padding:2px 7px;font-size:10px}

/* Activity log */
.log-section{flex:1;padding:16px;overflow:auto}
.log-container{display:flex;flex-direction:column;gap:3px}
.log-entry{display:flex;align-items:flex-start;gap:6px;padding:3px 6px;border-radius:5px}
.log-time{font-family:monospace;font-size:9px;color:#444;flex-shrink:0;margin-top:1px}
.log-dot{width:4px;height:4px;border-radius:50%;flex-shrink:0;margin-top:4px}
.log-text{font-size:11px;color:#888;line-height:1.3}

/* ── Animations ── */
@keyframes dotPulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.4;transform:scale(.7)}}
@keyframes floatLabel{0%,100%{transform:translateY(0)}50%{transform:translateY(-3px)}}

/* Scrollbar */
::-webkit-scrollbar{width:4px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:#2a2a3a;border-radius:4px}
</style>
</head>
<body>

<!-- ════════════════════ HEADER ════════════════════ -->
<div class="dash-header">
  <div class="dash-header-left">
    <div class="dash-title"><span class="gradient">Zinin Corp</span> Dashboard</div>
    <div class="scenario-badge" id="scenario-label">Ожидание событий</div>
  </div>
  <div class="dash-controls">
    <div class="completed-label">Выполнено: <span class="completed-val" id="completed-count">0</span></div>
    <button class="ctrl-btn toggle-btn-pause" id="toggle-btn" onclick="toggleRunning()" style="display:none">▶ Старт</button>
    <button class="scenario-btn" id="scenario-btn-0" onclick="selectScenario(0)">Демо: SMM</button>
    <button class="scenario-btn" id="scenario-btn-1" onclick="selectScenario(1)">Демо: Финансы</button>
    <button class="scenario-btn" id="scenario-btn-2" onclick="selectScenario(2)">Демо: Полный</button>
  </div>
</div>

<!-- ════════════════════ BODY ════════════════════ -->
<div class="dash-body">

  <!-- Canvas area -->
  <div class="dash-canvas" id="canvas">
    <div class="agents-row" id="agents-row"></div>
    <svg class="trails-svg" id="trails-svg"></svg>
    <div class="balls-container" id="balls-container"></div>
  </div>

  <!-- Sidebar -->
  <div class="dash-sidebar">
    <!-- Agent jobs -->
    <div class="sidebar-section">
      <div class="sidebar-title">Текущие задачи агентов</div>
      <div class="sidebar-agents" id="sidebar-agents"></div>
    </div>
    <!-- Task legend -->
    <div class="sidebar-section">
      <div class="sidebar-title">Типы задач</div>
      <div class="legend-row" id="legend-row"></div>
    </div>
    <!-- Log -->
    <div class="log-section">
      <div class="sidebar-title">Лог активности</div>
      <div class="log-container" id="log-container">
        <div style="color:#333;font-size:11px;font-style:italic">Ожидание...</div>
      </div>
    </div>
  </div>
</div>

<script>
// ═══════════════════════════════════════════════
// INITIAL DATA (injected from Python)
// ═══════════════════════════════════════════════
const INITIAL = __INITIAL_DATA__;

// ═══════════════════════════════════════════════
// CONFIGURATION
// ═══════════════════════════════════════════════
const AGENTS = [
  { id:"manager",    name:"Алексей",  icon:"👑", color:"#9d5cff", role:"CEO · Координация",  flag:"🇷🇺" },
  { id:"accountant", name:"Маттиас",  icon:"🏦", color:"#f39c12", role:"CFO · Финансы",      flag:"🇨🇭" },
  { id:"smm",        name:"Юки",      icon:"📱", color:"#ff5caa", role:"SMM · Контент",      flag:"🇰🇷" },
  { id:"automator",  name:"Мартин",   icon:"⚙️", color:"#3dd8ff", role:"CTO · Техника",      flag:"🇦🇷" },
];

const TASK_TYPES = [
  { type:"content",  label:"Контент-план", color:"#ff5caa", emoji:"📝" },
  { type:"design",   label:"Дизайн",       color:"#ffd23d", emoji:"🖼" },
  { type:"report",   label:"Отчёт",        color:"#3dff8a", emoji:"📊" },
  { type:"api",      label:"API запрос",   color:"#3dd8ff", emoji:"🔌" },
  { type:"strategy", label:"Стратегия",    color:"#9d5cff", emoji:"🎯" },
  { type:"post",     label:"Пост",         color:"#ff8a3d", emoji:"📮" },
];

const SCENARIOS = [
  {
    name: "SMM-кампания",
    steps: [
      { from:"manager", to:"smm",       task:"content",  delay:0,     duration:3200, workDuration:3500 },
      { from:"smm",     to:"manager",   task:"post",     delay:7000,  duration:2800, workDuration:3000 },
      { from:"manager", to:"accountant", task:"strategy", delay:13000, duration:2600, workDuration:2500 },
    ],
  },
  {
    name: "Финансовый отчёт",
    steps: [
      { from:"manager",    to:"accountant", task:"report", delay:0,     duration:2800, workDuration:4000 },
      { from:"accountant", to:"automator",  task:"api",    delay:7200,  duration:2600, workDuration:3500 },
      { from:"automator",  to:"accountant", task:"report", delay:13600, duration:2400, workDuration:3000 },
      { from:"accountant", to:"manager",    task:"report", delay:19300, duration:2600, workDuration:2000 },
    ],
  },
  {
    name: "Полный цикл",
    steps: [
      { from:"manager",    to:"smm",       task:"content",  delay:0,     duration:2600, workDuration:4000 },
      { from:"manager",    to:"accountant", task:"report",   delay:800,   duration:3000, workDuration:4500 },
      { from:"smm",        to:"automator",  task:"api",      delay:7000,  duration:2400, workDuration:3500 },
      { from:"accountant", to:"automator",  task:"api",      delay:8500,  duration:2600, workDuration:3000 },
      { from:"automator",  to:"manager",    task:"strategy", delay:14400, duration:2200, workDuration:2000 },
    ],
  },
];

// ═══════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════
const S = {
  activeBalls: [],
  agentJobs: {},
  currentScenario: 0,
  isRunning: false,
  completedTasks: INITIAL.completedCount || 0,
  logEntries: [],
  ballId: 0,
  jobId: 0,
  timeouts: [],
};

// ═══════════════════════════════════════════════
// UTILS
// ═══════════════════════════════════════════════
function ease(t) { return t < .5 ? 4*t*t*t : 1 - Math.pow(-2*t+2, 3)/2; }
function lerp(a, b, t) { return a + (b - a) * t; }
function findTask(type) { return TASK_TYPES.find(t => t.type === type) || TASK_TYPES[0]; }
function findAgent(id) { return AGENTS.find(a => a.id === id); }

function getPos(agentId) {
  var el = document.getElementById("acard-" + agentId);
  var c  = document.getElementById("canvas");
  if (!el || !c) return {x:0, y:0};
  var er = el.getBoundingClientRect(), cr = c.getBoundingClientRect();
  return { x: er.left - cr.left + er.width/2, y: er.top - cr.top + er.height/2 };
}

const STATUS_CFG = {
  idle:      { color:"#555",    label:"Свободен",   pulse:false },
  sending:   { color:"#9d5cff", label:"Отправляет", pulse:true  },
  working:   { color:"#3dff8a", label:"Работает",   pulse:true  },
  receiving: { color:"#3dd8ff", label:"Получает",   pulse:true  },
};

// ═══════════════════════════════════════════════
// BUILD DOM
// ═══════════════════════════════════════════════
function buildAgentCards() {
  var row = document.getElementById("agents-row");
  AGENTS.forEach(function(a) {
    var col = document.createElement("div");
    col.className = "agent-col";
    col.innerHTML =
      '<div class="task-label-container" id="tlabel-'+a.id+'"></div>' +
      '<div class="agent-card" id="acard-'+a.id+'">' +
        '<div class="status-dot" id="sdot-'+a.id+'"></div>' +
        '<div class="agent-avatar" id="avatar-'+a.id+'" style="background:'+a.color+'12;border:2px solid '+a.color+'28">' +
          '<span>'+a.icon+'</span>' +
        '</div>' +
        '<div class="agent-name">'+a.name+' <span style="font-size:10px;color:#555">'+a.flag+'</span></div>' +
        '<div class="agent-role">'+a.role+'</div>' +
        '<div class="status-badge" id="badge-'+a.id+'">Свободен</div>' +
        '<div class="progress-container" id="cprog-'+a.id+'">' +
          '<div class="progress-header">' +
            '<span class="progress-label" id="cplabel-'+a.id+'">Прогресс</span>' +
            '<span class="progress-pct" id="cppct-'+a.id+'">0%</span>' +
          '</div>' +
          '<div class="progress-track"><div class="progress-bar-fill" id="cpbar-'+a.id+'"></div></div>' +
        '</div>' +
      '</div>';
    row.appendChild(col);
  });
}

function buildSidebar() {
  var container = document.getElementById("sidebar-agents");
  AGENTS.forEach(function(a) {
    var el = document.createElement("div");
    el.className = "sidebar-agent";
    el.id = "sagent-" + a.id;
    el.innerHTML =
      '<div class="sidebar-agent-header">' +
        '<div class="sidebar-agent-left">' +
          '<span class="sidebar-agent-icon">'+a.icon+'</span>' +
          '<div>' +
            '<div class="sidebar-agent-name">'+a.name+'</div>' +
            '<div class="sidebar-agent-info" id="sinfo-'+a.id+'">Ожидает задач</div>' +
          '</div>' +
        '</div>' +
        '<div class="sidebar-agent-pct" id="spct-'+a.id+'"></div>' +
        '<div class="sidebar-agent-dot" id="sdot2-'+a.id+'"></div>' +
      '</div>' +
      '<div class="sidebar-agent-bar" id="sbar-'+a.id+'">' +
        '<div class="sidebar-bar-fill" id="sfill-'+a.id+'"></div>' +
      '</div>';
    container.appendChild(el);
  });

  // Legend
  var legend = document.getElementById("legend-row");
  TASK_TYPES.forEach(function(t) {
    var item = document.createElement("div");
    item.className = "legend-item";
    item.style.cssText = "background:"+t.color+"0c;border:1px solid "+t.color+"1a;color:"+t.color;
    item.textContent = t.emoji + " " + t.label;
    legend.appendChild(item);
  });
}

// ═══════════════════════════════════════════════
// LOG
// ═══════════════════════════════════════════════
function addLog(text, color) {
  var now = new Date();
  var time = now.toLocaleTimeString("ru-RU", {hour:"2-digit",minute:"2-digit",second:"2-digit"});
  S.logEntries.unshift({ text:text, color:color, time:time, id:Date.now()+Math.random() });
  if (S.logEntries.length > 20) S.logEntries.length = 20;
  renderLog();
}

function renderLog() {
  var c = document.getElementById("log-container");
  if (!c) return;
  if (!S.logEntries.length) { c.innerHTML = '<div style="color:#333;font-size:11px;font-style:italic">Ожидание...</div>'; return; }
  var h = "";
  S.logEntries.forEach(function(e, i) {
    var op = Math.max(.3, 1 - i*.05);
    var bg = i === 0 ? e.color+"08" : "transparent";
    h += '<div class="log-entry" style="background:'+bg+';opacity:'+op+'">' +
      '<span class="log-time">'+e.time+'</span>' +
      '<div class="log-dot" style="background:'+e.color+'"></div>' +
      '<span class="log-text">'+e.text+'</span></div>';
  });
  c.innerHTML = h;
}

// ═══════════════════════════════════════════════
// UPDATE AGENT VISUALS
// ═══════════════════════════════════════════════
function updateCard(agentId) {
  var a = findAgent(agentId);
  var job = S.agentJobs[agentId];
  var st = job ? job.status : "idle";
  var sc = STATUS_CFG[st] || STATUS_CFG.idle;

  // Card border & shadow
  var card = document.getElementById("acard-" + agentId);
  if (card) {
    card.style.borderColor = st !== "idle" ? sc.color+"44" : "#1e1e2e";
    card.style.boxShadow = st !== "idle" ? "0 0 30px "+sc.color+"15, inset 0 0 24px "+sc.color+"06" : "none";
  }

  // Status dot
  var dot = document.getElementById("sdot-" + agentId);
  if (dot) {
    dot.style.background = sc.color;
    dot.style.boxShadow = sc.pulse ? "0 0 8px "+sc.color : "none";
    dot.style.animation = sc.pulse ? "dotPulse 1.4s ease infinite" : "none";
  }

  // Avatar scale
  var av = document.getElementById("avatar-" + agentId);
  if (av) av.style.transform = st !== "idle" ? "scale(1.06)" : "scale(1)";

  // Badge
  var badge = document.getElementById("badge-" + agentId);
  if (badge) {
    badge.style.background = sc.color + (st !== "idle" ? "15" : "0a");
    badge.style.borderColor = sc.color + "22";
    badge.style.color = sc.color;
    badge.textContent = sc.label;
  }

  // Floating label
  var tlabel = document.getElementById("tlabel-" + agentId);
  if (tlabel) {
    if (job) {
      tlabel.style.opacity = "1";
      tlabel.innerHTML =
        '<div class="task-label" style="background:'+job.task.color+'15;border:1px solid '+job.task.color+'33">' +
          '<span style="font-size:14px">'+job.task.emoji+'</span>' +
          '<span style="font-size:11px;font-weight:600;color:'+job.task.color+'">'+job.task.label+'</span>' +
        '</div>' +
        '<div class="task-label-line" style="background:'+job.task.color+'44"></div>';
    } else {
      tlabel.style.opacity = "0";
    }
  }

  // Progress bar
  var cprog = document.getElementById("cprog-" + agentId);
  if (cprog) cprog.style.display = job ? "block" : "none";
  if (job) {
    var lbl = document.getElementById("cplabel-" + agentId);
    if (lbl) lbl.textContent = job.status === "working" ? "Прогресс" : "Передача";
  }
}

function updateSidebar(agentId) {
  var job = S.agentJobs[agentId];
  var st = job ? job.status : "idle";
  var sc = STATUS_CFG[st] || STATUS_CFG.idle;

  var el = document.getElementById("sagent-" + agentId);
  if (el) {
    el.style.background = job ? sc.color+"08" : "#0c0c14";
    el.style.borderColor = job ? sc.color+"22" : "#1a1a26";
  }

  var info = document.getElementById("sinfo-" + agentId);
  if (info) {
    if (job) {
      var act = job.status === "working" ? "Выполняет" : "Передаёт";
      info.innerHTML = '<span style="color:'+sc.color+';font-weight:500">'+act+': '+job.task.emoji+' '+job.task.label+'</span>';
    } else {
      info.innerHTML = '<span style="color:#444">Ожидает задач</span>';
    }
  }

  var pctEl  = document.getElementById("spct-" + agentId);
  var dotEl  = document.getElementById("sdot2-" + agentId);
  var barEl  = document.getElementById("sbar-" + agentId);
  if (job) {
    if (pctEl) { pctEl.style.display = "block"; pctEl.style.color = sc.color; }
    if (dotEl) dotEl.style.display = "none";
    if (barEl) {
      barEl.style.display = "block";
      var fill = document.getElementById("sfill-" + agentId);
      if (fill) {
        fill.style.background = "linear-gradient(90deg,"+sc.color+","+sc.color+"66)";
        fill.style.boxShadow = "0 0 8px "+sc.color+"33";
      }
    }
  } else {
    if (pctEl) pctEl.style.display = "none";
    if (dotEl) dotEl.style.display = "block";
    if (barEl) barEl.style.display = "none";
  }
}

function refreshAgent(agentId) {
  updateCard(agentId);
  updateSidebar(agentId);
}

// ═══════════════════════════════════════════════
// BALL LAUNCHER
// ═══════════════════════════════════════════════
function launchBall(from, to, taskType, duration, workDuration) {
  var id = ++S.ballId;
  var task = findTask(taskType);
  var fa = findAgent(from), ta = findAgent(to);

  addLog(fa.icon+" → "+task.emoji+" "+task.label+" → "+ta.icon, task.color);

  // Sender → "sending"
  var sjid = ++S.jobId;
  S.agentJobs[from] = { status:"sending", task:task, toAgent:ta.name, startTime:performance.now(), duration:duration, jobId:sjid };
  refreshAgent(from);

  // Create ball
  S.activeBalls.push({ id:id, from:from, to:to, task:task, startTime:performance.now(), duration:duration, progress:0 });

  // When ball arrives
  setTimeout(function() {
    S.activeBalls = S.activeBalls.filter(function(b){return b.id !== id;});
    if (S.agentJobs[from] && S.agentJobs[from].jobId === sjid) {
      delete S.agentJobs[from];
      refreshAgent(from);
    }
    // Receiver → "working"
    var wjid = ++S.jobId;
    S.agentJobs[to] = { status:"working", task:task, startTime:performance.now(), duration:workDuration, jobId:wjid };
    refreshAgent(to);
    addLog(ta.icon+" "+ta.name+": работает над «"+task.label+"»", ta.color);

    // Work done
    setTimeout(function() {
      if (S.agentJobs[to] && S.agentJobs[to].jobId === wjid) {
        delete S.agentJobs[to];
        refreshAgent(to);
      }
      S.completedTasks++;
      var cc = document.getElementById("completed-count");
      if (cc) cc.textContent = S.completedTasks;
      addLog("✅ "+ta.icon+" "+ta.name+": завершил «"+task.label+"»", "#3dff8a");
    }, workDuration);
  }, duration);
}

// ═══════════════════════════════════════════════
// SCENARIO RUNNER
// ═══════════════════════════════════════════════
function runScenario(idx) {
  S.timeouts.forEach(clearTimeout);
  S.timeouts = [];
  S.activeBalls = [];
  // Clear all jobs
  for (var k in S.agentJobs) delete S.agentJobs[k];
  AGENTS.forEach(function(a) { refreshAgent(a.id); });

  S.currentScenario = idx;
  updateScenarioBtns();

  var sc = SCENARIOS[idx];
  addLog("🚀 Сценарий: "+sc.name, "#fff");

  sc.steps.forEach(function(step) {
    var tid = setTimeout(function() {
      launchBall(step.from, step.to, step.task, step.duration, step.workDuration);
    }, step.delay);
    S.timeouts.push(tid);
  });

  // Next scenario
  var total = Math.max.apply(null, sc.steps.map(function(s){return s.delay+s.duration+s.workDuration;})) + 2500;
  var ntid = setTimeout(function() {
    if (S.isRunning) {
      runScenario((idx + 1) % SCENARIOS.length);
    }
  }, total);
  S.timeouts.push(ntid);
}

function updateScenarioBtns() {
  SCENARIOS.forEach(function(_,i) {
    var btn = document.getElementById("scenario-btn-"+i);
    if (btn) {
      btn.className = "scenario-btn" + (i === S.currentScenario ? " active" : "");
    }
  });
  var lbl = document.getElementById("scenario-label");
  if (lbl) lbl.textContent = SCENARIOS[S.currentScenario].name;
}

// ═══════════════════════════════════════════════
// ANIMATION LOOP
// ═══════════════════════════════════════════════
function animate() {
  var now = performance.now();

  // Update ball progress
  S.activeBalls.forEach(function(b) {
    b.progress = Math.min(1, (now - b.startTime) / b.duration);
  });

  // Update progress bars for active jobs
  for (var aid in S.agentJobs) {
    var job = S.agentJobs[aid];
    var pct = Math.min(100, ((now - job.startTime) / job.duration) * 100);

    // Card progress
    var cppct = document.getElementById("cppct-"+aid);
    var cpbar = document.getElementById("cpbar-"+aid);
    if (cppct) cppct.textContent = Math.round(pct)+"%";
    if (cpbar) cpbar.style.width = pct+"%";

    // Sidebar progress
    var spct = document.getElementById("spct-"+aid);
    var sfill = document.getElementById("sfill-"+aid);
    if (spct) spct.textContent = Math.round(pct)+"%";
    if (sfill) sfill.style.width = pct+"%";
  }

  // Render balls and trails
  renderBalls();

  requestAnimationFrame(animate);
}

function renderBalls() {
  var svg = document.getElementById("trails-svg");
  var bc  = document.getElementById("balls-container");
  if (!svg || !bc) return;

  svg.innerHTML = "";
  bc.innerHTML = "";

  S.activeBalls.forEach(function(ball) {
    var fp = getPos(ball.from), tp = getPos(ball.to);
    var mx = (fp.x + tp.x) / 2;
    var my = Math.min(fp.y, tp.y) - 50 - Math.abs(fp.x - tp.x) * 0.1;
    var d = "M "+fp.x+" "+fp.y+" Q "+mx+" "+my+" "+tp.x+" "+tp.y;

    // Dashed trail
    var path = document.createElementNS("http://www.w3.org/2000/svg","path");
    path.setAttribute("d", d);
    path.setAttribute("fill","none");
    path.setAttribute("stroke", ball.task.color);
    path.setAttribute("stroke-width","1.5");
    path.setAttribute("stroke-dasharray","6 4");
    path.setAttribute("opacity","0.3");
    svg.appendChild(path);

    // Glow trail
    var glow = document.createElementNS("http://www.w3.org/2000/svg","path");
    glow.setAttribute("d", d);
    glow.setAttribute("fill","none");
    glow.setAttribute("stroke", ball.task.color);
    glow.setAttribute("stroke-width","4");
    glow.setAttribute("opacity","0.06");
    svg.appendChild(glow);

    // Ball position (quadratic bezier)
    var t = ease(ball.progress);
    var x = lerp(lerp(fp.x, mx, t), lerp(mx, tp.x, t), t);
    var y = lerp(lerp(fp.y, my, t), lerp(my, tp.y, t), t);
    var sz = 34 + Math.sin(ball.progress * Math.PI) * 8;

    var bEl = document.createElement("div");
    bEl.style.cssText = "position:absolute;left:"+x+"px;top:"+y+"px;z-index:100;pointer-events:none;transform:translate(-50%,-50%)";

    // Label above
    var lbl = document.createElement("div");
    lbl.style.cssText = "position:absolute;bottom:"+(sz/2+8)+"px;left:50%;transform:translateX(-50%);white-space:nowrap;background:#0a0a0f;border:1px solid "+ball.task.color+"44;border-radius:6px;padding:2px 8px;font-size:10px;font-weight:600;color:"+ball.task.color+";box-shadow:0 0 10px "+ball.task.color+"22";
    lbl.textContent = ball.task.label;
    bEl.appendChild(lbl);

    // Circle
    var circ = document.createElement("div");
    circ.style.cssText = "width:"+sz+"px;height:"+sz+"px;border-radius:50%;background:radial-gradient(circle at 35% 35%,"+ball.task.color+","+ball.task.color+"77);box-shadow:0 0 20px "+ball.task.color+"55,0 0 50px "+ball.task.color+"18;display:flex;align-items:center;justify-content:center;font-size:16px";
    circ.textContent = ball.task.emoji;
    bEl.appendChild(circ);

    // Pct under
    var pctDiv = document.createElement("div");
    pctDiv.style.cssText = "position:absolute;top:"+(sz/2+4)+"px;left:50%;transform:translateX(-50%);font-size:9px;font-family:monospace;color:"+ball.task.color+"aa;font-weight:600";
    pctDiv.textContent = Math.round(ball.progress*100)+"%";
    bEl.appendChild(pctDiv);

    bc.appendChild(bEl);
  });
}

// ═══════════════════════════════════════════════
// CONTROLS
// ═══════════════════════════════════════════════
function toggleRunning() {
  S.isRunning = !S.isRunning;
  var btn = document.getElementById("toggle-btn");
  var lbl = document.getElementById("scenario-label");
  if (btn) {
    if (S.isRunning) {
      btn.className = "ctrl-btn toggle-btn-run";
      btn.textContent = "⏸ Пауза";
      runScenario(S.currentScenario);
    } else {
      btn.className = "ctrl-btn toggle-btn-pause";
      btn.textContent = "▶ Старт";
      S.timeouts.forEach(clearTimeout);
      if (lbl) { lbl.textContent = "Демо остановлено"; }
    }
  }
}

function selectScenario(idx) {
  S.isRunning = true;
  var btn = document.getElementById("toggle-btn");
  if (btn) { btn.style.display = ""; btn.className = "ctrl-btn toggle-btn-run"; btn.textContent = "⏸ Пауза"; }
  var lbl = document.getElementById("scenario-label");
  if (lbl) { lbl.textContent = "Демо: " + SCENARIOS[idx].name; lbl.style.borderColor = "#f39c1233"; lbl.style.color = "#f39c12"; }
  runScenario(idx);
}

// ═══════════════════════════════════════════════
// LOAD REAL DATA FROM ACTIVITY TRACKER
// ═══════════════════════════════════════════════
function loadRealData() {
  var hasRealActivity = false;

  // Load real agent statuses
  if (INITIAL.agentStatuses) {
    var taskMap = {
      "финанс": "report", "отчёт": "report", "бюджет": "report", "p&l": "report",
      "контент": "content", "пост": "post", "linkedin": "post",
      "api": "api", "интеграц": "api", "webhook": "api", "деплой": "api",
      "стратег": "strategy", "обзор": "strategy", "координац": "strategy",
      "дизайн": "design", "баннер": "design", "визуал": "design",
    };
    function guessTaskType(desc) {
      if (!desc) return "strategy";
      var lower = desc.toLowerCase();
      for (var kw in taskMap) { if (lower.indexOf(kw) >= 0) return taskMap[kw]; }
      return "strategy";
    }

    for (var agentId in INITIAL.agentStatuses) {
      var real = INITIAL.agentStatuses[agentId];
      if (real.status === "working" && real.task) {
        hasRealActivity = true;
        var tt = guessTaskType(real.task);
        var task = findTask(tt);
        var elapsed = 0;
        if (real.started_at) {
          try { elapsed = Date.now() - new Date(real.started_at).getTime(); } catch(e) {}
        }
        var jid = ++S.jobId;
        S.agentJobs[agentId] = {
          status: "working", task: task,
          startTime: performance.now() - elapsed,
          duration: Math.max(elapsed * 1.3, 30000),
          jobId: jid,
        };
        refreshAgent(agentId);
        addLog(findAgent(agentId).icon + " " + findAgent(agentId).name + ": работает над «" + (real.task || task.label) + "»", task.color);
      }
      if (real.communicating_with) {
        hasRealActivity = true;
        var other = findAgent(real.communicating_with);
        var self = findAgent(agentId);
        if (other && self) {
          addLog(self.icon + " " + self.name + " 💬 → " + other.icon + " " + other.name, self.color);
        }
      }
    }
  }

  // Load recent events into log
  if (INITIAL.recentEvents && INITIAL.recentEvents.length > 0) {
    var evts = INITIAL.recentEvents.slice(-15).reverse();
    evts.forEach(function(evt) {
      var ts = evt.timestamp || "";
      var timeStr = "";
      try { timeStr = new Date(ts).toLocaleTimeString("ru-RU", {hour:"2-digit",minute:"2-digit",second:"2-digit"}); } catch(e) { timeStr = ts.substring(11,19); }

      if (evt.type === "task_start") {
        var a = findAgent(evt.agent);
        if (a) S.logEntries.push({text: a.icon + " " + a.name + ": начал «" + (evt.task||"") + "»", color: a.color, time: timeStr, id: Math.random()});
      } else if (evt.type === "task_end") {
        var a2 = findAgent(evt.agent);
        var icon = evt.success !== false ? "✅" : "❌";
        var dur = evt.duration_sec ? " (" + evt.duration_sec + "с)" : "";
        if (a2) S.logEntries.push({text: icon + " " + a2.icon + " " + a2.name + ": завершил «" + (evt.task||"") + "»" + dur, color: evt.success !== false ? "#3dff8a" : "#ff4057", time: timeStr, id: Math.random()});
      } else if (evt.type === "communication") {
        var f = findAgent(evt.from_agent), t = findAgent(evt.to_agent);
        if (f && t) S.logEntries.push({text: f.icon + " " + f.name + " → " + t.icon + " " + t.name + ": " + (evt.description||""), color: "#3dd8ff", time: timeStr, id: Math.random()});
      }
    });
    if (S.logEntries.length > 0) {
      hasRealActivity = true;
      S.logEntries.reverse();
      if (S.logEntries.length > 20) S.logEntries.length = 20;
      renderLog();
    }
  }

  return hasRealActivity;
}

// ═══════════════════════════════════════════════
// INIT
// ═══════════════════════════════════════════════
buildAgentCards();
buildSidebar();
document.getElementById("completed-count").textContent = S.completedTasks;
updateScenarioBtns();
requestAnimationFrame(animate);

var hasReal = loadRealData();

// If real activity, set isRunning to animate real data
if (hasReal) {
  S.isRunning = true;
  var lbl = document.getElementById("scenario-label");
  if (lbl) lbl.textContent = "Реальная активность";
  lbl.style.borderColor = "#3dff8a33";
  lbl.style.color = "#3dff8a";
} else {
  // No real activity — show idle message in log
  addLog("⏳ Ожидание реальных событий агентов...", "#555");
  addLog("💡 Используйте чат для запуска задач или нажмите «Демо» для просмотра", "#555");
}
</script>
</body>
</html>"""
