from google.adk.sessions import VertexAiSessionService

sessions = VertexAiSessionService(project="p", location="us-central1")
EXTRA = {"ttl": "60s"}


async def start(user_id: str):
  await sessions.create_session(
      app_name="b", user_id=user_id, state={}, session_id="s", display_name="d",
      ttl="60s", labels={"env": "prod"},
  )
  await sessions.create_session(app_name="b", user_id=user_id, **EXTRA)
