"""Cross-file resolution, which single-file fixtures can't exercise."""

import json
from pathlib import Path
import subprocess
import textwrap

from adk_upgrade_check.cli import main
from adk_upgrade_check.engine import load_project
from adk_upgrade_check.rules import RULES_BY_ID
from adk_upgrade_check.versions import detect

ENUM = RULES_BY_ID["ADK214-ENUM-ARGS"]


def _write(root: Path, files: dict[str, str]) -> None:
  for rel, body in files.items():
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(body), encoding="utf-8")


MODELS = """
    import enum
    class Plan(enum.Enum):
      PRO = "pro"
"""
TOOLS = """
    from {models} import Plan
    def get_price(plan: Plan) -> int:
      return 20 if plan == "pro" else 0
"""


def test_tool_enum_and_agent_in_different_files(tmp_path):
  _write(tmp_path, {
      "billing/__init__.py": "",
      "billing/models.py": MODELS,
      "billing/tools.py": TOOLS.format(models=".models"),
      "billing/agent.py": """
          from google.adk.agents import Agent
          from .tools import get_price
          root_agent = Agent(name="b", tools=[get_price])
      """,
  })  # fmt: skip
  findings = list(ENUM.check(load_project(tmp_path)))
  assert [(f.path, f.line) for f in findings] == [("billing/tools.py", 4)]
  assert findings[0].fixable


def test_reexport_through_package_init(tmp_path):
  _write(tmp_path, {
      "billing/__init__.py": "from .tools import get_price\n",
      "billing/models.py": MODELS,
      "billing/tools.py": TOOLS.format(models="billing.models"),
      "agent.py": """
          from google.adk.agents import Agent
          from billing import get_price
          root_agent = Agent(name="b", tools=[get_price])
      """,
  })  # fmt: skip
  assert len(list(ENUM.check(load_project(tmp_path)))) == 1


def test_monorepo_picks_the_nearest_same_named_module(tmp_path):
  # Both projects have an `app.tools.get_price`, but only `a` registers it as
  # a tool, so only `a`'s copy may be reported.
  _write(tmp_path, {
      "agents/a/app/models.py": MODELS,
      "agents/a/app/tools.py": TOOLS.format(models="app.models"),
      "agents/a/app/agent.py": """
          from google.adk.agents import Agent
          from app.tools import get_price
          root_agent = Agent(name="x", tools=[get_price])
      """,
      "agents/b/app/models.py": MODELS,
      "agents/b/app/tools.py": TOOLS.format(models="app.models"),
  })  # fmt: skip
  findings = list(ENUM.check(load_project(tmp_path)))
  assert [f.path for f in findings] == ["agents/a/app/tools.py"]


def test_detects_version_from_uv_lock_then_requirements(tmp_path):
  (tmp_path / "requirements.txt").write_text("google-adk[a2a]>=1.15,<2\n")
  found = detect(tmp_path)
  assert (str(found.version), found.exact) == ("1.15", False)
  (tmp_path / "uv.lock").write_text(
      '[[package]]\nname = "google-adk"\nversion = "1.18.0"\n'
  )
  found = detect(tmp_path)
  assert (str(found.version), found.source, found.exact) == ("1.18.0", "uv.lock", True)


def test_cli_gates_rules_by_version_range(tmp_path, capsys):
  _write(tmp_path, {
      "app.py": """
          from google.adk.sessions import DatabaseSessionService
          s = DatabaseSessionService(db_url="sqlite:///x.db")
      """,
  })  # fmt: skip
  # Already past 1.19: the rule doesn't apply.
  assert main([str(tmp_path), "--from", "1.19.0", "--to", "2.15.1"]) == 0
  capsys.readouterr()
  assert main([str(tmp_path), "--from", "1.18.0", "--to", "1.19.0", "--format", "json"]) == 1
  out = json.loads(capsys.readouterr().out)
  assert [f["rule_id"] for f in out["findings"]] == ["ADK119-ASYNC-DB-URL"]


def test_fix_refuses_dirty_tree_then_applies(tmp_path, capsys):
  _write(tmp_path, {
      "app.py": """
          from google.adk.sessions import DatabaseSessionService
          s = DatabaseSessionService(db_url="sqlite:///x.db")
      """,
  })  # fmt: skip
  args = [str(tmp_path), "--from", "1.18.0", "--fix"]
  assert main(args) == 2  # not a git repo
  git = lambda *a: subprocess.run(["git", "-C", str(tmp_path), *a], check=True, capture_output=True)
  git("init", "-q")
  assert main(args) == 2  # app.py is untracked
  git("add", ".")
  git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init")
  capsys.readouterr()
  assert main(args) == 0
  assert "+s = DatabaseSessionService(db_url=\"sqlite+aiosqlite:///x.db\")" in capsys.readouterr().out
  assert "sqlite+aiosqlite:///x.db" in (tmp_path / "app.py").read_text()


def test_tools_from_a_shared_list_variable(tmp_path):
  _write(tmp_path, {
      "billing/__init__.py": "",
      "billing/models.py": MODELS,
      # Same 4-space indent as TOOLS, so dedent lines them up.
      "billing/tools.py": TOOLS.format(models=".models") + """
    BASE = [len]
    ALL_TOOLS = [*BASE, get_price]
""",
      "billing/agent.py": """
          from google.adk.agents import Agent
          from .tools import ALL_TOOLS
          root_agent = Agent(name="b", tools=ALL_TOOLS + [print])
      """,
  })  # fmt: skip
  assert len(list(ENUM.check(load_project(tmp_path)))) == 1


def test_sarif_output_lists_rules_and_results(tmp_path, capsys):
  _write(tmp_path, {
      "app.py": """
          from google.adk.sessions import DatabaseSessionService
          s = DatabaseSessionService(db_url="sqlite:///x.db")
      """,
  })  # fmt: skip
  assert main([str(tmp_path), "--from", "1.18.0", "--format", "sarif"]) == 1
  run = json.loads(capsys.readouterr().out)["runs"][0]
  assert {r["id"] for r in run["tool"]["driver"]["rules"]} >= {"ADK119-ASYNC-DB-URL"}
  [result] = run["results"]
  assert result["ruleId"] == "ADK119-ASYNC-DB-URL"
  assert result["locations"][0]["physicalLocation"]["region"]["startLine"] == 3
