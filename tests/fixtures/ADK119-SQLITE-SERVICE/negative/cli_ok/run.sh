#!/bin/sh
adk web --session_service_uri=sqlite+aiosqlite:///./sessions.db agents/
adk api_server --session_service_uri postgresql+asyncpg://agent@db/agents agents/
