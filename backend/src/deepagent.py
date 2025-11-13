"""
Supervisor Agent - Main Entry Point

Architecture Overview:
- Supervisor (DeepAgent) routes customer requests to domain-specific subagents (WiFi, Video)
- Each subagent has MCP server tools + dynamically injected client tools
- MCP servers provide domain-specific backend tools
- Client advertises available tools → Dynamic filtering by domain at runtime
- Client tools trigger UI components in frontend via LangGraph's Generative UI
- Interrupts pause execution until user provides input via UI
- DeepAgents provides built-in context quarantine for cleaner supervisor context
- ui_state_middleware extends supervisor state to propagate UI messages from subagents

Key Innovations:
1. CLIENT TOOL ADVERTISEMENT: Frontend sends available tools, backend filters per domain
2. MCP INTEGRATION: Each domain has dedicated MCP server (production pattern!)
3. VERSION-AGNOSTIC: Works with any client version (v1.0, v2.0, v3.0) simultaneously
4. GENERATIVE UI: Client tools push UI messages through dedicated UI channel
5. DEEPAGENTS PATTERN: Built-in context quarantine and official LangChain multi-agent pattern
6. MIDDLEWARE STATE EXTENSION: ui_state_middleware uses @after_model decorator with custom state (official pattern!)

For more details, see:
- utils/ui_middleware.py: Middleware function with @after_model that extends state schema with UI channel
- utils/subagent_utils.py: Dynamic tool filtering and agent context
- mcp_setup.py: MCP server initialization
- wifi_agent.py: WiFi domain specialist (CompiledSubAgent factory)
- video_agent.py: Video domain specialist (CompiledSubAgent factory)
- utils/tool_converter.py: AG UI tool schema converter
"""

from deepagents import create_deep_agent
from src.wifi_agent import create_wifi_subagent
from src.video_agent import create_video_subagent
from src.utils.ui_middleware import ui_state_middleware


# =============================================================================
# SUPERVISOR FACTORY FUNCTION
# =============================================================================

def rebuild_deepagent(runtime_config: dict):
    """
    Create the supervisor deep agent with dynamically configured subagents.
    
    This factory function creates a supervisor using DeepAgents pattern with
    CompiledSubAgent instances. Each subagent has dynamically filtered tools
    based on the runtime_config (client tool schemas).
    
    Args:
        runtime_config: Runtime configuration dict containing client_tool_schemas
                       from the frontend
    
    Returns:
        Compiled DeepAgent supervisor with domain-specific subagents
    
    Benefits:
    - Built-in context quarantine (supervisor doesn't see subagent internals)
    - Official LangChain multi-agent pattern
    - Automatic task() tool for delegation
    - General-purpose subagent available by default
    """
    # Create subagents with filtered tools based on runtime config
    wifi_subagent = create_wifi_subagent(runtime_config)
    video_subagent = create_video_subagent(runtime_config)
    
    return create_deep_agent(
        model="anthropic:claude-haiku-4-5",
        subagents=[wifi_subagent, video_subagent],
        middleware=[ui_state_middleware],
        system_prompt="""You are a helpful customer service assistant. You help customers with WiFi/internet issues and video content.

When a customer has a request, delegate to your specialized subagents using the task() tool:
- Use wifi-specialist for: internet connectivity, WiFi issues, network problems, router issues, slow speeds, connection drops, network diagnostics
- Use video-specialist for: finding shows/movies, streaming issues, watching content, video playback, content recommendations, searching catalog

CRITICAL: When you delegate to a subagent, they will return a complete response. You MUST return that response directly to the customer as if it's your own response. DO NOT add commentary like "The specialist says..." or "I've delegated your request...". Just return the subagent's response naturally.

Examples:
- Customer: "My WiFi is slow" 
  → task(name="wifi-specialist", task="Customer's WiFi is slow")
  → Return the subagent's response directly to the customer

- Customer: "I want to watch The Matrix"
  → task(name="video-specialist", task="Customer wants to watch The Matrix")

- When responding to the customer, don't ever send them a video url, since we have components in the frontend to render dynamic content.

Act as one unified assistant, not as a routing supervisor. The customer should feel like they're talking to one person who can help with everything. NEVER say 
"I'm delegating your request to the specialist" or "I've delegated your request...". Just return the subagent's response naturally.

You don't need to explicity ask the customer for approval when doing sensitive operations because we have a middleware that will interrupt the flow and ask for approval manually."""
    )
