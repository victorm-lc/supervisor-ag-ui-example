# Example "Everything App" - Architecture Plan

> **✅ MINIMAL IMPLEMENTATION COMPLETE**  
> A working minimal example of this architecture has been implemented in this repository.  
> See the main project files for a demonstration of:
> - Supervisor + Domain Subagents (WiFi & Video)
> - AG UI with tool-to-component mapping
> - Dynamic client tool filtering via middleware
> - HITL interrupts with confirmation dialogs
>
> Files: `agent.py`, `frontend/src/App.jsx`, `README.md`, `QUICKSTART.md`

---

## Executive Summary

**Goal:** Build a single agent system that can handle any Example customer request across all service domains (WiFi, video content, billing, etc.)

**Current Problem:** 
- Spinning up fresh agents on every request due to dynamic client tool binding
- Architecture is scattered and inefficient
- Client tools tied to app versions, backend needs to be version-agnostic

**Recommended Solution:**
- Supervisor pattern with `create_agent`
- Subagents as tools for domain specialization (WiFi, Video, Billing, etc.)
- Middleware for dynamic tool selection to handle version-specific client tools
- Interrupts for user confirmations and approvals

---

## Current Architecture

```
Client Application
  ↓ (sends: query + SAT token + client tools)
API Request
  ↓
LangGraph Supervisor
  ├─ Validate Client Tools
  ├─ Router Node (Select Agent)
  └─ Worker Coordinator
       ↓
LangChain Agent (NEW per request!)
  ├─ Receive Request
  ├─ Fetch MCP Tools from Registry
  ├─ Combine: Client Tools + MCP Tools
  └─ Execute with LangChain Agent Executor
       ↓
SSE Event Stream
  ↓
Client (via Aggregator)
```

**Problems:**
1. Agent spun up fresh on every request (inefficient)
2. Dynamic tool binding is scattered
3. No clear separation of concerns
4. Difficult to maintain and scale

---

## Proposed Architecture

```
Client Application
  ↓ (sends: query + SAT token + advertised_client_tools)
API Request
  ↓
Supervisor Agent (create_agent)
  ├─ Tools: [wifi_agent, video_agent, billing_agent, ...]
  ├─ Routes to appropriate domain specialist
  └─ Orchestrates high-level workflow
       ↓
Domain Subagent (create_agent with middleware)
  ├─ MCP Tools (domain-specific, static)
  ├─ Client Tools (filtered via middleware, dynamic)
  ├─ Middleware filters relevant client tools per domain
  └─ Executes and returns result to supervisor
       ↓
SSE Event Stream → Client
```

**Key Improvements:**
- Agents are persistent (not recreated per request)
- Clean separation: supervisor routes, subagents execute
- Dynamic tool selection via middleware
- Each subagent only sees relevant tools

---

## Implementation Plan

### Phase 1: Define State Schema

```python
from typing import Annotated, Literal
from langchain.agents import AgentState
from langchain_core.tools import BaseTool

class ExampleAgentState(AgentState):
    """Shared state across all agents"""
    messages: list  # Conversation history
    advertised_client_tools: list[BaseTool]  # Tools from client
    user_id: str
    session_id: str
    app_version: str  # Track client version

# Define context schema for runtime config
from dataclasses import dataclass

@dataclass
class RuntimeContext:
    user_id: str
    session_id: str
    app_version: str
```

### Phase 2: Create Domain Subagents with Middleware

Each subagent has:
1. Domain-specific MCP tools (static)
2. Middleware to filter client tools (dynamic)
3. Custom system prompt for specialization

```python
from langchain.agents import create_agent
from langchain.agents.middleware import wrap_model_call, ModelRequest, ModelResponse
from typing import Callable

# Define which client tools each domain needs
DOMAIN_TOOL_MAPPING = {
    "wifi": ["confirmation_dialog", "error_display", "loading_spinner", "network_status"],
    "video": ["confirmation_dialog", "video_player", "quality_selector", "error_display"],
    "billing": ["confirmation_dialog", "payment_form", "receipt_display", "error_display"],
}

# Middleware to filter client tools per domain
class DomainToolFilterMiddleware:
    def __init__(self, domain: str):
        self.domain = domain
    
    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse]
    ) -> ModelResponse:
        """Filter client tools to only those relevant for this domain"""
        # Get advertised client tools from state
        advertised_tools = request.state.get("advertised_client_tools", [])
        
        # Filter to domain-relevant tools
        allowed_tool_names = DOMAIN_TOOL_MAPPING.get(self.domain, [])
        filtered_client_tools = [
            tool for tool in advertised_tools 
            if tool.name in allowed_tool_names
        ]
        
        # Combine with existing domain-specific MCP tools
        all_tools = request.tools + filtered_client_tools
        request.tools = all_tools
        
        return handler(request)

# Create WiFi subagent
from langchain_mcp import MCPToolkit

# Initialize MCP tools for WiFi domain
wifi_mcp_toolkit = MCPToolkit(server_name="wifi-gateway")
wifi_mcp_tools = wifi_mcp_toolkit.get_tools()

wifi_agent = create_agent(
    model="anthropic:claude-sonnet-4-5",
    tools=wifi_mcp_tools,  # MCP tools registered upfront
    state_schema=ExampleAgentState,
    system_prompt="""You are a WiFi specialist agent for Example. 
    
Your role is to help customers with:
- WiFi connectivity issues
- Network diagnostics
- Router configuration
- Speed tests and optimization

You have access to network diagnostic tools and can display status information
to the customer via the UI. Always confirm actions with the customer using the
confirmation_dialog tool before making changes.""",
    middleware=[DomainToolFilterMiddleware("wifi")],
    context_schema=RuntimeContext,
)

# Create Video subagent
video_mcp_toolkit = MCPToolkit(server_name="video-service")
video_mcp_tools = video_mcp_toolkit.get_tools()

video_agent = create_agent(
    model="anthropic:claude-sonnet-4-5",
    tools=video_mcp_tools,
    state_schema=ExampleAgentState,
    system_prompt="""You are a video content specialist for Example.

Your role is to help customers with:
- Finding and playing video content
- Quality and streaming issues
- Content recommendations
- Parental controls

You can display video content directly in the UI using the video_player tool.
Always check content availability before suggesting titles.""",
    middleware=[DomainToolFilterMiddleware("video")],
    context_schema=RuntimeContext,
)

# Similarly create: billing_agent, support_agent, etc.
```

### Phase 3: Wrap Subagents as Tools

```python
from langchain.tools import tool, ToolRuntime

@tool
def handle_wifi_request(
    request: str,
    runtime: ToolRuntime
) -> str:
    """Handle WiFi and network connectivity requests.
    
    Use this when the customer needs help with:
    - Internet connectivity
    - WiFi setup or troubleshooting
    - Network speed issues
    - Router configuration
    """
    # Pass full state to subagent, including advertised client tools
    result = wifi_agent.invoke(
        {
            "messages": [{"role": "user", "content": request}],
            "advertised_client_tools": runtime.state["advertised_client_tools"],
            "user_id": runtime.state["user_id"],
            "session_id": runtime.state["session_id"],
        },
        context=runtime.context  # Pass runtime context through
    )
    return result["messages"][-1].content

@tool
def handle_video_request(
    request: str,
    runtime: ToolRuntime
) -> str:
    """Handle video content and streaming requests.
    
    Use this when the customer wants to:
    - Watch or find video content
    - Resolve streaming issues
    - Get content recommendations
    - Manage viewing preferences
    """
    result = video_agent.invoke(
        {
            "messages": [{"role": "user", "content": request}],
            "advertised_client_tools": runtime.state["advertised_client_tools"],
            "user_id": runtime.state["user_id"],
            "session_id": runtime.state["session_id"],
        },
        context=runtime.context
    )
    return result["messages"][-1].content

# Create tools for other domains (billing, support, etc.)
```

### Phase 4: Create Supervisor Agent

```python
from langchain_anthropic import ChatAnthropic

model = ChatAnthropic(model="claude-sonnet-4-5")

SUPERVISOR_PROMPT = """You are a helpful Example customer service supervisor.

Your role is to understand customer requests and route them to the appropriate 
specialist agent. You coordinate multiple specialists to resolve complex requests.

Available specialists:
- handle_wifi_request: For internet and WiFi issues
- handle_video_request: For video content and streaming
- handle_billing_request: For billing and account questions
- handle_support_request: For general support

When a request involves multiple domains, call the appropriate specialists in sequence.
Always be friendly and professional with customers."""

supervisor_agent = create_agent(
    model=model,
    tools=[
        handle_wifi_request,
        handle_video_request,
        # handle_billing_request,
        # handle_support_request,
    ],
    state_schema=ExampleAgentState,
    system_prompt=SUPERVISOR_PROMPT,
    context_schema=RuntimeContext,
)
```

### Phase 5: Handle Client Tools with Interrupts

For tools that need user confirmation (e.g., confirmation dialogs):

```python
from langchain_core.tools import tool

# Client tools are created by frontend team but can be modified
@tool(return_direct=True)  # For video player, return directly to UI
def video_player(
    video_id: str,
    title: str,
    thumbnail_url: str
) -> dict:
    """Display a video player in the UI"""
    return {
        "type": "video_player",
        "video_id": video_id,
        "title": title,
        "thumbnail_url": thumbnail_url
    }

# For confirmation dialogs, use interrupts
from langgraph.checkpoint.memory import MemorySaver

# Create checkpointer for interrupts
checkpointer = MemorySaver()

# Tools that should interrupt
INTERRUPT_TOOLS = ["confirmation_dialog", "payment_form", "sensitive_action"]

# Recreate subagents with interrupt configuration
wifi_agent = create_agent(
    model=model,
    tools=wifi_mcp_tools,
    state_schema=ExampleAgentState,
    system_prompt=WIFI_PROMPT,
    middleware=[DomainToolFilterMiddleware("wifi")],
    context_schema=RuntimeContext,
    checkpointer=checkpointer,
    interrupt_before=["tools"],  # Interrupt before tool execution
)

# Then in your tool execution logic, check if tool should interrupt:
from langgraph.types import interrupt

@tool
def confirmation_dialog(
    message: str,
    options: list[str]
) -> str:
    """Display a confirmation dialog to the user"""
    # This will pause execution and wait for user input
    user_choice = interrupt({
        "type": "confirmation",
        "message": message,
        "options": options
    })
    return user_choice
```

### Phase 6: API Request Handler

```python
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

app = FastAPI()

@app.post("/chat")
async def handle_chat(request: Request):
    """Main API endpoint that receives requests from client"""
    data = await request.json()
    
    # Extract from request
    user_message = data["query"]
    advertised_tools = data["client_tools"]  # Tools from client
    user_id = data["user_id"]
    session_id = data["session_id"]
    app_version = data.get("app_version", "1.0.0")
    
    # Convert advertised tools to BaseTool objects
    client_tools = convert_to_base_tools(advertised_tools)
    
    # Prepare input
    agent_input = {
        "messages": [{"role": "user", "content": user_message}],
        "advertised_client_tools": client_tools,
        "user_id": user_id,
        "session_id": session_id,
        "app_version": app_version,
    }
    
    context = RuntimeContext(
        user_id=user_id,
        session_id=session_id,
        app_version=app_version
    )
    
    # Stream response
    async def generate():
        async for chunk in supervisor_agent.astream(
            agent_input,
            context=context,
            config={"configurable": {"thread_id": session_id}}
        ):
            yield format_sse_event(chunk)
    
    return StreamingResponse(generate(), media_type="text/event-stream")

def convert_to_base_tools(advertised_tools: list[dict]) -> list[BaseTool]:
    """Convert client-advertised tools to BaseTool objects"""
    tools = []
    for tool_spec in advertised_tools:
        # Create tool from spec
        # This would need to dynamically create tools based on client spec
        # Implementation depends on your tool format
        pass
    return tools
```

---

## Handling Client Tools by Domain

### Strategy: Explicit Domain Mapping

Since your team controls both frontend and backend, use an explicit mapping:

```python
DOMAIN_TOOL_MAPPING = {
    "wifi": [
        "confirmation_dialog",      # Universal
        "error_display",            # Universal
        "loading_spinner",          # Universal
        "network_status_display",   # WiFi-specific
        "diagnostic_results",       # WiFi-specific
    ],
    "video": [
        "confirmation_dialog",      # Universal
        "error_display",            # Universal
        "video_player",             # Video-specific
        "quality_selector",         # Video-specific
        "playback_controls",        # Video-specific
    ],
    "billing": [
        "confirmation_dialog",      # Universal
        "error_display",            # Universal
        "payment_form",             # Billing-specific
        "receipt_display",          # Billing-specific
        "invoice_viewer",           # Billing-specific
    ],
}
```

**Benefits:**
- Simple and explicit
- Easy to maintain
- Clear ownership
- No over-exposure of tools

**Alternative:** If complexity grows, add metadata to client tools:

```python
# Client advertises tools with metadata
advertised_tools = [
    {
        "name": "confirmation_dialog",
        "domains": ["all"],
        "schema": {...}
    },
    {
        "name": "video_player", 
        "domains": ["video"],
        "schema": {...}
    },
]
```

---

## Key Considerations

### 1. Tool Parameter Configuration

```python
# For tools that need special behavior
@tool(return_direct=True)  # Sends output directly to UI
def video_player(...):
    pass

@tool  # Normal tool, result goes back to agent
def network_diagnostic(...):
    pass
```

### 2. Interrupt Handling

```python
# In your frontend, listen for interrupt events
async function handleChatStream(response) {
    for await (const event of response) {
        if (event.type === 'interrupt') {
            // Show confirmation dialog
            const userChoice = await showConfirmation(event.data);
            // Resume with user's choice
            await resumeAgent(sessionId, userChoice);
        }
    }
}
```

### 3. Version Agnostic Backend

The backend doesn't care about app versions because:
- Client advertises available tools per request
- Middleware filters dynamically
- Old versions with fewer tools still work
- New versions with more tools work immediately

### 4. Tool Discovery

```python
# Optionally, provide an endpoint for clients to register their tools
@app.post("/register-tools")
def register_client_tools(app_version: str, tools: list[dict]):
    """Store tool capabilities for this app version"""
    # Could cache this to improve performance
    pass
```

---

## Integration with Agent Generative UI

```python
# Client tools coupled with AG UI components
client_tools = [
    {
        "name": "confirmation_dialog",
        "ui_component": "ConfirmationModal",
        "interrupt": True,
    },
    {
        "name": "video_player",
        "ui_component": "VideoPlayerComponent",
        "return_direct": True,
    },
    {
        "name": "network_status",
        "ui_component": "NetworkStatusCard",
        "return_direct": False,
    }
]

# When tool is called, AG UI knows which component to render
```

---

## Next Steps

1. **Define all domains** - List all subagent domains needed (WiFi, Video, Billing, Support, etc.)
2. **Map client tools to domains** - Create `DOMAIN_TOOL_MAPPING` with all client tools
3. **Implement one subagent fully** - Start with WiFi as proof of concept
4. **Add supervisor routing** - Get supervisor → subagent flow working
5. **Test with dynamic tools** - Verify tools filter correctly per domain
6. **Add interrupts** - Implement confirmation dialogs with interrupt pattern
7. **Scale to all domains** - Roll out pattern to remaining subagents
8. **Performance testing** - Validate it's faster than current approach
9. **Deploy** - Roll out to production

---

## References

- [Supervisor Pattern](https://docs.langchain.com/oss/python/langchain/supervisor)
- [Dynamic Tool Selection](https://docs.langchain.com/oss/python/langchain/middleware#dynamically-selecting-tools)
- [Subagents as Tools](https://docs.langchain.com/oss/python/langchain/multi-agent#tool-calling)
- [Interrupts (Human-in-the-Loop)](https://docs.langchain.com/oss/python/langgraph/how-tos/human_in_the_loop/breakpoints)
- [create_agent Documentation](https://docs.langchain.com/oss/python/langchain/agents)