"""
WiFi Domain Agent

Handles all WiFi, internet connectivity, and network-related requests.

MCP Tools (from WiFi Gateway MCP):
- wifi_diagnostic: Run network diagnostics
- restart_router: Remotely restart customer's router

Client Tools (dynamically filtered):
- confirmation_dialog: User confirmation dialogs
- error_display: Error messages
- network_status_display: Network status cards
"""

from typing import Annotated
from langchain_core.tools import tool
from langchain.tools import ToolRuntime
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain_core.messages import HumanMessage

from src.mcp_setup import wifi_mcp_tools
from src.middleware import AgentContext
from src.tool_converter import convert_agui_schemas_to_tools


# =============================================================================
# WIFI AGENT FACTORY
# =============================================================================

WIFI_SYSTEM_PROMPT = """You are a helpful customer service assistant helping with WiFi and internet connectivity.

Speak directly to the customer in first person:
- "I'll run diagnostics on your network..."
- "Let me restart your router for you..."
- "I can help you troubleshoot that issue..."

When helping with connectivity issues:
1. Ask for their network name if needed for diagnostics
2. Run diagnostics to identify problems
3. Suggest solutions (like router restart) when appropriate
4. The router restart will automatically prompt for user confirmation

Be friendly, clear, and technically helpful."""

def create_wifi_agent(tools: list):
    """
    Create a WiFi agent with the specified tools.
    
    This follows the customer's pattern: "Currently each sub agent is initialised on each request."
    By creating the agent per-request with the combined tool list, we avoid tool caching issues.
    """
    return create_agent(
        model="anthropic:claude-haiku-4-5",
        tools=tools,  # MCP + client tools combined
        context_schema=AgentContext,
        middleware=[
            HumanInTheLoopMiddleware(
                interrupt_on={
                    "restart_router": True,  # Sensitive operation requires user approval
                },
                description_prefix="🚨 Action requires approval",
            ),
        ],
        system_prompt=WIFI_SYSTEM_PROMPT,
    )


# =============================================================================
# WIFI TOOL WRAPPER
# =============================================================================

@tool
async def handle_wifi_request(
    request: Annotated[str, "Customer's WiFi or connectivity request"],
    runtime: ToolRuntime
) -> str:
    """
    Route WiFi and network connectivity requests to the WiFi domain specialist.
    
    This tool invokes the wifi_agent subagent. Interrupts from the subagent
    automatically propagate to the supervisor via runtime.config.
    
    🔑 ASYNC: MCP tools require async invocation!
    """
    # Extract and convert client_tool_schemas from config
    tool_schemas = runtime.config.get("configurable", {}).get("client_tool_schemas", [])
    
    if tool_schemas:
        print(f"📤 [WIFI] Received {len(tool_schemas)} tool schemas from frontend")
        
        # Filter schemas by domain
        wifi_schemas = []
        for schema in tool_schemas:
            if "domains" not in schema:
                print(f"⚠️ [WIFI] Rejecting tool '{schema.get('name')}' - missing 'domains' property")
                continue
            if "wifi" in schema.get("domains", []):
                wifi_schemas.append(schema)
        
        print(f"🔍 [WIFI] Filtered to {len(wifi_schemas)} wifi domain tools: {[s['name'] for s in wifi_schemas]}")
        
        # Convert schemas to LangGraph tools
        client_tools = convert_agui_schemas_to_tools(wifi_schemas)
        print(f"🔄 [WIFI] Converted schemas to {len(client_tools)} tool instances")
    else:
        print(f"⚠️ [WIFI] No tool schemas in config")
        client_tools = []
    
    # Combine MCP tools + filtered client tools
    all_tools = wifi_mcp_tools + client_tools
    print(f"🔧 [WIFI] Creating subagent with {len(all_tools)} total tools: {[t.name for t in all_tools]}")
    
    # Create agent per-request with combined tools (customer's pattern!)
    # This avoids tool caching issues - each request gets a fresh agent
    wifi_agent = create_wifi_agent(all_tools)
    
    # Invoke with runtime.config for interrupt propagation
    # 🔑 MUST use ainvoke() for MCP tools!
    result = await wifi_agent.ainvoke(
        {"messages": [HumanMessage(content=request)]},
        config=runtime.config
    )
    
    # Return the final message content
    # Interrupts automatically propagate through the shared config
    return result["messages"][-1].content

