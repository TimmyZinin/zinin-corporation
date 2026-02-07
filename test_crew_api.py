"""
Test script: verify CrewAI API for task execution
"""
import inspect
from crewai import Crew, Task, Agent, Process, LLM

# 1. Check kickoff() signature
sig = inspect.signature(Crew.kickoff)
print(f"Crew.kickoff() signature: {sig}")
print(f"Parameters: {list(sig.parameters.keys())}")

# 2. Check Crew() constructor accepts tasks
sig_init = inspect.signature(Crew.__init__) if hasattr(Crew.__init__, '__wrapped__') else None
print(f"\nCrew fields (from model_fields):")
for name in Crew.model_fields:
    print(f"  - {name}: {Crew.model_fields[name].annotation}")

# 3. Check installed version
import crewai
print(f"\nCrewAI version: {crewai.__version__}")

# 4. Test creating Crew with tasks in constructor
print("\n--- Test: Create Crew with tasks in constructor ---")
try:
    llm = LLM(model="openrouter/anthropic/claude-3-5-haiku-latest", api_key="test", base_url="https://openrouter.ai/api/v1")
    agent = Agent(
        role="Test Agent",
        goal="Test goal",
        backstory="Test backstory",
        llm=llm,
        verbose=False,
        memory=False,
    )
    task = Task(
        description="Test task",
        expected_output="Test output",
        agent=agent,
    )
    crew = Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,
        verbose=False,
        memory=False,
    )
    print(f"SUCCESS: Crew created with {len(crew.tasks)} tasks")
    print(f"crew.kickoff() is ready to call (no tasks arg needed)")
except Exception as e:
    print(f"FAIL: {e}")

# 5. Verify kickoff() does NOT accept tasks
print("\n--- Test: Confirm kickoff(tasks=...) fails ---")
try:
    crew2 = Crew(
        agents=[agent],
        tasks=[],
        process=Process.sequential,
        verbose=False,
        memory=False,
    )
    crew2.kickoff(tasks=[task])
    print("UNEXPECTED: kickoff(tasks=...) worked")
except TypeError as e:
    print(f"CONFIRMED: kickoff(tasks=...) raises TypeError: {e}")
except Exception as e:
    print(f"OTHER ERROR: {type(e).__name__}: {e}")

print("\n✅ Test complete")
