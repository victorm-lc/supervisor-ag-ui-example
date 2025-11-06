"""
Shared Context Schema for Dynamic Client Tool Advertisement

This file defines the AgentContext dataclass used by subagents to receive
frontend-advertised tool schemas via runtime.config.

Key Pattern (Frontend-Owned Tool Schemas):
1. Frontend defines tool schemas in TypeScript (toolSchemas.ts)
2. Frontend sends schemas via config.configurable.client_tool_schemas
3. Each schema includes 'domains' array (e.g., ['wifi', 'video'])
4. Subagent wrapper tools extract schemas from runtime.config
5. Wrapper tools filter schemas by domain
6. Wrapper tools convert schemas to LangGraph tools
7. Wrapper tools bind tools at invocation time via agent.bind_tools()
8. Multiple client versions work simultaneously without backend changes

Example Flow:
- Mobile v1.0: sends ['play_video'] schema with domains: ['video']
- Mobile v2.0: sends ['play_video', 'network_status_display'] schemas
- Backend works with both versions (version-agnostic!)
- Frontend controls domain mapping (no backend changes needed!)
"""

from dataclasses import dataclass, field


# =============================================================================
# CONTEXT SCHEMA
# =============================================================================

@dataclass
class AgentContext:
    """
    Context passed from frontend to backend for dynamic tool filtering.
    
    Attributes:
        client_tool_schemas: List of AG UI tool schema dictionaries sent by frontend.
                            Each schema includes 'domains' metadata for filtering.
    
    This is accessible in wrapper tools via runtime.config.get("configurable", {})
    """
    client_tool_schemas: list[dict] = field(default_factory=list)
