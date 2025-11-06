#!/usr/bin/env python3
"""
WiFi MCP Server

This MCP server provides WiFi/connectivity domain tools.
Simulates backend services for WiFi diagnostics and router management.

In production, these would call actual backend APIs, databases, or IoT systems.
"""

from mcp.server.fastmcp import FastMCP
from typing import Annotated

# Create MCP server for WiFi domain
mcp = FastMCP("WiFi Gateway")


@mcp.tool()
def wifi_diagnostic(
    network_name: Annotated[str, "The WiFi network name (SSID) to diagnose"]
) -> str:
    """
    Run diagnostics on a WiFi network.
    
    In production, this would:
    - Query network monitoring systems
    - Check signal strength from IoT devices
    - Analyze traffic patterns
    - Return real diagnostic data
    """
    # Simulate diagnostic results
    return f"""WiFi Diagnostic Results for '{network_name}':
✅ Signal Strength: -45 dBm (Excellent)
✅ Channel: 36 (5 GHz)
⚠️ Connected Devices: 23 (High usage may cause slowdowns)
✅ Internet Speed: 250 Mbps down / 35 Mbps up
💡 Recommendation: Consider restarting router if speeds are slow"""


@mcp.tool()
def restart_router(
    router_id: Annotated[str, "Router identifier (optional, defaults to primary)"] = "primary",
    selected_option: Annotated[str, "The option selected by the user (filled after user interaction)"] = None
) -> str:
    """
    Restart the customer's router.
    
    This tool requires user confirmation via the ConfirmationDialog component.
    The HITL middleware intercepts this tool call and waits for user approval.
    
    In production, this would:
    - Send command to IoT platform
    - Track restart status
    - Notify customer when complete
    - Log action for customer service records
    
    ⚠️ This is a sensitive operation that requires user confirmation!
    """
    # If we have a selected option, the user has responded
    if selected_option:
        if selected_option == "Yes, Restart Router":
            return f"✅ Router restart initiated for {router_id}. Your router will be offline for about 2 minutes and then automatically come back online. Your devices should reconnect automatically."
        else:
            return "❌ Router restart cancelled by user"
    
    # This return is never reached - HITL middleware intercepts before execution
    # But we include it for clarity about what data the frontend needs
    return f"Awaiting confirmation to restart router {router_id}"


if __name__ == "__main__":
    # Run as stdio server (local subprocess communication)
    mcp.run(transport="stdio")

