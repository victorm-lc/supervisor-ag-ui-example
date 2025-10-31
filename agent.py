"""
Example "Everything App" Architecture Example for AG UI + LangGraph + MCP

This example demonstrates:
1. Supervisor agent routing to domain-specific subagents
2. Dynamic client tool filtering via middleware (VERSION-AGNOSTIC!)
3. **MCP integration: Each domain has its own MCP server** (WiFi Gateway, Video Gateway)
4. AG UI pattern: Agent tool calls → Frontend UI components
5. HITL interrupts for user confirmations

Architecture:
- Supervisor routes customer requests to WiFi or Video domain specialists
- Each domain subagent has **MCP server tools** + dynamically injected client tools
- **MCP servers** provide domain-specific backend tools (wifi_diagnostic, search_content)
- Client advertises available tools → Middleware filters by domain → Tools injected
- Client tools (confirmation_dialog, play_video) trigger UI components in frontend
- Interrupts pause execution until user provides input via UI

Key Innovation 1: CLIENT TOOL ADVERTISEMENT
- Frontend sends list of available UI tools in config
- Backend is version-agnostic - works with whatever client supports
- Middleware filters client tools by domain relevance
- Old app versions (fewer tools) and new versions (more tools) both work

Key Innovation 2: MCP INTEGRATION (Example PATTERN!)
- Each domain has dedicated MCP server (just like their architecture!)
- WiFi Gateway MCP: wifi_diagnostic, restart_router
- Video Gateway MCP: search_content
- Clean separation: MCP tools (backend) + Client tools (frontend UI)
"""

import asyncio
import os
from pathlib import Path
from typing import Annotated, Callable
from dataclasses import dataclass, field
from langchain_core.tools import tool
from langchain.tools import ToolRuntime
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware, AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.messages import HumanMessage
from langchain_mcp_adapters.client import MultiServerMCPClient

# Import client tool registry for dynamic tool injection
from tool_registry import get_tools_by_names, CLIENT_TOOL_REGISTRY


# =============================================================================
# CONTEXT SCHEMA FOR DYNAMIC TOOL INJECTION
# =============================================================================

@dataclass
class AgentContext:
    """
    Context passed from frontend to backend for dynamic tool filtering.
    
    This is accessible in middleware via request.runtime.context
    """
    advertised_client_tools: list[str] = field(default_factory=list)  # List of tool names the client supports


# =============================================================================
# MCP SERVER INITIALIZATION (Example PATTERN!)
# =============================================================================
#
# Each domain has its own dedicated MCP server - just like Example's architecture!
# - WiFi Gateway MCP: Provides wifi_diagnostic, restart_router
# - Video Gateway MCP: Provides search_content
#
# This demonstrates the production pattern where:
# - Each domain team owns their MCP server
# - MCP servers can be in separate repos/deployments
# - Backend tools are completely isolated by domain
# - LangGraph agent uses MCP adapters to access tools

# Get absolute path to MCP servers
PROJECT_ROOT = Path(__file__).parent
MCP_SERVERS_DIR = PROJECT_ROOT / "mcp_servers"

# Initialize MCP client with both domain servers
mcp_client = MultiServerMCPClient(
    {
        # WiFi Gateway MCP Server (stdio transport - local subprocess)
        "wifi": {
            "transport": "stdio",
            "command": "python",
            "args": [str(MCP_SERVERS_DIR / "wifi_server.py")],
        },
        # Video Gateway MCP Server (stdio transport - local subprocess)
        "video": {
            "transport": "stdio",
            "command": "python",
            "args": [str(MCP_SERVERS_DIR / "video_server.py")],
        }
    }
)

# Load tools from MCP servers
# This is called at module import time to initialize the agents
def _load_mcp_tools():
    """Load tools from MCP servers synchronously."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(mcp_client.get_tools())
    finally:
        loop.close()

# Get all MCP tools (wifi_diagnostic, restart_router, search_content)
mcp_tools = _load_mcp_tools()

# Separate MCP tools by domain for agent creation
wifi_mcp_tools = [t for t in mcp_tools if t.name in ["wifi_diagnostic", "restart_router"]]
video_mcp_tools = [t for t in mcp_tools if t.name in ["search_content"]]

print(f"✅ Loaded MCP tools from servers:")
print(f"   WiFi MCP: {[t.name for t in wifi_mcp_tools]}")
print(f"   Video MCP: {[t.name for t in video_mcp_tools]}")


# =============================================================================
# AG UI CLIENT TOOLS - Now in tool_registry.py!
# =============================================================================
# Client tools (confirmation_dialog, error_display, play_video, etc.) are defined in
# tool_registry.py and dynamically injected by the middleware below.
# This allows the backend to be version-agnostic - it works with whatever
# tools the client advertises, regardless of app version.
#
# ARCHITECTURE SUMMARY:
# - MCP tools (wifi_diagnostic, restart_router, search_content) → Backend services
# - Client tools (confirmation_dialog, play_video) → Frontend UI components


# =============================================================================
# DOMAIN TOOL FILTERING MIDDLEWARE (Example PATTERN)
# =============================================================================
#
# 🎯 THE KEY INNOVATION: Version-Agnostic Backend
#
# This architecture solves the problem of having multiple client versions in production:
# - Mobile v1.0 may only support ['confirmation_dialog', 'error_display']
# - Mobile v2.0 adds ['network_status_display', 'play_video']
# - Web v1.0 may have all tools from day 1
#
# The backend stays AGNOSTIC to versions:
# 1. Client advertises what it supports: config.configurable.advertised_client_tools
# 2. Middleware filters by domain: WiFi agent gets network_status_display, Video agent gets play_video
# 3. Backend never needs updating when client adds new tools!
#
# This mapping defines which client tools are RELEVANT for each domain.
# The client advertises what it HAS, this mapping defines what each domain NEEDS.

DOMAIN_TOOL_MAPPING = {
    "wifi": ["confirmation_dialog", "error_display", "network_status_display"],
    "video": ["confirmation_dialog", "error_display", "play_video"],  # play_video with return_direct!
}


class DomainToolFilterMiddleware(AgentMiddleware):
    """
    Middleware that dynamically filters and injects client tools based on domain.
    
    HOW IT WORKS:
    1. Frontend sends list of tool names in config: advertised_client_tools
    2. Middleware intercepts each model call via wrap_model_call
    3. Reads advertised tools from request.runtime.config.configurable
    4. Filters to domain-relevant tools using DOMAIN_TOOL_MAPPING
    5. Looks up tool implementations from CLIENT_TOOL_REGISTRY
    6. Sets request.tools to the filtered list before calling the model
    
    This makes the backend VERSION-AGNOSTIC:
    - Old app (v1.0): ["confirmation_dialog", "error_display"] → Works ✅
    - New app (v2.0): ["confirmation_dialog", "error_display", "network_status_display", "play_video"] → Works ✅
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
        self._logged = False  # Only log once to avoid spam
    
    def _filter_and_inject_tools(self, request: ModelRequest) -> None:
        """
        Helper method to filter and inject tools into the request.
        Used by both sync and async versions.
        """
        # Get advertised tool names from runtime.context (sent by frontend)
        # The context is passed from the parent agent and contains advertised_client_tools
        if isinstance(request.runtime.context, dict):
            advertised_tool_names = request.runtime.context.get("advertised_client_tools", [])
        else:
            advertised_tool_names = []
        
        # Log what we received (once per middleware instance)
        if not self._logged:
            print(f"📥 [{self.domain.upper()}] Middleware received advertised tools: {advertised_tool_names}")
            print(f"🔍 [{self.domain.upper()}] Allowed tools for this domain: {self.allowed_tool_names}")
        
        # Filter to domain-relevant tool names (intersection of advertised AND allowed)
        # FALLBACK TEMPORARILY DISABLED FOR TESTING
        if not advertised_tool_names:
            # No tools advertised - ERROR for now to ensure frontend is working
            if not self._logged:
                print(f"❌ [{self.domain.upper()}] NO TOOLS ADVERTISED - Frontend should send tools!")
            relevant_tool_names = []  # Will result in no client tools
        else:
            # Filter to intersection of advertised AND allowed
            relevant_tool_names = [
                name for name in advertised_tool_names 
                if name in self.allowed_tool_names
            ]
        
        # Get actual tool instances from registry
        client_tools = get_tools_by_names(relevant_tool_names)
        
        # Combine static MCP tools + dynamic client tools
        filtered_tools = self.static_tools + client_tools
        
        # Inject filtered tools into the request
        request.tools = filtered_tools
        
        # Log once for debugging (avoid spam on every model call)
        if not self._logged:
            print(f"🔧 [{self.domain.upper()}] Final injected tools: {[t.name for t in filtered_tools]}")
            self._logged = True
    
    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """
        Sync version: Intercepts model calls to dynamically filter and inject tools.
        
        🔑 For MCP tools, use awrap_model_call (async version) instead!
        """
        self._filter_and_inject_tools(request)
        return handler(request)
    
    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """
        Async version: Intercepts model calls to dynamically filter and inject tools.
        
        🔑 REQUIRED for MCP tools which are async-only!
        
        Flow:
        1. Get advertised_client_tools from request.runtime.config (sent by frontend)
        2. Filter to domain-relevant tools
        3. Get tool instances from registry
        4. Set request.tools to filtered list
        5. Call handler to execute model with filtered tools
        """
        self._filter_and_inject_tools(request)
        return await handler(request)


# =============================================================================
# DOMAIN SUBAGENTS
# =============================================================================

# Get ALL client tools from registry (middleware will filter by domain + advertisement)
all_client_tools = list(CLIENT_TOOL_REGISTRY.values())

# WiFi Domain Subagent
# MCP tools: wifi_diagnostic, restart_router (loaded from WiFi Gateway MCP server)
wifi_agent = create_agent(
    model="anthropic:claude-haiku-4-5",
    tools=wifi_mcp_tools + all_client_tools,  # MCP tools + ALL client tools (middleware filters!)
    context_schema=AgentContext,  # Define context schema for dynamic tool injection
    middleware=[
        DomainToolFilterMiddleware("wifi", wifi_mcp_tools),  # Filters client tools dynamically!
        HumanInTheLoopMiddleware(
            interrupt_on={
                "restart_router": True,  # Sensitive operation requires user approval
            },
            description_prefix="🚨 Action requires approval",
        ),
    ],
    system_prompt="""You are a helpful Example assistant helping with WiFi and internet connectivity.

Speak directly to the customer in first person:
- "I'll run diagnostics on your network..."
- "Let me restart your router for you..."
- "I can help you troubleshoot that issue..."


When helping with connectivity issues:
1. Ask for their network name if needed for diagnostics
2. Run diagnostics to identify problems
3. Suggest solutions (like router restart) when appropriate
4. The router restart will automatically prompt for user confirmation

Be friendly, clear, and technically helpful. Make the customer feel like they're talking to one unified Example assistant.""",
)


# Video Domain Subagent
# MCP tools: search_content (loaded from Video Gateway MCP server)
# Client tools: play_video (in tool_registry.py) with return_direct=True!
video_agent = create_agent(
    model="anthropic:claude-haiku-4-5",
    tools=video_mcp_tools + all_client_tools,  # MCP tools + ALL client tools (middleware filters!)
    context_schema=AgentContext,  # Define context schema for dynamic tool injection
    # No checkpointer! Subagent inherits parent's checkpointer for interrupt propagation
    middleware=[
        DomainToolFilterMiddleware("video", video_mcp_tools),  # Filters client tools dynamically!
        HumanInTheLoopMiddleware(
            interrupt_on={
                "confirmation_dialog": True,  # Requires user confirmation
            },
            description_prefix="🚨 Confirmation required",
        ),
    ],
    system_prompt="""You are a helpful Example assistant helping customers find and watch video content.

Speak directly to the customer in first person:
- "I'll search for that movie..."
- "Let me find some great dog videos for you..."
- "I can start playing that for you right now..."


When helping customers watch content:
1. Search for what they're looking for using search_content
2. Present the results naturally  
3. Call play_video to start the video - it will automatically render a video player in the UI!

Note: play_video has return_direct=True, so you don't need to send an additional message after calling it.
The video player will appear automatically in the UI.

Be enthusiastic, friendly, and helpful. Make the customer feel like they're talking to one unified Example assistant who loves helping them find great content.""",
)


# =============================================================================
# SUBAGENT TOOL WRAPPERS
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
    Context is also propagated for dynamic tool filtering.
    
    🔑 ASYNC: MCP tools require async invocation!
    """
    # Extract advertised_client_tools from config.configurable for subagent
    advertised_tools = runtime.config.get("configurable", {}).get("advertised_client_tools", [])
    if advertised_tools:
        print(f"📤 [WIFI] Passing advertised tools to subagent: {advertised_tools}")
    else:
        print(f"⚠️ [WIFI] No tools advertised in config - subagent will use fallback")
    
    # Invoke subagent with runtime.config for interrupt propagation
    # 🔑 MUST use ainvoke() for MCP tools!
    # Pass advertised tools in config (not context) so middleware can access them
    result = await wifi_agent.ainvoke(
        {"messages": [HumanMessage(content=request)]},
        config=runtime.config  # Config already has advertised_client_tools in configurable
    )
    
    # Return the final message content
    # Interrupts automatically propagate through the shared config
    return result["messages"][-1].content


@tool
async def handle_video_request(
    request: Annotated[str, "Customer's video or streaming request"],
    runtime: ToolRuntime
) -> str:
    """
    Route video content and streaming requests to the Video domain specialist.
    
    This tool invokes the video_agent subagent. Interrupts from the subagent
    automatically propagate to the supervisor via runtime.config.
    Context is also propagated for dynamic tool filtering.
    
    🔑 ASYNC: MCP tools require async invocation!
    """
    # Extract advertised_client_tools from config.configurable for subagent
    advertised_tools = runtime.config.get("configurable", {}).get("advertised_client_tools", [])
    if advertised_tools:
        print(f"📤 [VIDEO] Passing advertised tools to subagent: {advertised_tools}")
    else:
        print(f"⚠️ [VIDEO] No tools advertised in config - subagent will use fallback")
    
    # Invoke subagent with runtime.config for interrupt propagation
    # 🔑 MUST use ainvoke() for MCP tools!
    # Pass advertised tools in config (not context) so middleware can access them
    result = await video_agent.ainvoke(
        {"messages": [HumanMessage(content=request)]},
        config=runtime.config  # Config already has advertised_client_tools in configurable
    )
    
    # Return the final message content
    # Interrupts automatically propagate through the shared config
    return result["messages"][-1].content


# =============================================================================
# SUPERVISOR AGENT
# =============================================================================

supervisor = create_agent(
    model="anthropic:claude-haiku-4-5",
    tools=[handle_wifi_request, handle_video_request],
    system_prompt="""You are a helpful Example customer service assistant. You help customers with WiFi/internet issues and video content.

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
