"""1.19.0: DatabaseSessionService became fully async.

It builds its engine with `create_async_engine`, which rejects a synchronous
driver. A URL such as `postgresql://...` or `sqlite:///...` that worked on
1.18 now fails at startup with "resolves to a synchronous driver". The
changelog listed this as a feature, not a breaking change.
"""

from __future__ import annotations

import libcst as cst
from packaging.version import Version

from ..engine import is_adk
from ..engine import Module
from ..engine import string_value
from .base import Rule

# backend -> (sync drivers, async replacement). `None` is "no driver named",
# which SQLAlchemy resolves to the sync default (psycopg2, mysqldb, pysqlite).
_SYNC = {
    "postgresql": ({None, "psycopg2", "psycopg2cffi", "pg8000"}, "asyncpg"),
    "mysql": ({None, "mysqldb", "pymysql", "mysqlconnector"}, "aiomysql"),
    "mariadb": ({None, "mysqldb", "pymysql", "mysqlconnector"}, "asyncmy"),
    "sqlite": ({None, "pysqlite"}, "aiosqlite"),
}


def sync_url_fix(url: str) -> tuple[str, str] | None:
  """For a sync URL, returns (scheme, async scheme); otherwise None."""
  scheme, sep, _ = url.partition("://")
  if not sep:
    return None
  backend, _, driver = scheme.partition("+")
  if backend not in _SYNC:
    return None
  sync_drivers, async_driver = _SYNC[backend]
  if (driver or None) not in sync_drivers:
    return None
  return scheme, f"{backend}+{async_driver}"


class AsyncDbUrl(Rule):
  id = "ADK119-ASYNC-DB-URL"
  introduced_in = Version("1.19.0")
  severity = "error"
  title = "DatabaseSessionService needs an async database driver"
  changelog_url = "https://github.com/google/adk-python/commit/74959414d8ded733d584875a49fb4638a12d3ce5"

  def check(self, project):
    for m in project.modules:
      for call in m.calls:
        if not is_adk(m.qualname(call.func), "DatabaseSessionService"):
          continue
        arg = _db_url_arg(call)
        if arg is None:
          continue
        yield from self._check_value(m, arg)

  def _check_value(self, m: Module, arg: cst.BaseExpression):
    expr, confidence = arg, "certain"
    # A module-level constant: DB_URL = "postgresql://..."
    if isinstance(expr, cst.Name) and m.assigns.get(expr.value) is not None:
      expr = m.assigns[expr.value]
    # os.getenv("DB_URL", "postgresql://...") / os.environ.get(...)
    if isinstance(expr, cst.Call) and m.qualname(expr.func) in (
        "os.getenv",
        "os.environ.get",
    ):
      if len(expr.args) < 2:
        return
      expr = expr.args[1].value
      confidence = "likely"  # only wrong when the env var is unset

    if isinstance(expr, cst.FormattedString):
      head = expr.parts[0] if expr.parts else None
      url = head.value if isinstance(head, cst.FormattedStringText) else None
      replaceable = False
    else:
      url = string_value(expr)
      replaceable = isinstance(expr, cst.SimpleString)
    if url is None:
      return
    fix = sync_url_fix(url)
    if fix is None:
      return
    scheme, new_scheme = fix
    replacement = None
    # asyncpg does not accept libpq query options such as sslmode=, so only
    # rewrite URLs without a query string.
    if replaceable and "?" not in url:
      old = m.code(expr)
      replacement = old.replace(f"{scheme}://", f"{new_scheme}://", 1)
    driver = new_scheme.split("+")[1]
    yield self.finding(
        m,
        arg,
        f"DatabaseSessionService URL uses the synchronous scheme `{scheme}://`."
        " Since 1.19.0 the service is fully async and fails at startup with a"
        " synchronous driver.",
        f"use `{new_scheme}://` and add the `{driver}` package to your"
        " dependencies",
        confidence=confidence,
        replacement=replacement,
        fix_node=expr,
    )


def _db_url_arg(call: cst.Call) -> cst.BaseExpression | None:
  for i, arg in enumerate(call.args):
    if arg.keyword is not None and arg.keyword.value == "db_url":
      return arg.value
    if i == 0 and arg.keyword is None and not arg.star:
      return arg.value
  return None
