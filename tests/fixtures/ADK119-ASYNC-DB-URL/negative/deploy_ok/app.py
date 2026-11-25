import os

from google.adk.sessions import DatabaseSessionService
from sqlalchemy import create_engine

sessions = DatabaseSessionService(db_url=os.environ["SESSIONS_URL"])
reports = create_engine(os.environ["REPORTING_URL"])
