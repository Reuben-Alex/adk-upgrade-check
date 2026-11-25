import enum
import json

from google.adk.agents import LlmAgent


class Plan(enum.Enum):
  FREE = "free"
  PRO = "pro"


class Level(enum.IntEnum):
  LOW = 1


class Mode(enum.StrEnum):
  FAST = "fast"


class Size(str, enum.Enum):
  SMALL = "s"


def tool(plan: Plan, level: Level, mode: Mode, size: Size, other: str) -> str:
  if plan == Plan.PRO:  # compares against a member
    pass
  if plan.value == "pro":  # compares the value
    pass
  if level == 1 or mode == "fast" or size == "s":  # these still compare by value
    pass
  if other == "pro":  # not an Enum parameter
    pass
  return json.dumps({"plan": plan.value}) + plan.name.lower() + f"{plan!r}"


def converts_first(plan: Plan) -> bool:
  plan = Plan(plan)  # rebinds the parameter
  return plan == "pro"


def not_a_tool(plan: Plan) -> bool:
  return plan == "pro"  # never registered as a tool


agent = LlmAgent(name="a", model="gemini-2.5-flash", tools=[tool, converts_first])
