"""2.6.0: FileArtifactService namespaces artifacts by app.

Artifacts moved from `root/users/{user_id}/...` to
`root/apps/{app_name}/users/{user_id}/...`. Artifacts written before 2.6 are
still read from the old location, but the first save of one restarts its
version numbering and stops serving the older versions, and old artifacts
stay visible to every app that shares the root.
"""

from __future__ import annotations

from packaging.version import Version

from ..engine import is_adk
from .base import Rule


class ArtifactNamespace(Rule):
  id = "ADK206-ARTIFACT-NS"
  introduced_in = Version("2.6.0")
  severity = "info"
  title = "FileArtifactService stores artifacts per app"
  changelog_url = "https://github.com/google/adk-python/commit/f72f0db58c5c1f4e8b8d4f04b8c592c9e49cbe9e"

  def check(self, project):
    for m in project.modules:
      for call in m.calls:
        if is_adk(m.qualname(call.func), "FileArtifactService"):
          yield self.finding(
              m,
              call,
              "FileArtifactService stores artifacts under"
              " `root/apps/{app_name}/users/...` from 2.6.0. Older artifacts are"
              " still read from `root/users/...`, but the first save of one"
              " restarts its version numbering and hides the older versions.",
              "if you rely on version history, move existing artifacts to"
              " `root/apps/{app_name}/users/...` before upgrading",
          )
