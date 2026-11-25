from a2a.server.events import EventQueue
from google.adk.runners import Runner


async def execute(runner: Runner, event_queue: EventQueue, task):
  await event_queue.enqueue_event(task)  # A2A's queue, not ADK's
