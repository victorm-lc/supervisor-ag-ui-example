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

from typing import Annotated, Sequence, TypedDict
from langchain_core.tools import tool
from langchain.tools import ToolRuntime
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.graph.message import add_messages
from langgraph.graph.ui import AnyUIMessage, ui_message_reducer

from src.mcp_setup import wifi_mcp_tools
from src.utils.subagent_utils import propagate_ui_messages, AgentContext, get_filtered_tools    


# =============================================================================
# WIFI AGENT STATE
# =============================================================================

class WiFiAgentState(TypedDict):
    """WiFi agent state with UI channel for Generative UI."""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    ui: Annotated[Sequence[AnyUIMessage], ui_message_reducer]


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
    
    Using per-request agent creation pattern with centralized tool filtering.
    The get_filtered_tools() helper handles all tool extraction and filtering logic.
    """
    return create_agent(
        model="anthropic:claude-haiku-4-5",
        tools=tools,  # MCP + filtered client tools
        state_schema=WiFiAgentState,
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
    
    This tool invokes the wifi_agent subagent using per-request agent creation
    with dynamically filtered tools via get_filtered_tools() helper.
    
    Interrupts from the subagent automatically propagate to the supervisor via runtime.config.
    
    🔑 ASYNC: MCP tools require async invocation!
    """
    # Get filtered tools using centralized helper function
    all_tools = get_filtered_tools(
        domain="wifi",
        mcp_tools=wifi_mcp_tools,
        runtime_config=runtime.config
    )
    
    # Create agent per-request with combined tools
    # This ensures tools are properly registered at agent creation time
    wifi_agent = create_wifi_agent(all_tools)
    
    # Invoke with runtime.config for interrupt propagation
    # 🔑 MUST use ainvoke() for MCP tools!
    result = await wifi_agent.ainvoke(
        {"messages": [HumanMessage(content=request)]},
        config=runtime.config
    )
    
    # Propagate UI messages from subagent to supervisor
    propagate_ui_messages(result)
    
    # Return the final message content
    return result["messages"][-1].content

