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

IMPORTANT: All content in our catalog requires rental before viewing. This is a pay-per-view service.

When helping customers watch content:
1. Use search_content to find what they're looking for
2. Extract the video_url and title from the search results
3. Inform the customer about the content and the rental price
4. ALWAYS call rent_movie to process the rental (required for all content):
   - title: Movie title
   - video_url: The YouTube embed URL
   - rental_price: Price (default $3.99)

The rent_movie tool will pause and ask the user for payment confirmation.
After the user approves payment, they can watch the content.

DO NOT call play_video directly. All content must go through rent_movie first.

Example flow:
User: "play me the matrix" or "I want to watch The Matrix"
→ search_content("matrix")
→ Extract video_url and title
→ Inform customer: "I found The Matrix! It's available to rent for $3.99 for 48 hours."
→ rent_movie(title="The Matrix", video_url="https://...", rental_price=3.99)
→ Tool pauses and shows payment confirmation UI
→ User approves payment
→ Rental confirmed, user gets access

Be friendly and helpful, but make it clear all content requires rental."""

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

