# Refactor to Example Architecture Pattern

## Overview

Transform the current email assistant example into a demonstration of the Example "Everything App" architecture with supervisor routing, domain subagents, and dynamic client tool filtering.

## Core Changes to `agent.py`

### 1. Define Mock Domain Tools

Replace current tools (`send_email`, `search_web`, `collect_user_info`) with domain-specific mock tools:

**WiFi Domain Tools:**

```python
@tool
def wifi_diagnostic(network_name: str) -> str:
    """Run network diagnostics for the specified WiFi network"""
    return f"✅ Diagnostics complete for {network_name}: Signal Strong (95%), Speed: 500 Mbps"

@tool
def restart_router() -> str:
    """Restart the customer's WiFi router"""
    return "🔄 Router restart initiated. This will take ~2 minutes."
```

**Video Domain Tools:**

```python
@tool
def search_content(query: str) -> str:
    """Search for video content in the catalog"""
    return f"🎬 Found content for '{query}': Movie 1, Movie 2, TV Show 1"

@tool
def play_video(video_id: str, title: str) -> str:
    """Start playing a video"""
    return f"▶️ Now playing: {title}"
```

### 2. Define Mock Client Tools

Create mock client tools that will be "advertised" by the client:

```python
@tool
def confirmation_dialog(message: str, options: list[str]) -> str:
    """Universal client tool: Display confirmation dialog (requires HITL interrupt)"""
    # This will be intercepted by HITL middleware
    return f"User confirmed: {options[0]}"

@tool
def error_display(error_message: str) -> str:
    """Universal client tool: Display error message"""
    return f"❌ Error displayed: {error_message}"

@tool
def network_status_display(status_data: dict) -> str:
    """WiFi-specific client tool: Display network status card"""
    return f"📊 Network status displayed"

@tool
def video_player_ui(video_data: dict) -> str:
    """Video-specific client tool: Render video player component"""
    return f"🎥 Video player rendered"
```

### 3. Implement DomainToolFilterMiddleware

Create middleware class that filters client tools based on domain:

```python
from langchain.agents.middleware import AgentMiddleware

DOMAIN_TOOL_MAPPING = {
    "wifi": ["confirmation_dialog", "error_display", "network_status_display"],
    "video": ["confirmation_dialog", "error_display", "video_player_ui"],
}

class DomainToolFilterMiddleware(AgentMiddleware):
    def __init__(self, domain: str):
        self.domain = domain
    
    def on_agent_start(self, state, config):
        # Get advertised client tools from state
        advertised_tools = state.get("advertised_client_tools", [])
        
        # Filter to domain-relevant tools
        allowed_names = DOMAIN_TOOL_MAPPING.get(self.domain, [])
        filtered_tools = [t for t in advertised_tools if t.name in allowed_names]
        
        # Add to agent's available tools
        return {"filtered_client_tools": filtered_tools}
```

### 4. Create Domain Subagents

Create WiFi and Video subagents with their domain tools and middleware:

```python
wifi_agent = create_agent(
    model="anthropic:claude-sonnet-4-5",
    tools=[wifi_diagnostic, restart_router],
    middleware=[
        DomainToolFilterMiddleware("wifi"),
        HumanInTheLoopMiddleware(
            interrupt_on={"confirmation_dialog": True, "restart_router": True},
            description_prefix="🚨 Action requires approval"
        )
    ],
    system_prompt="You are a WiFi specialist for Example. Help customers with connectivity issues..."
)

video_agent = create_agent(
    model="anthropic:claude-sonnet-4-5",
    tools=[search_content, play_video],
    middleware=[
        DomainToolFilterMiddleware("video"),
        HumanInTheLoopMiddleware(
            interrupt_on={"confirmation_dialog": True},
            description_prefix="🚨 Action requires approval"
        )
    ],
    system_prompt="You are a video content specialist for Example. Help customers find and watch content..."
)
```

### 5. Wrap Subagents as Tools

Create tool wrappers that invoke subagents:

```python
@tool
def handle_wifi_request(request: str, runtime: ToolRuntime) -> str | Command:
    """Handle WiFi and network connectivity requests"""
    result = wifi_agent.invoke(
        {"messages": [HumanMessage(content=request)]},
        config=runtime.config
    )
    # Return Command to propagate interrupts (deepagents pattern)
    excluded_keys = ("messages", "todos")
    state_update = {k: v for k, v in result.items() if k not in excluded_keys}
    return Command(update={**state_update, "messages": [ToolMessage(...)]})

@tool
def handle_video_request(request: str, runtime: ToolRuntime) -> str | Command:
    """Handle video content and streaming requests"""
    # Same pattern as wifi
```

### 6. Create Supervisor Agent

Build supervisor that routes to domain subagents:

```python
supervisor = create_agent(
    model="anthropic:claude-sonnet-4-5",
    tools=[handle_wifi_request, handle_video_request],
    checkpointer=InMemorySaver(),
    system_prompt="""You are a Example customer service supervisor.
    
Route requests to the appropriate specialist:
- handle_wifi_request: For internet and WiFi issues
- handle_video_request: For video content and streaming

When routing, pass the customer's request to the appropriate handler."""
)
```

## Frontend Changes (`frontend/src/App.jsx`)

### Update Interrupt Detection

Modify to detect `confirmation_dialog` tool by name and show appropriate UI:

```javascript
// Detect confirmation_dialog interrupt
if (actionRequest.name === 'confirmation_dialog') {
  setInterruptType('confirmation')
  // Show confirmation dialog UI
} else if (actionRequest.name === 'restart_router') {
  setInterruptType('router_restart_confirmation')
  // Show router restart confirmation
}
```

### Add Confirmation Dialog Component

Replace `UserInfoForm` with `ConfirmationDialog`:

```jsx
function ConfirmationDialog({ message, options, onConfirm, onCancel }) {
  return (
    <div className="confirmation-card">
      <p>{message}</p>
      <div className="button-group">
        {options.map(opt => (
          <button onClick={() => onConfirm(opt)}>{opt}</button>
        ))}
        <button onClick={onCancel}>Cancel</button>
      </div>
    </div>
  )
}
```

## Documentation Updates

### Update `README.md`

- Replace email assistant description with Example architecture overview
- **Add "AG UI Architecture" section** explaining the pattern:
  - How agent tool calls trigger UI component rendering
  - Advertised tools pattern (client sends available tools)
  - Tool-to-component mapping
  - Interrupt-based user interactions
- **Add AG UI flow diagram**: Agent → Tool Call → Frontend Component → User Action → Resume
- Document supervisor → subagent routing pattern
- Explain dynamic client tool filtering
- Show example requests for WiFi vs Video domains

### Update `QUICKSTART.md`

- Update example queries to test WiFi and Video domains
- Show how to trigger confirmation dialogs
- Document interrupt approval flow

## State Schema (Optional Enhancement)

If needed, define explicit state schema:

```python
from typing import TypedDict

class AgentState(TypedDict):
    messages: list
    advertised_client_tools: list
    filtered_client_tools: list
```

## Key Files to Modify

1. `agent.py` - Complete rewrite with new architecture
2. `frontend/src/App.jsx` - Update interrupt handling for confirmation dialogs
3. `frontend/src/App.css` - Update styles for confirmation UI
4. `README.md` - Update documentation
5. `QUICKSTART.md` - Update usage examples
6. `proposed_solution.md` - Mark as "implemented in minimal example"