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
    # Simulate content search results
    mock_catalog = {
        "matrix": {
            "title": "The Matrix",
            "type": "movie",
            "year": 1999,
            "rating": "R",
            "video_id": "matrix_1999",
            "description": "A computer hacker learns the true nature of reality"
        },
        "nature": {
            "title": "Planet Earth II",
            "type": "documentary",
            "year": 2016,
            "rating": "TV-G",
            "video_id": "planet_earth_2",
            "description": "Stunning wildlife documentary series"
        },
        "comedy": {
            "title": "The Office",
            "type": "show",
            "year": 2005,
            "rating": "TV-14",
            "video_id": "the_office",
            "description": "Mockumentary about office workers"
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
Video ID: {content['video_id']}

Ready to play! Use video_id: {content['video_id']}"""
    
    # No match found
    return f"No exact matches found for '{query}'. Try searching for 'matrix', 'nature documentaries', or 'comedy shows'."


if __name__ == "__main__":
    # Run as stdio server (local subprocess communication)
    mcp.run(transport="stdio")

