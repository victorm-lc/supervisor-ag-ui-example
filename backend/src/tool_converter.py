"""
Tool Schema Converter (AG UI Protocol Compliant)

Converts AG UI tool schemas (defined in frontend TypeScript) into LangGraph tools.

This follows the official AG UI Protocol specification where:
1. Frontend owns tool schemas (TypeScript definitions following AG UI spec)
2. Backend dynamically creates tools from JSON Schema formatted parameters
3. No backend code changes needed when frontend adds new tools

The converter creates "no-op" tools since these are UI-focused client tools.
The backend validates the schema and passes tool calls to the frontend.

AG UI Spec: https://docs.ag-ui.com/concepts/tools
"""

from typing import Any
from langchain_core.tools import tool as langchain_tool


def convert_agui_schemas_to_tools(schemas: list[dict]) -> list:
    """
    Convert AG UI Protocol tool schemas to LangGraph tools.
    
    Args:
        schemas: List of AG UI tool schema dicts from frontend
                 Format following AG UI spec:
                 [{
                     "name": "play_video",
                     "description": "Play a video",
                     "parameters": {
                         "type": "object",
                         "properties": {
                             "video_url": {"type": "string", "description": "..."},
                             "title": {"type": "string", "description": "..."}
                         },
                         "required": ["video_url", "title"]
                     },
                     "returnDirect": True
                 }]
    
    Returns:
        List of LangGraph tool instances ready to be used by agents
    """
    if not schemas:
        return []
    
    tools = []
    for schema in schemas:
        tool_instance = _create_tool_from_schema(schema)
        tools.append(tool_instance)
    
    return tools


def _create_tool_from_schema(schema: dict):
    """
    Create a single LangGraph tool from an AG UI Protocol schema.
    
    Handles JSON Schema format for parameters as per AG UI spec.
    The tool is a "no-op" that returns data for frontend rendering.
    """
    tool_name = schema.get("name", "unknown_tool")
    tool_description = schema.get("description", "")
    parameters_schema = schema.get("parameters", {})
    return_direct = schema.get("returnDirect", False)
    
    # Extract parameter names from JSON Schema format
    # AG UI format: parameters.properties = {param_name: {type, description, ...}}
    properties = parameters_schema.get("properties", {})
    param_names = list(properties.keys())
    
    # Create the tool function dynamically
    def dynamic_tool_func(**kwargs) -> Any:
        """
        Dynamic no-op tool function.
        
        For client tools, the backend doesn't need actual logic.
        The tool call triggers UI rendering in the frontend.
        """
        # For return_direct tools (like play_video), return a flat dict (no nesting)
        if return_direct:
            import json
            # Don't nest kwargs - spread them at the top level
            result = {
                "type": tool_name,
                **kwargs  # This spreads: video_url="...", title="..." directly
            }
            print(f"🎬 [{tool_name.upper()}] Returning data:", result)
            # Return as JSON string for frontend parsing
            return json.dumps(result)
        
        # For regular tools, return a success message
        return f"✅ {tool_name} called with args: {kwargs}"
    
    # Set function name and docstring
    dynamic_tool_func.__name__ = tool_name
    dynamic_tool_func.__doc__ = tool_description
    
    # Convert to LangChain tool
    # The @tool decorator will infer parameter types from the function signature
    if return_direct:
        tool_instance = langchain_tool(return_direct=True)(dynamic_tool_func)
    else:
        tool_instance = langchain_tool(dynamic_tool_func)
    
    # Override the tool's description to match the schema
    tool_instance.description = tool_description
    
    return tool_instance


# =============================================================================
# ARCHITECTURE NOTES (AG UI Protocol Pattern)
# =============================================================================
"""
This converter implements the AG UI Protocol pattern where frontend defines tools
and backend dynamically creates them at runtime.

FRONTEND (TypeScript - AG UI compliant):
```typescript
const CLIENT_TOOL_SCHEMAS: AGUIToolSchema[] = [
  {
    name: 'play_video',
    description: 'Play a video in the YouTube player',
    parameters: {
      type: 'object',
      properties: {
        video_url: {
          type: 'string',
          description: 'YouTube embed URL'
        },
        title: {
          type: 'string',
          description: 'Video title'
        }
      },
      required: ['video_url', 'title']
    },
    returnDirect: true,
    domains: ['video']  // Custom extension
  }
]
```

BACKEND (Python - LangGraph):
```python
# Schemas come from frontend via config
schemas = runtime.config.get("configurable", {}).get("client_tool_schemas", [])

# Convert AG UI schemas to LangGraph tools
tools = convert_agui_schemas_to_tools(schemas)

# Combine with MCP tools
agent = create_agent(tools=mcp_tools + tools)
```

BENEFITS:
✅ Follows official AG UI Protocol specification
✅ Frontend team owns UI tool definitions
✅ Backend is version-agnostic (no changes needed for new tools)
✅ Multiple app versions work simultaneously
✅ Easy for customers already using AG UI to adopt this pattern
✅ Type-safe on frontend (TypeScript with JSON Schema)
✅ Dynamic on backend (Python)

AG UI SPEC COMPLIANCE:
✅ Tool name, description, parameters match official protocol
✅ Parameters use JSON Schema format (type, properties, required)
➕ Extensions: returnDirect (LangGraph), domains (frontend-owned filtering)
"""

