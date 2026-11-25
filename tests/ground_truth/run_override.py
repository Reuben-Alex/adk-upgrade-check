"""Ground truth for ADK200-RUN-OVERRIDE: is an overridden `_run_async_impl` still called?

uv run --no-project --with google-adk==1.39.1 python tests/ground_truth/run_override.py
uv run --no-project --with google-adk==2.0.0 python tests/ground_truth/run_override.py

Runs two agents through a Runner, with no model call needed if the override runs:
a BaseAgent subclass and an LlmAgent subclass, each overriding `_run_async_impl`.
"""

import asyncio
from importlib.metadata import version

from google.adk.agents import BaseAgent
from google.adk.agents import LlmAgent
from google.adk.events import Event
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types


def _reply(name, text):
  return Event(
      author=name,
      content=types.Content(role="model", parts=[types.Part(text=text)]),
  )


class CustomAgent(BaseAgent):

  async def _run_async_impl(self, ctx):
    yield _reply(self.name, "override ran")


class CustomLlmAgent(LlmAgent):

  async def _run_async_impl(self, ctx):
    yield _reply(self.name, "override ran")


async def run(agent):
  sessions = InMemorySessionService()
  runner = Runner(agent=agent, app_name="gt", session_service=sessions)
  await sessions.create_session(app_name="gt", user_id="u", session_id="s")
  msg = types.Content(role="user", parts=[types.Part(text="hi")])
  texts = []
  try:
    async for event in runner.run_async(user_id="u", session_id="s", new_message=msg):
      if event.content and event.content.parts:
        texts += [p.text for p in event.content.parts if p.text]
  except Exception as e:  # e.g. the bypass tries to reach a real model
    return f"{type(e).__name__}: {str(e)[:80]}"
  return texts


async def main():
  v = version("google-adk")
  print(f"google-adk {v}: BaseAgent subclass -> {await run(CustomAgent(name='custom'))}")
  print(f"google-adk {v}: LlmAgent subclass  -> {await run(CustomLlmAgent(name='llm', model='gemini-2.5-flash'))}")


asyncio.run(main())
