# Zinin Corporation — AI Multi-Agent System

> **Mission:** Autonomous AI team managing communities, content, and finances to reach $2,500 MRR by March 2, 2026.
> **Owner:** Tim Zinin (@TimmyZinin)
> **Repo:** https://github.com/TimmyZinin/zinin-corporation

---

## Prime Directive

This is a **production multi-agent system** with 6 specialized AI agents, 3 Telegram bots, and a Streamlit web interface. The system manages:
- **Revenue:** Tribute subscriptions, sponsor placements, premium content
- **Content:** LinkedIn + Threads publishing for Tim Zinin and Kristina Zhukova
- **Finance:** 20+ financial integrations (crypto, forex, banking, API billing)
- **Product:** Backlog management, sprint tracking, feature health monitoring

**Key constraint:** All changes must pass 1528+ existing tests. Never break existing functionality.

---

## Architecture

### Current State (CrewAI + Telegram Bots)

```
                    TIM (Human-in-the-Loop)
                         │
          ┌──────────────┼──────────────┐
          │              │              │
    ┌─────▼─────┐ ┌─────▼─────┐ ┌─────▼─────┐
    │ CEO Bot   │ │ CFO Bot   │ │ SMM Bot   │
    │ Алексей   │ │ Маттиас   │ │ Юки       │
    │ (TG)      │ │ (TG)      │ │ (TG)      │
    └─────┬─────┘ └─────┬─────┘ └─────┬─────┘
          │              │              │
          └──────────────┼──────────────┘
                         │
              ┌──────────▼──────────┐
              │  AgentBridge        │
              │  (src/telegram/     │
              │   bridge.py)        │
              └──────────┬──────────┘
                         │
              ┌──────────▼──────────┐
              │  CrewAI Corporation  │
              │  (src/crew.py)      │
              │  (src/flows.py)     │
              └──────────┬──────────┘
                         │
    ┌────────┬───────┬───┴───┬────────┬────────┐
    │        │       │       │        │        │
  CEO     CFO     CTO     SMM    Designer   CPO
 Алексей Маттиас Мартин  Юки    Райан      Софи
```

### Target State (Hybrid: CrewAI + Agent Teams + MCP)

```
    TIM ──→ CEO Bot Алексей (Telegram)
                    │
         Claude Code Agent Teams (Lead)
          CLAUDE.md context │ qmd KB │ Shared Tasks
                    │
    ┌───────┬───────┼───────┬────────┐
    │       │       │       │        │
  CTO   Analytic  SMM   Product  Designer
    │       │       │       │        │
    └───────┼───────┘       │        │
            │ MCP Connections│        │
    ┌───────▼───────────────▼────────▼───┐
    │           MCP Servers               │
    │  telegram-mcp │ cfo-mcp │ qmd      │
    │  crypto-mcp   │ tribute-mcp        │
    └────────────────────────────────────┘
```

**Migration strategy:** Gradual. CrewAI code stays as fallback. New Agent Teams layer built on top.

---

## Agents

See [AGENTS.md](AGENTS.md) for full registry with triggers, tools, and handoff rules.

| Agent | Role | Model | Status |
|-------|------|-------|--------|
| CEO Алексей | Orchestrator, delegation | Claude Sonnet 4 | Active |
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
- **Commands:** `/start`, `/help`, `/status`, `/review`, `/report`, `/content <topic>`, `/linkedin`, `/delegate <agent> <task>`, `/test`
- **Scheduler:** Morning briefing, weekly report, API health (30min), CTO proposals (4x/day)
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
│   ├── models/            # Pydantic models (CorporationState, outputs)
│   ├── tools/             # Agent tools
│   │   ├── financial/     # 17 financial API tools
│   │   ├── smm_tools.py   # Content + publishers (4 accounts)
│   │   ├── design_tools.py
│   │   ├── tech_tools.py
│   │   └── cpo_tools.py
│   ├── telegram/          # CFO Маттиас bot
│   ├── telegram_ceo/      # CEO Алексей bot
│   └── telegram_yuki/     # SMM Юки bot
├── tests/                 # 1528+ tests (39 files)
├── data/                  # Persistent storage (not in git)
├── Dockerfile
├── start.sh               # Launches 3 bots
└── requirements.txt
```

---

## Knowledge Base

- `knowledge/company.md` — Company info, mission
- `knowledge/team.md` — Team bios, roles
- `knowledge/content_guidelines.md` — Content rules, brand voice

**Planned:** qmd (tobi/qmd) for local BM25 + vector search, saving ~96% tokens.

---

## MCP Servers (Planned)

| Server | Purpose | Status |
|--------|---------|--------|
| `telegram-mcp` | CEO Алексей <-> Agent Teams | Planned |
| `cfo-mcp` | Financial data from CFO bot | Planned |
| `tribute-mcp` | Revenue/subscriber data | Planned |
| `crypto-mcp` | Crypto bot notifications | Planned |
| `sborka-mcp` | Sborka bot members/content | Planned |
| `qmd` | Knowledge base search | Planned |
| `github-mcp` | PR/issue management | Planned |

---

## Agent Teams

**Status:** Experimental, enabled in project settings.

Enable: `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` in `.claude/settings.json`

**How it works:**
- One session = team lead (coordinator)
- Teammates = separate Claude Code instances with own context
- Communication: mailbox (direct messages) + shared task list
- CLAUDE.md auto-loaded by all teammates
- Teams stored: `~/.claude/teams/{team-name}/`

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
pytest tests/ -v              # All 1528+ tests
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

*Updated: February 12, 2026 — Sprint 1 (Architecture Foundation)*
