"""Quick test: verify CrewAI kickoff works on Railway"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print(f"OPENROUTER_API_KEY set: {bool(os.getenv('OPENROUTER_API_KEY'))}")

from crewai import Crew, Task, Agent, Process, LLM

# Create a minimal agent and task
llm = LLM(
    model="openrouter/anthropic/claude-3-5-haiku-latest",
    api_key=os.getenv("OPENROUTER_API_KEY", ""),
    base_url="https://openrouter.ai/api/v1",
)

agent = Agent(
    role="Тестер",
    goal="Ответить на тестовый вопрос",
    backstory="Ты тестовый агент",
    llm=llm,
    verbose=False,
    memory=False,
)

task = Task(
    description="Скажи 'Привет, я работаю!' одной строкой.",
    expected_output="Короткое приветствие",
    agent=agent,
)

crew = Crew(
    agents=[agent],
    tasks=[task],
    process=Process.sequential,
    verbose=False,
    memory=False,
)

print("Starting kickoff...")
try:
    result = crew.kickoff()
    print(f"SUCCESS: {result}")
except Exception as e:
    print(f"ERROR: {e}")
