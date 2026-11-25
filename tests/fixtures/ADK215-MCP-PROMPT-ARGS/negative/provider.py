from google.adk.agents import McpInstructionProvider

PARAMS = {"url": "http://localhost:8080/mcp"}
KWARGS = {"arguments": {"tier": "gold"}}

a = McpInstructionProvider(PARAMS, "support_prompt", arguments={"tier": "gold"})
b = McpInstructionProvider(PARAMS, "triage", arguments=lambda ctx: {"user": ctx.state["user"]})
c = McpInstructionProvider(PARAMS, "triage", **KWARGS)
