from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService

from .tools import get_price

root_agent = Agent(
    name="billing",
    model="gemini-2.5-flash",
    instruction="Answer pricing questions with the get_price tool.",
    tools=[get_price],
)

runner = Runner(
    agent=root_agent,
    app_name="billing",
    session_service=DatabaseSessionService(db_url="sqlite:///./sessions.db"),
)
