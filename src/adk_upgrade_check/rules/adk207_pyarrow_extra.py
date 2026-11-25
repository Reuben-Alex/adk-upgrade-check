"""2.7.0: pyarrow moved out of the `gcp` extra.

`BigQueryAgentAnalyticsPlugin` needs pyarrow, which now lives in the new
`bigquery-analytics` extra. A project that installs `google-adk[gcp]` and uses
the plugin fails at import time after upgrading.
"""

from __future__ import annotations

import re

from packaging.version import Version

from .base import Rule

_ADK_EXTRAS = re.compile(r"google[-_.]adk\s*\[([^\]]*)\]", re.IGNORECASE)
_PYARROW = re.compile(r"""(^|["'\s,])pyarrow\b""", re.IGNORECASE | re.MULTILINE)


def _is_dependency_file(rel: str) -> bool:
  name = rel.rsplit("/", 1)[-1]
  return (
      name in ("pyproject.toml", "setup.cfg")
      or (name.startswith("requirements") and name.endswith(".txt"))
  )


class PyarrowExtra(Rule):
  id = "ADK207-PYARROW-EXTRA"
  introduced_in = Version("2.7.0")
  severity = "error"
  title = "BigQueryAgentAnalyticsPlugin needs the bigquery-analytics extra"
  changelog_url = "https://github.com/google/adk-python/commit/ac717091f6644f348c6f7e65a43cc0475a28fe45"

  def check(self, project):
    uses_plugin = any(
        v.endswith(".BigQueryAgentAnalyticsPlugin")
        or v.endswith(".bigquery_agent_analytics_plugin")
        for m in project.modules
        for v in m.imports.values()
    )
    if not uses_plugin:
      return
    files = [
        (rel, text)
        for rel, text in project.text_files(".toml", ".txt", ".cfg")
        if _is_dependency_file(rel)
    ]
    if any(_PYARROW.search(text) for _, text in files):
      return  # pyarrow is already a direct dependency
    for rel, text in files:
      for i, line in enumerate(text.splitlines(), 1):
        for match in _ADK_EXTRAS.finditer(line):
          extras = [e.strip().lower() for e in match.group(1).split(",")]
          if "gcp" not in extras or {"bigquery-analytics", "all"} & set(extras):
            continue
          new_extras = match.group(1).rstrip() + ",bigquery-analytics"
          yield self.text_finding(
              rel,
              i,
              match.start(1),
              f"`{match.group(0)}` relies on the `gcp` extra for pyarrow, which"
              " BigQueryAgentAnalyticsPlugin imports. From 2.7.0 pyarrow is in"
              " the `bigquery-analytics` extra instead.",
              "add the `bigquery-analytics` extra",
              end_col=match.end(1),
              replacement=new_extras,
          )
