"""Reads settings that live outside Python: env files, deploy scripts, CLI flags."""

from __future__ import annotations

from dataclasses import dataclass
import re

from .engine import Project

# Files where env vars are set or `adk web` / `adk api_server` is launched.
DEPLOY_FILES = (
    ".env", ".yaml", ".yml", ".sh", ".bash", ".ps1", ".bat", ".cmd", ".mk",
    ".toml", ".json", "Dockerfile", "Makefile", "Procfile",
)  # fmt: skip


@dataclass(frozen=True)
class Value:
  """A string value at an exact spot in a file (1-based line, 0-based columns)."""

  rel: str
  line: int
  start: int
  end: int
  text: str


# `--session_service_uri=URL`, `--session_service_uri URL`, and the JSON-array
# form `"--session_service_uri", "URL"` (Dockerfile CMD, launch.json).
# `--session_db_url` is the older name of the same flag.
_FLAG = re.compile(
    r"""--session_(?:service_uri|db_url)(?:=|\s+|["']\s*,\s*)(["']?)([^\s"',\]]+)\1"""
)
_ENV_REF = re.compile(r"^(?:\$\{?(\w+)\}?|%(\w+)%|\$env:(\w+))$")
_ASSIGN = [
    # NAME=value, export NAME=value, ENV NAME=value, - NAME=value
    re.compile(r"""^\s*(?:export\s+|ENV\s+|-\s+)?([A-Za-z_]\w*)\s*=\s*(["']?)([^"'\s]+)\2"""),
    # ENV NAME value (Dockerfile)
    re.compile(r"""^\s*ENV\s+([A-Za-z_]\w*)\s+(["']?)([^"'\s]+)\2"""),
    # NAME: value (docker-compose, Cloud Run / App Engine env_variables). Only
    # UPPER_CASE keys, so ordinary YAML keys such as `url:` aren't env vars.
    re.compile(r"""^\s*([A-Z_][A-Z0-9_]*)\s*:\s*(["']?)([^"'\s]+)\2\s*(?:#.*)?$"""),
]  # fmt: skip
_K8S_NAME = re.compile(r"""^\s*-?\s*name:\s*["']?([A-Za-z_]\w*)["']?\s*$""")
_K8S_VALUE = re.compile(r"""^\s*value:\s*(["']?)([^"'\s]+)\1""")


def cli_session_uris(project: Project) -> list[Value]:
  """Values passed to `--session_service_uri` in scripts and deploy config."""
  out = []
  for rel, text in project.text_files(*DEPLOY_FILES):
    for i, line in enumerate(text.splitlines(), 1):
      for m in _FLAG.finditer(line):
        out.append(Value(rel, i, m.start(2), m.end(2), m.group(2)))
  return out


def env_ref(value: str) -> str | None:
  """`$DATABASE_URL`, `${DATABASE_URL}`, `%DATABASE_URL%` -> `DATABASE_URL`."""
  m = _ENV_REF.match(value)
  return next((g for g in m.groups() if g), None) if m else None


def env_values(project: Project) -> dict[str, list[Value]]:
  """URL-valued environment variables set anywhere in the project."""
  out: dict[str, list[Value]] = {}
  for rel, text in project.text_files(*DEPLOY_FILES):
    k8s_name = None
    for i, line in enumerate(text.splitlines(), 1):
      if k8s_name and (m := _K8S_VALUE.match(line)):
        _add(out, k8s_name, Value(rel, i, m.start(2), m.end(2), m.group(2)))
      k8s_name = (m := _K8S_NAME.match(line)) and m.group(1)
      for pattern in _ASSIGN:
        m = pattern.match(line)
        if m:
          _add(out, m.group(1), Value(rel, i, m.start(3), m.end(3), m.group(3)))
          break
  return out


def _add(out: dict[str, list[Value]], name: str, value: Value) -> None:
  if "://" in value.text:
    out.setdefault(name, []).append(value)
