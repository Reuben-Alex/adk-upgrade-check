import os

from google.adk.sessions import InMemorySessionService, VertexAiSessionService

sessions = VertexAiSessionService(project="p", location="us-central1")


async def start(user_id: str, service):
  await sessions.create_session(
      app_name="billing",
      user_id=user_id,
      state={"tier": "gold"},  # expect
      ttl="3600s",
  )
  await sessions.create_session(app_name="billing", user_id=user_id, session_id="abc")  # expect
  await sessions.create_session(
      app_name="billing", user_id=user_id, state={}, session_state={"x": 1}  # expect
  )
  await service.create_session(app_name="b", user_id=user_id, wait_for_completion=True)  # expect
