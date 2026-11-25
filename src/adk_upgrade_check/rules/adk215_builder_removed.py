"""2.15.0: the Visual Agent Builder was removed from ADK Web.

`google.adk.cli.built_in_agents` and the `/dev/apps/{app_name}/builder*` HTTP
routes no longer exist. Agents built with the builder are plain Agent Config
YAML and still run with `adk web`, `adk run` and `adk deploy`.
"""

from __future__ import annotations

import re

import libcst as cst
from packaging.version import Version

from ..engine import find_all
from ..engine import string_value
from .base import Rule

_MODULE = "google.adk.cli.built_in_agents"
_ROUTE = re.compile(r"/dev/apps/[^\s\"'/]*/builder")


class BuilderRemoved(Rule):
  id = "ADK215-BUILDER-REMOVED"
  introduced_in = Version("2.15.0")
  severity = "error"
  title = "The Visual Agent Builder and its routes were removed"
  changelog_url = "https://github.com/google/adk-python/commit/c890aa317f61988c99ac9cd4df49a1443ed87d15"

  def check(self, project):
    for m in project.modules_containing("built_in_agents"):
      for node in find_all(m.tree, cst.Import, cst.ImportFrom):
        if _imports_builder(m, node):
          yield self.finding(
              m,
              node,
              f"`{m.code(node)}`: `{_MODULE}` was removed in 2.15.0.",
              "remove the import; build agents with `adk create` or a coding"
              " agent instead",
          )

    for m in project.modules_containing("/builder"):
      for node in find_all(m.tree, cst.SimpleString, cst.FormattedString):
        text = (
            string_value(node)
            if isinstance(node, cst.SimpleString)
            else m.code(node)
        )
        if text and _ROUTE.search(text):
          yield self.finding(
              m,
              node,
              "Calls an ADK Web `/dev/apps/{app}/builder` route, which was"
              " removed in 2.15.0.",
              "remove the call; builder-made agents are Agent Config YAML you"
              " can edit directly",
          )


def _imports_builder(m, node) -> bool:
  if isinstance(node, cst.Import):
    return any(m.code(a.name).startswith(_MODULE) for a in node.names)
  if node.relative or node.module is None:
    return False
  module = m.code(node.module)
  if module.startswith(_MODULE):
    return True
  return (
      module == "google.adk.cli"
      and not isinstance(node.names, cst.ImportStar)
      and any(m.code(a.name) == "built_in_agents" for a in node.names)
  )
