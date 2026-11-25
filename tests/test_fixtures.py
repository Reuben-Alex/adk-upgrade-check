"""Every rule ships positive, negative and (when fixable) fixed fixtures.

A case is one `.py` file, or a directory holding a small project (for rules
that also read pyproject.toml, requirements or dashboards).

- positive: findings land exactly on the lines marked `# expect`.
- negative: no findings.
- fixed/<case>: applying the auto-fixes to positive/<case> gives exactly these
  files, and the fixed case has nothing left to auto-fix.
"""

from collections import defaultdict
from pathlib import Path

import pytest

from adk_upgrade_check.engine import load_project
from adk_upgrade_check.engine import read_source
from adk_upgrade_check.fixes import apply_edits
from adk_upgrade_check.rules import RULES_BY_ID

FIXTURES = Path(__file__).parent / "fixtures"


def _cases(kind):
  return [
      pytest.param(rule_dir.name, case, id=f"{rule_dir.name}/{kind}/{case.name}")
      for rule_dir in sorted(FIXTURES.iterdir())
      if (rule_dir / kind).is_dir()
      for case in sorted((rule_dir / kind).iterdir())
      if case.is_dir() or case.suffix == ".py"
  ]


def _files(case: Path) -> dict[str, Path]:
  """{path relative to the case root: file}."""
  if case.is_file():
    return {case.name: case}
  return {
      p.relative_to(case).as_posix(): p for p in sorted(case.rglob("*")) if p.is_file()
  }


def _check(rule_id, case):
  if case.is_file():
    project = load_project(case.parent, files=[case])
  else:
    project = load_project(case)
  findings = list(RULES_BY_ID[rule_id].check(project))
  assert not project.errors
  return findings


def _expected(case):
  return sorted(
      (rel, i)
      for rel, path in _files(case).items()
      for i, line in enumerate(read_source(path).splitlines(), 1)
      if line.rstrip().endswith("# expect")
  )


def test_every_rule_has_fixtures():
  for rule_id in RULES_BY_ID:
    assert any((FIXTURES / rule_id / "positive").iterdir()), rule_id
    assert any((FIXTURES / rule_id / "negative").iterdir()), rule_id


@pytest.mark.parametrize("rule_id,case", _cases("positive"))
def test_positive(rule_id, case):
  findings = _check(rule_id, case)
  assert sorted((f.path, f.line) for f in findings) == _expected(case)


@pytest.mark.parametrize("rule_id,case", _cases("negative"))
def test_negative(rule_id, case):
  assert _check(rule_id, case) == []


@pytest.mark.parametrize("rule_id,case", _cases("fixed"))
def test_fixed(rule_id, case):
  positive = case.parent.parent / "positive" / case.name
  edits = defaultdict(list)
  for f in _check(rule_id, positive):
    if f.edit:
      edits[f.path].append(f.edit)
  before, after = _files(positive), _files(case)
  assert before.keys() == after.keys()
  for rel, path in before.items():
    assert apply_edits(read_source(path), edits[rel]) == read_source(after[rel]), rel
  assert not [f for f in _check(rule_id, case) if f.fixable]
