"""1.19.0: the CLI stores `sqlite://` sessions with a new service.

Up to 1.18, `adk web` / `adk api_server --session_service_uri sqlite:///x.db`
used DatabaseSessionService. From 1.19 the CLI hands `sqlite://` URIs to the
new SqliteSessionService, which uses a different schema and refuses to start
on a database written by 1.18 or earlier ("seems to use an old schema. Please
run the migration command"). Fresh databases are unaffected.
"""

from __future__ import annotations

from packaging.version import Version

from ..config_files import cli_session_uris
from ..config_files import env_ref
from ..config_files import env_values
from .base import Rule

_MIGRATE = (
    "python -m google.adk.sessions.migration.migrate_from_sqlalchemy_sqlite"
    " --source_db_path OLD.db --dest_db_path NEW.db"
)


class SqliteService(Rule):
  id = "ADK119-SQLITE-SERVICE"
  introduced_in = Version("1.19.0")
  severity = "error"
  title = "CLI sqlite:// sessions move to SqliteSessionService (needs migration)"
  changelog_url = "https://github.com/google/adk-python/commit/e2182544952c0174d1a8307fbba319456dca748b"

  def check(self, project):
    envs = None
    for flag in cli_session_uris(project):
      values = [(flag, "This `--session_service_uri`")]
      if (name := env_ref(flag.text)) is not None:
        envs = env_values(project) if envs is None else envs
        values = [(v, f"`{name}` (passed to `--session_service_uri` in {flag.rel})") for v in envs.get(name, [])]
      for v, subject in values:
        if not v.text.startswith("sqlite://"):
          continue  # sqlite+aiosqlite:// still goes to DatabaseSessionService
        yield self.text_finding(
            v.rel,
            v.line,
            v.start,
            f"{subject} is a `sqlite://` URL. From 1.19.0 the CLI opens it with"
            " SqliteSessionService, which refuses a database written by 1.18 or"
            " earlier.",
            f"migrate existing databases first: `{_MIGRATE}` (early 1.x"
            " releases name it `google.adk.sessions.migrate_from_sqlalchemy_sqlite`)",
            # Only databases that already exist are affected.
            confidence="likely",
        )
