"""Works out which google-adk version a project is on."""

from __future__ import annotations

import codecs
from dataclasses import dataclass
from pathlib import Path
import re
import tomllib

from packaging.requirements import InvalidRequirement
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion
from packaging.version import Version

# The newest release this rule pack knows about; the default for --to.
LATEST_KNOWN = Version("2.15.1")
_ADK = "google-adk"


@dataclass(frozen=True)
class Detected:
  version: Version
  source: str
  exact: bool  # False when only a range was declared and we used its floor


def _read(path: Path) -> str:
  """Text of a config file, tolerating BOMs and UTF-16 (common on Windows)."""
  data = path.read_bytes()
  if data[:2] in (codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE):
    return data.decode("utf-16", errors="replace")
  return data.decode("utf-8-sig", errors="replace")


def detect(root: Path) -> Detected | None:
  """Lock files first, then pinned requirements, then pyproject."""
  for lock in ("uv.lock", "poetry.lock", "pdm.lock"):
    path = root / lock
    if not path.is_file():
      continue
    try:
      data = tomllib.loads(_read(path))
    except tomllib.TOMLDecodeError:
      continue
    for pkg in data.get("package", []):
      if canonicalize_name(pkg.get("name", "")) == _ADK and "version" in pkg:
        return Detected(Version(pkg["version"]), lock, True)

  for path in sorted(root.glob("requirements*.txt")):
    for line in _read(path).splitlines():
      line = line.split("#", 1)[0].strip()
      if not line or line.startswith("-"):
        continue
      try:
        req = Requirement(line)
      except InvalidRequirement:
        continue
      if canonicalize_name(req.name) == _ADK:
        found = _from_specifier(req.specifier, path.name)
        if found:
          return found

  path = root / "pyproject.toml"
  if path.is_file():
    data = tomllib.loads(_read(path))
    deps = list(data.get("project", {}).get("dependencies", []))
    for group in data.get("dependency-groups", {}).values():
      deps += [d for d in group if isinstance(d, str)]
    for dep in deps:
      try:
        req = Requirement(dep)
      except InvalidRequirement:
        continue
      if canonicalize_name(req.name) == _ADK:
        found = _from_specifier(req.specifier, "pyproject.toml")
        if found:
          return found
    poetry = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
    for name, spec in poetry.items():
      if canonicalize_name(name) == _ADK:
        spec = spec.get("version", "") if isinstance(spec, dict) else spec
        found = _from_poetry(spec, "pyproject.toml")
        if found:
          return found
  return None


def _from_specifier(spec: SpecifierSet, source: str) -> Detected | None:
  floor = None
  for s in spec:
    try:
      v = Version(s.version.rstrip(".*"))
    except InvalidVersion:
      continue
    if s.operator in ("==", "===") and "*" not in s.version:
      return Detected(v, source, True)
    if s.operator in (">=", "~=", ">", "==") and (floor is None or v > floor):
      floor = v
  return Detected(floor, source, False) if floor else None


def _from_poetry(spec: str, source: str) -> Detected | None:
  m = re.match(r"^\s*([\^~]?=?)\s*(\d[\w.]*)", spec)
  if not m:
    return None
  return Detected(Version(m.group(2)), source, m.group(1) in ("", "=", "=="))
