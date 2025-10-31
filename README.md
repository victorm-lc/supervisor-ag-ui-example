# AG UI + LangGraph + MCP: Version-Agnostic Multi-Agent Architecture

**A production-ready example showing how to build multi-agent systems that work with any client version, using the Model Context Protocol (MCP).**

Demonstrates: Supervisor routing, domain subagents, **MCP server integration**, dynamic tool advertisement, and Agent-Generated UI (AG UI).

---

## 🎯 The Problem This Solves

Your mobile app has different versions in the wild (v1.0, v2.0, v3.0), each with different UI capabilities. **How do you build an agent backend that works with all versions without constantly updating the backend?**

**This example shows you how.**

---

## ⚡ Quick Start

```bash
# 1. Setup
echo "ANTHROPIC_API_KEY=your_key" > .env
uv venv && source .venv/bin/activate
uv sync

# 2. Start backend (Terminal 1)
langgraph dev

# 3. Start frontend (Terminal 2)
cd frontend && npm install && npm run dev

# 4. Test at http://localhost:3000
# Try: "restart my router" or "show me the matrix"
```

**Prerequisites:** Python 3.11+, Node.js 18+, [uv](https://astral.sh/uv), Anthropic API key

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  FRONTEND (v1.0, v2.0, v3.0)                                    │
│  Advertises: "I support these UI tools: [play_video, ...]"     │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  LANGGRAPH SUPERVISOR AGENT                                     │
│  Routes: WiFi issues → WiFi Agent, Video → Video Agent         │
└────────────┬────────────────────────────┬───────────────────────┘
             │                            │
     ┌───────▼─────────┐          ┌───────▼─────────┐
     │  WIFI AGENT     │          │  VIDEO AGENT    │
     │                 │          │                 │
     │  MCP Tools ✨   │          │  MCP Tools ✨   │
     │  (via adapter)  │          │  (via adapter)  │
     │  ↓              │          │  ↓              │
     └────┬────────────┘          └────┬────────────┘
          │                            │
          ▼                            ▼
┌──────────────────┐          ┌──────────────────┐
│ WiFi MCP Server  │          │ Video MCP Server │
│ (stdio)          │          │ (stdio)          │
│                  │          │                  │
│ • wifi_diagnostic│          │ • search_content │
│ • restart_router │          │                  │
└──────────────────┘          └──────────────────┘

     + Client Tools (dynamically filtered per domain):
       WiFi:  confirmation_dialog, network_status_display
       Video: confirmation_dialog, play_video
```

**Key Innovations:** 
1. **MCP Servers:** Each domain has dedicated MCP server (just like Comcast!)
2. **Dynamic Tool Filtering:** Agents only get tools the client actually supports
3. **No Backend Changes:** Add new UI features without touching backend code

---

## 🔑 Core Concepts

### 1. Dynamic Tool Advertisement

**Frontend** (App.jsx):
```javascript
// Frontend declares what it can render
const ADVERTISED_CLIENT_TOOLS = [
  'confirmation_dialog',
  'play_video',        // New in v2.0!
  'network_status_display'
]

// Sends with every request
client.runs.stream(threadId, 'supervisor', {
  config: { 
    configurable: { advertised_client_tools: ADVERTISED_CLIENT_TOOLS }
  }
})
```

**Backend** (agent.py):
```python
# Middleware filters tools per domain
DOMAIN_TOOL_MAPPING = {
    "wifi": ["confirmation_dialog", "network_status_display"],
    "video": ["confirmation_dialog", "play_video"],
}

# WiFi agent never sees play_video, Video agent never sees network_status_display
```

**Result:**
| App Version | Sends | WiFi Gets | Video Gets |
|-------------|-------|-----------|------------|
| v1.0 | 2 tools | 2 tools | 2 tools |
| v2.0 | 4 tools | 3 tools | 3 tools |

✅ **No backend changes needed!**

### 2. Supervisor + Subagents

```python
# Supervisor routes based on intent
supervisor = create_agent(
    tools=[handle_wifi_request, handle_video_request],
    system_prompt="Route WiFi → handle_wifi_request, Video → handle_video_request"
)

# Domain specialists
wifi_agent = create_agent(
    tools=[wifi_diagnostic, restart_router] + client_tools,
    middleware=[DomainToolFilterMiddleware("wifi")]
)
```

### 3. AG UI Pattern

Agent tool calls → React components:

```python
# Backend: Agent calls client tool
@tool(return_direct=True)
def play_video(video_id: str, title: str):
    return {"type": "video_player", "video_url": "..."}
```

```javascript
// Frontend: Maps to React component
{videoPlayer && <VideoPlayer url={videoPlayer.video_url} />}
```

### 4. MCP Integration (Production Pattern!) ⭐

**Each domain has its own MCP server** - exactly like Comcast's architecture!

**MCP Servers** (`mcp_servers/`):
```python
# wifi_server.py - WiFi Gateway MCP
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("WiFi Gateway")

@mcp.tool()
def wifi_diagnostic(network_name: str) -> str:
    """Run diagnostics on WiFi network"""
    return diagnostic_results

@mcp.tool()
def restart_router(router_id: str = "primary") -> str:
    """Restart customer's router"""
    return "Router restarting..."
```

**Agent connects via MCP adapters** (`agent.py`):
```python
from langchain_mcp_adapters.client import MultiServerMCPClient

mcp_client = MultiServerMCPClient({
    "wifi": {
        "transport": "stdio",
        "command": "python",
        "args": ["mcp_servers/wifi_server.py"],
    },
    "video": {
        "transport": "stdio",
        "command": "python",
        "args": ["mcp_servers/video_server.py"],
    }
})

# Load tools from MCP servers
mcp_tools = await mcp_client.get_tools()
wifi_mcp_tools = [t for t in mcp_tools if t.name in ["wifi_diagnostic", "restart_router"]]
video_mcp_tools = [t for t in mcp_tools if t.name in ["search_content"]]

# Use in agents
wifi_agent = create_agent(tools=wifi_mcp_tools + client_tools)
```

**Benefits:**
- ✅ **Clean separation:** MCP tools (backend services) vs Client tools (frontend UI)
- ✅ **Domain isolation:** WiFi team owns `wifi_server.py`, Video team owns `video_server.py`
- ✅ **Production-ready:** MCP servers can be deployed independently
- ✅ **Just like Comcast:** Each domain has dedicated MCP server (their exact pattern!)

### 5. Interrupt Propagation

Subagent interrupts automatically surface to the UI:

```python
@tool
def handle_wifi_request(request: str, runtime: ToolRuntime):
    # runtime.config propagates thread_id + interrupts
    result = wifi_agent.invoke(
        {"messages": [HumanMessage(content=request)]},
        config=runtime.config  # 🔑 Key for nested interrupts
    )
    return result["messages"][-1].content
```

---

## 📁 Project Structure

```
├── agent.py                    # Supervisor + subagents + MCP client
├── tool_registry.py            # Client tools (version-agnostic registry)
├── langgraph.json              # Config: points to supervisor
├── mcp_servers/                # 🆕 MCP servers (one per domain)
│   ├── wifi_server.py          #    WiFi Gateway MCP
│   └── video_server.py         #    Video Gateway MCP
└── frontend/
    ├── src/App.jsx             # React UI + tool advertisement
    └── src/App.css             # Component styles
```

**Key Files:**
- `agent.py`: Supervisor, subagents, MCP client, middleware (~400 lines)
- `mcp_servers/wifi_server.py`: WiFi backend tools (diagnostics, restart)
- `mcp_servers/video_server.py`: Video backend tools (search content)
- `tool_registry.py`: UI tool definitions shared by FE/BE teams
- `frontend/src/App.jsx`: Advertises tools + renders AG UI components

---

## 🧪 Try It

### Test 1: Interrupt Flow
```
You: "restart my router"
→ Confirmation dialog appears
→ Click "Yes"
→ Router restarts
```

### Test 2: return_direct Video Player
```
You: "show me the matrix"
→ YouTube player appears instantly
→ No interrupt, just renders!
```

### Test 3: Version Compatibility

**Simulate v1.0** (remove a tool from `ADVERTISED_CLIENT_TOOLS`):
```javascript
const ADVERTISED_CLIENT_TOOLS = [
  'confirmation_dialog',  // v1.0 only has this
]
```
✅ Backend still works! Just filters to what's available.

---

## 🔧 How It Works

### Request Flow

1. **Frontend** sends message + advertised tools
2. **Supervisor** analyzes intent → routes to domain agent
3. **Tool wrapper** extracts advertised tools from `runtime.config`
4. **MCP client** loads tools from domain MCP servers (WiFi, Video)
5. **Middleware** filters client tools: `advertised ∩ domain_allowed`
6. **Subagent** executes with MCP tools + filtered client tools
7. **Frontend** renders UI components for tool calls

### Logs You'll See

```
✅ Loaded MCP tools from servers:
   WiFi MCP: ['wifi_diagnostic', 'restart_router']
   Video MCP: ['search_content']
📤 [VIDEO] Passing advertised tools: ['play_video', 'confirmation_dialog', ...]
📥 [VIDEO] Middleware received: ['play_video', 'confirmation_dialog', ...]
🔍 [VIDEO] Allowed for domain: ['play_video', 'confirmation_dialog']
🔧 [VIDEO] Final injected: ['search_content', 'play_video', 'confirmation_dialog']
```

---

## 🎨 Customization

### Add a New Client Tool

**1. Define tool** (`tool_registry.py`):
```python
@tool
def my_new_ui(data: dict) -> str:
    """My custom UI component"""
    return "rendered"

CLIENT_TOOL_REGISTRY["my_new_ui"] = my_new_ui
```

**2. Map to domain** (`agent.py`):
```python
DOMAIN_TOOL_MAPPING = {
    "wifi": ["confirmation_dialog", "my_new_ui"],  # Add here
}
```

**3. Advertise** (`App.jsx`):
```javascript
const ADVERTISED_CLIENT_TOOLS = [
    'confirmation_dialog',
    'my_new_ui',  // ← Just add this!
]
```

**4. Render** (`App.jsx`):
```javascript
{interrupt && interruptType === 'my_new' && (
    <MyNewUI data={interruptData} />
)}
```

**No backend restart needed** - middleware automatically picks it up!

### Add a New MCP Tool

**1. Add tool to MCP server** (`mcp_servers/wifi_server.py`):
```python
@mcp.tool()
def check_modem_status(modem_id: str) -> str:
    """Check status of customer's modem"""
    return "Modem is online and functioning normally"
```

**2. Update agent to use new tool** (`agent.py`):
```python
# Tools automatically loaded from MCP server!
# Just restart langgraph dev to pick up changes
wifi_mcp_tools = [t for t in mcp_tools if t.name in [
    "wifi_diagnostic", 
    "restart_router",
    "check_modem_status"  # ← New tool!
]]
```

**3. Restart backend:**
```bash
# In Terminal 1
langgraph dev  # Restart to reload MCP servers
```

✅ **MCP servers can be updated independently** - just restart `langgraph dev`!

---

## 🐛 Troubleshooting

| Issue | Fix |
|-------|-----|
| "Failed to connect" | Check `langgraph dev` is running on port 2024 |
| "ANTHROPIC_API_KEY not found" | Create `.env` file in project root |
| Tools not working | Check logs for `📥 Middleware received:` to see what tools are injected |
| Video player not showing | Restart `langgraph dev` after changing `agent.py` |

**Debug tip:** Watch terminal logs for emoji markers (📤 📥 🔧) showing tool flow.

---

## 📚 Learn More

- **LangGraph:** [Docs](https://langchain-ai.github.io/langgraph/) | [HITL Middleware](https://langchain-ai.github.io/langgraph/middleware/human-in-the-loop/)
- **MCP:** [Protocol Docs](https://modelcontextprotocol.io/) | [LangChain MCP Docs](https://docs.langchain.com/oss/python/langchain/mcp) | [FastMCP](https://github.com/jlowin/fastmcp)
- **AG UI:** [Specification](https://github.com/assistant-ui/ag-ui)
- **Patterns:** [Deepagents](https://github.com/langchain-ai/deepagents) | [Subagents](https://langchain-ai.github.io/langgraph/patterns/subagents/)

---

## 💡 Key Takeaways

✅ **MCP integration** - Each domain has dedicated MCP server (Comcast pattern!)  
✅ **Version-agnostic backend** - Works with v1.0 and v2.0 simultaneously  
✅ **Dynamic tool injection** - Agents only get tools client supports  
✅ **Domain isolation** - WiFi agent never sees video tools  
✅ **Interrupt propagation** - Subagent pauses surface to UI automatically  
✅ **AG UI pattern** - Tool calls → React components  
✅ **Production-ready** - Clean separation: MCP tools (backend) + Client tools (frontend)

**Perfect for:** Multi-agent systems, customer service apps, platforms with multiple client versions

**Better than microservices:** Single deployment, no HTTP overhead, easier debugging, full state management

---

## 📄 License

MIT - Fork and adapt for your use case!

Questions? Join [LangChain Discord](https://discord.gg/langchain)
