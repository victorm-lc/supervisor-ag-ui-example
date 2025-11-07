"""
Tool Schema Converter (AG UI Protocol Compliant)

Converts AG UI tool schemas (defined in frontend TypeScript) into LangGraph tools
that push UI messages through LangGraph's Generative UI channel.

This follows the official AG UI Protocol specification where:
1. Frontend owns tool schemas (TypeScript definitions following AG UI spec)
2. Backend dynamically creates tools from JSON Schema formatted parameters
3. When agent calls tool, it pushes UI message to frontend via dedicated UI channel
4. No backend code changes needed when frontend adds new tools

AG UI Spec: https://docs.ag-ui.com/concepts/tools
LangGraph Generative UI: https://docs.langchain.com/langsmith/generative-ui-react
"""

from typing import Any
from langchain.tools import tool as langchain_tool
from langgraph.graph.ui import push_ui_message


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
    
    Why dynamic Pydantic models?
    - Frontend advertises: {"name": "play_video", "parameters": {...}}
    - LangChain needs: A Pydantic model for args_schema so LLM sees proper params
    - Solution: Use create_model() to build Pydantic schema from JSON Schema
    
    This is the standard LangChain pattern for dynamic tool creation.
    """
    from pydantic import Field, create_model
    
    tool_name = schema.get("name", "unknown_tool")
    tool_description = schema.get("description", "")
    parameters_schema = schema.get("parameters", {})
    
    # Step 1: Parse JSON Schema from frontend
    properties = parameters_schema.get("properties", {})
    required_params = parameters_schema.get("required", [])
    
    # Step 2: Convert JSON Schema to Pydantic field definitions
    # Format: {param_name: (type, Field(...))}
    pydantic_fields = {}
    for param_name, param_info in properties.items():
        param_type = _json_schema_type_to_python(param_info.get("type", "string"))
        param_description = param_info.get("description", "")
        
        # Required vs optional parameters
        if param_name in required_params:
            pydantic_fields[param_name] = (
                param_type,
                Field(description=param_description)
            )
        else:
            pydantic_fields[param_name] = (
                param_type,
                Field(default=None, description=param_description)
            )
    
    # Step 3: Build Pydantic model dynamically
    # This is what LangChain uses to serialize the tool schema for the LLM
    DynamicArgsModel = create_model(
        f"{tool_name}_args",
        **pydantic_fields
    )
    
    # Create the tool function dynamically
    def dynamic_tool_func(**kwargs) -> str:
        """
        AG UI-compliant tool that pushes UI message when called.
        
        When the agent calls this tool:
        1. Parameters are passed as kwargs (e.g., video_url="...", title="...")
        2. We push a UI message with these props to the frontend
        3. Return friendly text to the agent (goes in message stream)
        
        This follows LangGraph's Generative UI pattern where UI data
        flows through a dedicated channel separate from messages.
        """
        # Push UI message to frontend through dedicated UI channel
        print(f"🎬 [{tool_name.upper()}] Tool called with kwargs:", kwargs)
        push_ui_message(tool_name, kwargs)
        print(f"✅ [{tool_name.upper()}] UI message pushed to frontend")
        
        # Return success message to agent (goes in message stream)
        return f"✅ {tool_description} - UI updated successfully"
    
    # Set function name and docstring
    dynamic_tool_func.__name__ = tool_name
    dynamic_tool_func.__doc__ = tool_description
    
    # Convert to LangChain tool with explicit args_schema
    # No return_direct needed - UI messages flow through dedicated channel
        tool_instance = langchain_tool(
            args_schema=DynamicArgsModel
        )(dynamic_tool_func)
    
    # Override the tool's description to match the schema
    tool_instance.description = tool_description
    
    return tool_instance


def _json_schema_type_to_python(json_type: str) -> type:
    """
    Convert JSON Schema type string to Python type.
    
    JSON Schema types: string, number, integer, boolean, array, object
    """
    type_mapping = {
        "string": str,
        "number": float,
        "integer": int,
        "boolean": bool,
        "array": list,
        "object": dict,
    }
    return type_mapping.get(json_type, str)  # Default to str if unknown


# =============================================================================
# ARCHITECTURE NOTES (AG UI Protocol + LangGraph Generative UI)
# =============================================================================
"""
This converter implements the AG UI Protocol pattern with LangGraph's Generative UI,
where frontend defines tools and backend dynamically creates them at runtime.

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
    domains: ['video']  // Custom extension
  }
]
```

BACKEND (Python - LangGraph):
```python
# Schemas come from frontend via config
schemas = runtime.config.get("configurable", {}).get("client_tool_schemas", [])

# Convert AG UI schemas to LangGraph tools that push UI messages
tools = convert_agui_schemas_to_tools(schemas)

# Combine with MCP tools
agent = create_agent(tools=mcp_tools + tools)

# When agent calls play_video(video_url="...", title="..."):
# 1. Tool function executes
# 2. Calls push_ui_message("play_video", {video_url: "...", title: "..."})
# 3. Returns text message to agent
# 4. UI message flows to frontend through dedicated UI channel
```

FRONTEND (React - Consuming UI messages):
```javascript
for await (const chunk of stream) {
  if (chunk.event === 'ui/message') {
    const uiMsg = chunk.data
    if (uiMsg.name === 'play_video') {
      setVideoPlayer(uiMsg.props)  // props are already structured
    }
  }
}
```

BENEFITS:
✅ Follows official AG UI Protocol specification
✅ Uses LangGraph's official Generative UI pattern
✅ Frontend team owns UI tool definitions
✅ Backend is version-agnostic (no changes needed for new tools)
✅ Multiple app versions work simultaneously
✅ Clean separation: messages vs UI data
✅ No JSON parsing or tool message inspection needed
✅ Easy for customers already using AG UI to adopt this pattern
✅ Type-safe on frontend (TypeScript with JSON Schema)
✅ Dynamic on backend (Python)

AG UI SPEC COMPLIANCE:
✅ Tool name, description, parameters match official protocol
✅ Parameters use JSON Schema format (type, properties, required)
✅ Agents call tools normally (no special syntax)
➕ Extensions: domains (frontend-owned filtering for multi-domain routing)
"""

