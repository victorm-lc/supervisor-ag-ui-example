#"Everything App" Architecture Example
## AG UI + LangGraph + Domain Subagents + Dynamic Tool Advertisement

This example demonstrates the **"Everything App" architecture pattern** using LangGraph and AG UI. It shows how to build a **version-agnostic**, multi-domain customer service system with supervisor routing, domain-specific subagents, **dynamic client tool advertisement**, and interrupt-based UI interactions.

## 🏗️ What This Example Demonstrates

### 1. **Supervisor + Domain Subagents Pattern**
- **Supervisor agent** routes customer requests to domain specialists
- **WiFi domain subagent** handles internet and connectivity issues  
- **Video domain subagent** handles content search and streaming
- Each subagent has its own tools and expertise

### 2. **AG UI (Agent-Generated UI) Architecture**
- **Agent tool calls trigger frontend UI components**
- **Confirmation dialogs** for user approvals
- **Dynamic UI rendering** based on tool types
- **Interrupt-based interactions** with resume capability

### 3. **Dynamic Client Tool Advertisement** ⭐
- **Frontend advertises** available UI tools in each request
- **Backend dynamically injects** tools per domain at agent creation time
- **Version-agnostic** - works with any client version (v1.0, v2.0, etc.)
- WiFi agent gets `network_status_display`, Video agent gets `play_video`
- No backend changes needed when adding new client tools!

### 4. **Human-in-the-Loop (HITL) Middleware**
- Router restart requires user confirmation
- Custom confirmation dialogs for sensitive operations
- Interrupt propagation from subagents to supervisor

---

## 📋 AG UI Architecture Explained

**AG UI (Agent-Generated UI)** is a pattern where the agent's tool calls directly trigger UI component rendering in the frontend.

### The Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                         AG UI FLOW                               │
└─────────────────────────────────────────────────────────────────┘

1. User: "My router is having issues"
         ↓
2. Supervisor → Routes to WiFi Subagent
         ↓
3. WiFi Subagent: Calls confirmation_dialog tool
         ↓
4. HITL Middleware: Intercepts and pauses execution
         ↓
5. Frontend: Detects tool call → Renders ConfirmationDialog component
         ↓
6. User: Clicks "Yes, restart" in the UI
         ↓
7. Frontend: Sends resume command with user's choice
         ↓
8. WiFi Subagent: Continues execution → Calls restart_router
         ↓
9. User: Sees "Router restart initiated" message
```

### Tool-to-Component Mapping

The frontend maps tool names to React components:

| Tool Name | React Component | Purpose | Type |
|-----------|----------------|---------|------|
| `confirmation_dialog` | `<ConfirmationDialog>` | Generic Yes/No confirmations | Interrupt |
| `restart_router` | `<RouterRestartConfirmation>` | Special router restart UI | Interrupt |
| `network_status_display` | `<NetworkStatusCard>` | WiFi status display | Interrupt |
| `play_video` | `<VideoPlayer>` | YouTube video player | **return_direct** ✨ |
| `error_display` | `<ErrorDisplay>` | Error message display | Interrupt |

**Note:** `play_video` uses `return_direct=True`, meaning it renders immediately to the user rather than returning to the subagent!

### Dynamic Client Tool Advertisement ✨ (Fully Implemented!)

This example demonstrates the **dynamic client tool advertisement pattern** that makes the backend **version-agnostic**.

**How It Works:**

1. **Frontend advertises available tools**
   ```javascript
   const ADVERTISED_CLIENT_TOOLS = [
     'confirmation_dialog',
     'error_display',
     'network_status_display',
     'play_video',  // return_direct=True - renders video immediately!
   ]
   
   // Sent with every request
   client.runs.stream(threadId, 'supervisor', {
     config: { 
       configurable: { advertised_client_tools: ADVERTISED_CLIENT_TOOLS }
     }
   })
   ```

2. **Backend middleware filters per domain**
   ```python
   # DomainToolFilterMiddleware dynamically:
   # 1. Gets advertised tools from config
   # 2. Filters by DOMAIN_TOOL_MAPPING (wifi vs video)
   # 3. Looks up implementations from CLIENT_TOOL_REGISTRY
   # 4. Injects filtered tools into subagent
   ```

3. **Tool Registry provides implementations**
   ```python
   # tool_registry.py
   CLIENT_TOOL_REGISTRY = {
       "confirmation_dialog": confirmation_dialog,
       "error_display": error_display,
       "network_status_display": network_status_display,
       "play_video": play_video,  # return_direct=True!
   }
   
   @tool(return_direct=True)
   def play_video(video_id: str, title: str) -> dict:
       """Play video in YouTube player - renders immediately!"""
       return {
           "type": "video_player",
           "video_url": "https://www.youtube.com/embed/yVinK_ZIrt0?si=r9f67hrOSgwhiIe9",
           "title": title,
           "video_id": video_id,
       }
   ```

**Version Compatibility Example:**

| App Version | Advertised Tools | WiFi Agent Gets | Video Agent Gets |
|-------------|-----------------|-----------------|------------------|
| **v1.0** (old) | `confirmation_dialog`, `error_display` | `wifi_diagnostic`, `restart_router`, `confirmation_dialog`, `error_display` | `search_content`, `confirmation_dialog`, `error_display`, `play_video` |
| **v2.0** (new) | `confirmation_dialog`, `error_display`, `network_status_display`, `play_video` | `wifi_diagnostic`, `restart_router`, `confirmation_dialog`, `error_display`, `network_status_display` | `search_content`, `confirmation_dialog`, `error_display`, `play_video` |

✅ **No backend changes needed!** Old and new app versions work simultaneously.

**Key Benefits:**
- ✅ **Version-agnostic backend** - works with any client version
- ✅ **Platform-specific UI** - mobile vs web can advertise different tools
- ✅ **Graceful degradation** - missing tools handled automatically
- ✅ **Domain isolation** - WiFi agent never sees `video_player_ui`, Video agent never sees `network_status_display`

---

## 🏛️ System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      FRONTEND (React)                            │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  AG UI Component Registry                                │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │   │
│  │  │ Confirmation │  │ Router       │  │ Network      │ │   │
│  │  │ Dialog       │  │ Restart      │  │ Status       │ │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘ │   │
│  └─────────────────────────────────────────────────────────┘   │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                │ LangGraph SDK (HTTP/SSE)
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│             LANGGRAPH DEV SERVER (Port 2024)                     │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                   SUPERVISOR AGENT                       │   │
│  │                                                           │   │
│  │   Tools: [handle_wifi_request, handle_video_request]    │   │
│  │                                                           │   │
│  │   Routes based on: Internet/WiFi → WiFi Agent           │   │
│  │                   Video/Streaming → Video Agent          │   │
│  └──────────────┬─────────────────────┬──────────────────────┘   │
│                 │                     │                           │
│        ┌────────▼─────────┐  ┌───────▼────────┐                │
│        │   WIFI SUBAGENT  │  │  VIDEO SUBAGENT │                │
│        ├──────────────────┤  ├────────────────┤                │
│        │ MCP Tools:       │  │ MCP Tools:      │                │
│        │ • wifi_diagnostic│  │ • search_content│                │
│        │ • restart_router │  │                 │                │
│        │                  │  │                 │                │
│        │ Client Tools     │  │ Client Tools    │                │
│        │ (dynamically     │  │ (dynamically    │                │
│        │  injected):      │  │  injected):     │                │
│        │ • confirmation   │  │ • confirmation  │                │
│        │   _dialog        │  │   _dialog       │                │
│        │ • error_display  │  │ • error_display │                │
│        │ • network_status │  │ • play_video    │                │
│        │   _display       │  │   (return_      │                │
│        │                  │  │    direct=True) │                │
│        │                  │  │                 │                │
│        │ Middleware:      │  │ Middleware:     │                │
│        │ • HITL           │  │ • HITL          │                │
│        └──────────────────┘  └─────────────────┘                │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Key Concepts

### 1. Supervisor Routing

The supervisor analyzes the user's request and routes it to the appropriate domain specialist:

```python
supervisor = create_agent(
    model="anthropic:claude-sonnet-4-5",
    tools=[handle_wifi_request, handle_video_request],
    system_prompt="""Route requests to domain specialists:
    - WiFi issues → handle_wifi_request
    - Video content → handle_video_request"""
)
```

### 2. Domain Subagents with Dynamic Tool Injection

Each domain has its own agent with static MCP tools. Client tools are added at agent creation:

```python
# Define static MCP tools for WiFi domain
wifi_static_tools = [
    wifi_diagnostic,   # MCP tool (backend)
    restart_router,    # MCP tool (backend)
]

# Get all potential client tools for WiFi domain from registry
wifi_client_tools = get_tools_by_names(DOMAIN_TOOL_MAPPING["wifi"])

wifi_agent = create_agent(
    model="anthropic:claude-sonnet-4-5",
    tools=wifi_static_tools + wifi_client_tools,  # MCP tools + ALL client tools
    # Middleware used for logging and HITL
    middleware=[
        DomainToolFilterMiddleware("wifi", wifi_static_tools),
        HumanInTheLoopMiddleware(
            interrupt_on={"restart_router": True}
        )
    ]
)
```

### 3. Tool Wrappers with ToolRuntime for Interrupt Propagation

Subagents are wrapped as tools using **ToolRuntime** to propagate configuration and interrupts:

```python
@tool
def handle_wifi_request(
    request: str, 
    runtime: ToolRuntime  # Injected by LangGraph - provides access to config, state, etc.
) -> str:
    """
    ToolRuntime provides:
    - runtime.config: Contains thread_id and advertised_client_tools
    - runtime.state: Current agent state
    - runtime.context: Runtime context
    """
    # Pass runtime.config to subagent - this is crucial for interrupt propagation!
    result = wifi_agent.invoke(
        {"messages": [HumanMessage(content=request)]},
        config=runtime.config  # Propagates thread_id and enables nested interrupts
    )
    
    # Simply return the message content
    # Interrupts automatically propagate through the shared config
    return result["messages"][-1].content
```

**Key Points:**
- `ToolRuntime` is automatically injected into tools by LangGraph
- Passing `runtime.config` ensures subagent interrupts bubble up to supervisor
- No need for Command pattern - direct string return works with proper config propagation

### 4. Domain Tool Filtering

Tools are filtered per domain at agent creation time:

```python
DOMAIN_TOOL_MAPPING = {
    "wifi": ["confirmation_dialog", "error_display", "network_status_display"],
    "video": ["confirmation_dialog", "error_display", "play_video"],
}

# Tool registry provides implementations
def get_tools_by_names(tool_names: list[str]) -> list:
    return [
        CLIENT_TOOL_REGISTRY[name]
        for name in tool_names
        if name in CLIENT_TOOL_REGISTRY
    ]
```

**Key Points:**
- Each domain specifies which client tools it can use
- WiFi agent never sees `play_video`, Video agent never sees `network_status_display`
- All tools are added to the agent at creation time, not dynamically at runtime

---

## 🛠️ Prerequisites

- **Python >= 3.11**
- **Node.js >= 18**
- **uv** (install: `curl -LsSf https://astral.sh/uv/install.sh | sh`)
- **Anthropic API key** (get from https://console.anthropic.com/)

---

## 🚀 Quick Start

### 1. Clone and Setup Environment

```bash
# Create .env file with your Anthropic API key
echo "ANTHROPIC_API_KEY=your_api_key_here" > .env
# Or manually create .env and add your key

# Create and activate virtual environment
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install Python dependencies
uv sync
```

### 2. Start the Backend (Terminal 1)

```bash
langgraph dev
```

✅ LangGraph server starts at `http://localhost:2024`  
✅ LangGraph Studio UI at `http://localhost:2024`

### 3. Start the Frontend (Terminal 2)

```bash
cd frontend
npm install
npm run dev
```

✅ React app starts at `http://localhost:3000`

### 4. Test It Out!

Open `http://localhost:3000` in your browser and try:

**🔧 Test Interrupt (Router Restart):**
```
"restart my router"
```
→ Click "Yes, restart router" in the confirmation dialog

**🎬 Test Video Player (return_direct):**
```
"show me the matrix"
```
→ YouTube player appears instantly with video!

---

## 🎯 Usage Examples

### Example 1: WiFi Diagnostics

**User:** "My internet is really slow"

**Flow:**
1. Supervisor routes to WiFi subagent
2. WiFi agent calls `wifi_diagnostic("home network")`
3. Results displayed to user
4. No interrupt (auto-approved)

### Example 2: Router Restart (with Confirmation)

**User:** "Can you restart my router?"

**Flow:**
1. Supervisor routes to WiFi subagent
2. WiFi agent calls `confirmation_dialog(message="Are you sure?", options=["Yes", "No"])`
3. **INTERRUPT** - Frontend renders `<ConfirmationDialog>` component
4. User clicks "Yes"
5. Frontend resumes agent with approval
6. WiFi agent calls `restart_router()`
7. Success message displayed

### Example 3: Video Playback with return_direct ⚡

**User:** "Play The Matrix for me"

**Flow:**
1. Supervisor routes to Video subagent
2. Video agent calls `search_content("The Matrix")`
3. Agent calls `play_video(video_id="matrix", title="The Matrix")`
4. **YouTube video player renders immediately** (no interrupt, no pause!)
5. Agent sends "Great! I've started playing The Matrix for you. Enjoy!"

**Key:** `play_video` has `return_direct=True`, so the video player appears instantly without pausing agent execution! This demonstrates the AG UI pattern for immediate UI rendering.

---

## 🧪 Testing in LangGraph Studio

1. Open `http://localhost:2024` in your browser
2. Select the `supervisor` graph
3. Send a message: "My WiFi is slow"
4. Watch the supervisor route to the WiFi subagent
5. See interrupts appear when confirmation is needed
6. Provide approval via the Studio UI

**For interrupts in Studio:**
- Click the "Interrupt" tab when execution pauses
- Enter approval JSON:
  ```json
  {"decisions": [{"type": "approve"}]}
  ```

---

## 📂 Project Structure

```
.
├── agent.py                 # Main agent file with supervisor + subagents
├── tool_registry.py         # Client tool registry (version-agnostic)
├── langgraph.json           # LangGraph config (points to supervisor)
├── pyproject.toml           # Python dependencies
├── .env                     # Your API keys (create from .env.example)
├── README.md                # This file
└── frontend/
    ├── src/
    │   ├── App.jsx          # React app with AG UI component registry
    │   └── App.css          # Styles for all UI components
    ├── package.json
    └── vite.config.js
```

---

## 🔑 Key Files Explained

### `tool_registry.py`

Central registry for all AG UI client tools:

1. **Client Tool Implementations**: All AG UI tools like `confirmation_dialog`, `play_video` (with `return_direct=True`)
2. **CLIENT_TOOL_REGISTRY**: Dict mapping tool names to implementations
3. **get_tools_by_names()**: Helper to look up tools dynamically
4. **Version Compatibility Examples**: Shows how different app versions work

**Featured Tool:** `play_video` with `return_direct=True` demonstrates immediate UI rendering without interrupts!

### `agent.py`

Contains the complete system architecture:

1. **MCP Tools**: Backend tools like `wifi_diagnostic`, `restart_router`, `search_content`
2. **Domain Tool Mapping**: Defines which client tools each domain can use
3. **Domain Subagents**: WiFi and Video specialist agents with dynamically injected client tools
4. **Subagent Tool Wrappers**: Wrap subagents using `ToolRuntime` for interrupt propagation via `runtime.config`
5. **Supervisor Agent**: Routes requests to subagents, returns responses naturally

**Note:** Client tools like `play_video` are now in `tool_registry.py`, not `agent.py`!

### `frontend/src/App.jsx`

The React frontend with AG UI implementation:

1. **AG UI Components** (lines 30-100): `ConfirmationDialog`, `RouterRestartConfirmation`
2. **Tool-to-Component Mapping** (lines 195-225): Maps tool names to components
3. **Interrupt Handling** (lines 250-280): Processes HITL interrupts and renders UI
4. **Resume Logic** (lines 290-350): Sends user input back to agent

### `langgraph.json`

Configures which graph to expose via `langgraph dev`:

```json
{
  "graphs": {
    "supervisor": "./agent.py:supervisor"
  }
}
```

This tells LangGraph to expose the `supervisor` agent from `agent.py` at `http://localhost:2024`.

---

## 🎨 Customization Ideas

### Add a New Domain

1. **Create domain tools** in `agent.py`
2. **Create subagent** with those tools
3. **Add tool wrapper** (like `handle_wifi_request`)
4. **Update supervisor** to include the new wrapper
5. **Add routing logic** to supervisor's system prompt

### Add a New AG UI Component

1. **Define client tool** in `tool_registry.py`:
   ```python
   @tool
   def my_custom_ui(data: dict) -> str:
       """AG UI CLIENT TOOL: My custom component"""
       return "UI rendered"
   ```

2. **Add to CLIENT_TOOL_REGISTRY**:
   ```python
   CLIENT_TOOL_REGISTRY = {
       # ... existing tools ...
       "my_custom_ui": my_custom_ui,
   }
   ```

3. **Add to DOMAIN_TOOL_MAPPING** in `agent.py` for relevant domains:
   ```python
   DOMAIN_TOOL_MAPPING = {
       "wifi": ["confirmation_dialog", "error_display", "my_custom_ui"],
       # ...
   }
   ```

4. **Advertise in frontend** - Add to `ADVERTISED_CLIENT_TOOLS` in `App.jsx`:
   ```javascript
   const ADVERTISED_CLIENT_TOOLS = [
       'confirmation_dialog',
       'error_display',
       'my_custom_ui',  // New tool!
   ]
   ```

5. **Create React component** in `App.jsx`:
   ```jsx
   function MyCustomUI({ data, onConfirm }) {
       return <div>...</div>
   }
   ```

6. **Add to tool-to-component mapping** in `App.jsx`:
   ```javascript
   if (toolName === 'my_custom_ui') {
       setInterruptType('my_custom')
       setInterruptData(toolArgs)
   }
   ```

7. **Render in interrupt panel**:
   ```jsx
   {interrupt && interruptType === 'my_custom' && (
       <MyCustomUI data={interruptData} onConfirm={handleConfirm} />
   )}
   ```

---

## 📚 Learn More

### LangGraph
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [Human-in-the-Loop Middleware](https://langchain-ai.github.io/langgraph/middleware/human-in-the-loop/)
- [LangGraph Dev Server](https://langchain-ai.github.io/langgraph/cli/)

### AG UI
- [AG UI Specification](https://github.com/assistant-ui/ag-ui)
- [LangGraph SDK](https://github.com/langchain-ai/langgraph-sdk)

### Architecture Patterns
- [Deepagents](https://github.com/langchain-ai/deepagents) - Multi-agent patterns and middleware
- [Subagent Patterns](https://langchain-ai.github.io/langgraph/patterns/subagents/)

---

## 🐛 Troubleshooting

### "Failed to connect to LangGraph server"
- ✅ Make sure `langgraph dev` is running in Terminal 1
- ✅ Check that port 2024 isn't in use: `lsof -ti:2024`
- ✅ Verify you're in the virtual environment: `which python` should show `.venv`

### "ANTHROPIC_API_KEY not found"
- ✅ Create `.env` file: `echo "ANTHROPIC_API_KEY=sk-..." > .env`
- ✅ Make sure `.env` is in the project root (same folder as `agent.py`)

### Interrupts not appearing in frontend
- ✅ Check browser console for errors (F12)
- ✅ Verify tool name matches in `App.jsx` mapping
- ✅ Check that HITL middleware has `interrupt_on={"tool_name": True}`

### Video player not showing
- ✅ Make sure you restarted `langgraph dev` after changing `agent.py`
- ✅ Check browser console for "Video player detected" log
- ✅ Verify `play_video` is in `ADVERTISED_CLIENT_TOOLS` in `App.jsx`

### Agent not calling tools
- ✅ Test in LangGraph Studio first: `http://localhost:2024`
- ✅ Use explicit prompts: "restart my router" or "show me the matrix"
- ✅ Check agent logs in the `langgraph dev` terminal

---

## 💡 Tips

1. **Test in Studio first** - Use LangGraph Studio to verify agent logic before testing frontend
2. **Check console logs** - Frontend logs all interrupts and tool calls
3. **Use explicit prompts** - Be specific in user requests to trigger the right tools
4. **Restart dev server** - After `agent.py` changes, restart `langgraph dev`

---

## 📄 License

MIT

---

## 🤝 Contributing

This is an example project. Feel free to fork and adapt for your use case!

For questions about LangGraph, see the [LangGraph Discord](https://discord.gg/langchain).
