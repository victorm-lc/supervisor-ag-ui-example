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
from deepagents import CompiledSubAgent
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from langgraph.graph.ui import AnyUIMessage, ui_message_reducer

from src.mcp_setup import wifi_mcp_tools
from src.utils.subagent_utils import AgentContext, get_filtered_tools, UIPropagatoingRunnable


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
# WIFI SUBAGENT FACTORY
# =============================================================================

def create_wifi_subagent(runtime_config: dict) -> CompiledSubAgent:
    """
    Factory function that creates a CompiledSubAgent with dynamically filtered tools.
    
    This creates a WiFi specialist subagent for use with DeepAgents. The subagent
    has MCP tools + client tools filtered by the 'wifi' domain.
    
    The agent is wrapped with UIPropagatingRunnable to ensure UI messages from
    the subagent propagate to the supervisor and reach the frontend.
    
    Args:
        runtime_config: Runtime configuration dict containing client_tool_schemas
    
    Returns:
        CompiledSubAgent instance ready for use with create_deep_agent()
    
    Example:
        wifi_subagent = create_wifi_subagent(runtime_config)
        supervisor = create_deep_agent(subagents=[wifi_subagent, ...])
    """
    # Get filtered tools (MCP + client tools for wifi domain)
    all_tools = get_filtered_tools(
        domain="wifi",
        mcp_tools=wifi_mcp_tools,
        runtime_config=runtime_config
    )
    
    # Create and compile the agent graph
    wifi_agent = create_wifi_agent(all_tools)
    
    # Wrap with UIPropagatingRunnable to ensure UI messages reach frontend
    wrapped_agent = UIPropagatoingRunnable(wifi_agent)
    
    return CompiledSubAgent(
        name="wifi-specialist",
        description="Handles WiFi, internet connectivity, network problems, router issues, slow speeds, connection drops, and network diagnostics",
        runnable=wrapped_agent
    )

