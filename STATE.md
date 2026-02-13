# Zinin Corporation — System State

> Auto-updated by agents. Manual edits welcome.
> Last updated: 2026-02-13
> Strategy: v3.1 — Proactive System + Revenue-First + 3 Touchpoints

---

## System Health

| Agent | Status | Telegram Bot | Notes |
|-------|--------|-------------|-------|
| CEO Алексей | Active | CEO bot running | 14 commands, NLU routing, scheduler (12 jobs), Task Pool, brain dump, voice |
| CFO Маттиас | Active | CFO bot running | 20 financial tools, vault encrypted, MCP server |
| CTO Мартин | Active | — (via CEO) | Proposals 4x/day, API health 30min |
| SMM Юки | Active | SMM bot running | LinkedIn + Threads (Tim), LinkedIn (Kristina) |
| Designer Райан | Active | — (via CEO) | Gemini image gen |
| CPO Софи | Active | — (via CEO) | Backlog tracking |
| Analytic | Planned | — | Sprint 3+ |

---

## Revenue Tracker

**Goal: $2,500 MRR by March 2, 2026 (17 days left)**

| Source | Current MRR | Target MRR | Members | Progress |
|--------|-------------|------------|---------|----------|
| Crypto Marketologists | ~$350 | $800-1,000 | 215 | 35-44% |
| Sborka (Kristina) | $0 | $600-800 | 0 → 20+ trial | 0% |
| Botanica (botanicaschool.com) | ~$165 | $400-600 | 222 free + 3 paid | 28-41% |
| Personal brand (Tim) | $0 | $300-500 | — | 0% |
| Sponsor placements | $0 | $200-400 | — | 0% |
| **TOTAL** | **~$515** | **$2,500** | | **21%** |

---

## Sprint Kanban

### Sprint 1: Foundation (Feb 12) — DONE

- [x] Audit CrewAI codebase — 6 agents, 1528 tests, 3 bots
- [x] Review CEO bot (Алексей) — 9 commands, scheduler, proposal workflow
- [x] Review SMM bot (Юки) — approve flow, publishers, podcasts
- [x] CLAUDE.md v2 — full architecture doc
- [x] AGENTS.md v2 — agent registry
- [x] STATE.md — dynamic Kanban
- [x] Enable Agent Teams in settings
- [x] Fix per-user chat context (CEO + Yuki bots)
- [x] Fix Threads publisher stub in Yuki bot

### Sprint 2: Task Pool + MCP (Feb 12) — DONE

#### DONE
- [x] Shared Task Pool (`src/task_pool.py`) — Dependency Engine, auto-tag, agent routing
- [x] CEO bot: `/task` and `/tasks` commands with inline keyboards
- [x] CEO bot: task assign/start/done/block callbacks
- [x] CFO MCP Server (`src/mcp_servers/cfo_server.py`) — 8 tools (Active)
- [x] Tribute MCP Server (`src/mcp_servers/tribute_server.py`) — 4 tools (Active)
- [x] AgentBridge → Task Pool integration (delegation tracking)
- [x] Brain Dump processor (`src/brain_dump.py`) — auto-parse long messages
- [x] CLAUDE.md v2.3 — Task Pool, MCP, agent tags, file structure
- [x] AGENTS.md v2.3 — competency tags, escalation rules
- [x] 176 new tests (Task Pool: 115, MCP: 29, Brain Dump: 32)

### Sprint 3: Automation + Escalation + MCP (Feb 13) — DONE

#### DONE
- [x] Task Pool Archiver — archive DONE tasks >1 day to `data/archive/YYYY-MM-DD.json`
- [x] `updated_at` tracking on all task status changes
- [x] Scheduler: `archive_daily` job (CronTrigger hour=1)
- [x] CTO Orphan Task Patrol — `get_stale_tasks()` + `format_stale_report()`
- [x] Scheduler: `orphan_patrol` job (CronTrigger hour=10)
- [x] Escalation inline keyboards (4 options: extend, create agent, split, manual)
- [x] `ESCALATION_THRESHOLD = 0.3` — auto-triggers when no good agent match
- [x] Split task mode — text input for creating subtasks
- [x] telegram-mcp (`src/mcp_servers/telegram_server.py`) — 6 tools (Active)
- [x] Knowledge Base MCP (`src/mcp_servers/kb_server.py`) — 3 tools (Active)
- [x] Entry points: `run_telegram_mcp.py`, `run_kb_mcp.py`
- [x] Agent Teams validation — enabled, CLAUDE.md context visible
- [x] ~70 new tests (archiver, stale, escalation, telegram-mcp, kb-mcp)

#### BLOCKED
- [ ] Kristina Threads — waiting for her Meta App credentials
- [ ] Hetzner CX33 — Tim needs to register account

### Sprint 4: Analytics + Routing + NLU + Voice (Feb 13) — DONE

#### DONE
- [x] CP-019: Unified Error Handler (`src/error_handler.py`) — ErrorCategory, safe_agent_call, 27 tests
- [x] CP-006: NLU для русского (`src/telegram_ceo/nlu.py`) — intent detection, 9 commands, 5 agents, 46 tests
- [x] CP-018: Agent Teams coordination (`src/agent_teams.py`) — MCP config, team readiness, 23 tests
- [x] CP-001: Analytics Telegram Report (`src/analytics.py`) — token usage, agent activity, cost, quality, 28 tests
- [x] CP-004: Enhanced Morning + Evening Reports — Task Pool + rate alerts in morning, evening report 21:00
- [x] CP-005: Weekly Digest — Sunday 20:00, pure data aggregation, no LLM
- [x] CP-007: faster-whisper integration (`src/tools/voice_tools.py`) — CPU transcription, lazy-load, 16 tests
- [x] CP-003: CEO Smart Routing — NLU-based agent selection + `/route` command
- [x] CP-002: Smart Model Routing (`src/model_router.py`) — Groq/Haiku/Sonnet tiers, feature flag, 41 tests
- [x] CP-008: Brain Dump через голос — F.voice handler, OGG→WAV→text→brain dump/agent
- [x] 201 new tests (1789 → 1990), 0 failures

### Hotfix: Railway OOM + Health Check (Feb 13) — DONE

- [x] Fix Railway OOM: faster-whisper removed from requirements.txt (ctranslate2 ~500MB too heavy)
- [x] Whisper model default: tiny (39MB) instead of small (244MB)
- [x] release_model() — free whisper RAM after transcription before CrewAI agent runs
- [x] Remove Railway self-ping from API health check (502 because Streamlit disabled)
- [x] Rule-based CTO analysis fallback (replaces "Автоматический анализ недоступен")
- [x] Fix yuki.yaml — add missing anti-fabrication block
- [x] Dockerfile: add MCP entry points + AGENTS.md + STATE.md
- [x] Voice on Railway: gracefully disabled (is_voice_available() returns False)
- Commits: `55f2ba7`, `d45000b`, `5b43a29`

### Sprint 5: Revenue Sprint (Feb 13–18) — IN PROGRESS

**Strategy:** v3.1 — Proactive System + Revenue-First + 3 Touchpoints

#### P0 — Immediate (blocks revenue)
- [ ] PRO-001: Proactive Daily Planner (`src/proactive_planner.py`) — action plan + inline keyboards
- [ ] PRO-002: Revenue Tracker (`data/revenue.json`) — MRR per channel, gap, daily tracking
- [ ] PRO-003: 3 Touchpoints scheduler: morning (9:00) + midday (14:00) + evening (20:00)
- [ ] PRO-004: Agent auto-launch on [Запустить] button → AgentBridge → result
- [ ] CS-002: SMM Юки image optimization (post without image = 3K views!)

#### P1 — Today/Tomorrow (direct MRR impact)
- [ ] RV-SBR-001: Sborka content plan: 5 posts over 5 days to Feb 18 launch
- [ ] RV-SBR-002: Sborka landing/invite flow — Tribute link + CTA + trial messaging
- [ ] RV-KRM-001: КРМКТЛ upsell strategy — premium tier for 215 members
- [ ] CS-001: SMM Юки separate text + image generation
- [ ] CS-003: SMM Юки image regeneration with refined prompt
- [ ] CS-004: SMM Юки new approve flow (feedback → adjust → retry → publish)

#### BLOCKED
- [ ] Kristina Threads — waiting for her Meta App credentials
- [ ] Hetzner migration — Tim needs to register Hetzner account (infra last)

---

## Token Usage (Estimated)

| Provider | Daily Avg | Monthly Est | Budget |
|----------|-----------|-------------|--------|
| OpenRouter (Claude) | ~$2-5 | ~$60-150 | Included in Max 5x |
| Gemini (images) | Free | Free | — |
| ElevenLabs (TTS) | ~$0.5 | ~$15 | Free tier |
| ONNX embedder | Free | Free | — |

---

## Daily Log

### 2026-02-13 (Strategy v3.0 — Paradigm Shift)
- Strategy v3.0: Reactive → Proactive paradigm shift
- Revenue update: actual MRR $515 (added Botanica $165/mo, 3 paid × 5500₽)
- 5 revenue channels instead of 4 (КРМКТЛ, Sborka, Botanica, Personal, Sponsors)
- Proactive Daily Planner designed: 3 touchpoints (09:00, 14:00, 20:00) with inline keyboards
- Revenue Tracker: `data/revenue.json` — MRR per channel, gap tracking
- Agent auto-launch: button press → AgentBridge → result → next step
- Sborka soft launch plan: 5 posts Feb 14-18, 5 trial users, goal 20+
- Botanica relaunch plan: async course + club, self-sustaining model
- Unified backlog: 44 prioritized tasks (P0-P4), code first, infra last
- Updated: strategy_v3_0.md, CLAUDE.md v3.0, STATE.md

### 2026-02-13 (Hotfix — post-Sprint 4)
- Railway OOM fix: faster-whisper removed from requirements (ctranslate2 too heavy for ~512MB RAM)
- Whisper default: tiny (39MB), release_model() frees RAM after use
- Railway self-ping removed from _API_REGISTRY (13 APIs instead of 14)
- Rule-based CTO analysis: specific hints per API (rate limit, auth, timeout, missing keys)
- yuki.yaml: added anti-fabrication block (was missing, test was failing)
- Dockerfile updated: MCP entry points, AGENTS.md, STATE.md, WHISPER_MODEL_SIZE=tiny
- Voice on Railway: gracefully disabled, works locally with `pip install faster-whisper`
- 1990 tests still passing, 3 commits deployed

### 2026-02-13 (Sprint 4)
- Unified Error Handler: categorize_error, format_error_for_user, safe_agent_call
- NLU: Russian intent detection (9 commands) + agent detection (5 agents)
- Agent Teams: MCP server config, teammate context, readiness validation
- Analytics: token usage, agent activity, cost estimates, quality reports
- 3 new scheduler jobs: daily_analytics (22:00), evening_report (21:00), weekly_digest (Sun 20:00)
- Enhanced morning briefing: Task Pool + rate alerts
- faster-whisper: CPU-based voice transcription, lazy-loaded model
- Smart routing: NLU-based agent selection + /route + /analytics commands
- Smart model routing: Groq (simple) / Haiku (moderate) / Sonnet (complex)
- Voice brain dump: F.voice → OGG→WAV → transcribe → brain dump or agent
- `create_llm()` now supports Groq provider
- 201 new tests (1789 → 1990), all passing

### 2026-02-13 (Sprint 3)
- Task Pool Archiver: archive_done_tasks() + get_archived_tasks() + get_archive_stats()
- updated_at tracking in all task CRUD operations
- CTO Orphan Patrol: get_stale_tasks() + format_stale_report()
- 2 new scheduler jobs: archive_daily (01:00), orphan_patrol (10:00)
- Escalation system: ESCALATION_THRESHOLD=0.3, 4-button keyboard, split mode
- Telegram MCP Server: 6 tools (create/get/assign/complete/summary)
- Knowledge Base MCP Server: 3 tools (search/list/read)
- Agent Teams validated — enabled in settings, CLAUDE.md context shared
- ~70 new tests for Sprint 3 features

### 2026-02-12 (Sprint 1 + Sprint 2)
**Sprint 1:**
- Audited entire codebase: 6 agents, 50+ tools, 3 TG bots, 1528 tests
- Created CLAUDE.md v2, AGENTS.md v2, STATE.md
- Enabled Agent Teams, fixed per-user chat context, fixed Threads publisher

**Sprint 2:**
- Created Shared Task Pool with Dependency Engine (`src/task_pool.py`)
- Added `/task` and `/tasks` to CEO bot with full inline keyboard workflow
- Created CFO MCP Server (8 tools) + Tribute MCP Server (4 tools)
- Integrated Task Pool into AgentBridge (delegation → auto-track)
- Created Brain Dump processor (long messages → parsed tasks)
- Updated CLAUDE.md and AGENTS.md to v2.3 (tags, routing, escalation)
- Total: 1735 tests (1559 old + 176 new), all passing

---

*This file is the single source of truth for system state. Agents update it after completing tasks.*
