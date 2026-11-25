"""2.15.0: McpInstructionProvider no longer fills prompt arguments from state.

Before 2.15 it passed matching `session.state` keys to the MCP prompt. Now a
prompt that takes arguments gets none unless `arguments=` is passed.
"""

from __future__ import annotations

from packaging.version import Version

from ..engine import is_adk
from .base import Rule


class McpPromptArgs(Rule):
  id = "ADK215-MCP-PROMPT-ARGS"
  introduced_in = Version("2.15.0")
  severity = "warning"
  title = "McpInstructionProvider no longer auto-fills prompt arguments"
  changelog_url = "https://github.com/google/adk-python/commit/889ddd3134df1dd1a626205ee78811950dec2a5c"

  def check(self, project):
    for m in project.modules:
      for call in m.calls:
        if not is_adk(m.qualname(call.func), "McpInstructionProvider"):
          continue
        if any(a.star == "**" for a in call.args):
          continue  # arguments= may be inside **kwargs
        if any(a.keyword and a.keyword.value == "arguments" for a in call.args):
          continue
        yield self.finding(
            m,
            call,
            "`McpInstructionProvider(...)` has no `arguments=`. From 2.15.0 it"
            " no longer fills MCP prompt arguments from `session.state`, so a"
            " prompt that takes arguments now gets none.",
            "pass `arguments={...}` or `arguments=lambda ctx: {...}` with the"
            " state keys the prompt reads (no change needed if the prompt takes"
            " no arguments)",
            # We can't see the MCP server's prompt signature statically.
            confidence="likely",
        )
