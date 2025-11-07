#!/usr/bin/env python3
"""
Video MCP Server

This MCP server provides video/streaming domain tools.
Simulates backend services for content search and video catalog.

In production, these would call actual video APIs, content databases, or streaming platforms.
"""

from mcp.server.fastmcp import FastMCP
from typing import Annotated

# Create MCP server for Video domain
mcp = FastMCP("Video Gateway")


@mcp.tool()
def search_content(
    query: Annotated[str, "Search query for video content"]
) -> str:
    """
    Search for video content in the catalog. Returns information about matching content.
    
    This tool ONLY provides information about available content. To actually watch/rent
    the content, you MUST use the rent_movie tool afterwards with the exact title.
    
    Args:
        query: Search terms (e.g., "matrix", "nature", "comedy", "dogs")
    
    Returns:
        Information about the matching content including title, type, year, rating,
        description, and rental price. Does NOT include video URL - use rent_movie to get access.
    """
    # Simulate content search results
    # In production, this would query a real content database
    mock_catalog = {
        "matrix": {
            "title": "The Matrix",
            "type": "movie",
            "year": 1999,
            "rating": "R",
            "rental_price": 3.99,
            "description": "A computer hacker learns the true nature of reality"
        },
        "nature": {
            "title": "Planet Earth II",
            "type": "documentary",
            "year": 2016,
            "rating": "TV-G",
            "rental_price": 2.99,
            "description": "Stunning wildlife documentary series"
        },
        "comedy": {
            "title": "The Office",
            "type": "show",
            "year": 2005,
            "rating": "TV-14",
            "rental_price": 1.99,
            "description": "Mockumentary about office workers"
        },
        "dog": {
            "title": "Cute Dogs Compilation",
            "type": "video",
            "year": 2023,
            "rating": "G",
            "rental_price": 0.99,
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
Rental Price: ${content['rental_price']}
Description: {content['description']}

To rent and watch this content, use the rent_movie tool with the title: "{content['title']}" """
    
    # No match found
    return f"No exact matches found for '{query}'. Try searching for 'matrix', 'nature documentaries', 'comedy shows', or 'dogs'."


@mcp.tool()
def rent_movie(
    title: Annotated[str, "Exact title of the movie to rent (from search_content results)"],
    rental_price: Annotated[float, "Rental price from search_content results (e.g., 3.99)"],
    selected_option: Annotated[str, "User's confirmation decision (e.g., 'Yes, Rent', 'Cancel')"] = None
) -> str:
    """
    Rent a movie and get the video URL to play it. Requires user approval before processing payment.
    
    WORKFLOW:
    1. Call search_content(query) to find content and get the rental price
    2. Call rent_movie(title, rental_price) with the exact title and price from search results
    3. User will be prompted to confirm payment
    4. On approval, returns video URL for playback
    
    This tool triggers a human-in-the-loop confirmation (configured in video_agent.py).
    The HumanInTheLoopMiddleware intercepts this tool call and pauses for user approval
    before actually processing the rental.
    
    Args:
        title: Exact title of the content to rent (e.g., "The Matrix")
        rental_price: Price shown in search_content results (e.g., 3.99 for $3.99)
        selected_option: User's choice after confirmation prompt (set by middleware)
    
    Returns:
        On success: Rental confirmation with video URL to play the content
        On cancel: Cancellation message
    
    Production behavior:
        - Process payment through payment gateway
        - Grant temporary viewing rights
        - Send confirmation email
        - Log transaction for billing
    """
    # Check if user approved or cancelled
    if selected_option and "cancel" in selected_option.lower():
        return "❌ Rental cancelled by user"
    
    # Process rental successfully - return the video URL
    rental_id = f"R-{hash(title) % 100000:05d}"
    
    # For this demo, we use the same video URL for all content
    # In production, this would return the actual content URL from the video platform
    demo_video_url = "https://www.youtube.com/embed/vKQi3bBA1y8"
    
    return f"""✅ '{title}' rented successfully!

Rental ID: {rental_id}
Access: 48 hours
Video URL: {demo_video_url}"""


if __name__ == "__main__":
    # Run as stdio server (local subprocess communication)
    mcp.run(transport="stdio")

