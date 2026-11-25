from enum import Enum

from google.adk.agents import Agent


class Plan(Enum):
  FREE = "free"
  PRO = "pro"


def get_price(plan: Plan) -> int:
  """Returns the monthly price of a plan."""
  if plan == Plan.PRO:  # expect
    return 20
  if Plan.FREE != plan:  # expect
    return -1
  return 0


root_agent = Agent(
    name="billing",
    model="gemini-2.5-flash",
    tools=[get_price],
)
