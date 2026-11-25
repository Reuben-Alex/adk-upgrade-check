"""2.14.0: VertexAiSessionService.create_session accepts only config options.

Extra keyword arguments used to be merged into the Sessions API config. Now
only `display_name`, `ttl`, `expire_time` and `labels` (and their camelCase
aliases) are accepted; anything else, such as `session_state`, `sessionId`,
`http_options` or `wait_for_completion`, raises ValueError.
"""

from __future__ import annotations

import libcst as cst
from packaging.version import Version

from ..engine import is_adk
from ..engine import Module
from .base import Rule

_ALLOWED = {
    "app_name", "user_id", "state", "session_id",
    "display_name", "displayName", "ttl", "expire_time", "expireTime", "labels",
}  # fmt: skip
# Old config keys with an exact equivalent parameter.
_RENAMES = {"session_state": "state", "sessionId": "session_id"}


class VertexSessionKwargs(Rule):
  id = "ADK214-VERTEX-SESSION-KWARGS"
  introduced_in = Version("2.14.0")
  severity = "error"
  title = "VertexAiSessionService.create_session rejects unknown keyword arguments"
  changelog_url = "https://github.com/google/adk-python/commit/968cd869ff79be622eb921c5e314bd19efd889d2"

  def check(self, project):
    for m in project.modules:
      if not any(v.endswith(".VertexAiSessionService") for v in m.imports.values()):
        continue
      vertex_names = _vertex_instances(m)
      for call in m.calls:
        func = call.func
        if not (
            isinstance(func, cst.Attribute) and func.attr.value == "create_session"
        ):
          continue
        if any(a.star for a in call.args):
          continue  # can't see what **kwargs holds
        keywords = {a.keyword.value for a in call.args if a.keyword}
        receiver = func.value
        certain = (
            isinstance(receiver, cst.Name) and receiver.value in vertex_names
        ) or (
            isinstance(receiver, cst.Call)
            and is_adk(m.qualname(receiver.func), "VertexAiSessionService")
        )
        for arg in call.args:
          if arg.keyword is None or arg.keyword.value in _ALLOWED:
            continue
          name = arg.keyword.value
          new = _RENAMES.get(name)
          if new in keywords:
            new = None  # e.g. both `state=` and `session_state=` given
          yield self.finding(
              m,
              arg,
              f"`create_session(..., {name}=...)`: from 2.14.0"
              " VertexAiSessionService raises ValueError for keyword arguments"
              " other than display_name, ttl, expire_time and labels.",
              f"use `{new}=`" if new else "remove it, or pass it another way",
              confidence="certain" if certain else "likely",
              replacement=new,
              fix_node=arg.keyword,
          )


def _vertex_instances(m: Module) -> set[str]:
  """Module-level names bound to `VertexAiSessionService(...)`."""
  return {
      name
      for name, value in m.assigns.items()
      if isinstance(value, cst.Call)
      and is_adk(m.qualname(value.func), "VertexAiSessionService")
  }
