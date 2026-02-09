"""Strategic Dashboard — CEO-level overview for Zinin Corp.

Displays KPI metrics, quality scores from LLM-as-Judge,
agent activity, corporation state snapshots, and quick actions.
"""

import logging
from datetime import datetime, timedelta

import streamlit as st

logger = logging.getLogger(__name__)

# Agent display config (matches app.py AGENTS)
_AGENT_INFO = {
    "manager": {"name": "Алексей", "emoji": "👑", "color": "#e74c3c", "title": "CEO"},
    "accountant": {"name": "Маттиас", "emoji": "🏦", "color": "#f39c12", "title": "CFO"},
    "smm": {"name": "Юки", "emoji": "📱", "color": "#e91e63", "title": "SMM"},
    "automator": {"name": "Мартин", "emoji": "⚙️", "color": "#2ecc71", "title": "CTO"},
    "designer": {"name": "Райан", "emoji": "🎨", "color": "#9b59b6", "title": "Designer"},
    "cpo": {"name": "Софи", "emoji": "📋", "color": "#3498db", "title": "CPO"},
}


def render_strategic_dashboard():
    """Render the strategic dashboard page."""
    st.markdown("## 📊 Стратегический обзор")
    st.caption("CEO-дашборд Zinin Corp")

    _render_kpi_row()
    _render_corporation_state()
    _render_quality_section()
    _render_agent_status()
    _render_quick_actions()


def _render_kpi_row():
    """Top row: 4 KPI metric cards."""
    from ..activity_tracker import (
        get_agent_task_count,
        get_quality_summary,
        get_all_statuses,
    )

    quality = get_quality_summary()
    statuses = get_all_statuses()

    # Count tasks in last 24h across all agents
    total_tasks_24h = 0
    for agent_key in _AGENT_INFO:
        total_tasks_24h += get_agent_task_count(agent_key)

    # Count active agents
    active_agents = sum(
        1 for s in statuses.values() if s.get("status") == "working"
    )
    total_agents = len(_AGENT_INFO)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Задачи (24ч)", total_tasks_24h)
    with col2:
        avg_display = f"{quality['avg']:.1f}/5" if quality["count"] else "—"
        st.metric("Качество", avg_display)
    with col3:
        pass_display = f"{quality['passed_pct']}%" if quality["count"] else "—"
        st.metric("Pass Rate", pass_display)
    with col4:
        st.metric("Агенты", f"{active_agents}/{total_agents} активны")


def _render_corporation_state():
    """Corporation state overview from SharedCorporationState."""
    try:
        from ..models.corporation_state import load_shared_state, get_active_alerts
    except ImportError:
        return

    state = load_shared_state()

    st.markdown("### 🏢 Состояние корпорации")

    # Department snapshots in 4 columns
    col_fin, col_tech, col_content, col_product = st.columns(4)

    with col_fin:
        f = state.financial
        st.markdown("**💰 Финансы**")
        if f.updated_at:
            st.metric("Банк", f"{f.bank_balance_rub:,.0f} ₽")
            st.metric("Крипто", f"${f.crypto_portfolio_usd:,.0f}")
            st.metric("API", f"${f.api_costs_usd:,.2f}")
            st.caption(f"Обн. {f.updated_at[:10]}")
        else:
            st.caption("Нет данных")

    with col_tech:
        t = state.tech
        st.markdown("**⚙️ Техника**")
        if t.updated_at:
            status_icon = {"healthy": "🟢", "degraded": "🟡", "critical": "🔴"}.get(
                t.overall_status, "⚪"
            )
            st.metric("Статус", f"{status_icon} {t.overall_status}")
            st.metric("Сервисы", f"{t.services_up}/{t.services_total}")
            if t.errors_count:
                st.metric("Ошибки", t.errors_count)
            st.caption(f"Обн. {t.updated_at[:10]}")
        else:
            st.caption("Нет данных")

    with col_content:
        c = state.content
        st.markdown("**📱 Контент**")
        if c.updated_at:
            st.metric("Создано", c.posts_generated)
            st.metric("Опубликовано", c.posts_published)
            st.metric("LinkedIn", c.linkedin_status)
            st.caption(f"Обн. {c.updated_at[:10]}")
        else:
            st.caption("Нет данных")

    with col_product:
        p = state.product
        st.markdown("**📋 Продукт**")
        if p.updated_at:
            done_pct = (p.features_done / p.features_total * 100) if p.features_total else 0
            st.metric("Фичи", f"{p.features_done}/{p.features_total} ({done_pct:.0f}%)")
            if p.current_sprint:
                st.metric("Спринт", f"{p.current_sprint} ({p.sprint_progress_pct}%)")
            if p.features_blocked:
                st.metric("Заблокировано", p.features_blocked)
            st.caption(f"Обн. {p.updated_at[:10]}")
        else:
            st.caption("Нет данных")

    # Alerts and decisions row
    alerts = get_active_alerts()
    has_alerts = bool(alerts)
    has_decisions = bool(state.decisions)

    if has_alerts or has_decisions:
        col_alerts, col_decisions = st.columns(2)

        if has_alerts:
            with col_alerts:
                st.markdown(f"**⚠️ Алерты ({len(alerts)})**")
                for a in alerts[-5:]:
                    icon = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(
                        a.severity, "🔵"
                    )
                    st.markdown(f"{icon} {a.message}")

        if has_decisions:
            with col_decisions:
                st.markdown("**📝 Последние решения**")
                for d in state.decisions[-3:]:
                    st.markdown(f"• {d.decision}")

    # Timestamps
    timestamps = []
    if state.last_strategic_review:
        try:
            dt = datetime.fromisoformat(state.last_strategic_review)
            timestamps.append(f"Стратобзор: {dt.strftime('%d.%m %H:%M')}")
        except (ValueError, TypeError):
            pass
    if state.last_full_report:
        try:
            dt = datetime.fromisoformat(state.last_full_report)
            timestamps.append(f"Полный отчёт: {dt.strftime('%d.%m %H:%M')}")
        except (ValueError, TypeError):
            pass
    if timestamps:
        st.caption(" | ".join(timestamps))

    st.divider()


def _render_quality_section():
    """Quality by agent chart + recent scores table."""
    from ..activity_tracker import get_quality_summary, get_quality_scores

    quality = get_quality_summary()
    scores = get_quality_scores(hours=168, limit=20)

    st.markdown("### Качество ответов агентов")

    if not scores:
        st.info("Нет данных о качестве. Оценки появятся после выполнения задач агентами.")
        return

    col_chart, col_table = st.columns([1, 1])

    with col_chart:
        _render_quality_chart(quality)

    with col_table:
        _render_scores_table(scores)


def _render_quality_chart(quality: dict):
    """Bar chart of average quality per agent."""
    by_agent = quality.get("by_agent", {})
    if not by_agent:
        st.caption("Нет данных для графика")
        return

    try:
        import plotly.graph_objects as go

        agents = []
        values = []
        colors = []
        for key, avg_score in by_agent.items():
            info = _AGENT_INFO.get(key, {"name": key, "emoji": "", "color": "#888"})
            agents.append(f"{info['emoji']} {info['name']}")
            values.append(avg_score)
            colors.append(info["color"])

        fig = go.Figure(go.Bar(
            x=agents,
            y=values,
            marker_color=colors,
            text=[f"{v:.1f}" for v in values],
            textposition="auto",
        ))
        fig.update_layout(
            title="Среднее качество по агентам",
            yaxis=dict(range=[0, 5], title="Оценка (1-5)"),
            xaxis=dict(title=""),
            height=300,
            margin=dict(l=40, r=20, t=40, b=40),
            template="plotly_dark",
        )
        st.plotly_chart(fig, use_container_width=True)
    except ImportError:
        # Fallback without plotly
        st.markdown("**Среднее качество:**")
        for key, avg_score in by_agent.items():
            info = _AGENT_INFO.get(key, {"name": key, "emoji": ""})
            bar = "█" * int(avg_score) + "░" * (5 - int(avg_score))
            st.text(f"{info['emoji']} {info['name']}: {bar} {avg_score:.1f}/5")


def _render_scores_table(scores: list[dict]):
    """Recent quality scores table with pass/fail indicators."""
    st.markdown("**Последние оценки:**")

    for s in reversed(scores[-10:]):
        agent_key = s.get("agent", "?")
        info = _AGENT_INFO.get(agent_key, {"name": agent_key, "emoji": "?"})
        score = s.get("score", 0)
        details = s.get("details", {})
        passed = details.get("passed", False)
        icon = "✅" if passed else "❌"
        task = s.get("task", "—")[:60]

        # Timestamp formatting
        ts = s.get("timestamp", "")
        try:
            dt = datetime.fromisoformat(ts)
            time_str = dt.strftime("%d.%m %H:%M")
        except (ValueError, TypeError):
            time_str = "?"

        # Color based on score
        if score >= 4:
            score_color = "green"
        elif score >= 3:
            score_color = "orange"
        else:
            score_color = "red"

        st.markdown(
            f"{icon} **{info['emoji']} {info['name']}** — "
            f":{score_color}[{score:.1f}/5] — {task} "
            f"<small>({time_str})</small>",
            unsafe_allow_html=True,
        )


def _render_agent_status():
    """Compact agent status cards."""
    from ..activity_tracker import get_all_statuses, get_agent_task_count

    st.markdown("### Статус агентов")
    statuses = get_all_statuses()

    cols = st.columns(len(_AGENT_INFO))
    for i, (key, info) in enumerate(_AGENT_INFO.items()):
        with cols[i]:
            status_data = statuses.get(key, {})
            status = status_data.get("status", "idle")
            task_count = get_agent_task_count(key)

            status_map = {
                "idle": ("🟢", "Свободен"),
                "working": ("🟡", "Работает"),
                "communicating": ("🔵", "Общается"),
            }
            dot, label = status_map.get(status, ("⚪", status))

            st.markdown(
                f"**{info['emoji']} {info['name']}**\n\n"
                f"{dot} {label}\n\n"
                f"Задач за 24ч: **{task_count}**"
            )


def _render_quick_actions():
    """Quick action buttons for common CEO tasks."""
    st.markdown("### Быстрые действия")

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("📈 Стратегический обзор", use_container_width=True):
            st.session_state["quick_task"] = "strategic_review"
            st.session_state["nav_page"] = "💬 Чат"
            st.rerun()
    with col2:
        if st.button("💰 Финансовый отчёт", use_container_width=True):
            st.session_state["quick_task"] = "financial_report"
            st.session_state["nav_page"] = "💬 Чат"
            st.rerun()
    with col3:
        if st.button("📋 Полный отчёт", use_container_width=True):
            st.session_state["quick_task"] = "full_report"
            st.session_state["nav_page"] = "💬 Чат"
            st.rerun()
