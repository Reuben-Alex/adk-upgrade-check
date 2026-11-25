"""2.13.0: telemetry defaults to the OpenTelemetry GenAI v2 schema.

ADK now emits `otel_semconv_1_44` by default: there is no `call_llm` span, and
`invocation` became `invoke_workflow`. Dashboards, alerts and trace queries
that read `call_llm` silently go empty. Setting
`ADK_TELEMETRY_SCHEMA_VERSION_OPT_IN=otel_semconv_1_36` keeps the old schema
(supported until at least 2027-03-31).
"""

from __future__ import annotations

import re

import libcst as cst
from packaging.version import Version

from ..engine import find_all
from ..engine import string_value
from .base import Rule

_CALL_LLM = re.compile(r"\bcall_llm\b")
_OPT_IN = "ADK_TELEMETRY_SCHEMA_VERSION_OPT_IN"
_FIX = (
    "query the v2 spans instead (the agent span covers the model call), or set"
    f" {_OPT_IN}=otel_semconv_1_36 to keep the legacy schema"
)


def _is_test(rel: str) -> bool:
  name = rel.rsplit("/", 1)[-1]
  return (
      "/tests/" in f"/{rel}"
      or name.startswith("test_")
      or name.endswith("_test.py")
      or name == "conftest.py"
  )


class OtelSemconv(Rule):
  id = "ADK213-OTEL-SEMCONV"
  introduced_in = Version("2.13.0")
  severity = "warning"
  title = "The call_llm span is gone by default (OTel GenAI v2 schema)"
  changelog_url = "https://github.com/google/adk-python/commit/783848821aabc6656a79949996c31608d5043606"

  def check(self, project):
    text_files = project.text_files(
        ".yaml", ".yml", ".json", ".tf", ".sql", ".env", "Dockerfile", ".toml"
    )
    if project.modules_containing(_OPT_IN) or any(
        _OPT_IN in text for _, text in text_files
    ):
      return  # the project already pins a schema version

    for m in project.modules_containing("call_llm"):
      if _is_test(m.rel):
        continue  # tests building fake spans don't break
      docstrings = {id(e.value) for e in find_all(m.tree, cst.Expr)}
      for node in find_all(m.tree, cst.SimpleString, cst.ConcatenatedString):
        if id(node) in docstrings:
          continue
        value = string_value(node)
        if value is None or not _CALL_LLM.search(value):
          continue
        exact = value == "call_llm"
        yield self.finding(
            m,
            node,
            f"{'`call_llm`' if exact else 'This string mentions `call_llm`'}:"
            " from 2.13.0 ADK no longer emits that span by default, so queries"
            " or filters on it match nothing.",
            _FIX,
            # Code often handles both schemas, so this is a prompt to review.
            confidence="likely",
        )

    for rel, text in text_files:
      if not rel.endswith((".yaml", ".yml", ".json", ".tf", ".sql")):
        continue
      for i, line in enumerate(text.splitlines(), 1):
        match = _CALL_LLM.search(line)
        if match:
          yield self.text_finding(
              rel,
              i,
              match.start(),
              "This dashboard or query reads the `call_llm` span, which ADK no"
              " longer emits by default from 2.13.0.",
              _FIX,
              confidence="likely",
          )
