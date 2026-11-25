import httpx
from google.adk.cli.built_in_agents import root_agent as builder_agent  # expect
import google.adk.cli.built_in_agents.adk_agent_builder_assistant  # expect
from google.adk.cli import built_in_agents  # expect

APP = "billing"


def open_builder(base_url: str):
  return httpx.get(f"{base_url}/dev/apps/{APP}/builder/state")  # expect


SAVE_URL = "http://localhost:8000/dev/apps/billing/builder/save"  # expect
