"""Data types shared by the engine, the rules and the reporters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Severity = Literal["error", "warning", "info"]
Confidence = Literal["certain", "likely"]

SEVERITY_RANK = {"info": 0, "warning": 1, "error": 2}


@dataclass(frozen=True)
class TextEdit:
  """Replace the text between two positions (1-based lines, 0-based columns)."""

  start_line: int
  start_col: int
  end_line: int
  end_col: int
  replacement: str


@dataclass(frozen=True)
class Finding:
  rule_id: str
  severity: Severity
  confidence: Confidence
  path: str  # POSIX path relative to the project root
  line: int
  col: int
  message: str
  fix_hint: str
  changelog_url: str
  edit: TextEdit | None = None

  @property
  def fixable(self) -> bool:
    return self.edit is not None
