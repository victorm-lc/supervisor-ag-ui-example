"""
Video Domain Agent

Handles all video content, streaming, and entertainment-related requests.

MCP Tools (from Video Gateway MCP):
- search_content: Search for movies, TV shows, and other video content

Client Tools (dynamically filtered):
- confirmation_dialog: User confirmation dialogs
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
from src.middleware import AgentContext, DomainToolFilterMiddleware
from src.tool_registry import CLIENT_TOOL_REGISTRY


# =============================================================================
# VIDEO AGENT
# =============================================================================

# Get ALL client tools (middleware will filter by domain + advertisement)
all_client_tools = list(CLIENT_TOOL_REGISTRY.values())

video_agent = create_agent(
    model="anthropic:claude-haiku-4-5",
    tools=video_mcp_tools + all_client_tools,  # MCP tools + ALL client tools (middleware filters!)
    context_schema=AgentContext,
    middleware=[
        DomainToolFilterMiddleware("video", video_mcp_tools),  # Filters client tools dynamically!
        HumanInTheLoopMiddleware(
            interrupt_on={
                "confirmation_dialog": True,  # Requires user confirmation
            },
            description_prefix="🚨 Confirmation required",
        ),
    ],
    system_prompt="""You are a helpful customer service assistant helping customers find and watch video content.

Speak directly to the customer in first person:
- "I'll search for that movie..."
- "Let me find some great dog videos for you..."
- "I can start playing that for you right now..."

When helping customers watch content:
1. Search for what they're looking for using search_content
2. Present the results naturally  
3. For FREE content (trailers, previews): Use play_video to start the video immediately
4. For RENTALS (if customer says "rent", "buy", or "purchase"): Use rent_movie which will ask for payment confirmation

The rent_movie tool will automatically handle payment confirmation with the user before completing the rental.

Be enthusiastic, friendly, and helpful.""",
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
    # Extract advertised_client_tools from config for subagent
    advertised_tools = runtime.config.get("configurable", {}).get("advertised_client_tools", [])
    if advertised_tools:
        print(f"📤 [VIDEO] Passing advertised tools to subagent: {advertised_tools}")
    else:
        print(f"⚠️ [VIDEO] No tools advertised in config")
    
    # Invoke subagent with runtime.config for interrupt propagation
    # 🔑 MUST use ainvoke() for MCP tools!
    result = await video_agent.ainvoke(
        {"messages": [HumanMessage(content=request)]},
        config=runtime.config  # Config has advertised_client_tools in configurable
    )
    
    # Return the final message content
    # Interrupts automatically propagate through the shared config
    return result["messages"][-1].content

