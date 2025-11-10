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
from deepagents import CompiledSubAgent
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from langgraph.graph.ui import AnyUIMessage, ui_message_reducer

from src.mcp_setup import video_mcp_tools
from src.utils.subagent_utils import AgentContext, get_filtered_tools, UIPropagatoingRunnable


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
# VIDEO SUBAGENT FACTORY
# =============================================================================

def create_video_subagent(runtime_config: dict) -> CompiledSubAgent:
    """
    Factory function that creates a CompiledSubAgent with dynamically filtered tools.
    
    This creates a Video specialist subagent for use with DeepAgents. The subagent
    has MCP tools + client tools filtered by the 'video' domain.
    
    The agent is wrapped with UIPropagatingRunnable to ensure UI messages from
    the subagent propagate to the supervisor and reach the frontend.
    
    Args:
        runtime_config: Runtime configuration dict containing client_tool_schemas
    
    Returns:
        CompiledSubAgent instance ready for use with create_deep_agent()
    
    Example:
        video_subagent = create_video_subagent(runtime_config)
        supervisor = create_deep_agent(subagents=[video_subagent, ...])
    """
    # Get filtered tools (MCP + client tools for video domain)
    all_tools = get_filtered_tools(
        domain="video",
        mcp_tools=video_mcp_tools,
        runtime_config=runtime_config
    )
    
    # Create and compile the agent graph
    video_agent = create_video_agent(all_tools)
    
    # Wrap with UIPropagatingRunnable to ensure UI messages reach frontend
    wrapped_agent = UIPropagatoingRunnable(video_agent)
    
    return CompiledSubAgent(
        name="video-specialist",
        description="Handles finding shows/movies, streaming issues, watching content, video playback, content recommendations, and searching catalog",
        runnable=wrapped_agent
    )

