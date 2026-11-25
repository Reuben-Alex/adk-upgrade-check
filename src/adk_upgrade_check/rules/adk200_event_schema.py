"""2.0.0: Event gains `node_info` and `output` fields.

A custom `BaseSessionService` that maps events to fixed SQL or NoSQL columns
fails on insert or deserialization when it meets a 2.0 event. Services that
store each event as one serialized JSON blob are not affected.
"""

from __future__ import annotations

import libcst as cst
from packaging.version import Version

from ..engine import is_adk
from .base import Rule

# A class that serializes whole events like this stores a blob, which is fine.
_BLOB_MARKERS = ("model_dump_json", "model_validate_json", "pickle")


def _wraps_another_service(m, cls) -> bool:
  """A decorator-style service: `__init__(self, inner: BaseSessionService)`."""
  init = next(
      (
          s
          for s in cls.body.body
          if isinstance(s, cst.FunctionDef) and s.name.value == "__init__"
      ),
      None,
  )
  if init is None:
    return False
  return any(
      p.annotation is not None
      and (m.qualname(p.annotation.annotation) or "").endswith("SessionService")
      for p in init.params.params
  )


class EventSchema(Rule):
  id = "ADK200-EVENT-SCHEMA"
  introduced_in = Version("2.0.0")
  severity = "warning"
  title = "Custom session storage must accept Event.node_info and Event.output"
  changelog_url = "https://adk.dev/2.0/"

  def check(self, project):
    for m in project.modules:
      for cls in m.classes.values():
        if not any(
            is_adk(m.qualname(b.value), "BaseSessionService") for b in cls.bases
        ):
          continue
        if any(marker in m.source for marker in _BLOB_MARKERS):
          continue  # serializes whole events somewhere in this module
        if _wraps_another_service(m, cls):
          continue  # delegates storage to an inner service
        yield self.finding(
            m,
            cls.name,
            f"`{cls.name.value}` is a custom session service. From 2.0.0 every"
            " Event carries `node_info` and `output`, so storage that maps"
            " events to fixed columns fails on insert or read.",
            "store events as one JSON blob (`event.model_dump_json()`), or add"
            " `node_info` and `output` columns; update every reader before"
            " writing 2.0 sessions to a shared database",
            confidence="likely",  # the column mapping may live elsewhere
        )
