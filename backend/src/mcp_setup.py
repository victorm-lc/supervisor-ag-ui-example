"""
MCP Server Initialization

Each domain has its own dedicated MCP server - production pattern!
- WiFi Gateway MCP: Provides wifi_diagnostic, restart_router
- Video Gateway MCP: Provides search_content

This demonstrates the production pattern where:
- Each domain team owns their MCP server
- MCP servers can be in separate repos/deployments
- Backend tools are completely isolated by domain
- LangGraph agent uses MCP adapters to access tools
"""

import asyncio
from pathlib import Path
from langchain_mcp_adapters.client import MultiServerMCPClient


# Get absolute path to MCP servers
# __file__ is in backend/src/, so parent is backend/src/
PROJECT_ROOT = Path(__file__).parent  # backend/src/
MCP_SERVERS_DIR = PROJECT_ROOT / "mcp_servers"  # backend/src/mcp_servers/

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


async def _fetch_mcp_tools():
    """Fetch tools from all configured MCP servers."""
    return await mcp_client.get_tools()


def load_mcp_tools():
    """
    Load tools from MCP servers synchronously.
    
    Called at module import time to initialize the agents.
    Returns separate lists for WiFi and Video domain tools.
    """
    try:
        # Prefer asyncio.run so we don't disturb the global event loop
        mcp_tools = asyncio.run(_fetch_mcp_tools())
    except RuntimeError as exc:
        # asyncio.run() cannot be called from a running loop (e.g. during tests).
        # Fall back to a dedicated loop without mutating the global policy.
        if "asyncio.run() cannot be called" not in str(exc):
            raise
        loop = asyncio.new_event_loop()
        try:
            mcp_tools = loop.run_until_complete(_fetch_mcp_tools())
        finally:
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()
    
    # Separate MCP tools by domain
    wifi_mcp_tools = [t for t in mcp_tools if t.name in ["wifi_diagnostic", "restart_router"]]
    video_mcp_tools = [t for t in mcp_tools if t.name in ["search_content"]]
    
    print(f"✅ Loaded MCP tools from servers:")
    print(f"   WiFi MCP: {[t.name for t in wifi_mcp_tools]}")
    print(f"   Video MCP: {[t.name for t in video_mcp_tools]}")
    
    return wifi_mcp_tools, video_mcp_tools


# Load tools at module import time
wifi_mcp_tools, video_mcp_tools = load_mcp_tools()

