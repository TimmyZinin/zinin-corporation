"""
🏢 AI Corporation — Web Interface
Streamlit app for interacting with CrewAI agents
"""

import os
import re
import sys
import yaml
import streamlit as st
from datetime import datetime

# Add src to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ──────────────────────────────────────────────────────────
# Agent registry — single source of truth for all agents
# ──────────────────────────────────────────────────────────
AGENTS = {
    "manager": {
        "name": "Санторо",
        "emoji": "👑",
        "flag": "🇮🇹",
        "title": "CEO",
        "keywords": ["санторо", "ceo", "директор", "босс", "шеф", "стратеги", "управлен"],
    },
    "accountant": {
        "name": "Амара",
        "emoji": "📊",
        "flag": "🇸🇳",
        "title": "Финансы",
        "keywords": ["амара", "бухгалтер", "финанс", "деньги", "бюджет", "отчёт", "p&l", "roi", "подписк", "подписок", "расход", "трат", "прибыл", "убыт", "mrr", "выручк"],
    },
    "smm": {
        "name": "Юки",
        "emoji": "📱",
        "flag": "🇰🇷",
        "title": "SMM",
        "keywords": ["юки", "smm", "пост", "контент", "linkedin", "публикац", "генерац", "статья", "копирайт", "текст для", "опубликуй", "напиши пост"],
    },
    "automator": {
        "name": "Нирадж",
        "emoji": "⚙️",
        "flag": "🇳🇵",
        "title": "Техдир",
        "keywords": ["нирадж", "техдир", "техник", "интеграц", "автоматиз", "деплой", "код", "webhook", "cron"],
    },
}


def detect_agent(message: str) -> str:
    """Detect which agent is being addressed in the message.

    Priority: @mention > name mention > keyword match > default (manager)
    """
    text = message.lower().strip()

    # 1) @mention: @Санторо, @Амара, @Нирадж
    for key, info in AGENTS.items():
        if f"@{info['name'].lower()}" in text:
            return key

    # 2) Direct name mention
    for key, info in AGENTS.items():
        if info["name"].lower() in text:
            return key

    # 3) Keyword match (first match wins by keyword specificity)
    for key, info in AGENTS.items():
        if key == "manager":
            continue  # check manager last (it's default)
        for kw in info["keywords"]:
            if kw in text:
                return key

    # 4) Default to CEO
    return "manager"


def format_chat_context(messages: list, max_messages: int = 10) -> str:
    """Format recent chat history as context for the agent."""
    recent = messages[-(max_messages + 1):-1]  # exclude the current message
    if not recent:
        return ""

    lines = ["Контекст предыдущей переписки в корпоративном чате:"]
    for msg in recent:
        if msg["role"] == "user":
            lines.append(f"Тим: {msg['content']}")
        else:
            agent_name = msg.get("agent_name", "Санторо")
            lines.append(f"{agent_name}: {msg['content'][:300]}")
    return "\n".join(lines)

# Page config
st.set_page_config(
    page_title="AI Corporation",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 800;
        background: linear-gradient(135deg, #6c5ce7, #00cec9);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    .agent-card {
        background: #1a1a2e;
        border: 1px solid #2d2d44;
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1rem;
    }
    .status-ready { color: #00cec9; }
    .status-pending { color: #ffc107; }
    .status-error { color: #ff6b6b; }
    /* Full-width chat messages */
    .stChatMessage {
        background: #1a1a2e;
        border-radius: 12px;
        max-width: 100% !important;
    }
    .stChatMessage [data-testid="stMarkdownContainer"] {
        max-width: 100% !important;
        width: 100% !important;
    }
    /* Make main block full width */
    .block-container {
        max-width: 100% !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
    }
    /* Chat container scrollable area */
    [data-testid="stVerticalBlockBorderWrapper"] > div > div[data-testid="stVerticalBlock"] {
        max-width: 100% !important;
    }
</style>
""", unsafe_allow_html=True)


def load_agent_config(agent_name: str) -> dict:
    """Load agent configuration from YAML file"""
    try:
        paths = [
            f"/app/agents/{agent_name}.yaml",
            f"agents/{agent_name}.yaml",
        ]
        for path in paths:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f)
    except Exception as e:
        st.error(f"Error loading {agent_name}: {e}")
    return {}


def check_env_vars() -> dict:
    """Check required environment variables"""
    required = {
        'OPENROUTER_API_KEY': os.getenv('OPENROUTER_API_KEY'),
        'OPENAI_API_BASE': os.getenv('OPENAI_API_BASE', 'https://openrouter.ai/api/v1'),
        'OPENAI_MODEL_NAME': os.getenv('OPENAI_MODEL_NAME', 'openrouter/anthropic/claude-sonnet-4-20250514'),
    }
    optional = {
        'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY'),
        'DATABASE_URL': os.getenv('DATABASE_URL'),
    }
    return {'required': required, 'optional': optional}


def get_corporation():
    """Get AI Corporation instance (lazy init)"""
    if 'corporation' not in st.session_state:
        try:
            from src.crew import get_corporation as _get_corp
            corp = _get_corp()
            if corp.initialize():
                st.session_state.corporation = corp
                st.session_state.corp_ready = True
            else:
                st.session_state.corporation = None
                st.session_state.corp_ready = False
        except Exception as e:
            st.session_state.corporation = None
            st.session_state.corp_ready = False
            st.session_state.corp_error = str(e)
    return st.session_state.get('corporation')


def main():
    # Header
    st.markdown('<h1 class="main-header">🏢 AI Corporation</h1>', unsafe_allow_html=True)
    st.caption("Мульти-агентная система для управления сообществами")

    env_status = check_env_vars()

    # Sidebar - Status
    with st.sidebar:
        st.header("⚙️ Статус системы")

        # Check API keys
        if env_status['required']['OPENROUTER_API_KEY']:
            st.success("✅ OpenRouter API подключен")
            api_ready = True
        else:
            st.error("❌ OPENROUTER_API_KEY не настроен")
            api_ready = False

        if env_status['optional']['OPENAI_API_KEY']:
            st.success("✅ OpenAI (embeddings) подключен")
        else:
            st.warning("⚠️ OPENAI_API_KEY не настроен (embeddings)")

        if env_status['optional']['DATABASE_URL']:
            st.success("✅ PostgreSQL подключен")
        else:
            st.info("ℹ️ Память в режиме in-memory")

        st.divider()

        # CrewAI Status
        st.subheader("🤖 CrewAI")
        if api_ready:
            corp = get_corporation()
            if corp and corp.is_ready:
                st.success("✅ Агенты готовы к работе")
            else:
                error = st.session_state.get('corp_error', 'Инициализация не выполнена')
                st.warning(f"⚠️ {error}")
        else:
            st.info("ℹ️ Добавьте API ключ для активации")

        st.divider()

        # Model info
        st.subheader("🧠 Модель")
        st.code(env_status['required']['OPENAI_MODEL_NAME'])

        st.divider()
        st.caption(f"Запущено: {datetime.now().strftime('%d.%m.%Y %H:%M')}")

    # Main content - Tabs
    tab1, tab2, tab3, tab4 = st.tabs(["💬 Чат", "👥 Агенты", "📋 Задачи", "📊 Статистика"])

    # Tab 1: Chat
    with tab1:
        # Hint about addressing agents
        st.caption("💡 Обращайтесь к агентам по имени: **Санторо**, **Амара**, **Юки**, **Нирадж** — или просто пишите, ответит CEO")

        # Initialize chat history
        if "messages" not in st.session_state:
            st.session_state.messages = [
                {
                    "role": "assistant",
                    "content": "Ciao! 👋 Я Санторо — CEO AI-корпорации. Со мной в команде Амара (📊 финансы), Юки (📱 контент) и Нирадж (⚙️ техника). Обращайтесь к любому из нас по имени!",
                    "agent_key": "manager",
                    "agent_name": "Санторо",
                }
            ]

        # Scrollable chat history container
        chat_container = st.container(height=550)
        with chat_container:
            for message in st.session_state.messages:
                if message["role"] == "user":
                    with st.chat_message("user"):
                        st.markdown(message["content"])
                else:
                    agent_key = message.get("agent_key", "manager")
                    agent_info = AGENTS.get(agent_key, AGENTS["manager"])
                    display_name = f"{agent_info['flag']} {agent_info['name']}"
                    with st.chat_message(display_name, avatar=agent_info["emoji"]):
                        st.markdown(message["content"])

        # Chat input at the bottom
        if prompt := st.chat_input("Напишите сообщение... (можно @Амара или @Нирадж)"):
            # Add user message
            st.session_state.messages.append({"role": "user", "content": prompt})

            # Detect target agent
            target_key = detect_agent(prompt)
            target_info = AGENTS[target_key]

            # Check if API is configured
            if not api_ready:
                response = """⚠️ **API не настроен**

Добавьте `OPENROUTER_API_KEY` в переменные окружения Railway:

```bash
railway variables set OPENROUTER_API_KEY=sk-or-v1-ваш-ключ
```

Получить ключ: https://openrouter.ai/keys"""
                agent_key_resp = "manager"

            else:
                corp = get_corporation()
                if corp and corp.is_ready:
                    # Build context from chat history
                    context = format_chat_context(st.session_state.messages)
                    task_with_context = prompt
                    if context:
                        task_with_context = f"{context}\n\n---\nНовое сообщение от Тима: {prompt}"

                    with st.spinner(f"{target_info['emoji']} {target_info['name']} думает..."):
                        response = corp.execute_task(task_with_context, target_key)
                    agent_key_resp = target_key
                else:
                    response = f"""🤖 **Получено сообщение:**

> {prompt}

---

⚠️ **CrewAI инициализируется...**

Агенты сконфигурированы, но не все зависимости загружены.
Попробуйте перезагрузить страницу."""
                    agent_key_resp = "manager"

            # Add assistant response with agent identity
            st.session_state.messages.append({
                "role": "assistant",
                "content": response,
                "agent_key": agent_key_resp,
                "agent_name": AGENTS[agent_key_resp]["name"],
            })
            st.rerun()

    # Tab 2: Agents
    with tab2:
        st.subheader("Команда агентов")

        agents_display = [
            {
                "key": "manager",
                "yaml": "manager",
                "model": "Claude Sonnet 4",
                "role": "CEO, стратегия, веб-поиск",
            },
            {
                "key": "accountant",
                "yaml": "accountant",
                "model": "Claude 3.5 Haiku",
                "role": "P&L, ROI, подписки, API бюджет",
            },
            {
                "key": "smm",
                "yaml": "yuki",
                "model": "Llama 3.3 70B (free)",
                "role": "Контент, LinkedIn, Self-Refine",
            },
            {
                "key": "automator",
                "yaml": "automator",
                "model": "Claude Sonnet 4",
                "role": "Интеграции, автоматизация, веб-поиск",
            },
        ]

        cols = st.columns(len(agents_display))

        for i, agent in enumerate(agents_display):
            with cols[i]:
                info = AGENTS[agent["key"]]
                config = load_agent_config(agent["yaml"])

                # Use avatar image for Yuki if available
                avatar_path = None
                if agent["key"] == "smm":
                    for p in ["/app/data/avatars/yuki.jpg", "data/avatars/yuki.jpg"]:
                        if os.path.exists(p):
                            avatar_path = p
                            break

                if avatar_path:
                    st.image(avatar_path, width=80)
                st.markdown(f"### {info['emoji']} {info['name']} ({info['title']}) {info['flag']}")

                status = "ready" if api_ready else "pending"
                status_class = "status-ready" if status == "ready" else "status-pending"
                status_text = "Активен" if status == "ready" else "Ожидает API"
                st.markdown(f'<span class="{status_class}">● {status_text}</span>', unsafe_allow_html=True)

                st.caption(f"**Роль:** {agent['role']}")
                st.caption(f"**Модель:** {agent['model']}")

                if config:
                    with st.expander("Показать конфигурацию"):
                        st.code(yaml.dump(config, allow_unicode=True, default_flow_style=False), language="yaml")

    # Tab 3: Tasks
    with tab3:
        st.subheader("Быстрые задачи")

        tasks = [
            {
                "name": "📈 Стратегический обзор",
                "agent": "manager",
                "description": "Анализ состояния корпорации, приоритеты на неделю",
                "method": "strategic_review",
            },
            {
                "name": "💰 Финансовый отчёт",
                "agent": "accountant",
                "description": "Полный P&L по проектам, MRR, расходы на API, ROI",
                "method": "financial_report",
            },
            {
                "name": "💻 Проверка API бюджета",
                "agent": "accountant",
                "description": "Расходы по агентам, алерты превышений",
                "method": "api_budget_check",
            },
            {
                "name": "📊 Анализ подписок",
                "agent": "accountant",
                "description": "Подписчики, прогноз MRR, отток",
                "method": "subscription_analysis",
            },
            {
                "name": "✍️ Сгенерировать пост",
                "agent": "smm",
                "description": "Юки создаст пост для LinkedIn с Self-Refine",
                "method": "generate_post",
            },
            {
                "name": "🔗 Статус LinkedIn",
                "agent": "smm",
                "description": "Проверка токена, статистика генераций Юки",
                "method": "linkedin_status",
            },
            {
                "name": "🔧 Проверка систем",
                "agent": "automator",
                "description": "Полная проверка здоровья системы, агентов, ошибок",
                "method": "system_health_check",
            },
            {
                "name": "🔌 Статус интеграций",
                "agent": "automator",
                "description": "Все внешние сервисы и cron-задачи",
                "method": "integration_status",
            },
        ]

        for task in tasks:
            with st.container():
                agent_info = AGENTS.get(task["agent"], AGENTS["manager"])
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**{task['name']}**")
                    st.caption(f"{task['description']} • {agent_info['flag']} {agent_info['name']}")
                with col2:
                    disabled = not api_ready
                    if st.button("Запустить", key=task["name"], disabled=disabled):
                        corp = get_corporation()
                        if corp and corp.is_ready:
                            with st.spinner(f"{agent_info['emoji']} {agent_info['name']} работает..."):
                                method = getattr(corp, task["method"])
                                result = method()
                            # Add result to chat history too
                            st.session_state.messages.append({
                                "role": "assistant",
                                "content": result,
                                "agent_key": task["agent"],
                                "agent_name": agent_info["name"],
                            })
                            st.success(f"✅ {agent_info['name']} завершил(а) задачу!")
                            st.markdown(result)
                        else:
                            st.error("❌ CrewAI не инициализирован")
                st.divider()

        if not api_ready:
            st.info("💡 Добавьте OPENROUTER_API_KEY для активации задач")

    # Tab 4: Stats
    with tab4:
        st.subheader("Статистика")

        col1, col2, col3, col4 = st.columns(4)

        # Get stats from session
        tasks_completed = st.session_state.get('tasks_completed', 0)
        tokens_used = st.session_state.get('tokens_used', 0)
        api_cost = st.session_state.get('api_cost', 0.0)

        with col1:
            st.metric("Агентов", "4")
        with col2:
            st.metric("Задач выполнено", tasks_completed)
        with col3:
            st.metric("Токенов", f"{tokens_used:,}")
        with col4:
            st.metric("Расходы API", f"${api_cost:.2f}")

        st.divider()

        st.subheader("📁 Проекты")

        projects = [
            {"name": "💰 Крипто маркетологи", "priority": "#1", "status": "Активен"},
            {"name": "🔧 Сборка", "priority": "#2", "status": "Активен"},
            {"name": "🌱 Ботаника", "priority": "—", "status": "Позже"},
            {"name": "👤 Личный бренд", "priority": "—", "status": "Позже"},
        ]

        for project in projects:
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                st.write(project["name"])
            with col2:
                st.caption(f"Приоритет: {project['priority']}")
            with col3:
                st.caption(project["status"])

        st.divider()

        # Setup instructions
        with st.expander("🔧 Настройка API ключей"):
            st.markdown("""
### Шаг 1: OpenRouter API (обязательно)

```bash
railway variables set OPENROUTER_API_KEY=sk-or-v1-ваш-ключ
```

Получить ключ: https://openrouter.ai/keys

### Шаг 2: OpenAI API (для embeddings/памяти)

```bash
railway variables set OPENAI_API_KEY=sk-ваш-ключ
```

Получить ключ: https://platform.openai.com/api-keys

### После добавления ключей

Перезапустите сервис:
```bash
railway service redeploy
```
            """)


if __name__ == "__main__":
    main()
