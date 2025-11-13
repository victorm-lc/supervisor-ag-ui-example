"""
Shared utilities for subagent invocation.

Provides helpers for common subagent patterns:
1. Dynamic tool filtering by domain
2. AgentContext dataclass for frontend-advertised tool schemas

Key Pattern (Frontend-Owned Tool Schemas):
1. Frontend defines tool schemas in TypeScript (toolSchemas.ts)
2. Frontend sends schemas via config.configurable.client_tool_schemas
3. Each schema includes 'domains' array (e.g., ['wifi', 'video'])
4. get_filtered_tools() filters schemas by domain and converts to LangGraph tools
5. Combined tools (MCP + client) are passed to create_agent() at request time
6. Multiple client versions work simultaneously without backend changes

Example Flow:
- Mobile v1.0: sends ['play_video'] schema with domains: ['video']
- Mobile v2.0: sends ['play_video', 'network_status_display'] schemas
- Backend works with both versions (version-agnostic!)
- Frontend controls domain mapping (no backend changes needed!)

UI Message Propagation:
- UI messages from subagents propagate automatically via ui_state_middleware
- Middleware extends agent state with a 'ui' channel using @after_model decorator
- No manual propagation wrappers needed
"""

from dataclasses import dataclass, field
from src.utils.tool_converter import convert_agui_schemas_to_tools


# =============================================================================
# AGENT CONTEXT
# =============================================================================

@dataclass
class AgentContext:
    """
    Context passed from frontend to backend for dynamic tool filtering.
    
    Attributes:
        client_tool_schemas: List of AG UI tool schema dictionaries sent by frontend.
                            Each schema includes 'domains' metadata for filtering.
    
    This is accessible in agent tool handlers via runtime.config.get("configurable", {})
    """
    client_tool_schemas: list[dict] = field(default_factory=list)


# =============================================================================
# DYNAMIC TOOL FILTERING
# =============================================================================

def get_filtered_tools(domain: str, mcp_tools: list, runtime_config: dict) -> list:
    """
    Extract, filter, and convert client tools by domain from runtime config.
    
    This helper function centralizes the tool filtering logic used across domain agents.
    It extracts client tool schemas from the runtime config, filters them by domain,
    converts them to LangGraph tools, and combines them with MCP tools.
    
    Args:
        domain: The domain to filter for (e.g., "wifi", "video")
        mcp_tools: List of MCP tools for this domain
        runtime_config: Runtime config dict from ToolRuntime containing client_tool_schemas
    
    Returns:
        Combined list of MCP tools + filtered client tools
    
    Example:
        all_tools = get_filtered_tools(
            domain="video",
            mcp_tools=video_mcp_tools,
            runtime_config=runtime.config
        )
        agent = create_agent(tools=all_tools, ...)
    """
    # Extract client_tool_schemas from runtime config
    tool_schemas = runtime_config.get("configurable", {}).get("client_tool_schemas", [])
    
    if tool_schemas:
        print(f"📤 [{domain.upper()}] Received {len(tool_schemas)} tool schemas from frontend")
        
        # Filter schemas by domain
        domain_schemas = []
        for schema in tool_schemas:
            if "domains" not in schema:
                print(f"⚠️  [{domain.upper()}] Rejecting tool '{schema.get('name')}' - missing 'domains' property")
                continue
            if domain in schema.get("domains", []):
                domain_schemas.append(schema)
        
        print(f"🔍 [{domain.upper()}] Filtered to {len(domain_schemas)} {domain} domain tools: {[s['name'] for s in domain_schemas]}")
        
        # Convert schemas to LangGraph tools
        client_tools = convert_agui_schemas_to_tools(domain_schemas)
        print(f"🔄 [{domain.upper()}] Converted schemas to {len(client_tools)} tool instances")
    else:
        print(f"⚠️  [{domain.upper()}] No tool schemas in config")
        client_tools = []
    
    # Combine MCP tools + filtered client tools
    all_tools = mcp_tools + client_tools
    print(f"🔧 [{domain.upper()}] Combined {len(all_tools)} total tools: {[t.name for t in all_tools]}")
    
    return all_tools

