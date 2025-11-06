#!/usr/bin/env python3
"""
Video MCP Server

This MCP server provides video/streaming domain tools.
Simulates backend services for content search and video catalog.

In production, these would call actual video APIs, content databases, or streaming platforms.
"""

from mcp.server.fastmcp import FastMCP
from typing import Annotated
from langgraph.types import interrupt

# Create MCP server for Video domain
mcp = FastMCP("Video Gateway")


@mcp.tool()
def search_content(
    query: Annotated[str, "Search query for video content"],
    content_type: Annotated[str, "Type of content (movie, show, documentary)"] = "any"
) -> str:
    """
    Search the video catalog for content.
    
    In production, this would:
    - Query video content API
    - Search across multiple streaming platforms
    - Return real availability, ratings, descriptions
    - Check user's subscription entitlements
    """
    # Simulate content search results with YouTube embed URLs
    # In production, these would be real content URLs from your video platform
    mock_catalog = {
        "matrix": {
            "title": "The Matrix",
            "type": "movie",
            "year": 1999,
            "rating": "R",
            "video_url": "https://www.youtube.com/embed/vKQi3bBA1y8",  # Matrix trailer
            "description": "A computer hacker learns the true nature of reality"
        },
        "nature": {
            "title": "Planet Earth II",
            "type": "documentary",
            "year": 2016,
            "rating": "TV-G",
            "video_url": "https://www.youtube.com/embed/c8aFcHFu8QM",  # Planet Earth II trailer
            "description": "Stunning wildlife documentary series"
        },
        "comedy": {
            "title": "The Office",
            "type": "show",
            "year": 2005,
            "rating": "TV-14",
            "video_url": "https://www.youtube.com/embed/LHOtME2DL4g",  # The Office trailer
            "description": "Mockumentary about office workers"
        },
        "dog": {
            "title": "Cute Dogs Compilation",
            "type": "video",
            "year": 2023,
            "rating": "G",
            "video_url": "https://www.youtube.com/embed/j5a0jTc9S10",  # Cute dogs video
            "description": "Adorable dogs doing funny things"
        }
    }
    
    # Simple keyword matching
    query_lower = query.lower()
    for key, content in mock_catalog.items():
        if key in query_lower or content["title"].lower() in query_lower:
            return f"""Found: {content['title']} ({content['year']})
Type: {content['type'].title()}
Rating: {content['rating']}
Description: {content['description']}

🎬 Ready to play! To watch this content, use the play_video tool with:
- title: "{content['title']}"
- video_url: {content['video_url']}"""
    
    # No match found
    return f"No exact matches found for '{query}'. Try searching for 'matrix', 'nature documentaries', 'comedy shows', or 'dogs'."


@mcp.tool()
def rent_movie(
    title: Annotated[str, "Title of the movie to rent"],
    video_url: Annotated[str, "YouTube embed URL for the movie"],
    rental_price: Annotated[float, "Rental price in USD"] = 3.99,
    selected_option: Annotated[str, "User's confirmation decision (e.g., 'Yes, Rent', 'Cancel')"] = None
) -> str:
    """
    Rent a movie with payment confirmation.
    
    Uses middleware-based HITL pattern (configured in video_agent.py).
    The HumanInTheLoopMiddleware intercepts this tool and pauses for user approval.
    
    Note: interrupt() cannot be called inside MCP tools because they run in a 
    separate process without access to the LangGraph runnable context.
    
    In production, this would:
    - Process payment through payment gateway
    - Grant temporary viewing rights
    - Send confirmation email
    - Log transaction for billing
    """
    # Check if user approved or cancelled
    if selected_option and "cancel" in selected_option.lower():
        return "❌ Rental cancelled by user"
    
    # Process rental
    rental_id = f"R-{hash(title) % 100000:05d}"
    return f"✅ '{title}' rented successfully! You have 48 hours to watch. Rental ID: {rental_id}"


if __name__ == "__main__":
    # Run as stdio server (local subprocess communication)
    mcp.run(transport="stdio")

