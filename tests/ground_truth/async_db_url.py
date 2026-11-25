"""Ground truth for ADK119-ASYNC-DB-URL: run against a real google-adk install.

uv run --no-project --with google-adk==1.18.0 --with aiosqlite --with "sqlalchemy[asyncio]" python tests/ground_truth/async_db_url.py
uv run --no-project --with google-adk==1.19.0 --with aiosqlite --with "sqlalchemy[asyncio]" python tests/ground_truth/async_db_url.py
"""

from importlib.metadata import version
import tempfile

from google.adk.sessions import DatabaseSessionService

with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
  for url in (f"sqlite:///{d}/a.db", f"sqlite+aiosqlite:///{d}/b.db"):
    try:
      DatabaseSessionService(db_url=url)
      outcome = "ok"
    except Exception as e:  # report whatever the version raises
      outcome = f"{type(e).__name__}: {e}"
    print(f"google-adk {version('google-adk')}: {url.split('://')[0]}:// -> {outcome}")
