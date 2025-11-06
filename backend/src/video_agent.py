"""
Video Domain Agent

Handles all video content, streaming, and entertainment-related requests.

MCP Tools (from Video Gateway MCP):
- search_content: Search for movies, TV shows, and other video content

Client Tools (dynamically filtered):
- error_display: Error messages
- play_video: Video player component (return_direct=True)
"""

from typing import Annotated
from langchain_core.tools import tool
from langchain.tools import ToolRuntime
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain_core.messages import HumanMessage

from src.mcp_setup import video_mcp_tools
from src.middleware import AgentContext
from src.tool_converter import convert_agui_schemas_to_tools


# =============================================================================
# VIDEO AGENT FACTORY
# =============================================================================

VIDEO_SYSTEM_PROMPT = """You are a helpful customer service assistant for a premium video streaming service.

You are able to help the customer with their video streaming requests. Use 
your tools to help the customer with their requests.

The Play Video tool will display the video for the user, so do NOT give the user the video_url.
Be friendly and helpful, but make it clear all content requires rental.

Act as one unified assistant, not as a subagent. The customer should feel like they're talking to one person who can help with everything.""",

def create_video_agent(tools: list):
    """
    Create a video agent with the specified tools.
    
    This follows the customer's pattern: "Currently each sub agent is initialised on each request."
    By creating the agent per-request with the combined tool list, we avoid tool caching issues.
    
    Note: rent_movie uses middleware-based HITL (same pattern as restart_router).
    interrupt() cannot be called inside MCP tools because they run in a separate process.
    """
    return create_agent(
        model="anthropic:claude-haiku-4-5",
        tools=tools,  # MCP + client tools combined
        context_schema=AgentContext,
        middleware=[
            HumanInTheLoopMiddleware(
                interrupt_on={
                    "rent_movie": True,  # Rental requires payment confirmation
                },
                description_prefix="🚨 Payment confirmation required",
            ),
        ],
        system_prompt=VIDEO_SYSTEM_PROMPT,
    )


# =============================================================================
# VIDEO TOOL WRAPPER
# =============================================================================

@tool
async def handle_video_request(
    request: Annotated[str, "Customer's video or streaming request"],
    runtime: ToolRuntime
) -> str:
    """
    Route video content and streaming requests to the Video domain specialist.
    
    This tool invokes the video_agent subagent. Interrupts from the subagent
    automatically propagate to the supervisor via runtime.config.
    
    🔑 ASYNC: MCP tools require async invocation!
    """
    # Extract and convert client_tool_schemas from config
    tool_schemas = runtime.config.get("configurable", {}).get("client_tool_schemas", [])
    
    if tool_schemas:
        print(f"📤 [VIDEO] Received {len(tool_schemas)} tool schemas from frontend")
        
        # Filter schemas by domain
        video_schemas = []
        for schema in tool_schemas:
            if "domains" not in schema:
                print(f"⚠️ [VIDEO] Rejecting tool '{schema.get('name')}' - missing 'domains' property")
                continue
            if "video" in schema.get("domains", []):
                video_schemas.append(schema)
        
        print(f"🔍 [VIDEO] Filtered to {len(video_schemas)} video domain tools: {[s['name'] for s in video_schemas]}")
        
        # Convert schemas to LangGraph tools
        client_tools = convert_agui_schemas_to_tools(video_schemas)
        print(f"🔄 [VIDEO] Converted schemas to {len(client_tools)} tool instances")
    else:
        print(f"⚠️ [VIDEO] No tool schemas in config")
        client_tools = []
    
    # Combine MCP tools + filtered client tools
    all_tools = video_mcp_tools + client_tools
    print(f"🔧 [VIDEO] Creating subagent with {len(all_tools)} total tools: {[t.name for t in all_tools]}")
    
    # Create agent per-request with combined tools (customer's pattern!)
    # This avoids tool caching issues - each request gets a fresh agent
    video_agent = create_video_agent(all_tools)
    
    # Invoke with runtime.config for interrupt propagation
    # 🔑 MUST use ainvoke() for MCP tools!
    result = await video_agent.ainvoke(
        {"messages": [HumanMessage(content=request)]},
        config=runtime.config
    )
    
    # Return the final message content
    # Interrupts automatically propagate through the shared config
    return result["messages"][-1].content

