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
from src.middleware import AgentContext, DomainToolFilterMiddleware
from src.tool_registry import CLIENT_TOOL_REGISTRY


# =============================================================================
# WIFI AGENT
# =============================================================================

# Get ALL client tools (middleware will filter by domain + advertisement)
all_client_tools = list(CLIENT_TOOL_REGISTRY.values())

wifi_agent = create_agent(
    model="anthropic:claude-haiku-4-5",
    tools=wifi_mcp_tools + all_client_tools,  # MCP tools + ALL client tools (middleware filters!)
    context_schema=AgentContext,
    middleware=[
        DomainToolFilterMiddleware("wifi", wifi_mcp_tools),  # Filters client tools dynamically!
        HumanInTheLoopMiddleware(
            interrupt_on={
                "restart_router": True,  # Sensitive operation requires user approval
            },
            description_prefix="🚨 Action requires approval",
        ),
    ],
    system_prompt="""You are a helpful customer service assistant helping with WiFi and internet connectivity.

Speak directly to the customer in first person:
- "I'll run diagnostics on your network..."
- "Let me restart your router for you..."
- "I can help you troubleshoot that issue..."

When helping with connectivity issues:
1. Ask for their network name if needed for diagnostics
2. Run diagnostics to identify problems
3. Suggest solutions (like router restart) when appropriate
4. The router restart will automatically prompt for user confirmation

Be friendly, clear, and technically helpful.""",
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
    # Extract advertised_client_tools from config for subagent
    advertised_tools = runtime.config.get("configurable", {}).get("advertised_client_tools", [])
    if advertised_tools:
        print(f"📤 [WIFI] Passing advertised tools to subagent: {advertised_tools}")
    else:
        print(f"⚠️ [WIFI] No tools advertised in config")
    
    # Invoke subagent with runtime.config for interrupt propagation
    # 🔑 MUST use ainvoke() for MCP tools!
    result = await wifi_agent.ainvoke(
        {"messages": [HumanMessage(content=request)]},
        config=runtime.config  # Config has advertised_client_tools in configurable
    )
    
    # Return the final message content
    # Interrupts automatically propagate through the shared config
    return result["messages"][-1].content

