"""The rule registry, in release order. Add each new rule module here."""

from .adk119_async_db_url import AsyncDbUrl
from .adk119_sqlite_service import SqliteService
from .adk200_direct_append import DirectAppend
from .adk200_event_schema import EventSchema
from .adk206_artifact_ns import ArtifactNamespace
from .adk207_pyarrow_extra import PyarrowExtra
from .adk213_otel_semconv import OtelSemconv
from .adk214_enum_args import EnumArgs
from .adk214_vertex_session_kwargs import VertexSessionKwargs
from .adk215_builder_removed import BuilderRemoved
from .adk215_mcp_prompt_args import McpPromptArgs
from .base import Rule

ALL_RULES: list[Rule] = [
    AsyncDbUrl(),
    SqliteService(),
    DirectAppend(),
    EventSchema(),
    ArtifactNamespace(),
    PyarrowExtra(),
    OtelSemconv(),
    EnumArgs(),
    VertexSessionKwargs(),
    BuilderRemoved(),
    McpPromptArgs(),
]
RULES_BY_ID = {r.id: r for r in ALL_RULES}
