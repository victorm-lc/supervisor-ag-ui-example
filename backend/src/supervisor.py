"""
Supervisor Agent - Main Entry Point

Architecture Overview:
- Supervisor routes customer requests to domain-specific subagents (WiFi, Video)
- Each subagent has MCP server tools + dynamically injected client tools
- MCP servers provide domain-specific backend tools
- Client advertises available tools → Middleware filters by domain
- Client tools trigger UI components in frontend
- Interrupts pause execution until user provides input via UI

Key Innovations:
1. CLIENT TOOL ADVERTISEMENT: Frontend sends available tools, backend filters per domain
2. MCP INTEGRATION: Each domain has dedicated MCP server (production pattern!)
3. VERSION-AGNOSTIC: Works with any client version (v1.0, v2.0, v3.0) simultaneously

For more details, see:
- middleware.py: Dynamic tool filtering logic
- mcp_setup.py: MCP server initialization
- wifi_agent.py: WiFi domain specialist
- video_agent.py: Video domain specialist
- tool_registry.py: Client tool definitions
"""

from langchain.agents import create_agent

# Import domain agents and their tool wrappers
from src.wifi_agent import handle_wifi_request
from src.video_agent import handle_video_request


# =============================================================================
# SUPERVISOR AGENT
# =============================================================================

supervisor = create_agent(
    model="anthropic:claude-haiku-4-5",
    tools=[handle_wifi_request, handle_video_request],
    system_prompt="""You are a helpful customer service assistant. You help customers with WiFi/internet issues and video content.

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
