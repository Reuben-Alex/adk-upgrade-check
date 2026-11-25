"""Ground truth for ADK215-BUILDER-REMOVED, ADK214-VERTEX-SESSION-KWARGS and
ADK207-PYARROW-EXTRA. Run with the versions either side of each change:

uv run --no-project --with google-adk==2.14.1 python tests/ground_truth/removals.py builder
uv run --no-project --with google-adk==2.15.0 python tests/ground_truth/removals.py builder
uv run --no-project --with google-adk==2.13.0 --with google-cloud-agentplatform python tests/ground_truth/removals.py vertex
uv run --no-project --with google-adk==2.14.0 --with google-cloud-agentplatform python tests/ground_truth/removals.py vertex
uv run --no-project --with "google-adk[gcp]==2.6.3" python tests/ground_truth/removals.py pyarrow
uv run --no-project --with "google-adk[gcp]==2.7.0" python tests/ground_truth/removals.py pyarrow
"""

import asyncio
from importlib.metadata import version
import sys


def builder():
  import google.adk.cli.built_in_agents  # noqa: F401


def vertex():
  from google.adk.sessions import VertexAiSessionService

  service = VertexAiSessionService(project="p", location="us-central1", agent_engine_id="1")
  # 2.14 rejects the kwarg before any network call; 2.13 gets as far as auth.
  asyncio.run(
      service.create_session(app_name="a", user_id="u", session_state={"x": 1})
  )


def pyarrow():
  from google.adk.plugins.bigquery_agent_analytics_plugin import BigQueryAgentAnalyticsPlugin  # noqa: F401
  import pyarrow  # noqa: F401


check = sys.argv[1]
try:
  globals()[check]()
  outcome = "ok"
except BaseException as e:  # report whatever the version raises
  outcome = f"{type(e).__name__}: {str(e).splitlines()[0][:110] if str(e) else ''}"
print(f"google-adk {version('google-adk')} {check}: {outcome}")
