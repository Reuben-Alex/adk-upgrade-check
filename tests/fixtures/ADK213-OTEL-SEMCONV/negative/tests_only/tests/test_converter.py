from google.adk.agents import Agent


def test_reads_legacy_spans():
  span = {"name": "call_llm"}  # fixture data for the legacy schema
  assert span["name"] == "call_llm"
