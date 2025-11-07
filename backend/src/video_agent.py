"""
Video Domain Agent

Handles all video content, streaming, and entertainment-related requests.

MCP Tools (from Video Gateway MCP):
- search_content: Search for movies, TV shows, and other video content

Client Tools (dynamically filtered):
- error_display: Error messages
- play_video: Video player component (pushes UI message)
"""

from typing import Annotated, Sequence, TypedDict
from langchain_core.tools import tool
from langchain.tools import ToolRuntime
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.graph.message import add_messages
from langgraph.graph.ui import AnyUIMessage, ui_message_reducer

from src.mcp_setup import video_mcp_tools
from src.utils.agent_helpers import AgentContext, get_filtered_tools
from src.utils.subagent_utils import propagate_ui_messages


# =============================================================================
# VIDEO AGENT STATE
# =============================================================================

class VideoAgentState(TypedDict):
    """Video agent state with UI channel for Generative UI."""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    ui: Annotated[Sequence[AnyUIMessage], ui_message_reducer]


# =============================================================================
# VIDEO AGENT FACTORY
# =============================================================================

VIDEO_SYSTEM_PROMPT = """You are a helpful customer service assistant helping customers find and watch video content.

Speak directly to the customer in first person:
- "I'll search for that movie..."
- "Let me find some great dog videos for you..."
- "I can start playing that for you right now..."

When helping customers watch content:
1. Search for what they're looking for using search_content
2. Present the results naturally  
3. Use play_video to start the video immediately

The rent_movie tool will automatically handle payment confirmation with the user before completing the rental.

Be enthusiastic, friendly, and helpful."""

def create_video_agent(tools: list):
    """
    Create a video agent with the specified tools.
    
    Using per-request agent creation pattern with centralized tool filtering.
    The get_filtered_tools() helper handles all tool extraction and filtering logic.
    """
    return create_agent(
        model="anthropic:claude-haiku-4-5",
        tools=tools,  # MCP + filtered client tools
        state_schema=VideoAgentState,
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
    
    This tool invokes the video_agent subagent using per-request agent creation
    with dynamically filtered tools via get_filtered_tools() helper.
    
    Interrupts from the subagent automatically propagate to the supervisor via runtime.config.
    
    🔑 ASYNC: MCP tools require async invocation!
    """
    # Get filtered tools using centralized helper function
    all_tools = get_filtered_tools(
        domain="video",
        mcp_tools=video_mcp_tools,
        runtime_config=runtime.config
    )
    
    # Create agent per-request with combined tools
    # This ensures tools are properly registered at agent creation time
    video_agent = create_video_agent(all_tools)
    
    # Invoke with runtime.config for interrupt propagation
    # 🔑 MUST use ainvoke() for MCP tools!
    result = await video_agent.ainvoke(
        {"messages": [HumanMessage(content=request)]},
        config=runtime.config
    )
    
    # Propagate UI messages from subagent to supervisor
    propagate_ui_messages(result)
    
    # Return the final message content
    return result["messages"][-1].content

