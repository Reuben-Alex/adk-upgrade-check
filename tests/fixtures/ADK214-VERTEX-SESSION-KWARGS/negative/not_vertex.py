from google.adk.sessions import InMemorySessionService

sessions = InMemorySessionService()


async def start(client):
  await client.create_session(app_name="b", user_id="u", session_state={})
