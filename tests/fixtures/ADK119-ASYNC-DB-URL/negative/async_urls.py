import os

from google.adk.sessions import DatabaseSessionService
from sqlalchemy import create_engine

a = DatabaseSessionService(db_url="sqlite+aiosqlite:///./sessions.db")
b = DatabaseSessionService(db_url="postgresql+asyncpg://u:p@db/agents")
c = DatabaseSessionService(db_url="postgresql+psycopg://u:p@db/agents")  # psycopg 3 has an async mode
d = DatabaseSessionService(db_url=os.environ["DATABASE_URL"])  # can't see the value
e = create_engine("postgresql://u:p@db/reporting")  # not a session service
