"""2.0.0: events must be yielded, not appended to the session directly.

ADK 2.0 runs agents as nodes in a workflow graph and emits events under
framework control (state, routing, streaming). Code that calls
`ctx.session.events.append(event)` itself bypasses that, so the event is not
persisted, routed or streamed.
"""

from __future__ import annotations

import libcst as cst
from packaging.version import Version

from .base import Rule


class DirectAppend(Rule):
  id = "ADK200-DIRECT-APPEND"
  introduced_in = Version("2.0.0")
  severity = "warning"
  title = "Events appended to the session directly instead of yielded"
  changelog_url = "https://adk.dev/2.0/"

  def check(self, project):
    for m in project.modules:
      visitor = _Visitor(m)
      m.tree.visit(visitor)
      for call in visitor.hits:
        yield self.finding(
            m,
            call,
            f"`{m.code(call.func)}(...)` adds an event to the session"
            " directly. From 2.0.0 the framework controls event emission, so"
            " this event is not persisted, routed or streamed.",
            "`yield` the event from the agent, tool or callback instead",
        )


class _Visitor(cst.CSTVisitor):
  """Finds direct appends, skipping custom session services, whose job it is."""

  def __init__(self, module):
    self.m = module
    self.hits: list[cst.Call] = []
    self._in_session_service = 0

  def _is_session_service(self, node: cst.ClassDef) -> bool:
    return any(
        (self.m.qualname(b.value) or "").endswith("SessionService")
        for b in node.bases
    )

  def visit_ClassDef(self, node: cst.ClassDef) -> None:
    if self._is_session_service(node):
      self._in_session_service += 1

  def leave_ClassDef(self, node: cst.ClassDef) -> None:
    if self._is_session_service(node):
      self._in_session_service -= 1

  def visit_Call(self, node: cst.Call) -> None:
    if self._in_session_service or not isinstance(node.func, cst.Attribute):
      return
    f = node.func
    if (
        f.attr.value == "append"
        and isinstance(f.value, cst.Attribute)
        and f.value.attr.value == "events"
        and isinstance(f.value.value, cst.Attribute)
        and f.value.value.attr.value == "session"
    ):
      self.hits.append(node)
