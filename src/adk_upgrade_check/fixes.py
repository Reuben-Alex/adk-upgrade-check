"""Applies auto-fixes as text edits, so all other formatting is untouched."""

from __future__ import annotations

from collections import defaultdict
import difflib
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from .engine import read_source
from .model import Finding
from .model import TextEdit

# Lines as LibCST counts them (str.splitlines also splits on form feeds etc.).
_LINE = re.compile(r"[^\r\n]*(?:\r\n|\r|\n)|[^\r\n]+$")


def apply_edits(source: str, edits: list[TextEdit]) -> str:
  starts = [0]
  for line in _LINE.findall(source):
    starts.append(starts[-1] + len(line))

  def offset(line: int, col: int) -> int:
    return starts[line - 1] + col

  out, last_start = source, None
  for e in sorted(
      edits, key=lambda e: (e.start_line, e.start_col), reverse=True
  ):
    start, end = offset(e.start_line, e.start_col), offset(e.end_line, e.end_col)
    if last_start is not None and end > last_start:
      continue  # overlaps an edit we already applied
    out = out[:start] + e.replacement + out[end:]
    last_start = start
  return out


def plan_fixes(root: Path, findings: list[Finding]) -> dict[str, tuple[str, str]]:
  """Returns {relative path: (old source, new source)} for fixable findings."""
  by_file = defaultdict(list)
  for f in findings:
    if f.edit is not None:
      by_file[f.path].append(f.edit)
  plans = {}
  for rel, edits in sorted(by_file.items()):
    old = read_source(root / rel)
    new = apply_edits(old, edits)
    if new != old:
      plans[rel] = (old, new)
  return plans


def unified_diff(plans: dict[str, tuple[str, str]]) -> str:
  chunks = []
  for rel, (old, new) in plans.items():
    chunks.extend(
        difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"a/{rel}",
            tofile=f"b/{rel}",
        )
    )
  return "".join(chunks)


def dirty_files(root: Path, rels: list[str]) -> list[str] | None:
  """Files with uncommitted changes; None if `root` is not in a git repo."""
  try:
    out = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain", "--", *rels],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
  except (OSError, subprocess.CalledProcessError):
    return None
  return [line[3:] for line in out.splitlines() if line.strip()]


def write_fixes(root: Path, plans: dict[str, tuple[str, str]]) -> None:
  for rel, (_, new) in plans.items():
    path = root / rel
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
      fh.write(new)
    shutil.copymode(path, tmp)
    os.replace(tmp, path)
