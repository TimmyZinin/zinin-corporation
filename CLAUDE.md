# Zinin Corporation — AI Multi-Agent System

> **Mission:** Autonomous AI team managing communities, content, and finances to reach $2,500 MRR by March 2, 2026.
> **Owner:** Tim Zinin (@TimmyZinin)
> **Repo:** https://github.com/TimmyZinin/zinin-corporation
> **Strategy:** v2.3 — CEO as sole navigator + Shared Task Pool + Dependency Engine

---

## Prime Directive

This is a **production multi-agent system** with 6 specialized AI agents, 3 Telegram bots, and a Streamlit web interface. The system manages:
- **Revenue:** Tribute subscriptions, sponsor placements, premium content
- **Content:** LinkedIn + Threads publishing for Tim Zinin and Kristina Zhukova
- **Finance:** 20+ financial integrations (crypto, forex, banking, API billing)
- **Product:** Backlog management, sprint tracking, feature health monitoring
- **Tasks:** Shared Task Pool with dependency blocking and auto-routing

**Key constraint:** All changes must pass 1800+ existing tests. Never break existing functionality.

---

## Architecture (Hybrid: CrewAI + Agent Teams + MCP)

```
    TIM ──→ CEO Bot Алексей (Telegram)
                    │
         Claude Code Agent Teams (Lead)
          CLAUDE.md context │ qmd KB
                    │
         ┌──────────▼──────────┐
         │   SHARED TASK POOL  │
         │  CEO assigns all    │
         │  Dependency Engine  │
         │  Auto-tag + Route   │
         └──────────┬──────────┘
                    │ CEO assigns
    ┌───────┬───────┼───────┬────────┐
    │       │       │       │        │
  CTO   Analytic  SMM   Product  Designer
    │       │       │       │        │
    └───────┼───────┘       │        │
            │ MCP Connections│        │
    ┌───────▼───────────────▼────────▼───┐
    │           MCP Servers               │
    │  cfo-mcp (Active) │ tribute-mcp    │
    │  telegram-mcp     │ qmd (Planned)  │
    └────────────────────────────────────┘
```

**Migration strategy:** Gradual. CrewAI code stays as fallback. New Agent Teams layer built on top.

---

## Shared Task Pool (v2.3)

**File:** `src/task_pool.py` — Core coordination mechanism.

### Task Lifecycle
```
Tim/System creates task → CEO Алексей assigns → Agent executes → DONE
                                                    ↓
                              Dependency Engine unblocks dependents
```

### Statuses
`TODO` → `ASSIGNED` → `IN_PROGRESS` → `DONE` (or `BLOCKED`)

### Key Concepts
- **CEO = sole navigator:** Only CEO Алексей assigns tasks. Agents don't self-assign.
- **Dependency blocking:** `blocked_by` / `blocks` fields. Task stays BLOCKED until all dependencies are DONE.
- **Auto-tag:** Extracts competency tags from task title (keyword matching).
- **Agent Router:** `suggest_assignee()` matches task tags to agent competencies.
- **Brain Dump:** Long structured messages (>300 chars) auto-parsed into tasks.
- **Delegation tracking:** AgentBridge auto-creates tasks for `/delegate` commands.

### Agent Competency Tags
| Agent | Tags |
|-------|------|
| manager | strategy, delegation, coordination, review, report, planning |
| accountant | finance, budget, revenue, portfolio, crypto, banking, tribute |
| automator | architecture, infrastructure, mcp, code, api, health, deployment |
| smm | content, linkedin, threads, post, podcast, social, copywriting |
| designer | design, visual, image, infographic, chart, video, branding |
| cpo | product, backlog, sprint, feature, roadmap, metrics, analytics |

---

## Agents

See [AGENTS.md](AGENTS.md) for full registry with triggers, tools, and handoff rules.

| Agent | Role | Model | Status |
|-------|------|-------|--------|
| CEO Алексей | Orchestrator, task navigator | Claude Sonnet 4 | Active |
| CFO Маттиас | Finance, P&L, portfolio | Claude Sonnet 4 | Active |
| CTO Мартин | Architecture, health, code audit | Claude Sonnet 4 | Active |
| SMM Юки | Content, LinkedIn, Threads | Claude 3.5 Haiku | Active |
| Designer Райан | Visual, infographics, video | Claude 3.5 Haiku | Active |
| CPO Софи | Product, backlog, sprints | Claude 3.5 Haiku | Active |
| Analytic | Agent metrics, optimization | TBD | Planned |

---

## Telegram Bots

### CEO Алексей (`src/telegram_ceo/`)
- **Token:** `TELEGRAM_CEO_BOT_TOKEN`
- **Whitelist:** `TELEGRAM_CEO_ALLOWED_USERS`
- **Commands:** `/start`, `/help`, `/status`, `/review`, `/report`, `/content <topic>`, `/linkedin`, `/task <title>`, `/tasks`, `/delegate <agent> <task>`, `/test`
- **Task Pool:** `/task` creates tasks with auto-tag + agent suggestion. Inline keyboards for assign/start/complete/block.
- **Brain Dump:** Long messages (>300 chars with list markers) auto-parsed into Task Pool.
- **Scheduler:** Morning briefing, weekly report, API health (30min), CTO proposals (4x/day), archive_daily (01:00), orphan_patrol (10:00)
- **Escalation:** When `suggest_assignee()` confidence < 0.3, shows 4-option keyboard (extend prompt, create agent, split task, manual assign)
- **Entry:** `run_alexey_bot.py`

### CFO Маттиас (`src/telegram/`)
- **Token:** `TELEGRAM_BOT_TOKEN`
- **Commands:** `/start`, `/balance`, `/report`, `/help`
- **Features:** Vision (screenshots), CSV uploads, AES-256 vault
- **Entry:** `run_telegram.py`

### SMM Юки (`src/telegram_yuki/`)
- **Token:** `TELEGRAM_YUKI_BOT_TOKEN`
- **Commands:** `/start`, `/help`, `/пост <topic>`, `/подкаст <topic>`, `/status`, `/health`, `/level`, `/schedule`, `/linkedin`, `/reflexion`
- **Features:** Approve flow, image gen (Gemini), podcast (ElevenLabs), LinkedIn/Threads publishing
- **Entry:** `run_yuki_bot.py`

---

## Tools by Agent

### CFO Маттиас (20 tools)
Banking: `TBankBalance`, `TBankStatement` | Crypto: `EVMPortfolio`, `SolanaPortfolio`, `TONPortfolio`, `StacksPortfolio`, `PapayaPositions`, `EventumPortfolio` | Price: `CryptoPrice`, `ForexRates` | Revenue: `TributeRevenue` | API billing: `OpenRouterUsage`, `ElevenLabsUsage`, `OpenAIUsage` | Data: `ScreenshotData`, `TinkoffData`, `PortfolioSummary`

### CTO Мартин (5 tools + web)
`SystemHealthChecker`, `IntegrationManager`, `APIHealthMonitor`, `AgentPromptWriter`, `AgentImprovementAdvisor`, `WebSearch`, `WebPageReader`

### SMM Юки (7 tools)
`ContentGenerator`, `YukiMemory`, `LinkedInTimPublisher`, `LinkedInKristinaPublisher`, `ThreadsTimPublisher`, `ThreadsKristinaPublisher`, `PodcastScriptGenerator`

### Designer Райан (10 tools)
`ImageGenerator`, `ImageEnhancer`, `ChartGenerator`, `InfographicBuilder`, `VisualAnalyzer`, `VideoCreator`, `TelegraphPublisher`, `DesignSystemManager`, `ImageResizer`, `BrandVoiceVisual`

### CPO Софи (4 tools)
`FeatureHealthChecker`, `SprintTracker`, `BacklogAnalyzer`, `ProgressReporter`

---

## MCP Servers

| Server | Purpose | Tools | Status |
|--------|---------|-------|--------|
| `cfo-mcp` | Financial data (Маттиас tools) | 8 tools: balance, portfolio, crypto, tribute, forex, API costs | **Active** |
| `tribute-mcp` | Revenue/subscriber data | 4 tools: products, revenue, subscriptions, stats | **Active** |
| `telegram-mcp` | CEO Алексей ↔ Task Pool bridge | 6 tools: create/get/assign/complete tasks, pool summary | **Active** |
| `kb-mcp` | Knowledge base search | 3 tools: search, list topics, read topic | **Active** |
| `crypto-mcp` | Crypto bot notifications | Planned | Planned |

**Run:** `python run_cfo_mcp.py` / `python run_tribute_mcp.py` / `python run_telegram_mcp.py` / `python run_kb_mcp.py`

---

## Security

- **Vault:** AES-256 encryption for all financial data (`src/telegram/vault.py`)
- **Key:** `VAULT_PASSWORD` env var
- **Encrypted:** tinkoff_transactions, screenshot_data, tribute_payments, financial_data
- **Credentials:** Brokered — agents never see API keys, only tool results
- **Git:** `data/*.json` in `.gitignore`, no secrets committed
- **Auth:** Telegram bots use `AuthMiddleware` with user ID whitelist
- **Access:** CFO tools only through Маттиас, CEO through delegation

---

## File Structure

```
ai_corporation/
├── CLAUDE.md              # This file — system context
├── AGENTS.md              # Agent registry with details
├── STATE.md               # Dynamic Kanban state
├── agents/                # YAML configs (6 agents)
├── crews/                 # CrewAI crew definitions
├── knowledge/             # RAG knowledge base (company, team, guidelines)
├── src/
│   ├── agents.py          # Agent factory functions
│   ├── crew.py            # CrewAI crew orchestration
│   ├── flows.py           # CrewAI Flows (Pydantic state, reflection)
│   ├── app.py             # Streamlit web UI
│   ├── task_pool.py       # Shared Task Pool + Dependency Engine (v2.3)
│   ├── brain_dump.py      # Brain dump → tasks parser
│   ├── task_extractor.py  # Legacy task extraction from messages
│   ├── models/            # Pydantic models (CorporationState, outputs)
│   ├── mcp_servers/        # MCP servers for Agent Teams
│   │   ├── cfo_server.py      # CFO financial tools (8 MCP tools)
│   │   ├── tribute_server.py  # Tribute revenue tools (4 MCP tools)
│   │   ├── telegram_server.py # Task Pool bridge (6 MCP tools)
│   │   └── kb_server.py       # Knowledge base search (3 MCP tools)
│   ├── tools/             # Agent tools
│   │   ├── financial/     # 20+ financial API tools
│   │   ├── smm_tools.py   # Content + publishers (4 accounts)
│   │   ├── design_tools.py
│   │   ├── tech_tools.py
│   │   └── cpo_tools.py
│   ├── telegram/          # CFO Маттиас bot
│   ├── telegram_ceo/      # CEO Алексей bot
│   └── telegram_yuki/     # SMM Юки bot
├── tests/                 # 1800+ tests (45+ files)
├── run_cfo_mcp.py         # CFO MCP server entry point
├── run_tribute_mcp.py     # Tribute MCP server entry point
├── run_telegram_mcp.py    # Telegram Task Pool MCP entry point
├── run_kb_mcp.py          # Knowledge Base MCP entry point
├── data/                  # Persistent storage (not in git)
├── Dockerfile
├── start.sh               # Launches 3 bots
└── requirements.txt
```

---

## Agent Teams

**Status:** Enabled in project settings.

Enable: `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` in `.claude/settings.json`

**How it works:**
- One session = team lead (coordinator)
- Teammates = separate Claude Code instances with own context
- Communication: shared task list + CLAUDE.md context
- MCP servers provide tool access to financial and revenue data

**Best practices:**
- Each teammate owns separate files (no conflicts)
- Use for: parallel research, multi-module features, competing hypotheses
- Avoid for: sequential tasks, same-file edits
- Monitor token usage — scales with teammate count

---

## Development

### Local Setup
```bash
cd /Users/timofeyzinin/ai_corporation
source .venv312/bin/activate  # Python 3.12
pip install -r requirements.txt
```

### Tests
```bash
pytest tests/ -v              # All 1800+ tests
pytest tests/test_X.py -v     # Single file
```

### Deploy
```bash
git add <files> && git commit -m "message" && git push
# Railway auto-deploys from main, or:
railway up --detach
```

### Environment Variables
See `.env.example` for full list. Key vars:
- `OPENROUTER_API_KEY` — LLM provider
- `TELEGRAM_*_BOT_TOKEN` — 3 bot tokens
- `LINKEDIN_ACCESS_TOKEN` / `_KRISTINA` — LinkedIn OAuth
- `THREADS_ACCESS_TOKEN` / `_KRISTINA` — Threads OAuth
- `VAULT_PASSWORD` — AES-256 encryption key

---

## Revenue Target

**Goal:** $2,500 MRR by March 2, 2026

| Source | Current | Target |
|--------|---------|--------|
| Crypto Marketologists (215 members) | ~$350 | $800-1,000 |
| Sborka (with Kristina) | $0 | $600-800 |
| Personal brand (Tim) | $0 | $500-700 |
| Sponsor placements | $0 | $200-400 |

See [STATE.md](STATE.md) for live progress tracking.

---

*Updated: February 13, 2026 — Sprint 3 (Archiver + Escalation + telegram-mcp + kb-mcp)*
