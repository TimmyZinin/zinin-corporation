"""
🏢 AI Corporation — Web Interface
Streamlit app for interacting with CrewAI agents
"""

import os
import re
import json
import html as html_module
import sys
import yaml
import streamlit as st
import streamlit.components.v1 as st_components
from datetime import datetime, timedelta

# Add src to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ──────────────────────────────────────────────────────────
# Agent registry — single source of truth for all agents
# ──────────────────────────────────────────────────────────
AGENTS = {
    "manager": {
        "name": "Алексей",
        "emoji": "👑",
        "flag": "🇷🇺",
        "title": "CEO",
        "keywords": ["алексей", "ceo", "директор", "босс", "шеф", "стратеги", "управлен"],
    },
    "accountant": {
        "name": "Маттиас",
        "emoji": "🏦",
        "flag": "🇨🇭",
        "title": "CFO",
        "keywords": ["маттиас", "cfo", "бухгалтер", "финанс", "деньги", "бюджет", "отчёт", "p&l", "roi", "подписк", "подписок", "расход", "затрат", "потрат", "прибыл", "убыт", "mrr", "выручк"],
    },
    "smm": {
        "name": "Юки",
        "emoji": "📱",
        "flag": "🇰🇷",
        "title": "Head of SMM",
        "keywords": ["юки", "smm", "пост", "контент", "linkedin", "публикац", "генерац", "статья", "копирайт", "текст для", "опубликуй", "напиши пост"],
    },
    "automator": {
        "name": "Мартин",
        "emoji": "⚙️",
        "flag": "🇦🇷",
        "title": "CTO",
        "keywords": ["мартин", "cto", "техдир", "техник", "интеграц", "автоматиз", "деплой", "код", "webhook", "cron"],
    },
}

AGENT_COLORS = {
    "manager": "#e74c3c",
    "accountant": "#f39c12",
    "smm": "#e91e63",
    "automator": "#2ecc71",
}


def hex_to_rgba(hex_color: str, alpha: float) -> str:
    """Convert hex color to rgba() for browser compatibility."""
    h = hex_color.lstrip('#')
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


# ──────────────────────────────────────────────────────────
# Chat history persistence
# ──────────────────────────────────────────────────────────
def _chat_path() -> str:
    for p in ["/app/data/chat_history.json", "data/chat_history.json"]:
        parent = os.path.dirname(p)
        if os.path.isdir(parent):
            return p
    return "data/chat_history.json"


def load_chat_history() -> list:
    """Load chat messages from persistent storage."""
    path = _chat_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    return data
        except Exception:
            pass
    return []


def save_chat_history(messages: list):
    """Save chat messages to persistent storage."""
    path = _chat_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(messages, f, ensure_ascii=False, indent=2, default=str)
    except Exception:
        pass


def detect_agents(message: str) -> list[str]:
    """Detect ALL agents being addressed in the message. Returns list of agent keys."""
    text = message.lower().strip()
    found = []

    # Check for "all" keywords
    all_keywords = ["всем", "все агенты", "вся команда", "всей команде"]
    for kw in all_keywords:
        if kw in text:
            return list(AGENTS.keys())

    # 1) @mentions
    for key, info in AGENTS.items():
        if f"@{info['name'].lower()}" in text:
            if key not in found:
                found.append(key)

    if found:
        return found

    # 2) Direct name mentions
    for key, info in AGENTS.items():
        if info["name"].lower() in text:
            if key not in found:
                found.append(key)

    if found:
        return found

    # 3) Keyword match
    for key, info in AGENTS.items():
        if key == "manager":
            continue
        for kw in info["keywords"]:
            if kw in text:
                if key not in found:
                    found.append(key)
                break

    if found:
        return found

    # 4) Default to last agent or CEO
    return [st.session_state.get("last_agent_key", "manager")]


def detect_agent(message: str) -> str:
    """Detect single agent (backward compat). Returns first detected agent."""
    agents = detect_agents(message)
    return agents[0] if agents else "manager"


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
            agent_name = msg.get("agent_name", "Алексей")
            lines.append(f"{agent_name}: {msg['content'][:300]}")
    return "\n".join(lines)


def md_to_html(text: str) -> str:
    """Convert markdown text to safe HTML for chat display."""
    if not text or not text.strip():
        return ''
    segments = re.split(r'(```(?:\w*)\n[\s\S]*?```)', text)
    html_parts = []

    for segment in segments:
        if segment.startswith('```'):
            match = re.match(r'```(\w*)\n([\s\S]*?)```', segment)
            if match:
                code = html_module.escape(match.group(2).rstrip())
                html_parts.append(
                    f'<pre class="zc-code-block"><code>{code}</code></pre>'
                )
            else:
                # #46: malformed code block fallback
                html_parts.append(
                    f'<pre class="zc-code-block"><code>{html_module.escape(segment)}</code></pre>'
                )
        else:
            # #13: extract links BEFORE escaping to preserve & in URLs
            links = []
            def _link_sub(m):
                links.append((m.group(1), m.group(2)))
                return f'%%ZCL{len(links) - 1}%%'
            t = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', _link_sub, segment)
            # Extract inline code BEFORE escaping to prevent markdown inside code
            inline_codes = []
            def _code_sub(m):
                inline_codes.append(html_module.escape(m.group(1)))
                return f'%%ZCC{len(inline_codes) - 1}%%'
            t = re.sub(r'`([^`\n]+)`', _code_sub, t)
            t = html_module.escape(t)
            # #11: bold+italic before separate bold/italic
            t = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', t)
            t = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', t)
            t = re.sub(r'(?<!\*)\*([^*\n]+)\*(?!\*)', r'<em>\1</em>', t)
            # Headings
            t = re.sub(r'^###\s+(.+)$', r'<div class="zc-h3">\1</div>', t, flags=re.MULTILINE)
            t = re.sub(r'^##\s+(.+)$', r'<div class="zc-h2">\1</div>', t, flags=re.MULTILINE)
            t = re.sub(r'^#\s+(.+)$', r'<div class="zc-h1">\1</div>', t, flags=re.MULTILINE)
            # #16: blockquotes (after html escape, > becomes &gt;)
            t = re.sub(r'^&gt;\s+(.+)$', r'<div class="zc-bq">\1</div>', t, flags=re.MULTILINE)
            # Lists
            t = re.sub(r'^(\d+)\.\s+(.+)$', r'<div class="zc-li-num"><span class="zc-num">\1.</span> \2</div>', t, flags=re.MULTILINE)
            t = re.sub(r'^[\-\*]\s+(.+)$', r'<div class="zc-li">\1</div>', t, flags=re.MULTILINE)
            t = re.sub(r'^-{3,}$', '<hr class="zc-hr">', t, flags=re.MULTILINE)
            # #13: restore links with safe labels and raw URLs
            for i, (label, url) in enumerate(links):
                safe_label = html_module.escape(label)
                safe_url = html_module.escape(url, quote=True)
                t = t.replace(
                    f'%%ZCL{i}%%',
                    f'<a href="{safe_url}" target="_blank" rel="noopener" class="zc-link">{safe_label} <span class="zc-ext" aria-label="opens in new tab">\u2197</span></a>',
                )
            # Restore inline code (after all markdown processing)
            for i, code_content in enumerate(inline_codes):
                t = t.replace(f'%%ZCC{i}%%', f'<code class="zc-inline-code">{code_content}</code>')
            # Newlines
            t = t.replace('\n\n', '<br><br>')
            t = t.replace('\n', '<br>')
            html_parts.append(t)

    return ''.join(html_parts)


def ru_plural(n: int, one: str, few: str, many: str) -> str:
    """Russian pluralization: 1 сообщение, 2 сообщения, 5 сообщений."""
    if n % 10 == 1 and n % 100 != 11:
        return f"{n} {one}"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return f"{n} {few}"
    return f"{n} {many}"


def render_chat_html(messages: list) -> str:
    """Render all chat messages as modern HTML."""
    # #32: ARIA roles for accessibility
    parts = ['<div class="zc-chat" role="log" aria-label="Корпоративный чат" aria-live="polite">']
    prev_role = None
    prev_agent_key = None
    prev_date = None
    total = len(messages)

    for idx, msg in enumerate(messages):
        role = msg["role"]
        content = msg["content"]
        msg_time = msg.get("time", "")
        msg_date = msg.get("date", datetime.now().strftime("%d.%m.%Y"))
        agent_key = msg.get("agent_key", "manager")
        is_last = idx == total - 1

        # #33: date separator with ARIA
        if msg_date and msg_date != prev_date:
            today_str = datetime.now().strftime("%d.%m.%Y")
            yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%d.%m.%Y")
            date_label = "Сегодня" if msg_date == today_str else ("Вчера" if msg_date == yesterday_str else msg_date)
            parts.append(f'<div class="zc-date-sep" role="separator" aria-label="Сообщения за {date_label}"><span>{date_label}</span></div>')
            prev_date = msg_date

        is_first = True
        if role == prev_role:
            if role == "user":
                is_first = False
            elif agent_key == prev_agent_key:
                is_first = False

        content_html = md_to_html(content)
        # #8: animate only the last message
        new_cls = " zc-new" if is_last else ""

        if role == "user":
            g = "" if is_first else " zc-grouped"
            sender = '<div class="zc-sender" style="color:#c4b5fd">Тим</div>' if is_first else ""
            br_cls = " zc-first" if is_first else ""
            # #32: aria-label, #37: tabindex
            parts.append(
                f'<div class="zc-row zc-sent{g}{new_cls}" role="article" aria-label="Тим, {msg_time}">'
                f'<div class="zc-bubble zc-b-sent{br_cls}" tabindex="0">'
                f'{sender}<div class="zc-text">{content_html}</div>'
                f'<span class="zc-time">{msg_time}</span></div></div>'
            )
        else:
            info = AGENTS.get(agent_key, AGENTS["manager"])
            color = AGENT_COLORS.get(agent_key, "#00cec9")
            g = "" if is_first else " zc-grouped"
            br_cls = " zc-first" if is_first else ""
            if is_first:
                avatar = f'<div class="zc-avatar" style="background:{hex_to_rgba(color, 0.08)};border-color:{color}"><span>{info["emoji"]}</span></div>'
                sender = f'<div class="zc-sender" style="color:{color}">{info["flag"]} {info["name"]} <span class="zc-role">· {info["title"]}</span></div>'
            else:
                avatar = '<div class="zc-avatar-space"></div>'
                # #35: mini role tag for grouped messages (colorblind accessibility)
                sender = f'<div class="zc-sender-mini" style="color:{color}">{info["title"]}</div>'
            # #5: colored left-border for agent differentiation, #32: aria, #37: tabindex
            parts.append(
                f'<div class="zc-row zc-received{g}{new_cls}" role="article" aria-label="{info["name"]}, {info["title"]}, {msg_time}">'
                f'{avatar}<div class="zc-bubble zc-b-recv{br_cls}" style="border-left:3px solid {color}" tabindex="0">'
                f'{sender}<div class="zc-text">{content_html}</div>'
                f'<span class="zc-time">{msg_time}</span></div></div>'
            )

        prev_role = role
        prev_agent_key = agent_key if role == "assistant" else None

    parts.append('</div>')
    return '\n'.join(parts)


# Page config
st.set_page_config(
    page_title="Zinin Corp",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS — Modern Chat UI (v2 — 50-issue audit applied)
st.markdown("""
<style>
    /* ── General ── */
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
    .block-container {
        max-width: 100% !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
    }

    /* ── Chat Container (#7: wider max-width) ── */
    .zc-chat {
        max-width: 960px;
        margin: 0 auto;
        padding: 4px 0 20px;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    }

    /* ── Date Separator (#9: horizontal rules) ── */
    .zc-date-sep {
        display: flex;
        align-items: center;
        gap: 16px;
        padding: 18px 16px 14px;
        user-select: none;
    }
    .zc-date-sep::before,
    .zc-date-sep::after {
        content: '';
        flex: 1;
        height: 1px;
        background: rgba(255,255,255,0.06);
    }
    .zc-date-sep span {
        background: rgba(255,255,255,0.055);
        color: #7e7e8e;
        font-size: 12px;
        font-weight: 500;
        padding: 5px 16px;
        border-radius: 10px;
        letter-spacing: 0.2px;
        flex-shrink: 0;
    }

    /* ── Message Row (#8: animate only last message) ── */
    .zc-row {
        display: flex;
        align-items: flex-end;
        gap: 10px;
        margin-bottom: 10px;
        padding: 0 16px;
    }
    .zc-row.zc-new { animation: zcIn 0.25s ease-out; }
    .zc-row.zc-grouped { margin-bottom: 3px; }
    .zc-row.zc-sent { justify-content: flex-end; }
    .zc-row.zc-received { justify-content: flex-start; }

    /* ── Avatar (#6: no scale jitter) ── */
    .zc-avatar {
        width: 36px;
        height: 36px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 17px;
        flex-shrink: 0;
        border: 2px solid;
        transition: box-shadow 0.15s ease;
    }
    .zc-avatar:hover { box-shadow: 0 0 0 3px rgba(255,255,255,0.08); }
    .zc-avatar-space { width: 36px; flex-shrink: 0; }

    /* ── Bubble Base (#1: different widths, #15: overflow-wrap) ── */
    .zc-bubble {
        padding: 10px 14px;
        border-radius: 18px;
        word-wrap: break-word;
        overflow-wrap: anywhere;
        word-break: break-word;
    }

    /* Sent (user) (#3: darker gradient for contrast) */
    .zc-b-sent {
        max-width: 72%;
        background: linear-gradient(135deg, #5b4bd4 0%, #4a3bc9 100%);
        color: #fff;
        border-bottom-right-radius: 6px;
    }
    .zc-b-sent.zc-first { border-top-right-radius: 20px; }
    .zc-row.zc-grouped .zc-b-sent { border-top-right-radius: 6px; border-bottom-right-radius: 6px; }

    /* Received (agent) (#1: wider) */
    .zc-b-recv {
        max-width: 85%;
        background: #151728;
        color: #e4e4e7;
        border: 1px solid #1f2240;
        border-bottom-left-radius: 6px;
    }
    .zc-b-recv.zc-first { border-top-left-radius: 20px; }
    .zc-row.zc-grouped .zc-b-recv { border-top-left-radius: 6px; border-bottom-left-radius: 6px; }

    /* ── Sender Name ── */
    .zc-sender {
        font-size: 12.5px;
        font-weight: 600;
        margin-bottom: 4px;
        letter-spacing: 0.2px;
    }
    .zc-sender-mini {
        font-size: 10px;
        font-weight: 500;
        opacity: 0.45;
        margin-bottom: 2px;
    }
    .zc-role { font-weight: 400; opacity: 0.55; font-size: 11.5px; }

    /* ── Message Text ── */
    .zc-text {
        font-size: 14.5px;
        line-height: 1.55;
        color: inherit;
    }
    .zc-text p { margin: 0; }
    .zc-text strong { font-weight: 600; color: #fff; }
    .zc-text em { font-style: italic; opacity: 0.9; }

    .zc-text .zc-link {
        color: #7cb3ff;
        text-decoration: none;
        border-bottom: 1px solid rgba(124,179,255,0.3);
        transition: border-color 0.15s;
    }
    .zc-text .zc-link:hover { border-bottom-color: #7cb3ff; }
    /* #36: external link indicator */
    .zc-ext { font-size: 10px; opacity: 0.45; vertical-align: super; margin-left: 1px; }

    /* #10: cyan-blue inline code (no clash with Маттиас orange) */
    .zc-text .zc-inline-code {
        background: rgba(255,255,255,0.08);
        padding: 2px 7px;
        border-radius: 5px;
        font-family: 'SF Mono', Menlo, Consolas, 'Liberation Mono', 'Courier New', monospace;
        font-size: 13px;
        color: #a8d8ea;
    }
    /* #2, #30: better code blocks + iOS scroll */
    .zc-text .zc-code-block {
        background: #0c0e1a;
        padding: 14px 16px;
        border-radius: 10px;
        overflow-x: auto;
        -webkit-overflow-scrolling: touch;
        scrollbar-width: thin;
        scrollbar-color: #333 transparent;
        margin: 10px -14px;
        padding-left: 16px;
        padding-right: 16px;
        border: 1px solid #1c1f38;
        font-family: 'SF Mono', Menlo, Consolas, 'Liberation Mono', 'Courier New', monospace;
        font-size: 13px;
        line-height: 1.5;
        color: #d4d4d8;
    }
    .zc-text .zc-code-block::-webkit-scrollbar { height: 6px; }
    .zc-text .zc-code-block::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.15); border-radius: 3px; }
    .zc-text .zc-code-block::-webkit-scrollbar-track { background: transparent; }
    .zc-text .zc-code-block code {
        background: none;
        padding: 0;
        color: inherit;
        font-size: inherit;
    }

    /* #14: better heading hierarchy */
    .zc-text .zc-h1 { font-size: 18px; font-weight: 700; margin: 16px 0 8px; color: #fff; border-bottom: 1px solid rgba(255,255,255,0.08); padding-bottom: 6px; }
    .zc-text .zc-h2 { font-size: 16px; font-weight: 600; margin: 14px 0 6px; color: #f0f0f3; }
    .zc-text .zc-h3 { font-size: 12.5px; font-weight: 600; margin: 10px 0 4px; color: #c8c8d0; text-transform: uppercase; letter-spacing: 0.5px; }

    .zc-text .zc-li {
        padding-left: 18px;
        position: relative;
        margin: 3px 0;
    }
    .zc-text .zc-li::before {
        content: '\2022';
        position: absolute;
        left: 5px;
        color: #6c5ce7;
    }
    .zc-text .zc-li-num {
        padding-left: 18px;
        margin: 3px 0;
    }
    .zc-text .zc-num { color: #6c5ce7; font-weight: 600; font-size: 13px; }
    .zc-text .zc-hr { border: none; border-top: 1px solid #252842; margin: 10px 0; }

    /* #16: blockquote styling */
    .zc-text .zc-bq {
        border-left: 3px solid #6c5ce7;
        padding: 4px 12px;
        margin: 6px 0;
        color: #a0a0b0;
        background: rgba(108,92,231,0.05);
        border-radius: 0 6px 6px 0;
    }

    /* ── Timestamp (#4: more readable) ── */
    .zc-time {
        display: block;
        font-size: 10.5px;
        text-align: right;
        margin-top: 4px;
        opacity: 0.45;
        user-select: none;
    }
    .zc-b-sent .zc-time { opacity: 0.55; }

    /* ── Typing Indicator ── */
    .zc-typing-row {
        display: flex;
        align-items: flex-end;
        gap: 10px;
        padding: 0 16px;
        margin-bottom: 10px;
    }
    .zc-typing-bubble {
        background: #151728;
        border: 1px solid #1f2240;
        padding: 14px 20px;
        border-radius: 18px;
        border-bottom-left-radius: 6px;
        display: inline-flex;
        gap: 5px;
        align-items: center;
    }
    .zc-typing-name {
        font-size: 12px;
        font-weight: 600;
        margin-right: 6px;
    }
    .zc-dot {
        width: 7px;
        height: 7px;
        border-radius: 50%;
        background: #555;
        animation: zcBounce 1.4s infinite;
    }
    .zc-dot:nth-child(3) { animation-delay: 0.15s; }
    .zc-dot:nth-child(4) { animation-delay: 0.3s; }

    /* ── Chat Header ── */
    .zc-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 14px 20px;
        background: rgba(18,20,34,0.5);
        border: 1px solid #1f2240;
        border-radius: 14px;
        margin-bottom: 6px;
        max-width: 960px;
        margin-left: auto;
        margin-right: auto;
        backdrop-filter: blur(12px);
    }
    .zc-header-title {
        font-size: 16px;
        font-weight: 700;
        color: #e4e4e7;
    }
    .zc-header-sub {
        font-size: 12px;
        color: #6c6c7a;
        margin-top: 2px;
    }
    .zc-online {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        display: inline-block;
        margin-right: 4px;
        animation: zcPulse 2s infinite;
    }

    /* ── Agent hint bar ── */
    .zc-agent-hints {
        max-width: 960px;
        margin: 0 auto;
        display: flex;
        gap: 8px;
        padding: 6px 16px;
        justify-content: center;
    }
    .zc-hint {
        font-size: 11px;
        padding: 3px 10px;
        border-radius: 8px;
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.06);
        opacity: 0.6;
        transition: opacity 0.15s;
    }
    .zc-hint:hover { opacity: 1; }

    /* #37: keyboard navigation */
    .zc-bubble:focus {
        outline: 2px solid rgba(108,92,231,0.5);
        outline-offset: 2px;
    }
    .zc-bubble:focus:not(:focus-visible) { outline: none; }

    /* ── Animations ── */
    @keyframes zcIn {
        from { opacity: 0; transform: translateY(8px); }
        to { opacity: 1; transform: translateY(0); }
    }
    @keyframes zcBounce {
        0%, 60%, 100% { transform: translateY(0); opacity: 0.35; }
        30% { transform: translateY(-5px); opacity: 1; }
    }
    @keyframes zcPulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.4; }
    }
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.3; }
    }

    /* ── Responsive ── */
    @media (min-width: 769px) and (max-width: 1024px) {
        .zc-chat { max-width: 100%; padding: 4px 8px 16px; }
        .zc-header { max-width: 100%; margin: 0 8px 6px; }
        .zc-b-recv { max-width: 82%; }
    }
    @media (max-width: 768px) {
        .zc-chat { padding: 4px 0 12px; }
        .zc-row { padding: 0 8px; }
        .zc-b-sent { max-width: 88%; }
        .zc-b-recv { max-width: 92%; }
        .zc-text { font-size: 14.5px; }
        .zc-avatar { width: 34px; height: 34px; font-size: 16px; }
        .zc-avatar-space { width: 34px; }
        .zc-header { margin: 0 8px 6px; }
        .zc-agent-hints { padding: 4px 8px; gap: 4px; }
        .zc-hint { font-size: 10px; padding: 2px 8px; }
    }

    /* #47: style Streamlit chat input to match theme */
    [data-testid="stChatInput"] {
        max-width: 960px !important;
        margin: 0 auto !important;
    }
    [data-testid="stChatInput"] textarea {
        border-radius: 14px !important;
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
    st.markdown('<h1 class="main-header">🏢 Zinin Corp</h1>', unsafe_allow_html=True)
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

        st.success("✅ ONNX Embedder (память, бесплатно)")

        if env_status['optional']['DATABASE_URL']:
            st.success("✅ PostgreSQL подключен")
        else:
            st.info("ℹ️ Память в режиме in-memory")

        st.divider()

        # Agent Status
        st.subheader("🤖 Агенты")
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
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(["💬 Чат", "👥 Агенты", "📋 Задачи", "📱 Контент", "📡 Мониторинг", "🎮 Дашборд", "📊 Статистика"])

    # Tab 1: Chat
    with tab1:
        # Initialize chat history (try loading from persistent storage first)
        if "messages" not in st.session_state:
            saved = load_chat_history()
            if saved:
                st.session_state.messages = saved
            else:
                st.session_state.messages = [
                    {
                        "role": "assistant",
                        "content": "Добрый день! Я Алексей Воронов — CEO AI-корпорации. Со мной Маттиас (🏦 финансы), Юки (📱 контент) и Мартин (⚙️ техника). Обращайтесь к любому из нас по имени!",
                        "agent_key": "manager",
                        "agent_name": "Алексей",
                        "time": datetime.now().strftime("%H:%M"),
                        "date": datetime.now().strftime("%d.%m.%Y"),
                    }
                ]

        # Chat header (#22: Russian plural, #49: dynamic online status)
        msg_count = len([m for m in st.session_state.messages if m["role"] == "user"])
        is_thinking = st.session_state.get("is_thinking", False)
        thinking_agent = st.session_state.get("thinking_agent", "manager")
        corp_online = st.session_state.get("corp_ready", False)
        online_text = "4 агента онлайн" if corp_online else "ожидание подключения"
        dot_color = "#00cec9" if corp_online else "#ff6b6b"

        col_hdr, col_clr = st.columns([8, 1])
        with col_hdr:
            msg_text = ru_plural(msg_count, "сообщение", "сообщения", "сообщений")
            st.html(f'''<div class="zc-header">
  <div>
    <div class="zc-header-title">💬 Корпоративный чат</div>
    <div class="zc-header-sub"><span class="zc-online" style="background:{dot_color}"></span>{online_text} &middot; {msg_text}</div>
  </div>
</div>''')
        with col_clr:
            # #21: two-step clear confirmation
            if st.session_state.get("confirm_clear"):
                c_yes, c_no = st.columns(2)
                with c_yes:
                    if st.button("Да", key="confirm_yes"):
                        st.session_state.messages = [
                            {
                                "role": "assistant",
                                "content": "Чат очищен. Я Алексей — CEO. Обращайтесь к любому из нас!",
                                "agent_key": "manager",
                                "agent_name": "Алексей",
                                "time": datetime.now().strftime("%H:%M"),
                                "date": datetime.now().strftime("%d.%m.%Y"),
                            }
                        ]
                        save_chat_history(st.session_state.messages)
                        st.session_state.is_thinking = False
                        st.session_state.confirm_clear = False
                        st.rerun()
                with c_no:
                    if st.button("Нет", key="confirm_no"):
                        st.session_state.confirm_clear = False
                        st.rerun()
            else:
                if st.button("🗑️", key="clear_chat", help="Очистить чат"):
                    st.session_state.confirm_clear = True
                    st.rerun()

        # Render chat messages as modern HTML
        chat_html = render_chat_html(st.session_state.messages)

        # #34: typing indicator with ARIA
        typing_html = ""
        if is_thinking:
            t_info = AGENTS.get(thinking_agent, AGENTS["manager"])
            t_color = AGENT_COLORS.get(thinking_agent, "#00cec9")
            typing_html = f'''<div class="zc-typing-row" role="status" aria-live="polite" aria-label="{t_info['name']} печатает">
  <div class="zc-avatar" style="background:{hex_to_rgba(t_color, 0.08)};border-color:{t_color}"><span>{t_info["emoji"]}</span></div>
  <div class="zc-typing-bubble">
    <span class="zc-typing-name" style="color:{t_color}">{t_info["name"]}</span>
    <div class="zc-dot"></div><div class="zc-dot"></div><div class="zc-dot"></div>
  </div>
</div>'''

        st.html(chat_html + typing_html)

        # #18: auto-scroll to bottom using components.html (allows JS execution)
        st_components.html("""
            <script>
                const mainBlock = window.parent.document.querySelector('[data-testid="stAppViewBlockContainer"]');
                if (mainBlock) mainBlock.scrollTop = mainBlock.scrollHeight;
                const tabs = window.parent.document.querySelectorAll('[data-testid="stVerticalBlock"]');
                tabs.forEach(t => t.scrollTop = t.scrollHeight);
            </script>
        """, height=0)

        # #48: retry button for failed requests
        if "last_failed_prompt" in st.session_state:
            if st.button("🔄 Повторить последний запрос", key="retry_btn"):
                failed_target = st.session_state.pop("last_failed_target", "manager")
                st.session_state.pending_prompt = st.session_state.pop("last_failed_prompt")
                st.session_state.pending_targets = [failed_target]
                st.session_state.is_thinking = True
                st.session_state.thinking_agent = failed_target
                st.rerun()

        # Process pending message (runs after chat is rendered so typing indicator is visible)
        if "pending_prompt" in st.session_state:
            prompt = st.session_state.pop("pending_prompt")
            targets = st.session_state.pop("pending_targets", [])
            st.session_state.pop("pending_target", None)  # cleanup old key

            if not targets:
                targets = [st.session_state.get("last_agent_key", "manager")]

            if not api_ready:
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": "**API не настроен.** Добавьте `OPENROUTER_API_KEY` в Railway.",
                    "agent_key": "manager",
                    "agent_name": "Алексей",
                    "time": datetime.now().strftime("%H:%M"),
                    "date": datetime.now().strftime("%d.%m.%Y"),
                })
            else:
                corp = get_corporation()
                if corp and corp.is_ready:
                    context = format_chat_context(st.session_state.messages)
                    task_with_context = prompt
                    if context:
                        task_with_context = f"{context}\n\n---\nНовое сообщение от Тима: {prompt}"

                    for target_key in targets:
                        # Update typing indicator for current agent
                        st.session_state.thinking_agent = target_key
                        try:
                            response = corp.execute_task(task_with_context, target_key)
                            st.session_state.pop("last_failed_prompt", None)
                            st.session_state.pop("last_failed_target", None)
                        except Exception as e:
                            response = f"Ошибка: `{type(e).__name__}: {str(e)[:200]}`"
                            st.session_state["last_failed_prompt"] = prompt
                            st.session_state["last_failed_target"] = target_key

                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": response,
                            "agent_key": target_key,
                            "agent_name": AGENTS[target_key]["name"],
                            "time": datetime.now().strftime("%H:%M"),
                            "date": datetime.now().strftime("%d.%m.%Y"),
                        })
                    st.session_state.last_agent_key = targets[-1]
                else:
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": "**Zinin Corp инициализируется...** Попробуйте перезагрузить страницу.",
                        "agent_key": "manager",
                        "agent_name": "Алексей",
                        "time": datetime.now().strftime("%H:%M"),
                        "date": datetime.now().strftime("%d.%m.%Y"),
                    })

            save_chat_history(st.session_state.messages)
            st.session_state.is_thinking = False
            st.rerun()

        # #25: clickable agent hint buttons
        agent_keys = list(AGENTS.keys())
        hint_cols = st.columns(len(agent_keys))
        for i, key in enumerate(agent_keys):
            info = AGENTS[key]
            color = AGENT_COLORS[key]
            with hint_cols[i]:
                selected = st.session_state.get("selected_agent") == key
                label = f"{info['emoji']} @{info['name']}" + (" ✓" if selected else "")
                if st.button(label, key=f"hint_{key}", use_container_width=True):
                    if st.session_state.get("selected_agent") == key:
                        st.session_state.pop("selected_agent", None)  # toggle off
                    else:
                        st.session_state.selected_agent = key
                    st.rerun()

        # Show selected agent indicator
        sel = st.session_state.get("selected_agent")
        if sel:
            sel_info = AGENTS[sel]
            sel_color = AGENT_COLORS[sel]
            st.html(
                f'<div style="text-align:center;font-size:12px;padding:2px;color:{sel_color}">'
                f'Адресат: {sel_info["emoji"]} <b>@{sel_info["name"]}</b> (нажмите снова чтобы сбросить)</div>'
            )

        # Chat input
        placeholder = "Напишите сообщение..."
        if sel:
            placeholder = f"Сообщение для {AGENTS[sel]['name']}..."
        if prompt := st.chat_input(placeholder):
            # #43: empty message validation
            prompt = prompt.strip()
            if not prompt:
                st.toast("Пустое сообщение", icon="⚠️")
            else:
                now = datetime.now()
                # Determine target agent(s)
                if st.session_state.get("selected_agent"):
                    targets = [st.session_state.pop("selected_agent")]
                else:
                    targets = detect_agents(prompt)

                st.session_state.messages.append({
                    "role": "user",
                    "content": prompt,
                    "time": now.strftime("%H:%M"),
                    "date": now.strftime("%d.%m.%Y"),
                })
                save_chat_history(st.session_state.messages)

                # Set thinking state and rerun to show typing indicator
                st.session_state.pending_prompt = prompt
                st.session_state.pending_targets = targets
                st.session_state.is_thinking = True
                st.session_state.thinking_agent = targets[0]
                # #24: toast feedback
                names = ", ".join(f"{AGENTS[k]['emoji']} {AGENTS[k]['name']}" for k in targets)
                st.toast(f"Отправлено → {names}", icon="📤")
                st.rerun()

    # Tab 2: Agents
    with tab2:
        st.subheader("Команда агентов")

        agents_display = [
            {
                "key": "manager",
                "yaml": "manager",
                "model": "Claude Sonnet 4",
                "role": "CEO, координация, стратегия",
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
                "model": "Claude 3.5 Haiku",
                "role": "Контент, LinkedIn, Self-Refine",
            },
            {
                "key": "automator",
                "yaml": "automator",
                "model": "Claude Sonnet 4",
                "role": "Интеграции, автоматизация, код",
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
            {
                "name": "📋 Полный отчёт корпорации",
                "agent": "manager",
                "description": "Все агенты готовят данные → CEO синтезирует еженедельный отчёт",
                "method": "full_corporation_report",
            },
        ]

        # Handle task execution via session_state
        for task in tasks:
            agent_info = AGENTS.get(task["agent"], AGENTS["manager"])
            col1, col2 = st.columns([4, 1])
            with col1:
                st.markdown(f"**{task['name']}**")
                st.caption(f"{task['description']} • {agent_info['flag']} {agent_info['name']}")
            with col2:
                if st.button("▶", key=f"btn_{task['method']}", disabled=not api_ready, help="Запустить задачу"):
                    corp = get_corporation()
                    if corp and corp.is_ready:
                        with st.spinner(f"{agent_info['emoji']} {agent_info['name']} работает..."):
                            method = getattr(corp, task["method"])
                            result = method()
                        st.session_state[f"task_result_{task['method']}"] = {
                            "result": result,
                            "agent": agent_info["name"],
                            "time": datetime.now().strftime("%H:%M:%S"),
                        }
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": result,
                            "agent_key": task["agent"],
                            "agent_name": agent_info["name"],
                            "time": datetime.now().strftime("%H:%M"),
                            "date": datetime.now().strftime("%d.%m.%Y"),
                        })
                        save_chat_history(st.session_state.messages)
                        st.rerun()
                    else:
                        st.error("❌ Zinin Corp не инициализирован")

            # Show result FULL WIDTH if exists
            result_key = f"task_result_{task['method']}"
            if result_key in st.session_state:
                res = st.session_state[result_key]
                with st.expander(f"✅ Результат от {res['agent']} ({res['time']})", expanded=True):
                    st.markdown(res["result"])
                    if st.button("Скрыть", key=f"hide_{task['method']}"):
                        del st.session_state[result_key]
                        st.rerun()
            st.divider()

        if not api_ready:
            st.info("💡 Добавьте OPENROUTER_API_KEY для активации задач")

    # Tab 4: Content (Yuki SMM)
    with tab4:
        st.subheader("📱 Контент-студия Юки")
        st.caption("🇰🇷 Генерация, оценка и публикация постов для LinkedIn")

        # Settings row
        col_topic, col_author = st.columns([3, 1])
        with col_topic:
            topic = st.text_input(
                "Тема поста",
                placeholder="Например: как составить резюме, LinkedIn профиль, ошибки на собеседовании...",
                key="yuki_topic",
            )
        with col_author:
            author = st.selectbox(
                "Автор",
                ["Кристина Жукова", "Тим Зинин"],
                key="yuki_author",
            )

        author_key = "kristina" if "Кристина" in author else "tim"

        # Generate button
        col_gen, col_status = st.columns([1, 1])
        with col_gen:
            generate_clicked = st.button(
                "✍️ Сгенерировать пост",
                disabled=not api_ready or not topic,
                use_container_width=True,
            )
        with col_status:
            check_linkedin = st.button(
                "🔗 Проверить LinkedIn",
                disabled=not api_ready,
                use_container_width=True,
            )

        # LinkedIn status check
        if check_linkedin:
            corp = get_corporation()
            if corp and corp.is_ready:
                with st.spinner("📱 Юки проверяет LinkedIn..."):
                    result = corp.linkedin_status()
                st.info(result)

        # Generation flow
        if generate_clicked and topic:
            corp = get_corporation()
            if corp and corp.is_ready:
                with st.spinner(f"📱 Юки генерирует пост про «{topic}»..."):
                    result = corp.generate_post(topic=topic, author=author_key)

                # Store result in session
                st.session_state["yuki_last_post"] = result
                st.session_state["yuki_last_topic"] = topic
                st.session_state["yuki_last_author"] = author

        # Display last generated post
        if "yuki_last_post" in st.session_state:
            st.divider()
            st.markdown(f"**Тема:** {st.session_state.get('yuki_last_topic', '')} • **Автор:** {st.session_state.get('yuki_last_author', '')}")

            raw_post = st.session_state["yuki_last_post"]

            # Extract just the post text (after --- separator if present)
            post_text = raw_post
            if "---\n" in raw_post:
                parts = raw_post.split("---\n", 1)
                meta = parts[0]
                post_text = parts[1] if len(parts) > 1 else raw_post
                # Show meta info
                with st.expander("📊 Метаданные генерации"):
                    st.text(meta)

            # Editable post
            edited_post = st.text_area(
                "Текст поста (можно редактировать)",
                value=post_text,
                height=400,
                key="yuki_edit_post",
            )

            # Post stats
            char_count = len(edited_post)
            word_count = len(edited_post.split())
            color = "green" if 1200 <= char_count <= 3000 else "orange" if 800 <= char_count <= 3500 else "red"
            st.caption(f":{color}[{char_count} символов] • {word_count} слов")

            # Action buttons
            col_pub, col_critique, col_regen = st.columns(3)
            with col_pub:
                if st.button("🚀 Опубликовать в LinkedIn", use_container_width=True, disabled=not api_ready):
                    corp = get_corporation()
                    if corp and corp.is_ready and corp.smm:
                        from src.tools.smm_tools import LinkedInPublisherTool
                        pub = LinkedInPublisherTool()
                        with st.spinner("Публикуем..."):
                            pub_result = pub._run(action="publish", text=edited_post)
                        if "✅" in pub_result:
                            st.success(pub_result)
                        else:
                            st.error(pub_result)

            with col_critique:
                if st.button("🔍 Оценить пост", use_container_width=True, disabled=not api_ready):
                    from src.tools.smm_tools import ContentGenerator
                    cg = ContentGenerator()
                    critique = cg._run(action="critique", content=edited_post)
                    st.info(critique)

            with col_regen:
                if st.button("🔄 Переделать", use_container_width=True, disabled=not api_ready or not topic):
                    corp = get_corporation()
                    if corp and corp.is_ready:
                        with st.spinner("📱 Юки переделывает..."):
                            result = corp.generate_post(topic=topic, author=author_key)
                        st.session_state["yuki_last_post"] = result
                        st.rerun()

    # Tab 5: Monitoring
    with tab5:
        st.subheader("📡 Мониторинг агентов")

        # Import tracker
        try:
            from src.activity_tracker import (
                get_all_statuses,
                get_recent_events,
                get_agent_task_count,
                get_task_progress,
                AGENT_NAMES,
                AGENT_EMOJI,
            )
            tracker_available = True
        except Exception:
            tracker_available = False

        if not tracker_available:
            st.warning("Модуль мониторинга недоступен")
        else:
            # Auto-refresh hint
            col_ref1, col_ref2 = st.columns([4, 1])
            with col_ref1:
                st.caption("Данные обновляются при перезагрузке страницы")
            with col_ref2:
                if st.button("🔄 Обновить", key="refresh_monitor"):
                    st.rerun()

            statuses = get_all_statuses()

            # Agent status table
            for agent_key in ["manager", "accountant", "automator", "smm"]:
                info = AGENTS.get(agent_key, {})
                status = statuses.get(agent_key, {})
                agent_status = status.get("status", "idle")
                current_task = status.get("task")
                communicating_with = status.get("communicating_with")
                last_task = status.get("last_task")
                last_task_time = status.get("last_task_time")
                last_task_success = status.get("last_task_success", True)
                last_duration = status.get("last_task_duration_sec", 0)
                tasks_24h = get_agent_task_count(agent_key, hours=24)
                progress = get_task_progress(agent_key)

                # Container for each agent
                with st.container():
                    cols = st.columns([1, 2, 2, 1, 1])

                    # Col 1: Agent identity
                    with cols[0]:
                        st.markdown(f"### {info.get('emoji', '')} {info.get('name', agent_key)}")
                        st.caption(f"{info.get('flag', '')} {info.get('title', '')}")

                    # Col 2: Current status + progress
                    with cols[1]:
                        if agent_status == "working":
                            st.markdown("🟢 **Работает**")
                            if current_task:
                                st.caption(f"📝 {current_task}")
                            # Animated typing indicator
                            st.markdown(
                                '<span style="color: #00cec9; animation: pulse 1.5s infinite;">⌨️ печатает...</span>',
                                unsafe_allow_html=True,
                            )
                            # Progress bar
                            if progress is not None:
                                st.progress(progress, text=f"{int(progress * 100)}%")
                            else:
                                st.progress(0.5, text="⏳ в процессе")
                        elif communicating_with:
                            other_name = AGENT_NAMES.get(communicating_with, communicating_with)
                            other_emoji = AGENT_EMOJI.get(communicating_with, "")
                            st.markdown(f"🔵 **Общается**")
                            st.markdown(
                                f'<span style="color: #6c5ce7;">💬 → {other_emoji} {other_name}</span>',
                                unsafe_allow_html=True,
                            )
                        else:
                            st.markdown("⚪ **Свободен**")

                    # Col 3: Last task info
                    with cols[2]:
                        if last_task:
                            icon = "✅" if last_task_success else "❌"
                            st.caption(f"{icon} {last_task}")
                            if last_task_time:
                                try:
                                    t = datetime.fromisoformat(last_task_time)
                                    elapsed = datetime.now() - t
                                    if elapsed < timedelta(minutes=1):
                                        ago = "только что"
                                    elif elapsed < timedelta(hours=1):
                                        ago = f"{int(elapsed.total_seconds() // 60)} мин назад"
                                    elif elapsed < timedelta(hours=24):
                                        ago = f"{int(elapsed.total_seconds() // 3600)} ч назад"
                                    else:
                                        ago = t.strftime("%d.%m %H:%M")
                                    duration_str = f" ({last_duration}с)" if last_duration else ""
                                    st.caption(f"🕐 {ago}{duration_str}")
                                except Exception:
                                    pass
                        else:
                            st.caption("Нет выполненных задач")

                    # Col 4: 24h stats
                    with cols[3]:
                        st.metric("24ч", tasks_24h, help="Задач за 24 часа")

                    # Col 5: Quick action
                    with cols[4]:
                        if agent_status == "working":
                            st.markdown("🔴")
                        elif communicating_with:
                            st.markdown("🟡")
                        else:
                            st.markdown("⚪")

                st.divider()

            # CSS for pulse animation
            st.markdown("""
            <style>
                @keyframes pulse {
                    0%, 100% { opacity: 1; }
                    50% { opacity: 0.3; }
                }
            </style>
            """, unsafe_allow_html=True)

            # Recent activity feed
            st.subheader("📜 Последняя активность")
            events = get_recent_events(hours=24, limit=20)

            if not events:
                st.info("Пока нет событий. Запустите задачу, чтобы увидеть активность.")
            else:
                for event in reversed(events):
                    etype = event.get("type", "")
                    ts = event.get("timestamp", "")
                    try:
                        t = datetime.fromisoformat(ts)
                        time_str = t.strftime("%H:%M:%S")
                    except Exception:
                        time_str = ts[:8] if ts else ""

                    if etype == "task_start":
                        agent = event.get("agent", "")
                        name = AGENT_NAMES.get(agent, agent)
                        emoji = AGENT_EMOJI.get(agent, "")
                        st.caption(f"`{time_str}` {emoji} **{name}** начал: _{event.get('task', '')}_")
                    elif etype == "task_end":
                        agent = event.get("agent", "")
                        name = AGENT_NAMES.get(agent, agent)
                        emoji = AGENT_EMOJI.get(agent, "")
                        success = event.get("success", True)
                        icon = "✅" if success else "❌"
                        dur = event.get("duration_sec", 0)
                        dur_str = f" ({dur}с)" if dur else ""
                        st.caption(f"`{time_str}` {icon} {emoji} **{name}** завершил: _{event.get('task', '')}_{dur_str}")
                    elif etype == "communication":
                        from_a = event.get("from_agent", "")
                        to_a = event.get("to_agent", "")
                        from_name = AGENT_NAMES.get(from_a, from_a)
                        to_name = AGENT_NAMES.get(to_a, to_a)
                        from_emoji = AGENT_EMOJI.get(from_a, "")
                        to_emoji = AGENT_EMOJI.get(to_a, "")
                        st.caption(f"`{time_str}` 💬 {from_emoji} **{from_name}** → {to_emoji} **{to_name}**: _{event.get('description', '')}_")

    # Tab 6: Agent Dashboard
    with tab6:
        try:
            from src.dashboard import generate_dashboard_html
            from src.activity_tracker import get_all_statuses as dash_get_statuses, get_recent_events as dash_get_events, get_agent_task_count as dash_task_count
            dash_statuses = dash_get_statuses()
            dash_events = dash_get_events(hours=24, limit=30)
            dash_completed = sum(dash_task_count(a, hours=24) for a in ["manager", "accountant", "smm", "automator"])
        except Exception:
            dash_statuses = {}
            dash_events = []
            dash_completed = 0

        completed = max(st.session_state.get('tasks_completed', 0), dash_completed)
        dash_html = generate_dashboard_html(
            completed_count=completed,
            agent_statuses=dash_statuses,
            recent_events=dash_events,
        )
        st_components.html(dash_html, height=750, scrolling=False)

    # Tab 7: Stats
    with tab7:
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
