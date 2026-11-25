from enum import Enum

from some_other_framework import Agent


class Plan(Enum):
  PRO = "pro"


def get_price(plan: Plan) -> int:
  return 20 if plan == "pro" else 0


root_agent = Agent(name="billing", tools=[get_price])
