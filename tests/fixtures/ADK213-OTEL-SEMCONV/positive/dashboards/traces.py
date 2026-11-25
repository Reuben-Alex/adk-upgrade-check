"""Queries for our latency dashboard. Docstrings that mention call_llm are ignored."""
from google.cloud import trace_v1

LLM_SPAN = "call_llm"  # expect
FILTER = "span_name = call_llm AND agent = billing"  # expect
