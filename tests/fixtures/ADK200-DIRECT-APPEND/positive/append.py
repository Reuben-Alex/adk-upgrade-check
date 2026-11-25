from google.adk.agents import BaseAgent
from google.adk.events import Event


class Auditor(BaseAgent):

  async def _run_async_impl(self, ctx):
    event = Event(author=self.name)
    ctx.session.events.append(event)  # expect
    yield event


def after_tool(tool, args, tool_context, tool_response):
  tool_context._invocation_context.session.events.append(Event(author="audit"))  # expect
