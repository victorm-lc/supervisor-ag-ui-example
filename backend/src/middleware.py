"""
Shared Middleware for Dynamic Client Tool Filtering

For more information on Dynamic Tool Filtering visit the docs here: 
https://docs.langchain.com/oss/python/langchain/middleware#dynamically-selecting-tools

This middleware enables version-agnostic tool injection, allowing the backend
to work with any client version without code changes.

Key Pattern:
1. Frontend advertises available tools via config.configurable.advertised_client_tools
2. Middleware filters tools per domain using DOMAIN_TOOL_MAPPING
3. Agent receives only relevant tools for its domain
4. Multiple client versions work simultaneously

Example:
- Mobile v1.0: advertises ['confirmation_dialog']
- Mobile v2.0: advertises ['confirmation_dialog', 'play_video']
- Backend works with both versions without changes!
"""

from typing import Callable
from dataclasses import dataclass, field
from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse

from src.tool_registry import get_tools_by_names


# =============================================================================
# CONTEXT SCHEMA
# =============================================================================

@dataclass
class AgentContext:
    """
    Context passed from frontend to backend for dynamic tool filtering.
    
    This is accessible in middleware via request.runtime.context
    """
    advertised_client_tools: list[str] = field(default_factory=list)


# =============================================================================
# DOMAIN TOOL MAPPING
# =============================================================================

DOMAIN_TOOL_MAPPING = {
    "wifi": ["confirmation_dialog", "error_display", "network_status_display"],
    "video": ["confirmation_dialog", "error_display", "play_video"],
}


# =============================================================================
# DOMAIN TOOL FILTER MIDDLEWARE
# =============================================================================

class DomainToolFilterMiddleware(AgentMiddleware):
    """
    Middleware that dynamically filters and injects client tools based on domain.
    
    HOW IT WORKS:
    1. Frontend sends list of tool names in config: advertised_client_tools
    2. Middleware intercepts each model call via wrap_model_call
    3. Reads advertised tools from request.runtime.context
    4. Filters to domain-relevant tools using DOMAIN_TOOL_MAPPING
    5. Looks up tool implementations from CLIENT_TOOL_REGISTRY
    6. Sets request.tools to the filtered list before calling the model
    
    This makes the backend VERSION-AGNOSTIC:
    - Old app (v1.0): ["confirmation_dialog"] → Works ✅
    - New app (v2.0): ["confirmation_dialog", "play_video"] → Works ✅
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
        if isinstance(request.runtime.context, dict):
            advertised_tool_names = request.runtime.context.get("advertised_client_tools", [])
        else:
            advertised_tool_names = []
        
        # Log what we received (once per middleware instance)
        if not self._logged:
            print(f"📥 [{self.domain.upper()}] Middleware received advertised tools: {advertised_tool_names}")
            print(f"🔍 [{self.domain.upper()}] Allowed tools for this domain: {self.allowed_tool_names}")
        
        # Filter to domain-relevant tool names (intersection of advertised AND allowed)
        if not advertised_tool_names:
            if not self._logged:
                print(f"❌ [{self.domain.upper()}] NO TOOLS ADVERTISED - Frontend should send tools!")
            relevant_tool_names = []
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
        
        # Log once for debugging
        if not self._logged:
            print(f"🔧 [{self.domain.upper()}] Final injected tools: {[t.name for t in filtered_tools]}")
            self._logged = True
    
    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """Sync version: Intercepts model calls to filter and inject tools."""
        self._filter_and_inject_tools(request)
        return handler(request)
    
    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """
        Async version: Required for MCP tools which are async-only!
        
        Flow:
        1. Get advertised_client_tools from request.runtime.context
        2. Filter to domain-relevant tools
        3. Get tool instances from registry
        4. Set request.tools to filtered list
        5. Call handler to execute model with filtered tools
        """
        self._filter_and_inject_tools(request)
        return await handler(request)

