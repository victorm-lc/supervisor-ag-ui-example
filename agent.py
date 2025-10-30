"""
Comcast "Everything App" Architecture Example for AG UI + LangGraph

This example demonstrates:
1. Supervisor agent routing to domain-specific subagents
2. Dynamic client tool filtering via middleware (VERSION-AGNOSTIC!)
3. AG UI pattern: Agent tool calls → Frontend UI components
4. HITL interrupts for user confirmations

Architecture:
- Supervisor routes customer requests to WiFi or Video domain specialists
- Each domain subagent has MCP tools + dynamically injected client tools
- Client advertises available tools → Middleware filters by domain → Tools injected
- Client tools (confirmation_dialog, etc.) trigger UI components in frontend
- Interrupts pause execution until user provides input via UI

Key Innovation: CLIENT TOOL ADVERTISEMENT
- Frontend sends list of available UI tools in config
- Backend is version-agnostic - works with whatever client supports
- Middleware filters client tools by domain relevance
- Old app versions (fewer tools) and new versions (more tools) both work
"""

from typing import Annotated
from langchain_core.tools import tool
from langchain.tools import ToolRuntime
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware, AgentMiddleware
from langchain_core.messages import HumanMessage

# Import client tool registry for dynamic tool injection
from tool_registry import get_tools_by_names, CLIENT_TOOL_REGISTRY


# =============================================================================
# MOCK MCP TOOLS (Backend tools - would connect to real services in production)
# =============================================================================

# WiFi Domain MCP Tools
@tool
def wifi_diagnostic(network_name: Annotated[str, "Name of the WiFi network"]) -> str:
    """
    Run network diagnostics for the specified WiFi network.
    This would typically call Comcast's network management APIs.
    """
    return f"✅ Diagnostics complete for '{network_name}':\n- Signal Strength: 95%\n- Speed: 500 Mbps\n- Latency: 12ms\n- No issues detected"


@tool
def restart_router() -> str:
    """
    Restart the customer's WiFi router remotely.
    This is a sensitive operation that requires user confirmation.
    """
    return "🔄 Router restart initiated successfully. Your router will be back online in approximately 2 minutes."


# Video Domain MCP Tools
@tool
def search_content(title: Annotated[str, "Search query for video content"]) -> str:
    """
    Search for video content in the Comcast catalog.
    ARGS: 
    title: The title of the video to search for.
    RETURN:
    video_id: The ID of the video to play.
    title: The title of the video to play.
    """
    return f"video_id: yVinK_ZIrt0, title: {title}"


# =============================================================================
# AG UI CLIENT TOOLS - Now in tool_registry.py!
# =============================================================================
# Client tools (confirmation_dialog, error_display, etc.) are now defined in
# tool_registry.py and dynamically injected by the middleware below.
# This allows the backend to be version-agnostic - it works with whatever
# tools the client advertises, regardless of app version.


# =============================================================================
# DOMAIN TOOL FILTERING MIDDLEWARE
# =============================================================================

# Define which AG UI client tools each domain can access
DOMAIN_TOOL_MAPPING = {
    "wifi": ["confirmation_dialog", "error_display", "network_status_display"],
    "video": ["confirmation_dialog", "error_display", "play_video"],  # play_video with return_direct!
}


class DomainToolFilterMiddleware(AgentMiddleware):
    """
    Middleware that dynamically filters and injects client tools based on domain.
    
    HOW IT WORKS:
    1. Frontend sends list of tool names in config: advertised_client_tools
    2. Middleware gets this list from config.configurable
    3. Filters to domain-relevant tools using DOMAIN_TOOL_MAPPING
    4. Looks up tool implementations from CLIENT_TOOL_REGISTRY
    5. Injects filtered tools into the agent dynamically
    
    This makes the backend VERSION-AGNOSTIC:
    - Old app (v1.0): ["confirmation_dialog", "error_display"] → Works ✅
    - New app (v2.0): ["confirmation_dialog", "error_display", "network_status_display", "video_player_ui"] → Works ✅
    - No backend changes needed when adding new client tools!
    """
    
    def __init__(self, domain: str, static_tools: list):
        """
        Args:
            domain: Domain name (wifi, video, etc.)
            static_tools: MCP tools that are always available (e.g. wifi_diagnostic)
        """
        self.domain = domain
        self.allowed_tool_names = DOMAIN_TOOL_MAPPING.get(domain, [])
        self.static_tools = static_tools
    
    def on_agent_start(self, state, config):
        """
        Called when agent starts. Dynamically injects client tools.
        
        Flow:
        1. Get advertised_client_tools from config (sent by frontend)
        2. Filter to domain-relevant tools
        3. Get tool instances from registry
        4. Inject into agent's tool list
        """
        # Get advertised tool names from config
        advertised_tool_names = config.get("configurable", {}).get("advertised_client_tools", [])
        
        # Filter to domain-relevant tool names
        # (intersection of what client advertises AND what this domain can use)
        relevant_tool_names = [
            name for name in advertised_tool_names 
            if name in self.allowed_tool_names
        ]
        
        # Get actual tool instances from registry
        client_tools = get_tools_by_names(relevant_tool_names)
        
        # Combine static MCP tools + dynamic client tools
        all_tools = self.static_tools + client_tools
        
        print(f"🔧 [{self.domain.upper()}] Injected tools: {[t.name for t in all_tools]}")
        
        # Return tools to be injected
        return {"tools": all_tools}


# =============================================================================
# DOMAIN SUBAGENTS
# =============================================================================

# Define static MCP tools for WiFi domain
wifi_static_tools = [
    wifi_diagnostic,
    restart_router,
]

# Get all potential client tools for WiFi domain from registry
wifi_client_tools = get_tools_by_names(DOMAIN_TOOL_MAPPING["wifi"])

# WiFi Domain Subagent
wifi_agent = create_agent(
    model="anthropic:claude-sonnet-4-5",
    tools=wifi_static_tools + wifi_client_tools,  # MCP tools + client tools
    middleware=[
        DomainToolFilterMiddleware("wifi", wifi_static_tools),  # Now just for logging/debug
        HumanInTheLoopMiddleware(
            interrupt_on={
                "restart_router": True,  # Sensitive operation requires user approval
            },
            description_prefix="🚨 Action requires approval",
        ),
    ],
    system_prompt="""You are a helpful Comcast assistant helping with WiFi and internet connectivity.

Speak directly to the customer in first person:
- "I'll run diagnostics on your network..."
- "Let me restart your router for you..."
- "I can help you troubleshoot that issue..."

Available tools:
- wifi_diagnostic: Check network performance and identify issues
- restart_router: Remotely restart the customer's router (will prompt user for confirmation)
- confirmation_dialog: Ask user to confirm general actions
- error_display: Show error messages in the UI
- network_status_display: Show detailed network status in the UI

When helping with connectivity issues:
1. Ask for their network name if needed for diagnostics
2. Run diagnostics to identify problems
3. Suggest solutions (like router restart) when appropriate
4. The router restart will automatically prompt for user confirmation

Be friendly, clear, and technically helpful. Make the customer feel like they're talking to one unified Comcast assistant.""",
)


# Define static MCP tools for Video domain
video_static_tools = [
    search_content,
    # play_video is now a client tool (in tool_registry.py) with return_direct=True!
]

# Get all potential client tools for Video domain from registry  
video_client_tools = get_tools_by_names(DOMAIN_TOOL_MAPPING["video"])

# Video Domain Subagent
video_agent = create_agent(
    model="anthropic:claude-sonnet-4-5",
    tools=video_static_tools + video_client_tools,  # MCP tools + client tools
    # No checkpointer! Subagent inherits parent's checkpointer for interrupt propagation
    middleware=[
        DomainToolFilterMiddleware("video", video_static_tools),  # Now just for logging/debug
        HumanInTheLoopMiddleware(
            interrupt_on={
                "confirmation_dialog": True,  # Requires user confirmation
            },
            description_prefix="🚨 Confirmation required",
        ),
    ],
    system_prompt="""You are a helpful Comcast assistant helping customers find and watch video content.

Speak directly to the customer in first person:
- "I'll search for that movie..."
- "Let me find some great dog videos for you..."
- "I can start playing that for you right now..."

Available tools:
- search_content: Search for movies, TV shows, and other video content
- play_video: Play a video directly in a YouTube player (will render immediately in the UI)
- confirmation_dialog: Ask user to confirm actions
- error_display: Show error messages in the UI

When helping customers watch content:
1. Search for what they're looking for using search_content
2. Present the results naturally  
3. Call play_video to start the video - it will automatically render a video player in the UI!

Note: play_video has return_direct=True, so you don't need to send an additional message after calling it.
The video player will appear automatically in the UI.

Be enthusiastic, friendly, and helpful. Make the customer feel like they're talking to one unified Comcast assistant who loves helping them find great content.""",
)


# =============================================================================
# SUBAGENT TOOL WRAPPERS
# =============================================================================

@tool
def handle_wifi_request(
    request: Annotated[str, "Customer's WiFi or connectivity request"],
    runtime: ToolRuntime
) -> str:
    """
    Route WiFi and network connectivity requests to the WiFi domain specialist.
    
    This tool invokes the wifi_agent subagent. Interrupts from the subagent
    automatically propagate to the supervisor via runtime.config.
    """
    # Invoke subagent with runtime.config for interrupt propagation
    result = wifi_agent.invoke(
        {"messages": [HumanMessage(content=request)]},
        config=runtime.config
    )
    
    # Return the final message content
    # Interrupts automatically propagate through the shared config
    return result["messages"][-1].content


@tool
def handle_video_request(
    request: Annotated[str, "Customer's video or streaming request"],
    runtime: ToolRuntime
) -> str:
    """
    Route video content and streaming requests to the Video domain specialist.
    
    This tool invokes the video_agent subagent. Interrupts from the subagent
    automatically propagate to the supervisor via runtime.config.
    """
    # Invoke subagent with runtime.config for interrupt propagation
    result = video_agent.invoke(
        {"messages": [HumanMessage(content=request)]},
        config=runtime.config
    )
    
    # Return the final message content
    # Interrupts automatically propagate through the shared config
    return result["messages"][-1].content


# =============================================================================
# SUPERVISOR AGENT
# =============================================================================

supervisor = create_agent(
    model="anthropic:claude-sonnet-4-5",
    tools=[handle_wifi_request, handle_video_request],
    system_prompt="""You are a helpful Comcast customer service assistant. You help customers with WiFi/internet issues and video content.

When a customer has a request, you have specialized tools to help them:
- Use handle_wifi_request for: internet connectivity, WiFi issues, network problems, router issues, slow speeds, connection drops, network diagnostics
- Use handle_video_request for: finding shows/movies, streaming issues, watching content, video playback, content recommendations, searching catalog

CRITICAL: When you call these tools, they will return a complete response. You MUST return that response directly to the customer as if it's your own response. DO NOT add commentary like "The specialist says..." or "I've routed your request...". Just return the tool's response naturally.

Examples:
- Customer: "My WiFi is slow" 
  → Call handle_wifi_request("My WiFi is slow")
  → Return the tool's response directly to the customer

- Customer: "I want to watch The Matrix"
  → Call handle_video_request("I want to watch The Matrix")
  → Return the tool's response directly to the customer

Act as one unified assistant, not as a routing supervisor. The customer should feel like they're talking to one person who can help with everything.""",
)
