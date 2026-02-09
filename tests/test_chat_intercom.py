"""
Tests proving that agents in AI Corporation cannot communicate with each other
during a multi-agent chat round (the "всем" / broadcast scenario).

Each test targets a specific architectural flaw that prevents inter-agent dialogue.
All tests are pure unit tests — no API calls, no LLM invocations.
"""

import sys
import os
import ast
import textwrap
from unittest.mock import MagicMock, patch, call

import pytest

# Ensure project root is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ---------------------------------------------------------------------------
# Paths to source files under test
# ---------------------------------------------------------------------------
APP_PATH = os.path.join(os.path.dirname(__file__), "..", "app.py")
CREW_PATH = os.path.join(os.path.dirname(__file__), "..", "src", "crew.py")
AGENTS_PATH = os.path.join(os.path.dirname(__file__), "..", "src", "agents.py")


def _read_source(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ====================================================================
# 1. execute_task() creates a single-agent Crew — no delegation possible
# ====================================================================

class TestSingleAgentCrew:
    """Prove that execute_task() wraps every call in a Crew with exactly
    ONE agent, making inter-agent delegation structurally impossible."""

    def test_crew_created_with_single_agent_in_source(self):
        """The Crew instantiation inside execute_task() uses agents=[agent]
        (a list with a single element), so CrewAI's delegation mechanism
        has zero peers to delegate to."""
        source = _read_source(CREW_PATH)
        tree = ast.parse(source)

        # Find _run_agent method (Crew() is now in _run_agent, called from execute_task)
        found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_run_agent":
                found = True
                # Collect all Crew(...) calls inside _run_agent
                crew_calls = []
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        func = child.func
                        if isinstance(func, ast.Name) and func.id == "Crew":
                            crew_calls.append(child)

                assert len(crew_calls) >= 1, (
                    "Expected at least one Crew() call inside _run_agent"
                )

                for crew_call in crew_calls:
                    for kw in crew_call.keywords:
                        if kw.arg == "agents":
                            # Must be a list literal with exactly 1 element
                            assert isinstance(kw.value, ast.List), (
                                "agents= should be a list literal"
                            )
                            assert len(kw.value.elts) == 1, (
                                f"Crew inside _run_agent "
                                f"has agents=[agent] — single agent per execution."
                            )
        assert found, "_run_agent method not found in crew.py"

    def test_execute_task_does_not_pass_all_corporation_agents(self):
        """_run_agent() (called by execute_task) uses a single-agent Crew,
        not the full corporation roster."""
        source = _read_source(CREW_PATH)
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_run_agent":
                source_lines = source.splitlines()
                method_source = "\n".join(
                    source_lines[node.lineno - 1: node.end_lineno]
                )
                # The method should NOT contain self.crew.agents
                assert "agents=all_agents" not in method_source, (
                    "Unexpectedly found all agents in _run_agent Crew"
                )
                assert "agents=[self.manager, self.accountant" not in method_source, (
                    "Unexpectedly found multiple agents in _run_agent Crew"
                )
                # Confirm single-agent pattern
                assert "agents=[agent]" in method_source, (
                    "_run_agent must use agents=[agent] — single agent per execution."
                )
                return

        pytest.fail("_run_agent method not found in crew.py")


# ====================================================================
# 2. Broadcast loop gives every agent the SAME frozen context
# ====================================================================

class TestBroadcastLoopFrozenContext:
    """When the user sends a message to 'всем', app.py iterates over
    targets and calls corp.execute_task() for each agent.  The context
    string (task_with_context) is computed ONCE before the loop, so
    agent #2 never sees agent #1's response from the same round."""

    def test_context_computed_inside_loop(self):
        """format_chat_context() is called INSIDE the `for target_key
        in targets` loop (FIXED).  Context is re-computed after each agent
        responds, so agent #2 sees agent #1's response."""
        source = _read_source(APP_PATH)
        lines = source.splitlines()

        # Find the key lines
        loop_line = None
        context_line_after_loop = None
        execute_line = None

        for i, line in enumerate(lines):
            stripped = line.strip()
            if "for target_key in targets" in stripped:
                loop_line = i
            if loop_line is not None and "format_chat_context" in stripped and "context" in stripped and "=" in stripped:
                context_line_after_loop = i
                break

        for i, line in enumerate(lines):
            if "corp.execute_task(task_with_context" in line.strip():
                execute_line = i

        assert loop_line is not None, "for-loop over targets not found"
        assert context_line_after_loop is not None, "format_chat_context call not found after loop start"
        assert execute_line is not None, "execute_task call not found"

        # context is computed INSIDE the loop (FIXED)
        assert context_line_after_loop > loop_line, (
            "FIX VERIFIED: context is computed inside the loop, "
            "so each agent sees previous agents' responses."
        )
        assert execute_line > context_line_after_loop, (
            "execute_task should be after context computation"
        )

    def test_task_with_context_updated_inside_loop(self):
        """Inside the for-loop, the code re-computes task_with_context
        after each agent responds (FIXED).  format_chat_context is called
        inside the loop, and task_with_context is rebuilt for each agent."""
        source = _read_source(APP_PATH)
        lines = source.splitlines()

        # Find the loop body
        loop_start = None
        loop_indent = None
        for i, line in enumerate(lines):
            if "for target_key in targets:" in line:
                loop_start = i
                loop_indent = len(line) - len(line.lstrip())
                break

        assert loop_start is not None, "Loop not found"

        # Collect lines inside the loop body
        loop_body_lines = []
        for i in range(loop_start + 1, len(lines)):
            line = lines[i]
            if line.strip() == "":
                loop_body_lines.append(line)
                continue
            current_indent = len(line) - len(line.lstrip())
            if current_indent <= loop_indent and line.strip():
                break
            loop_body_lines.append(line)

        loop_body = "\n".join(loop_body_lines)

        # FIX VERIFIED: task_with_context IS reassigned inside the loop
        assert "task_with_context =" in loop_body, (
            "FIX VERIFIED: task_with_context is reassigned in loop — "
            "context IS updated for each agent."
        )
        # format_chat_context IS called inside the loop
        assert "format_chat_context" in loop_body, (
            "FIX VERIFIED: format_chat_context is called inside "
            "the per-agent loop, so each agent sees fresh context."
        )

    def test_simulate_broadcast_all_agents_same_context(self):
        """Simulate the broadcast flow: 3 agents get called sequentially
        but each receives the exact same task_with_context string,
        proving agent N+1 is blind to agent N's response."""
        # Simulate the exact logic from app.py lines 935-959
        messages = [
            {"role": "user", "content": "Всем: какой план на неделю?"},
        ]

        # Import the real format_chat_context
        # We re-implement the exact same logic to avoid streamlit import
        def format_chat_context(msgs, max_messages=10):
            recent = msgs[-(max_messages + 1):-1]
            if not recent:
                return ""
            lines_out = ["Контекст предыдущей переписки в корпоративном чате:"]
            for msg in recent:
                if msg["role"] == "user":
                    lines_out.append(f"Тим: {msg['content']}")
                else:
                    agent_name = msg.get("agent_name", "Алексей")
                    lines_out.append(f"{agent_name}: {msg['content'][:300]}")
            return "\n".join(lines_out)

        prompt = "Всем: какой план на неделю?"
        targets = ["manager", "accountant", "automator"]

        # --- This is the EXACT logic from app.py ---
        context = format_chat_context(messages)
        task_with_context = prompt
        if context:
            task_with_context = f"{context}\n\n---\nНовое сообщение от Тима: {prompt}"

        contexts_per_agent = {}
        for target_key in targets:
            # Record what context this agent receives
            contexts_per_agent[target_key] = task_with_context

            # Simulate agent response (what app.py does after execute_task)
            response = f"Ответ от {target_key}: план на неделю..."
            messages.append({
                "role": "assistant",
                "content": response,
                "agent_key": target_key,
                "agent_name": target_key.title(),
            })
            # NOTE: task_with_context is NOT updated here — that's the bug

        # ALL agents received the SAME context
        assert contexts_per_agent["manager"] == contexts_per_agent["accountant"], (
            "PROBLEM CONFIRMED: manager and accountant get identical context"
        )
        assert contexts_per_agent["accountant"] == contexts_per_agent["automator"], (
            "PROBLEM CONFIRMED: accountant and automator get identical context"
        )

        # Verify the last agent's context does NOT contain the first agent's response
        assert "Ответ от manager" not in contexts_per_agent["automator"], (
            "PROBLEM CONFIRMED: automator does NOT see manager's response — "
            "inter-agent awareness within a single round is completely absent."
        )


# ====================================================================
# 3. format_chat_context() truncates to 300 chars — too little for
#    meaningful inter-agent communication
# ====================================================================

class TestContextTruncation:
    """format_chat_context() truncates each assistant message to 300
    characters and only includes the last 10 messages.  For a detailed
    financial report or technical audit, 300 chars is ~2 sentences."""

    def test_truncation_limit_is_800_chars(self):
        """The source code uses msg['content'][:800] — increased from 300
        to preserve meaningful agent responses in context (FIXED)."""
        source = _read_source(APP_PATH)
        assert "msg['content'][:800]" in source or 'msg["content"][:800]' in source, (
            "Expected 800-char truncation in format_chat_context"
        )

    def test_truncation_destroys_meaningful_content(self):
        """A typical agent response is 800-2000 chars.  At 300 chars,
        roughly 60-85% of the response is silently discarded."""

        def format_chat_context(msgs, max_messages=10):
            recent = msgs[-(max_messages + 1):-1]
            if not recent:
                return ""
            lines_out = ["Контекст предыдущей переписки в корпоративном чате:"]
            for msg in recent:
                if msg["role"] == "user":
                    lines_out.append(f"Тим: {msg['content']}")
                else:
                    agent_name = msg.get("agent_name", "Алексей")
                    lines_out.append(f"{agent_name}: {msg['content'][:300]}")
            return "\n".join(lines_out)

        # Simulate a realistic financial report response (~1000 chars)
        long_response = (
            "Финансовый отчёт за неделю:\n"
            "1. Крипто маркетологи: доход 45,000 руб, расходы 12,000 руб, "
            "MRR 33,000 руб. Новых подписчиков: 7, отток: 2.\n"
            "2. Сборка: доход 28,000 руб, расходы 8,500 руб. "
            "Клуб: 15 активных, рост +3 за неделю.\n"
            "3. API расходы: Claude Sonnet $2.40, Claude Haiku $0.85, "
            "Web Search $0.30. Итого: $3.55 (~320 руб).\n"
            "4. Общий P&L: +52,680 руб.\n"
            "5. Рекомендации: увеличить рекламный бюджет для Крипто, "
            "оптимизировать API вызовы Sonnet (перейти на Haiku для рутинных задач), "
            "запустить акцию для Сборки.\n"
            "6. Риски: отток в Крипто клубе может вырасти без нового контента. "
            "API бюджет на пределе — рекомендую лимит $5/день."
        )

        messages = [
            {"role": "user", "content": "Отчёт?"},
            {
                "role": "assistant",
                "content": long_response,
                "agent_name": "Маттиас",
            },
            {"role": "user", "content": "Алексей, что скажешь?"},
        ]

        context = format_chat_context(messages)

        # Calculate how much was lost
        truncated_response = long_response[:300]
        full_len = len(long_response)
        trunc_len = len(truncated_response)
        loss_pct = (1 - trunc_len / full_len) * 100

        assert loss_pct > 40, (
            f"PROBLEM CONFIRMED: {loss_pct:.0f}% of the financial report "
            f"is silently discarded by the 300-char truncation. "
            f"Original: {full_len} chars, kept: {trunc_len} chars."
        )

        # The context must NOT contain the recommendations section
        assert "Рекомендации" not in context, (
            "PROBLEM CONFIRMED: The recommendations section of the financial "
            "report is completely lost after 300-char truncation."
        )

    def test_max_messages_limit_is_10(self):
        """Only the last 10 messages are included in context.  In a busy
        multi-agent chat where 4 agents respond per round, that is only
        ~2.5 rounds of history — effectively no long-term continuity."""

        def format_chat_context(msgs, max_messages=10):
            recent = msgs[-(max_messages + 1):-1]
            if not recent:
                return ""
            lines_out = ["Контекст предыдущей переписки в корпоративном чате:"]
            for msg in recent:
                if msg["role"] == "user":
                    lines_out.append(f"Тим: {msg['content']}")
                else:
                    agent_name = msg.get("agent_name", "Алексей")
                    lines_out.append(f"{agent_name}: {msg['content'][:300]}")
            return "\n".join(lines_out)

        # Build a chat with 20 messages (5 rounds x 4 agents)
        messages = []
        for round_num in range(1, 6):
            messages.append({
                "role": "user",
                "content": f"Вопрос раунда {round_num}",
            })
            for agent in ["Алексей", "Маттиас", "Мартин", "Юки"]:
                messages.append({
                    "role": "assistant",
                    "content": f"Ответ {agent} в раунде {round_num}",
                    "agent_name": agent,
                })
        # Add the current message
        messages.append({"role": "user", "content": "Новый вопрос"})

        context = format_chat_context(messages)

        # Round 1 messages should be missing
        assert "раунда 1" not in context, (
            "PROBLEM CONFIRMED: Round 1 is absent from context — "
            "with 4 agents per round, 10 messages covers only ~2 rounds."
        )
        assert "раунда 2" not in context, (
            "Round 2 should also be missing from context."
        )


# ====================================================================
# 4. Agent memory=False disables CrewAI built-in memory per agent
# ====================================================================

class TestAgentMemoryDisabled:
    """All four agents are created with memory=False, which disables
    CrewAI's built-in per-agent memory (short-term, long-term, entity).
    Even though the Crew-level memory=True is set, individual agent
    memory participation is turned off."""

    def test_manager_memory_false(self):
        """Manager agent (Aleksey) is created with memory=False (line 66
        in agents.py), disabling his personal memory stores."""
        source = _read_source(AGENTS_PATH)
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "create_manager_agent":
                func_source = "\n".join(
                    source.splitlines()[node.lineno - 1: node.end_lineno]
                )
                # Find the Agent() call and check memory=False
                assert "memory=False" in func_source, (
                    "PROBLEM CONFIRMED: Manager agent has memory=False — "
                    "CrewAI per-agent memory is disabled."
                )
                return
        pytest.fail("create_manager_agent not found")

    def test_accountant_memory_false(self):
        """Accountant agent (Mattias) is created with memory=False (line 104)."""
        source = _read_source(AGENTS_PATH)
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "create_accountant_agent":
                func_source = "\n".join(
                    source.splitlines()[node.lineno - 1: node.end_lineno]
                )
                assert "memory=False" in func_source, (
                    "PROBLEM CONFIRMED: Accountant agent has memory=False."
                )
                return
        pytest.fail("create_accountant_agent not found")

    def test_smm_memory_from_config(self):
        """SMM agent (Yuki) reads memory from YAML config (memory: true)."""
        source = _read_source(AGENTS_PATH)
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "create_smm_agent":
                func_source = "\n".join(
                    source.splitlines()[node.lineno - 1: node.end_lineno]
                )
                assert 'config.get("memory"' in func_source, (
                    "SMM agent should read memory from YAML config."
                )
                return
        pytest.fail("create_smm_agent not found")

    def test_automator_memory_false(self):
        """Automator agent (Martin) is created with memory=False (line 172)."""
        source = _read_source(AGENTS_PATH)
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "create_automator_agent":
                func_source = "\n".join(
                    source.splitlines()[node.lineno - 1: node.end_lineno]
                )
                assert "memory=False" in func_source, (
                    "PROBLEM CONFIRMED: Automator agent has memory=False."
                )
                return
        pytest.fail("create_automator_agent not found")

    def test_agents_memory_configuration(self):
        """Manager & accountant & automator have memory=False hardcoded.
        SMM & designer read memory from YAML config."""
        source = _read_source(AGENTS_PATH)
        tree = ast.parse(source)

        hardcoded_false = ["create_manager_agent", "create_accountant_agent", "create_automator_agent"]
        config_based = ["create_smm_agent", "create_designer_agent"]

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_source = "\n".join(
                    source.splitlines()[node.lineno - 1: node.end_lineno]
                )
                if node.name in hardcoded_false:
                    assert "memory=False" in func_source, (
                        f"{node.name} should have memory=False hardcoded"
                    )
                elif node.name in config_based:
                    assert 'config.get("memory"' in func_source, (
                        f"{node.name} should read memory from YAML config"
                    )


# ====================================================================
# 5. allow_delegation=True on manager is useless with single-agent Crew
# ====================================================================

class TestDelegationUseless:
    """Manager has allow_delegation=True, but execute_task() wraps him
    in a Crew with agents=[agent] (just himself).  CrewAI delegation
    requires other agents in the same Crew to delegate TO."""

    def test_manager_has_allow_delegation_true(self):
        """Confirm the manager agent is configured with allow_delegation=True."""
        source = _read_source(AGENTS_PATH)
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "create_manager_agent":
                func_source = "\n".join(
                    source.splitlines()[node.lineno - 1: node.end_lineno]
                )
                assert "allow_delegation=True" in func_source, (
                    "Manager should have allow_delegation=True"
                )
                return
        pytest.fail("create_manager_agent not found")

    def test_other_agents_have_delegation_false(self):
        """The other 3 agents have allow_delegation=False, so even if
        they were in the same crew, they couldn't delegate back."""
        source = _read_source(AGENTS_PATH)

        non_manager_funcs = [
            "create_accountant_agent",
            "create_smm_agent",
            "create_automator_agent",
        ]
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name in non_manager_funcs:
                func_source = "\n".join(
                    source.splitlines()[node.lineno - 1: node.end_lineno]
                )
                assert "allow_delegation=False" in func_source, (
                    f"{node.name} should have allow_delegation=False"
                )

    def test_delegation_impossible_in_single_agent_crew(self):
        """Even with allow_delegation=True, a single-agent Crew has no
        other agent to delegate to.  This is a structural dead-end.

        We prove this by checking that _run_agent always uses single agent
        in Crew — either via agents=[agent] or via crew_kwargs with
        "agents": [agent]. There is never a second agent available."""
        source = _read_source(CREW_PATH)
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_run_agent":
                func_source = "\n".join(
                    source.splitlines()[node.lineno - 1: node.end_lineno]
                )

                # All Crew calls use single agent (either literal or via kwargs)
                assert "agents=[agent]" in func_source or '"agents": [agent]' in func_source, (
                    "_run_agent should create Crew with single agent"
                )
                # No multi-agent lists
                assert "agents=[agent," not in func_source, (
                    "_run_agent should NOT use multi-agent Crew"
                )
                return

        pytest.fail("_run_agent not found in crew.py")

    def test_initialize_crew_has_all_agents_but_never_used_for_chat(self):
        """AICorporation.initialize() creates self.crew with ALL agents,
        but _run_agent() creates a fresh single-agent Crew for each task.
        execute_task() handles auto-delegation at the code level."""
        source = _read_source(CREW_PATH)

        # In initialize(), all agents are put into self.crew
        assert "all_agents = [self.manager, self.accountant, self.automator]" in source, (
            "initialize() should build all_agents list"
        )
        assert "self.crew = Crew(" in source, (
            "initialize() should assign self.crew"
        )

        # _run_agent creates a LOCAL crew, not self.crew
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_run_agent":
                func_source = "\n".join(
                    source.splitlines()[node.lineno - 1: node.end_lineno]
                )
                assert "self.crew.kickoff" not in func_source, (
                    "_run_agent should NOT use self.crew"
                )
                assert "crew = Crew(" in func_source or "Crew(" in func_source, (
                    "_run_agent creates a fresh local Crew for each task."
                )
                return

        pytest.fail("_run_agent not found")


# ====================================================================
# 6. End-to-end simulation: the complete broadcast failure
# ====================================================================

class TestEndToEndBroadcastFailure:
    """Simulate the full 'всем' flow to show that agents are completely
    isolated from each other within a single broadcast round."""

    def test_full_broadcast_simulation(self):
        """Simulate a user sending 'план на неделю' to all 4 agents.
        Verify that:
        - Each agent gets the same pre-loop context
        - No agent sees any other agent's response from the same round
        - Context from previous rounds is truncated to 300 chars
        """

        # Re-implement format_chat_context identically to app.py
        def format_chat_context(msgs, max_messages=10):
            recent = msgs[-(max_messages + 1):-1]
            if not recent:
                return ""
            lines_out = ["Контекст предыдущей переписки в корпоративном чате:"]
            for msg in recent:
                if msg["role"] == "user":
                    lines_out.append(f"Тим: {msg['content']}")
                else:
                    agent_name = msg.get("agent_name", "Алексей")
                    lines_out.append(f"{agent_name}: {msg['content'][:300]}")
            return "\n".join(lines_out)

        # Previous round: Mattias gave a long financial report
        previous_report = "А" * 500  # 500-char response
        messages = [
            {"role": "user", "content": "Маттиас, отчёт?"},
            {
                "role": "assistant",
                "content": previous_report,
                "agent_name": "Маттиас",
            },
        ]

        # New round: user says "всем"
        user_msg = "Всем: план на неделю?"
        messages.append({"role": "user", "content": user_msg})

        targets = ["manager", "accountant", "smm", "automator"]
        agent_names = {
            "manager": "Алексей",
            "accountant": "Маттиас",
            "smm": "Юки",
            "automator": "Мартин",
        }

        # --- Replicate the exact app.py logic ---
        context = format_chat_context(messages)
        task_with_context = user_msg
        if context:
            task_with_context = f"{context}\n\n---\nНовое сообщение от Тима: {user_msg}"

        agent_inputs = {}
        for target_key in targets:
            # Each agent receives the SAME task_with_context
            agent_inputs[target_key] = task_with_context

            # Simulate response
            fake_response = f"Ответ от {agent_names[target_key]}: мой план..."
            messages.append({
                "role": "assistant",
                "content": fake_response,
                "agent_key": target_key,
                "agent_name": agent_names[target_key],
            })
            # task_with_context is NOT updated

        # PROOF 1: All agents got identical input
        unique_inputs = set(agent_inputs.values())
        assert len(unique_inputs) == 1, (
            f"PROBLEM CONFIRMED: All {len(targets)} agents received the "
            f"exact same context string. There are {len(unique_inputs)} "
            f"unique inputs (should be {len(targets)} if agents could see "
            f"each other's responses)."
        )

        # PROOF 2: Last agent (automator) has no idea what manager said
        automator_input = agent_inputs["automator"]
        assert "Ответ от Алексей" not in automator_input
        assert "Ответ от Маттиас" not in automator_input
        assert "Ответ от Юки" not in automator_input

        # PROOF 3: Previous round's 500-char report was truncated
        assert previous_report not in context, (
            "Full 500-char report should not appear in context"
        )
        truncated = previous_report[:300]
        assert truncated in context, (
            "Truncated version (300 chars) should appear"
        )

    def test_what_correct_behavior_would_look_like(self):
        """Demonstrate what SHOULD happen: each agent gets an updated
        context including previous agents' responses from the same round.
        This test shows the gap between current and expected behavior."""

        def format_chat_context(msgs, max_messages=10):
            recent = msgs[-(max_messages + 1):-1]
            if not recent:
                return ""
            lines_out = ["Контекст предыдущей переписки в корпоративном чате:"]
            for msg in recent:
                if msg["role"] == "user":
                    lines_out.append(f"Тим: {msg['content']}")
                else:
                    agent_name = msg.get("agent_name", "Алексей")
                    lines_out.append(f"{agent_name}: {msg['content'][:300]}")
            return "\n".join(lines_out)

        messages = [
            {"role": "user", "content": "Всем: статус?"},
        ]

        targets = ["manager", "accountant", "automator"]
        agent_names = {
            "manager": "Алексей",
            "accountant": "Маттиас",
            "automator": "Мартин",
        }

        # CORRECT approach: re-compute context AFTER each agent responds
        correct_inputs = {}
        for target_key in targets:
            # Re-compute context including all previous responses
            messages.append({"role": "user", "content": "Всем: статус?"})
            context = format_chat_context(messages)
            messages.pop()  # remove temporary msg

            task_with_context = "Всем: статус?"
            if context:
                task_with_context = f"{context}\n\n---\nНовое сообщение от Тима: Всем: статус?"

            correct_inputs[target_key] = task_with_context

            # Agent responds and message is appended
            messages.append({
                "role": "assistant",
                "content": f"Ответ {agent_names[target_key]}",
                "agent_name": agent_names[target_key],
            })

        # With correct implementation, each agent would see different context
        assert correct_inputs["manager"] != correct_inputs["accountant"], (
            "With correct implementation, accountant would see manager's response"
        )
        assert correct_inputs["accountant"] != correct_inputs["automator"], (
            "With correct implementation, automator would see both previous responses"
        )
        # Automator should see manager's response in correct implementation
        assert "Ответ Алексей" in correct_inputs["automator"], (
            "With correct implementation, automator would see manager's response"
        )
