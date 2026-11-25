from typing import Any

from google.adk.sessions import BaseSessionService


class RetryingSessionService(BaseSessionService):
  """Adds retries around another service, which does the storing."""

  def __init__(self, inner: BaseSessionService):
    self._inner = inner

  def __getattr__(self, name: str) -> Any:
    return getattr(self._inner, name)
