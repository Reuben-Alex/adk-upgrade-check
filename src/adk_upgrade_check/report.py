"""Text, JSON and SARIF output."""

from __future__ import annotations

import json
import shutil
import textwrap

from . import __version__
from .model import Finding

_SEVERITY_STYLE = {"error": "1;31", "warning": "1;33", "info": "1;34"}
_SARIF_LEVEL = {"error": "error", "warning": "warning", "info": "note"}


def _style(color: bool):
  def paint(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if color else text

  return paint


def _plural(n: int, word: str) -> str:
  return f"{n} {word}{'' if n == 1 else 's'}"


def text(findings: list[Finding], header: str, parse_errors, color: bool = False) -> str:
  paint = _style(color)
  width = max(60, min(110, shutil.get_terminal_size((100, 24)).columns))
  wrap = lambda s, first, rest: textwrap.fill(
      s, width, initial_indent=first, subsequent_indent=rest,
      break_on_hyphens=False, break_long_words=False,
  )  # fmt: skip
  out = [paint(header, "1"), ""]
  for f in findings:
    likely = paint(" (likely)", "2") if f.confidence == "likely" else ""
    severity = paint(f"{f.severity.upper():<8}", _SEVERITY_STYLE[f.severity])
    rule = paint(f"{f.rule_id:<30}", "36")
    out.append(f"{severity}{rule}{paint(f'{f.path}:{f.line}', '1')}{likely}")
    out.append(wrap(f.message, " " * 8, " " * 8))
    tag = "  [auto-fixable]" if f.fixable else ""
    fix = wrap(f"fix: {f.fix_hint}{tag}", " " * 8, " " * 13)
    fix = fix.replace("fix:", paint("fix:", "32"), 1)
    out.append(fix.replace("[auto-fixable]", paint("[auto-fixable]", "32")))
    out.append("")
  for rel, err in parse_errors:
    out.append(paint(f"SKIPPED {rel}: could not parse ({err})", "2"))
  n = len(findings)
  if not n:
    out.append(paint("No breaking changes found.", "1;32"))
    return "\n".join(out)
  counts = {s: sum(f.severity == s for f in findings) for s in ("error", "warning", "info")}
  summary = f"{_plural(n, 'finding')}: " + ", ".join(
      _plural(c, s) for s, c in counts.items() if c
  )
  fixable = sum(f.fixable for f in findings)
  if fixable:
    summary += f". {fixable} auto-fixable, run with --fix to apply."
  out.append(paint(summary, "1"))
  return "\n".join(out)


def to_json(findings: list[Finding], meta: dict, parse_errors) -> str:
  return json.dumps(
      {
          **meta,
          "findings": [
              {
                  "rule_id": f.rule_id,
                  "severity": f.severity,
                  "confidence": f.confidence,
                  "path": f.path,
                  "line": f.line,
                  "col": f.col,
                  "message": f.message,
                  "fix": f.fix_hint,
                  "fixable": f.fixable,
                  "changelog_url": f.changelog_url,
              }
              for f in findings
          ],
          "parse_errors": [{"path": p, "error": e} for p, e in parse_errors],
      },
      indent=2,
  )


def to_sarif(findings: list[Finding], rules) -> str:
  """SARIF 2.1.0, so findings show up in GitHub code scanning."""
  return json.dumps(
      {
          "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
          "version": "2.1.0",
          "runs": [{
              "tool": {
                  "driver": {
                      "name": "adk-upgrade-check",
                      "version": __version__,
                      "informationUri": "https://github.com/Reuben-Alex/adk-upgrade-check",
                      "rules": [
                          {
                              "id": r.id,
                              "shortDescription": {"text": r.title},
                              "helpUri": r.changelog_url,
                              "defaultConfiguration": {"level": _SARIF_LEVEL[r.severity]},
                              "properties": {"introducedIn": str(r.introduced_in)},
                          }
                          for r in rules
                      ],
                  }
              },
              "results": [
                  {
                      "ruleId": f.rule_id,
                      "level": _SARIF_LEVEL[f.severity],
                      "message": {"text": f"{f.message} Fix: {f.fix_hint}"},
                      "locations": [{
                          "physicalLocation": {
                              "artifactLocation": {"uri": f.path},
                              "region": {"startLine": f.line, "startColumn": f.col + 1},
                          }
                      }],
                      "properties": {"confidence": f.confidence},
                  }
                  for f in findings
              ],
          }],
      },
      indent=2,
  )  # fmt: skip
