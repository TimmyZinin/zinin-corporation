# Zinin Corporation — Agent Registry v2

> Updated: February 12, 2026

---

## Active Agents

### CEO Алексей Воронов
- **Role:** Orchestrator, point of entry for Tim
- **Model:** `openrouter/anthropic/claude-sonnet-4` (via OpenRouter)
- **Personality:** Ice Peak, T=0.1, decisive, minimal words
- **YAML:** `agents/manager.yaml`
- **Factory:** `src/agents.py:create_manager_agent()`
- **Tools:** DelegateTaskTool, WebSearchTool, WebPageReaderTool
- **Telegram:** `src/telegram_ceo/` — CEO bot with 9 commands
- **Triggers:**
  - `/ceo` or any text message to CEO bot
  - `/review` — strategic review (chains CFO + CTO)
  - `/report` — full corporation report (all agents)
  - `/delegate <agent> <task>` — manual delegation
- **Delegation targets:** accountant, automator, smm, manager
- **Scheduler:** Morning briefing, weekly report, API health (30min), CTO proposals (4x/day)

### CFO Маттиас Бруннер
- **Role:** Finance, P&L, portfolio tracking, burn rate
- **Model:** `openrouter/anthropic/claude-sonnet-4`
- **Personality:** Swiss precision, T=0.1, data-driven
- **YAML:** `agents/accountant.yaml`
- **Factory:** `src/agents.py:create_accountant_agent()`
- **Tools (20):** TBankBalance, TBankStatement, TributeRevenue, EVMPortfolio, EVMTransactions, SolanaPortfolio, SolanaTransactions, TONPortfolio, TONTransactions, CryptoPrice, PortfolioSummary, ScreenshotData, TinkoffData, OpenRouterUsage, ElevenLabsUsage, OpenAIUsage, PapayaPositions, StacksPortfolio, ForexRates, EventumPortfolio
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
- **Triggers:** SMM request (content needs visual), CEO delegation
- **Image gen:** Gemini 2.5 Flash (free) → Pollinations (fallback)

### CPO Софи Андерсен
- **Role:** Product management, backlog, sprint tracking, feature health
- **Model:** `openrouter/anthropic/claude-3-5-haiku-latest`
- **Personality:** Visionary product thinker, T=0.5
- **YAML:** `agents/cpo.yaml`
- **Factory:** `src/agents.py:create_cpo_agent()`
- **Tools (4):** FeatureHealthChecker, SprintTracker, BacklogAnalyzer, ProgressReporter
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
