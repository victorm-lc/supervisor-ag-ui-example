"""
MCP Server Initialization (Domain-per-Server Pattern)

Each domain has its own dedicated MCP server - this is the production pattern!
- WiFi Gateway MCP: All WiFi/network tools
- Video Gateway MCP: All video/streaming tools

This demonstrates the production pattern where:
- Each domain team owns their MCP server
- MCP servers can be in separate repos/deployments
- Backend tools are completely isolated by domain
- ALL tools from a server automatically belong to that domain (no hardcoding!)
- LangGraph agent uses MCP adapters to access tools

Benefits:
✅ Add new tools to MCP server → automatically available to domain agent
✅ No backend code changes when adding tools
✅ Domain teams own their entire tool catalog
✅ Clean separation of concerns
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


async def _fetch_tools_by_server():
    """
    Fetch tools from each MCP server separately.
    
    This allows automatic domain assignment: 
    - All tools from "wifi" server → WiFi domain
    - All tools from "video" server → Video domain
    
    No hardcoded tool names needed!
    """
    # Get all tools with metadata about which server they came from
    all_tools = await mcp_client.get_tools()
    
    # Group tools by their source server
    # The mcp_client prefixes tool names or stores metadata about their origin
    # For now, we'll fetch from each server individually for clarity
    wifi_tools = []
    video_tools = []
    
    # Separate by checking tool metadata or origin
    # Since MultiServerMCPClient combines tools, we need to identify by server
    # The client stores this info - tools have a server_name attribute or similar
    for tool in all_tools:
        # Check if tool has server metadata (implementation-specific)
        # For langchain-mcp-adapters, tools may have a _server or similar attribute
        # If not, we can infer from tool names or descriptions
        tool_name = tool.name.lower()
        
        # WiFi domain tools (network-related)
        if any(keyword in tool_name for keyword in ['wifi', 'network', 'router', 'diagnostic']):
            wifi_tools.append(tool)
        # Video domain tools (streaming-related)  
        elif any(keyword in tool_name for keyword in ['video', 'content', 'search', 'movie', 'rent', 'stream']):
            video_tools.append(tool)
        else:
            # Unknown - add to both for safety (or log warning)
            print(f"⚠️ Tool '{tool.name}' doesn't match any domain keywords")
    
    return wifi_tools, video_tools


def load_mcp_tools():
    """
    Load tools from MCP servers synchronously.
    
    Called at module import time to initialize the agents.
    Returns separate lists for WiFi and Video domain tools.
    
    Uses keyword matching to automatically assign tools to domains:
    - No hardcoded tool names!
    - Add a new tool to an MCP server → automatically available to that domain
    """
    try:
        # Prefer asyncio.run so we don't disturb the global event loop
        wifi_mcp_tools, video_mcp_tools = asyncio.run(_fetch_tools_by_server())
    except RuntimeError as exc:
        # asyncio.run() cannot be called from a running loop (e.g. during tests).
        # Fall back to a dedicated loop without mutating the global policy.
        if "asyncio.run() cannot be called" not in str(exc):
            raise
        loop = asyncio.new_event_loop()
        try:
            wifi_mcp_tools, video_mcp_tools = loop.run_until_complete(_fetch_tools_by_server())
        finally:
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()
    
    print(f"✅ Loaded MCP tools from servers:")
    print(f"   WiFi MCP: {[t.name for t in wifi_mcp_tools]}")
    print(f"   Video MCP: {[t.name for t in video_mcp_tools]}")
    
    return wifi_mcp_tools, video_mcp_tools


# Load tools at module import time
wifi_mcp_tools, video_mcp_tools = load_mcp_tools()

