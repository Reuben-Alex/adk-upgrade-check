"""Ground truth for ADK214-ENUM-ARGS: run against a real google-adk install.

uv run --no-project --with google-adk==2.13.0 python tests/ground_truth/enum_args.py
uv run --no-project --with google-adk==2.14.0 python tests/ground_truth/enum_args.py

Prints what a tool sees for an Enum parameter.
"""

import asyncio
from enum import Enum
from importlib.metadata import version
from unittest import mock

from google.adk.tools import FunctionTool


class Plan(Enum):
  FREE = "free"
  PRO = "pro"


def get_price(plan: Plan) -> dict:
  """Returns the price of a plan."""
  return {"type": type(plan).__name__, "eq_string": plan == "pro"}


class Billing:

  def get_price(self, plan: Plan) -> dict:
    """Returns the price of a plan."""
    return {"type": type(plan).__name__, "eq_string": plan == "pro"}


async def main():
  ctx = mock.MagicMock()
  ctx.tool_confirmation = None
  for label, fn in (("function", get_price), ("bound method", Billing().get_price)):
    result = await FunctionTool(fn).run_async(args={"plan": "pro"}, tool_context=ctx)
    print(f"google-adk {version('google-adk')} {label}: {result}")


asyncio.run(main())
