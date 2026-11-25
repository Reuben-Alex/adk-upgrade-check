"""Ground truth for ADK119-SQLITE-SERVICE: can 1.19 read sessions written by 1.18
when both run `adk web --session_service_uri sqlite:///...`?

uv run --no-project --with google-adk==1.18.0 --with "sqlalchemy[asyncio]" python tests/ground_truth/sqlite_cli_switch.py write DB
uv run --no-project --with google-adk==1.19.0 --with "sqlalchemy[asyncio]" --with aiosqlite python tests/ground_truth/sqlite_cli_switch.py read DB

Both phases build the session service the way the CLI does, from the URI.
"""

import asyncio
from importlib.metadata import version
import sys

from google.adk.cli.service_registry import get_service_registry


def service(path: str):
  return get_service_registry().create_session_service(f"sqlite:///{path}")


async def main(phase: str, path: str):
  svc = service(path)
  print(f"google-adk {version('google-adk')}: sqlite:/// -> {type(svc).__name__}")
  if phase == "write":
    await svc.create_session(app_name="app", user_id="u", session_id="s1", state={"k": 1})
    print("  wrote session s1")
    return
  try:
    found = await svc.get_session(app_name="app", user_id="u", session_id="s1")
    print(f"  read session s1 -> {'found, state=' + str(found.state) if found else 'NOT FOUND'}")
  except Exception as e:  # report whatever the version raises
    print(f"  read session s1 -> {type(e).__name__}: {str(e)[:120]}")


asyncio.run(main(sys.argv[1], sys.argv[2]))
