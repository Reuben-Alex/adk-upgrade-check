from .models import Plan

SEATS = {"free": 1, "pro": 1, "team": 10}


def get_price(plan: Plan, seats: int = 1) -> dict:
  """Returns the monthly price for a plan."""
  if plan == "free":
    return {"plan": plan.value, "price": 0}
  per_seat = 20 if plan == "pro" else 15
  return {"plan": plan.value, "price": per_seat * max(seats, SEATS[plan])}
