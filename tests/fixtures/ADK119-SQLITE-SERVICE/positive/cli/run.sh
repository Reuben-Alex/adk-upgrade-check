#!/bin/sh
adk web --session_service_uri=sqlite:///./sessions.db agents/  # expect
adk api_server --session_service_uri "$SESSIONS" agents/
