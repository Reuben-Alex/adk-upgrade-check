from google.adk.sessions import BaseSessionService


class BlobSessionService(BaseSessionService):

  async def append_event(self, session, event):
    await self.db.execute(
        "INSERT INTO events (id, body) VALUES ($1, $2)",
        event.id, event.model_dump_json(),
    )
    return event


class NotASessionService:
  pass
