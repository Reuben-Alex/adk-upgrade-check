from google.adk.agents import LlmAgent
from google.adk.agents import mcp_instruction_provider as mip
from google.adk.agents.mcp_instruction_provider import McpInstructionProvider

PARAMS = {"url": "http://localhost:8080/mcp"}

agent = LlmAgent(
    name="support",
    model="gemini-2.5-flash",
    instruction=McpInstructionProvider(PARAMS, "support_prompt"),  # expect
)
other = mip.McpInstructionProvider(  # expect
    connection_params=PARAMS,
    prompt_name="triage",
)
