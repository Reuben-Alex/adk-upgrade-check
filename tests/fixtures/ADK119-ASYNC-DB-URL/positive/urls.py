import os

from google.adk.sessions import DatabaseSessionService
from google.adk.sessions.database_session_service import DatabaseSessionService as DSS

DB_URL = "postgresql://user:pass@localhost:5432/agents"

a = DatabaseSessionService(db_url="sqlite:///./sessions.db")  # expect
b = DatabaseSessionService(DB_URL)  # expect
c = DSS(db_url="postgresql+psycopg2://u:p@db/agents")  # expect
d = DatabaseSessionService(db_url="mysql+pymysql://u:p@db/agents")  # expect
e = DatabaseSessionService(os.getenv("DATABASE_URL", "sqlite:///local.db"))  # expect
f = DatabaseSessionService(db_url="postgresql://u:p@db/agents?sslmode=require")  # expect
g = DatabaseSessionService(db_url=f"postgresql://{os.environ['DB_HOST']}/agents")  # expect
