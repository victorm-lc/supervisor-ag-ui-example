"""
Client Tool Registry for AG UI

This registry contains all UI tools that can be advertised by the frontend client.
The frontend sends a list of tool names it supports (which may vary by app version),
and the backend dynamically injects only the relevant tools for each domain.

This pattern makes the backend version-agnostic:
- Old app versions with fewer tools still work
- New app versions with more tools work automatically
- No backend changes needed when adding new client tools
"""

from typing import Annotated
from langchain_core.tools import tool


# =============================================================================
# AG UI CLIENT TOOL IMPLEMENTATIONS
# =============================================================================

@tool
def confirmation_dialog(
    message: Annotated[str, "Message to display in the confirmation dialog"],
    options: Annotated[list[str], "List of options for the user to choose from"]
) -> str:
    """
    AG UI CLIENT TOOL: Display a confirmation dialog in the frontend.
    
    This tool triggers the ConfirmationDialog React component.
    The agent execution pauses (HITL interrupt) until the user selects an option.
    
    Universal tool - available to all domains.
    """
    # This will be intercepted by HITL middleware before execution
    # The frontend will render a ConfirmationDialog component
    # User selection will be passed back via the interrupt resume
    return f"✅ User confirmed: {options[0]}"


@tool
def error_display(error_message: Annotated[str, "Error message to display"]) -> str:
    """
    AG UI CLIENT TOOL: Display an error message in the frontend.
    
    This tool triggers the ErrorDisplay React component.
    
    Universal tool - available to all domains.
    """
    return f"❌ Error displayed to user: {error_message}"


@tool
def network_status_display(
    status_data: Annotated[dict, "Network status data to display"]
) -> str:
    """
    AG UI CLIENT TOOL: Display a network status card in the frontend.
    
    This tool triggers the NetworkStatusCard React component.
    
    WiFi domain-specific tool.
    """
    return f"📊 Network status card displayed with data: {status_data}"


@tool(return_direct=True)
def play_video(
    video_id: Annotated[str, "Video ID or search term"],
    title: Annotated[str, "Title of the video"]
) -> dict:
    """
    AG UI CLIENT TOOL: Play a video in the frontend YouTube player.
    
    This tool triggers the VideoPlayer React component with return_direct=True,
    meaning the UI renders immediately without sending a message back through the agent.
    
    Video domain-specific tool.
    """
    # Mock YouTube video - always show Big Buck Bunny demo
    # In production, you'd use the video_id to fetch the actual video
    return {
        "type": "video_player",
        "video_url": "https://www.youtube.com/embed/yVinK_ZIrt0?si=r9f67hrOSgwhiIe9",
        "title": title,
        "video_": video_id,
    }


# =============================================================================
# TOOL REGISTRY
# =============================================================================

CLIENT_TOOL_REGISTRY = {
    "confirmation_dialog": confirmation_dialog,
    "error_display": error_display,
    "network_status_display": network_status_display,
    "play_video": play_video,
}


def get_tools_by_names(tool_names: list[str]) -> list:
    """
    Get tool instances from the registry by name.
    
    This function is used by the middleware to dynamically inject tools
    based on what the client advertises.
    
    Args:
        tool_names: List of tool names advertised by the client
        
    Returns:
        List of tool instances that match the requested names
        
    Example:
        # Client advertises: ["confirmation_dialog", "error_display"]
        tools = get_tools_by_names(["confirmation_dialog", "error_display"])
        # Returns: [confirmation_dialog, error_display] tool instances
    """
    return [
        CLIENT_TOOL_REGISTRY[name] 
        for name in tool_names 
        if name in CLIENT_TOOL_REGISTRY
    ]


# =============================================================================
# VERSION COMPATIBILITY EXAMPLE
# =============================================================================
"""
Example: How this pattern supports multiple app versions

App Version 1.0 (older):
- Advertised tools: ["confirmation_dialog", "error_display"]
- Backend receives these 2 tools and injects them
- WiFi agent gets: [wifi_diagnostic, restart_router, confirmation_dialog, error_display]
- Works perfectly ✅

App Version 2.0 (newer):
- Advertised tools: ["confirmation_dialog", "error_display", "network_status_display", "play_video"]
- Backend receives these 4 tools and injects them
- WiFi agent gets: [wifi_diagnostic, restart_router, confirmation_dialog, error_display, network_status_display]
- Video agent gets: [search_content, confirmation_dialog, error_display, play_video]
- Works automatically ✅ (no backend changes needed!)

App Version 3.0 (future):
- Advertised tools: ["confirmation_dialog", "error_display", "network_status_display", "play_video", "payment_form"]
- Backend receives 5 tools, filters per domain
- New tool "payment_form" would only go to billing agent (if we add that domain)
- Works automatically ✅
"""

