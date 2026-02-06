"""
🏢 AI Corporation — Web Interface
Streamlit app for interacting with CrewAI agents
"""

import os
import sys
import yaml
import streamlit as st
from datetime import datetime

# Add src to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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
    .stChatMessage {
        background: #1a1a2e;
        border-radius: 12px;
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
        st.subheader("Общение с командой агентов")

        # Initialize chat history
        if "messages" not in st.session_state:
            st.session_state.messages = [
                {"role": "assistant", "content": "👋 Привет! Я Управленец — CEO AI-корпорации. Чем могу помочь?"}
            ]

        # Display chat messages
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        # Chat input
        if prompt := st.chat_input("Напишите сообщение..."):
            # Add user message
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            # Check if API is configured
            if not api_ready:
                response = """⚠️ **API не настроен**

Добавьте `OPENROUTER_API_KEY` в переменные окружения Railway:

```bash
railway variables set OPENROUTER_API_KEY=sk-or-v1-ваш-ключ
```

Получить ключ: https://openrouter.ai/keys"""

            else:
                corp = get_corporation()
                if corp and corp.is_ready:
                    with st.spinner("🤖 Думаю..."):
                        response = corp.execute_task(prompt, "manager")
                else:
                    response = f"""🤖 **Получено сообщение:**

> {prompt}

---

⚠️ **CrewAI инициализируется...**

Агенты сконфигурированы, но не все зависимости загружены.
Попробуйте перезагрузить страницу."""

            # Add assistant response
            st.session_state.messages.append({"role": "assistant", "content": response})
            with st.chat_message("assistant"):
                st.markdown(response)

    # Tab 2: Agents
    with tab2:
        st.subheader("Команда агентов")

        col1, col2, col3 = st.columns(3)

        agents_info = [
            {
                "name": "👑 Управленец",
                "file": "manager",
                "status": "ready" if api_ready else "pending",
                "model": "Claude Sonnet 4",
                "role": "CEO, координация",
            },
            {
                "name": "📊 Бухгалтер",
                "file": "accountant",
                "status": "ready" if api_ready else "pending",
                "model": "Claude Haiku",
                "role": "Финансы, P&L",
            },
            {
                "name": "⚙️ Автоматизатор",
                "file": "automator",
                "status": "ready" if api_ready else "pending",
                "model": "Claude Sonnet",
                "role": "Интеграции",
            },
        ]

        for i, agent in enumerate(agents_info):
            with [col1, col2, col3][i]:
                config = load_agent_config(agent["file"])

                st.markdown(f"### {agent['name']}")

                status_class = "status-ready" if agent["status"] == "ready" else "status-pending"
                status_text = "Активен" if agent["status"] == "ready" else "Ожидает API"
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
                "description": "MRR, расходы на API, P&L",
                "method": "financial_report",
            },
            {
                "name": "🔧 Проверка систем",
                "agent": "automator",
                "description": "Статус интеграций, логи ошибок",
                "method": "system_health_check",
            },
        ]

        for task in tasks:
            with st.container():
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**{task['name']}**")
                    st.caption(f"{task['description']} • Агент: {task['agent']}")
                with col2:
                    disabled = not api_ready
                    if st.button("Запустить", key=task["name"], disabled=disabled):
                        corp = get_corporation()
                        if corp and corp.is_ready:
                            with st.spinner(f"⏳ Выполняю {task['name']}..."):
                                method = getattr(corp, task["method"])
                                result = method()
                            st.success("✅ Готово!")
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
            st.metric("Агентов", "3")
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
