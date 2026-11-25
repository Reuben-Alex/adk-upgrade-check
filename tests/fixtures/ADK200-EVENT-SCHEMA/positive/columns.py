from google.adk.sessions import BaseSessionService


class PostgresSessionService(BaseSessionService):  # expect

  async def append_event(self, session, event):
    await self.db.execute(
        "INSERT INTO events (id, author, content) VALUES ($1, $2, $3)",
        event.id, event.author, event.content,
    )
    return event
