"""
Shared utilities for subagent invocation.


This file provides shared utilities for agent creation and tool management:
1. AgentContext dataclass for frontend-advertised tool schemas
2. get_filtered_tools() for domain-based tool filtering and combination
3. Provides helpers for common subagent patterns like UI message propagation.

Key Pattern (Frontend-Owned Tool Schemas):
1. Frontend defines tool schemas in TypeScript (toolSchemas.ts)
2. Frontend sends schemas via config.configurable.client_tool_schemas
3. Each schema includes 'domains' array (e.g., ['wifi', 'video'])
4. get_filtered_tools() filters schemas by domain and converts to LangGraph tools
5. Combined tools (MCP + client) are passed to create_agent() at request time
6. Multiple client versions work simultaneously without backend changes
"""

from typing import Any, Dict
from langgraph.graph.ui import push_ui_message
from dataclasses import dataclass, field
from src.utils.tool_converter import convert_agui_schemas_to_tools

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




def propagate_ui_messages(subagent_result: Dict[str, Any]) -> None:
    """
    Propagate UI messages from a subagent's state to the parent supervisor's state.
    
    LangGraph subagents have their own UI state channel, but UI messages don't
    automatically bubble up to the parent. This helper re-pushes them to the
    supervisor's context so they reach the frontend.
    
    Args:
        subagent_result: The result dict from subagent.ainvoke(), containing
                        'messages' and 'ui' keys.
    
    Example:
        result = await video_agent.ainvoke({"messages": [...]}, config=runtime.config)
        propagate_ui_messages(result)  # ← Makes UI messages reach frontend
        return result["messages"][-1].content
    """
    ui_messages = subagent_result.get("ui", [])
    
    if not ui_messages:
        return
    
    print(f"🎨 [SUBAGENT] Propagating {len(ui_messages)} UI messages to supervisor")
    
    for ui_msg in ui_messages:
        name = ui_msg.get("name")
        props = ui_msg.get("props", {})
        
        if not name:
            print(f"⚠️ [SUBAGENT] Skipping UI message with no name: {ui_msg}")
            continue
        
        print(f"  ↳ Pushing UI message: {name} with props {props}")
        push_ui_message(name, props)

