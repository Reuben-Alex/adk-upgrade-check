import os

from google.adk.sessions import DatabaseSessionService

sessions = DatabaseSessionService(db_url=os.environ["DATABASE_URL"])
