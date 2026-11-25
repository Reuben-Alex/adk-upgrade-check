from google.adk.events import Event
from google.adk.sessions import BaseSessionService


class MySessionService(BaseSessionService):
  """A custom session service appends events: that is its job."""

  async def append_event(self, session, event: Event) -> Event:
    session.events.append(event)
    return event


async def good_agent_body(ctx):
  yield Event(author="me")
  history = list(ctx.session.events)
  history.append(Event(author="local copy only"))
