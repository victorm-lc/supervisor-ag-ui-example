# AG UI + LangGraph + MCP: Version-Agnostic Multi-Agent System

**Production-ready multi-agent architecture that works with any client version—no backend changes needed when you add UI features.**

✨ **MCP server integration • Dynamic tool filtering • Supervisor routing • Interrupt propagation • Agent-Generated UI**

---

## 🎯 The Problem

Your app has v1.0, v2.0, v3.0 in the wild with different UI capabilities. How do you build an agent backend that works with **all versions** without constant backend updates?

**This example shows the solution.**

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

## 🏗️ Architecture

```
Frontend (v1.0+) → Supervisor Agent
  Advertises:         ↓
  ["play_video",      Routes to domain agents
   "confirmation", 
   ...]           ┌─────────┬─────────┐
                  ↓         ↓         ↓
              WiFi Agent  Video Agent
                  ↓         ↓
            WiFi MCP    Video MCP
            Server      Server
```

**Flow:**
1. Frontend advertises tools: `{configurable: {advertised_client_tools: [...]}}`
2. Supervisor routes to WiFi or Video agent
3. Middleware filters: `advertised ∩ domain_allowed`
4. Agent executes with MCP tools + filtered client tools

---

## 🔑 Core Concepts

### 1. MCP Integration ⭐

Each domain has its own MCP server with backend tools:

```python
# mcp_servers/wifi_server.py
from mcp.server.fastmcp import FastMCP
mcp = FastMCP("WiFi Gateway")

@mcp.tool()
def wifi_diagnostic(network_name: str) -> str:
    return "Diagnostics complete..."

@mcp.tool()
def restart_router(router_id: str = "primary") -> str:
    return "Router restarting..."
```

Agents connect via `langchain-mcp-adapters`:

```python
# agent.py
from langchain_mcp_adapters.client import MultiServerMCPClient

mcp_client = MultiServerMCPClient({
    "wifi": {"transport": "stdio", "command": "python", "args": ["mcp_servers/wifi_server.py"]},
    "video": {"transport": "stdio", "command": "python", "args": ["mcp_servers/video_server.py"]},
})

mcp_tools = await mcp_client.get_tools()
wifi_agent = create_agent(tools=wifi_mcp_tools + client_tools)
```

**Benefits:** Clean separation (MCP = backend, Client = UI), domain isolation, production-ready

### 2. Dynamic Tool Advertisement

Frontend declares capabilities → Backend filters per domain:

```javascript
// App.jsx - Frontend
const ADVERTISED_CLIENT_TOOLS = ['play_video', 'confirmation_dialog']
client.runs.stream(threadId, 'supervisor', {
  config: { configurable: { advertised_client_tools: ADVERTISED_CLIENT_TOOLS }}
})
```

```python
# agent.py - Backend
DOMAIN_TOOL_MAPPING = {
    "wifi": ["confirmation_dialog", "network_status_display"],
    "video": ["confirmation_dialog", "play_video"],
}
# WiFi agent never sees play_video!
```

**Result:** v1.0 (2 tools) and v2.0 (4 tools) work simultaneously, zero backend changes.

### 3. AG UI Pattern

Tool calls → React components:

```python
@tool(return_direct=True)  # Renders immediately, no agent message
def play_video(video_id: str, title: str):
    return {"type": "video_player", "video_url": f"https://youtube.com/embed/{video_id}"}
```

```javascript
{videoPlayer && <VideoPlayer url={videoPlayer.video_url} />}
```

### 4. Interrupt Propagation

Subagent interrupts surface to UI via `runtime.config`:

```python
@tool
async def handle_wifi_request(request: str, runtime: ToolRuntime):
    result = await wifi_agent.ainvoke(
        {"messages": [HumanMessage(content=request)]},
        config=runtime.config  # 🔑 Propagates thread_id + interrupts
    )
    return result["messages"][-1].content
```

---

## 📁 Project Structure

```
├── agent.py                # Supervisor + subagents + MCP client (~440 lines)
├── tool_registry.py        # Client tools (shared FE/BE registry)
├── mcp_servers/
│   ├── wifi_server.py      # WiFi backend tools (MCP server)
│   └── video_server.py     # Video backend tools (MCP server)
└── frontend/
    └── src/App.jsx         # Tool advertisement + AG UI rendering
```

---

## 🧪 Test Cases

| Command | What Happens |
|---------|--------------|
| "restart my router" | Confirmation dialog → Approve → Router restarts |
| "show me the matrix" | YouTube player renders instantly (`return_direct=True`) |

**Simulate v1.0:** Remove `play_video` from `ADVERTISED_CLIENT_TOOLS` → Backend still works!

---

## 🔧 How It Works

```
1. Frontend → sends message + advertised tools
2. Supervisor → routes to WiFi or Video agent
3. Tool wrapper → passes advertised tools via runtime.context
4. Middleware → filters: advertised ∩ domain_allowed
5. Subagent → executes with MCP tools + filtered client tools
6. Frontend → renders AG UI components
```

**Logs you'll see:**
```
✅ Loaded MCP tools: WiFi MCP: ['wifi_diagnostic', 'restart_router']
📤 [VIDEO] Passing advertised tools: ['play_video', 'confirmation_dialog']
📥 [VIDEO] Middleware received: ['play_video', 'confirmation_dialog']
🔧 [VIDEO] Final injected: ['search_content', 'play_video', 'confirmation_dialog']
```

---

## 🎨 Customization

### Add a Client Tool (Frontend UI)

**1. Define:** `tool_registry.py`
```python
@tool
def my_ui(data: dict) -> str:
    """My custom UI component"""
    return "rendered"

CLIENT_TOOL_REGISTRY["my_ui"] = my_ui
```

**2. Map:** `agent.py`
```python
DOMAIN_TOOL_MAPPING = {
    "wifi": ["confirmation_dialog", "my_ui"],  # Add here
}
```

**3. Advertise:** `App.jsx`
```javascript
const ADVERTISED_CLIENT_TOOLS = ['confirmation_dialog', 'my_ui']
```

**4. Render:** `App.jsx`
```javascript
{interrupt && interruptType === 'my_ui' && <MyUI data={interruptData} />}
```

### Add an MCP Tool (Backend Service)

**1. Define:** `mcp_servers/wifi_server.py`
```python
@mcp.tool()
def check_modem(modem_id: str) -> str:
    return "Modem online"
```

**2. Use:** `agent.py`
```python
wifi_mcp_tools = [t for t in mcp_tools if t.name in [
    "wifi_diagnostic", "restart_router", "check_modem"  # ← Add
]]
```

**3. Restart:** `langgraph dev`

---

## 🐛 Troubleshooting

| Issue | Fix |
|-------|-----|
| "Failed to connect" | `langgraph dev` running on port 2024? |
| "ANTHROPIC_API_KEY not found" | Create `.env` file |
| Tools not working | Check logs for `📥 Middleware received:` |
| Video not showing | Restart `langgraph dev` |

**Tip:** Watch logs for 📤📥🔧 emojis showing tool flow.

---

## 📚 Learn More

- **LangGraph:** [Docs](https://langchain-ai.github.io/langgraph/) | [HITL Middleware](https://langchain-ai.github.io/langgraph/middleware/human-in-the-loop/)
- **MCP:** [Protocol](https://modelcontextprotocol.io/) | [LangChain MCP](https://docs.langchain.com/oss/python/langchain/mcp) | [FastMCP](https://github.com/jlowin/fastmcp)
- **AG UI:** [Specification](https://github.com/assistant-ui/ag-ui)
- **Patterns:** [Deepagents](https://github.com/langchain-ai/deepagents) | [Subagents](https://langchain-ai.github.io/langgraph/patterns/subagents/)

---

## 💡 Key Takeaways

✅ **MCP per domain** - Each domain has dedicated MCP server (production pattern!)  
✅ **Version-agnostic** - Works with v1.0, v2.0, v3.0 simultaneously  
✅ **Dynamic filtering** - Agents only get tools client supports  
✅ **Domain isolation** - WiFi agent never sees video tools  
✅ **Interrupt propagation** - Subagent pauses surface automatically  
✅ **AG UI pattern** - Tool calls → React components  

**Perfect for:** Multi-agent systems, customer service apps, multiple client versions

**Better than microservices:** Single deployment, no HTTP, easier debugging, full state management

---

## 📄 License

MIT - Fork it!

Questions? [LangChain Discord](https://discord.gg/langchain)
