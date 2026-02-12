# Zinin Corporation — Agent Registry v2.3

> Updated: February 12, 2026 — Sprint 2 (Task Pool + Agent Routing)

---

## Active Agents

### CEO Алексей Воронов
- **Role:** Orchestrator, **sole task navigator** (v2.3)
- **Model:** `openrouter/anthropic/claude-sonnet-4` (via OpenRouter)
- **Personality:** Ice Peak, T=0.1, decisive, minimal words
- **YAML:** `agents/manager.yaml`
- **Factory:** `src/agents.py:create_manager_agent()`
- **Tools:** DelegateTaskTool, WebSearchTool, WebPageReaderTool
- **Tags:** `strategy, delegation, coordination, review, report, planning, escalation`
- **Telegram:** `src/telegram_ceo/` — CEO bot with 11 commands
- **Triggers:**
  - `/ceo` or any text message to CEO bot
  - `/review` — strategic review (chains CFO + CTO)
  - `/report` — full corporation report (all agents)
  - `/task <title>` — create task in Shared Task Pool (auto-tag + suggest)
  - `/tasks` — view task pool summary
  - `/delegate <agent> <task>` — manual delegation (+ Task Pool tracking)
  - Brain dump: long messages (>300 chars) auto-parsed into tasks
- **Delegation targets:** accountant, automator, smm, designer, cpo
- **Scheduler:** Morning briefing, weekly report, API health (30min), CTO proposals (4x/day)
- **Task Pool role:** Assigns all tasks. Suggests agent via tag matching. Escalates to Tim if no match.

### CFO Маттиас Бруннер
- **Role:** Finance, P&L, portfolio tracking, burn rate
- **Model:** `openrouter/anthropic/claude-sonnet-4`
- **Personality:** Swiss precision, T=0.1, data-driven
- **YAML:** `agents/accountant.yaml`
- **Factory:** `src/agents.py:create_accountant_agent()`
- **Tools (20):** TBankBalance, TBankStatement, TributeRevenue, EVMPortfolio, EVMTransactions, SolanaPortfolio, SolanaTransactions, TONPortfolio, TONTransactions, CryptoPrice, PortfolioSummary, ScreenshotData, TinkoffData, OpenRouterUsage, ElevenLabsUsage, OpenAIUsage, PapayaPositions, StacksPortfolio, ForexRates, EventumPortfolio
- **Tags:** `finance, budget, revenue, p&l, portfolio, crypto, banking, billing, tribute, costs, forex, transactions`
- **MCP:** `cfo-mcp` (8 tools) + `tribute-mcp` (4 tools) — Active
- **Telegram:** `src/telegram/` — CFO bot with vision + CSV
- **Triggers:** CEO delegation, Tribute webhook, daily scheduler
- **Data:** Encrypted via AES-256 vault

### CTO Мартин Эчеверрия
- **Role:** Architecture, code audit, API health, technical decisions
- **Model:** `openrouter/anthropic/claude-sonnet-4`
- **Personality:** Systematic, T=0.2, thorough
- **YAML:** `agents/automator.yaml`
- **Factory:** `src/agents.py:create_automator_agent()`
- **Tools (7):** SystemHealthChecker, IntegrationManager, APIHealthMonitor, AgentPromptWriter, AgentImprovementAdvisor, WebSearchTool, WebPageReaderTool
- **Tags:** `architecture, infrastructure, mcp, code, api, health, deployment, testing, audit, security, devops, monitoring`
- **Triggers:**
  - Night cron (CTO code audit, 4x/day proposals)
  - CEO delegation
  - API health check (every 30 min via scheduler)
- **Proposals:** Auto-generates improvement proposals → CEO approval workflow

### SMM Юки Пак
- **Role:** Content generation, social media publishing, podcasts
- **Model:** `openrouter/anthropic/claude-3.5-haiku`
- **Personality:** Provocative, T=0.7, creative
- **YAML:** `agents/yuki.yaml`
- **Factory:** `src/agents.py:create_smm_agent()`
- **Tools (7):** ContentGenerator, YukiMemory, LinkedInTimPublisher, LinkedInKristinaPublisher, ThreadsTimPublisher, ThreadsKristinaPublisher, PodcastScriptGenerator
- **Tags:** `content, linkedin, threads, post, podcast, social, copywriting, seo, brand`
- **Telegram:** `src/telegram_yuki/` — SMM bot with approve flow
- **Triggers:** CEO delegation, `/пост <topic>`, `/подкаст <topic>`, scheduled posts
- **Publishing accounts:**
  - Tim Zinin: LinkedIn (`LINKEDIN_ACCESS_TOKEN`) + Threads (`THREADS_ACCESS_TOKEN`)
  - Kristina Zhukova: LinkedIn (`LINKEDIN_ACCESS_TOKEN_KRISTINA`) + Threads (pending)

### Designer Райан Чэнь
- **Role:** Visual content, infographics, charts, video
- **Model:** `openrouter/anthropic/claude-3.5-haiku`
- **Personality:** Aesthetic, T=0.6, visionary
- **YAML:** `agents/designer.yaml`
- **Factory:** `src/agents.py:create_designer_agent()`
- **Tools (10):** ImageGenerator, ImageEnhancer, ChartGenerator, InfographicBuilder, VisualAnalyzer, VideoCreator, TelegraphPublisher, DesignSystemManager, ImageResizer, BrandVoiceVisual
- **Tags:** `design, visual, image, infographic, chart, video, branding, ui, ux`
- **Triggers:** SMM request (content needs visual), CEO delegation
- **Image gen:** Gemini 2.5 Flash (free) → Pollinations (fallback)

### CPO Софи Андерсен
- **Role:** Product management, backlog, sprint tracking, feature health
- **Model:** `openrouter/anthropic/claude-3-5-haiku-latest`
- **Personality:** Visionary product thinker, T=0.5
- **YAML:** `agents/cpo.yaml`
- **Factory:** `src/agents.py:create_cpo_agent()`
- **Tools (4):** FeatureHealthChecker, SprintTracker, BacklogAnalyzer, ProgressReporter
- **Tags:** `product, backlog, sprint, feature, roadmap, metrics, analytics, kpi`
- **Triggers:** CEO delegation, sprint review requests

---

## Planned Agents

### Analytic Agent (NEW)
- **Role:** Monitor agent performance, metrics, optimization recommendations
- **Model:** TBD (likely Claude 3.5 Haiku)
- **Personality:** Analytical, T=0.1, data-only
- **Triggers:** Every 6 hours, CEO request
- **Tools (planned):** agent-metrics, token-tracker, dashboard-gen
- **Deliverables:** Daily report → CEO bot, token usage alerts, performance recommendations
- **Status:** Sprint 2+ (after Agent Teams validation)

---

## Inter-Agent Communication

### Current (CrewAI)
- **Delegation:** CEO → any agent via DelegateTaskTool
- **Context chains:** `strategic_review()` = CFO + CTO → CEO synthesis
- **Reports:** `corporation_report()` = all agents → CEO synthesis
- **State:** SharedCorporationState (financial + tech + content + product snapshots)

### Target (Agent Teams)
- **Mailbox:** Direct agent-to-agent messages
- **Shared task list:** Self-coordination with task claiming
- **CLAUDE.md:** Shared context for all teammates
- **MCP:** Tools for accessing existing bot data

---

## Escalation Rules (v2.3)

When CEO cannot assign a task (no agent's tags match), he escalates to Tim with up to 4 options:

| Option | When | Example |
|--------|------|---------|
| Extend agent prompt | Task close to existing competency | "Add `seo` tag to SMM Юки" |
| Create new agent | New responsibility zone (3+ similar tasks) | "Create SEO micro-agent" |
| Split task | Too broad, crosses competencies | "Split: copy → Юки, tech SEO → CTO" |
| Manual assign | One-off or obsolete task | "Assign to CTO" or "Archive" |

**Evolution:** Each Tim's decision permanently expands the system. Extended prompt → future tasks auto-route. New agent → whole responsibility zone covered.

---

## Handoff Rules

| From | To | Trigger | Data |
|------|----|---------|------|
| CEO | CFO | Financial question | Task description |
| CEO | CTO | Technical question | Task description |
| CEO | SMM | Content request | Topic + author |
| CEO | Designer | Visual request | Design brief |
| CEO | CPO | Product question | Feature/sprint context |
| CTO | CEO | Improvement proposal | Proposal JSON |
| SMM | Designer | Image needed | Post text + topic |
| CFO | CEO | Alert (budget deviation) | Financial snapshot |
