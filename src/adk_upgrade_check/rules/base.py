"""The interface every rule implements."""

from __future__ import annotations

from typing import ClassVar
from typing import Iterable

import libcst as cst
from packaging.version import Version

from ..engine import Module
from ..engine import Project
from ..model import Confidence
from ..model import Finding
from ..model import Severity
from ..model import TextEdit


class Rule:
  id: ClassVar[str]  # "ADK214-ENUM-ARGS": release + slug, stable forever
  introduced_in: ClassVar[Version]  # fires when from < introduced_in <= to
  severity: ClassVar[Severity]
  title: ClassVar[str]
  changelog_url: ClassVar[str]

  def check(self, project: Project) -> Iterable[Finding]:
    raise NotImplementedError

  def finding(
      self,
      module: Module,
      node: cst.CSTNode,
      message: str,
      fix_hint: str,
      *,
      confidence: Confidence = "certain",
      severity: Severity | None = None,
      replacement: str | None = None,
      fix_node: cst.CSTNode | None = None,
  ) -> Finding:
    """A finding at `node`.

    `replacement`, if given, is an auto-fix that replaces `fix_node` (default:
    `node`).
    """
    r = module.pos(node)
    edit = None
    if replacement is not None:
      fr = module.pos(fix_node or node)
      edit = TextEdit(
          fr.start.line, fr.start.column, fr.end.line, fr.end.column, replacement
      )
    return Finding(
        rule_id=self.id,
        severity=severity or self.severity,
        confidence=confidence,
        path=module.rel,
        line=r.start.line,
        col=r.start.column,
        message=message,
        fix_hint=fix_hint,
        changelog_url=self.changelog_url,
        edit=edit,
    )

  def text_finding(
      self,
      rel: str,
      line: int,
      col: int,
      message: str,
      fix_hint: str,
      *,
      end_col: int | None = None,
      replacement: str | None = None,
      confidence: Confidence = "certain",
      severity: Severity | None = None,
  ) -> Finding:
    """A finding in a non-Python file (1-based line, 0-based columns)."""
    edit = None
    if replacement is not None and end_col is not None:
      edit = TextEdit(line, col, line, end_col, replacement)
    return Finding(
        rule_id=self.id,
        severity=severity or self.severity,
        confidence=confidence,
        path=rel,
        line=line,
        col=col,
        message=message,
        fix_hint=fix_hint,
        changelog_url=self.changelog_url,
        edit=edit,
    )
