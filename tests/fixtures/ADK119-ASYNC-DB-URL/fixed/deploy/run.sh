#!/bin/sh
adk api_server --session_service_uri "$SESSION_URI" agents/
adk web --session_service_uri=postgresql+asyncpg://agent@db/agents agents/  # expect
