"""adk-upgrade-check [PATH] --to VERSION: find what a google-adk upgrade breaks."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

from packaging.version import InvalidVersion
from packaging.version import Version

from . import __version__
from . import fixes
from . import report
from .engine import load_project
from .model import Finding
from .model import SEVERITY_RANK
from .rules import ALL_RULES
from .rules import RULES_BY_ID
from .rules.base import Rule
from .versions import detect
from .versions import LATEST_KNOWN


def select_rules(from_v: Version, to_v: Version, ids: list[str] | None) -> list[Rule]:
  rules = [r for r in ALL_RULES if from_v < r.introduced_in <= to_v]
  if ids:
    rules = [r for r in rules if r.id in ids]
  return rules


def run_rules(root: Path, rules: list[Rule], exclude: list[str] | None = None):
  project = load_project(root, exclude=exclude)
  findings = [f for r in rules for f in r.check(project)]
  findings.sort(key=lambda f: (f.path, f.line, f.col, f.rule_id))
  return findings, project.errors


def _version(s: str) -> Version:
  if s == "latest":
    return LATEST_KNOWN
  try:
    return Version(s)
  except InvalidVersion:
    raise argparse.ArgumentTypeError(f"not a version: {s!r}")


def _parser() -> argparse.ArgumentParser:
  p = argparse.ArgumentParser(
      prog="adk-upgrade-check",
      description=(
          "Find code that a google-adk upgrade will break. Also: "
          "`adk-upgrade-check list-rules`, `adk-upgrade-check explain RULE_ID`."
      ),
  )
  p.add_argument("path", nargs="?", default=".", help="project root (default: .)")
  p.add_argument("--from", dest="from_v", type=_version, help="current google-adk version (default: detected)")
  p.add_argument("--to", dest="to_v", type=_version, default=LATEST_KNOWN, help=f"target version (default: latest known, {LATEST_KNOWN})")
  p.add_argument("--format", choices=["text", "json", "sarif"], default="text", help="sarif shows findings in GitHub code scanning")
  p.add_argument("--fail-on", choices=["error", "warning", "info", "never"], default="error", help="lowest severity that exits 1 (default: error)")
  p.add_argument("--strict", action="store_true", help="let `likely` findings fail the run too")
  p.add_argument("--rule", action="append", help="only run this rule ID (repeatable)")
  p.add_argument("--exclude", action="append", default=[], help="glob of paths to skip (repeatable)")
  p.add_argument("--fix", action="store_true", help="apply auto-fixes (shows the diff)")
  p.add_argument("--force", action="store_true", help="with --fix: allow uncommitted changes or no git repo")
  p.add_argument("--color", choices=["auto", "always", "never"], default="auto", help="colour text output (default: auto; honours NO_COLOR)")
  p.add_argument("--version", action="version", version=f"%(prog)s {__version__} (rules up to google-adk {LATEST_KNOWN})")
  return p  # fmt: skip


def _use_color(choice: str) -> bool:
  if choice != "auto":
    return choice == "always"
  if os.environ.get("NO_COLOR") or not sys.stdout.isatty():
    return False
  if os.name == "nt":  # turn on ANSI escapes in the Windows console
    try:
      import ctypes

      kernel32 = ctypes.windll.kernel32
      handle = kernel32.GetStdHandle(-11)
      mode = ctypes.c_uint32()
      if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
        kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except (AttributeError, OSError):
      return False
  return True


def main(argv: list[str] | None = None) -> int:
  argv = sys.argv[1:] if argv is None else argv
  if argv[:1] == ["list-rules"]:
    for r in ALL_RULES:
      print(f"{r.id:<30} {str(r.introduced_in):<8} {r.severity:<8} {r.title}")
    return 0
  if argv[:1] == ["explain"]:
    rule = RULES_BY_ID.get(argv[1]) if len(argv) > 1 else None
    if rule is None:
      print("usage: adk-upgrade-check explain RULE_ID  (see list-rules)", file=sys.stderr)
      return 2
    doc = sys.modules[type(rule).__module__].__doc__ or ""
    print(f"{rule.id}: {rule.title}\nIntroduced in {rule.introduced_in}. {rule.changelog_url}\n\n{doc.strip()}")
    return 0

  try:
    args = _parser().parse_args(argv)
  except SystemExit as e:
    return 2 if e.code else 0
  root = Path(args.path).resolve()
  if not root.is_dir():
    print(f"error: {args.path} is not a directory", file=sys.stderr)
    return 2

  if args.from_v is not None:
    from_v, source = args.from_v, "--from"
  else:
    found = detect(root)
    if found is None:
      from_v, source = Version("0"), None
    else:
      from_v, source = found.version, found.source
      if not found.exact:
        print(f"note: {found.source} only gives a range for google-adk; assuming its lower bound {found.version}. Pass --from to override.", file=sys.stderr)
  if source is None:
    print("note: could not detect your google-adk version; checking every rule up to the target. Pass --from to narrow it.", file=sys.stderr)
  to_v = args.to_v
  if to_v <= from_v:
    print(f"error: --to {to_v} is not newer than the current version {from_v}", file=sys.stderr)
    return 2
  if args.rule and (unknown := set(args.rule) - RULES_BY_ID.keys()):
    print(f"error: unknown rule(s): {', '.join(sorted(unknown))}", file=sys.stderr)
    return 2

  rules = select_rules(from_v, to_v, args.rule)
  findings, errors = run_rules(root, rules, args.exclude)

  if args.fix:
    plans = fixes.plan_fixes(root, findings)
    if plans:
      dirty = fixes.dirty_files(root, list(plans))
      if not args.force and (dirty is None or dirty):
        why = "is not in a git repository" if dirty is None else f"has uncommitted changes in {', '.join(dirty)}"
        print(f"error: refusing to --fix: {root} {why}. Commit first, or pass --force.", file=sys.stderr)
        return 2
      # Keep stdout machine-readable for json and sarif.
      log = sys.stdout if args.format == "text" else sys.stderr
      print(fixes.unified_diff(plans), file=log)
      fixes.write_fixes(root, plans)
      print(f"Applied fixes to {len(plans)} file(s).\n", file=log)
      findings, errors = run_rules(root, rules, args.exclude)

  from_label = f"google-adk {from_v} (from {source})" if source else "google-adk version unknown"
  if args.format == "json":
    meta = {"from": str(from_v) if source else None, "from_source": source, "to": str(to_v), "rules": [r.id for r in rules]}
    print(report.to_json(findings, meta, errors))
  elif args.format == "sarif":
    print(report.to_sarif(findings, rules))
  else:
    header = f"{from_label}  ->  target {to_v}   ({len(rules)} {'rule applies' if len(rules) == 1 else 'rules apply'})"
    print(report.text(findings, header, errors, color=_use_color(args.color)))

  return 1 if _fails(findings, args.fail_on, args.strict) else 0


def _fails(findings: list[Finding], fail_on: str, strict: bool) -> bool:
  if fail_on == "never":
    return False
  return any(
      SEVERITY_RANK[f.severity] >= SEVERITY_RANK[fail_on]
      and (strict or f.confidence == "certain")
      for f in findings
  )


if __name__ == "__main__":
  sys.exit(main())
