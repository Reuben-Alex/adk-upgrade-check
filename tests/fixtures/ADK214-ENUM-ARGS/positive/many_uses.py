import enum
import json
from typing import Optional

from google.adk.tools import FunctionTool as FT

PRICES = {"free": 0, "pro": 20}


class Color(enum.Enum):
  RED = "red"
  BLUE = "blue"


class Size(str, enum.Enum):
  SMALL = "s"
  LARGE = "l"


def paint(
    color: Optional[Color],
    shades: list[Color],
    size: "Size",
    plan: Color | None = None,
) -> str:
  if color in ("red", "blue"):  # expect
    pass
  if "red" in shades:  # expect
    pass
  match color:
    case "red" | "green":  # expect
      pass
    case _:
      pass
  payload = json.dumps({"color": color})  # expect
  name = color.upper()  # expect
  price = PRICES[plan]  # expect
  label = f"painted {color}"  # expect
  text = "color: " + color  # expect
  size_label = f"size {size}"  # expect
  as_text = str(size)  # expect
  if color == "purple":  # expect
    pass
  return payload + name + str(price) + label + text + size_label + as_text


paint_tool = FT(paint)
