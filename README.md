# LangGraph Generative UI + MCP: Multi-Agent System

**Multi-agent architecture with frontend-advertised UI capabilities using LangGraph's official Generative UI pattern.**

✨ **LangGraph push_ui_message • MCP servers • Dynamic tool binding • Supervisor routing • Client-advertised tools**

---

## 🎯 The Pattern

Clients advertise their UI capabilities at runtime → Backend dynamically converts them to tools → Agents call them → UI renders via `push_ui_message()` custom events.

**This example shows how to build version-agnostic agent UIs using LangGraph's Generative UI + AG UI tool schemas.**

---

## ⚡ Quick Start

```bash
# 1. Setup backend
cd backend
cp .env.example .env  # Then add your real API key
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
Frontend → Supervisor Agent → Domain Agents (WiFi/Video) → MCP Servers
    ↓                                    ↓
Advertises UI schemas          Calls push_ui_message()
["play_video", ...]                     ↓
    ↑                          UI stream (custom events)
    └──────────── renders VideoPlayer ──────────┘
```

**Flow:**
1. Frontend advertises AG UI tool schemas via `client_tool_schemas` config
2. Backend converts schemas → LangGraph tools (via `tool_converter.py`)
3. Supervisor routes to domain agents with dynamically bound tools
4. Agent calls tool → `push_ui_message(name, props)` → Custom event stream
5. Frontend receives `{event: 'custom', data: {name, props}}` → Renders UI

---

## 🔑 Core Concepts

### 1. LangGraph Generative UI ⭐

Frontend-advertised tools use `push_ui_message()` to send structured UI data:

```python
# backend/src/tool_converter.py
from langgraph.graph.ui import push_ui_message

def dynamic_tool_func(**kwargs) -> str:
    """Auto-generated from client AG UI schema"""
    push_ui_message(tool_name, kwargs)  # Sends to custom event stream
    return f"✅ {tool_description} - UI updated successfully"
```

```javascript
// frontend/src/App.jsx
streamMode: ['messages', 'custom']  // Messages + UI events

if (chunk.event === 'custom') {
  if (chunk.data.name === 'play_video') {
    setVideoPlayer(chunk.data.props)  // { video_url, title }
  }
}
```

**Key:** UI messages propagate from subagents → supervisor via explicit `push_ui_message()` calls.

### 2. Client Tool Advertisement

Frontend sends AG UI schemas → Backend converts to LangGraph tools:

```javascript
// frontend/src/toolSchemas.ts
export const CLIENT_TOOL_SCHEMAS = [
  {
    name: "play_video",
    description: "Play a video in the frontend YouTube player",
    parameters: {
      type: "object",
      properties: {
        video_url: { type: "string" },
        title: { type: "string" }
      }
    }
  }
]
```

```python
# Supervisor receives and converts at runtime
client_schemas = config.get("configurable", {}).get("client_tool_schemas", [])
client_tools = convert_schemas_to_tools(client_schemas)
```

**Result:** v1.0 (2 tools) and v2.0 (5 tools) work with the same backend.

### 3. MCP Backend Tools

Domain logic stays in MCP servers (WiFi diagnostics, video rentals):

```python
# backend/src/mcp_servers/video_server.py
from mcp.server.fastmcp import FastMCP
mcp = FastMCP("Video Service")

@mcp.tool()
def rent_movie(title: str, rental_price: float) -> str:
    rental_id = f"R-{random.randint(10000, 99999)}"
    return f"✅ '{title}' rented! Rental ID: {rental_id}"
```

**Separation:** MCP = backend services, Client tools = UI rendering

---

## 📁 Project Structure

```
backend/src/
├── supervisor.py        # Supervisor agent (routes to domains)
├── video_agent.py       # Video domain agent + UI propagation
├── wifi_agent.py        # WiFi domain agent
├── tool_converter.py    # AG UI schemas → LangGraph tools + push_ui_message
├── mcp_setup.py         # MCP client initialization
└── mcp_servers/
    ├── video_server.py  # Video MCP server (rent_movie, search_content)
    └── wifi_server.py   # WiFi MCP server (restart_router, etc)

frontend/src/
├── App.jsx              # Streaming + custom event handling
└── toolSchemas.ts       # AG UI tool schemas (advertised to backend)
```

---

## 🧪 Test Cases

| Command | What Happens |
|---------|--------------|
| "play me the matrix" | Video agent → rent_movie → play_video → `push_ui_message()` → YouTube player |
| "restart my router" | WiFi agent → confirmation_dialog → Approve → restart_router |

**Simulate v1.0:** Remove `play_video` from `ADVERTISED_CLIENT_TOOLS` → Backend adapts automatically!

---

## 🔧 How It Works

```
1. Frontend sends AG UI schemas via client_tool_schemas config
2. tool_converter.py converts schemas → LangGraph tools
3. Supervisor routes request to domain agent (WiFi/Video)
4. Agent calls tool → push_ui_message(name, props)
5. Subagent UI messages propagate to supervisor via explicit re-push
6. Frontend receives custom event → Renders component
```

**Key logs:**
```
🎬 [PLAY_VIDEO] Tool called with kwargs: {'video_url': '...', 'title': 'The Matrix'}
✅ [PLAY_VIDEO] UI message pushed to frontend
🎨 [VIDEO] Propagating 1 UI messages to supervisor
```

---

## 🎨 Add New UI Components

### 1. Define Schema (Frontend)

```typescript
// frontend/src/toolSchemas.ts
{
  name: "show_chart",
  description: "Display a chart component",
  parameters: {
    type: "object",
    properties: {
      data: { type: "array" },
      chartType: { type: "string" }
    }
  }
}
```

### 2. Advertise It

```javascript
// frontend/src/App.jsx
const ADVERTISED_CLIENT_TOOLS = ['play_video', 'show_chart']
```

### 3. Render Custom Event

```javascript
if (chunk.event === 'custom' && chunk.data.name === 'show_chart') {
  setChartData(chunk.data.props)
}
```

**That's it!** The backend auto-converts the schema → tool with `push_ui_message()`.

---

## 🐛 Troubleshooting

| Issue | Fix |
|-------|-----|
| UI not rendering | Check console for `🎨 Custom event received:` |
| "Failed to connect" | `langgraph dev` running on port 2024? |
| "Thread not found (404)" | Click "Clear Chat" (server restarted) |
| Video not playing | Check backend logs for `🎬 [PLAY_VIDEO] Tool called` |
| Import errors | Run `cd backend && uv sync` |

**Debug logs:** Look for 🎬 tool calls, 🎨 UI propagation, ✅ push_ui_message success.

---

## 📚 Learn More

- **LangGraph Generative UI:** [Docs](https://docs.langchain.com/langsmith/generative-ui-react.md)
- **MCP:** [Protocol](https://modelcontextprotocol.io/) | [FastMCP](https://github.com/jlowin/fastmcp)
- **AG UI:** [Specification](https://github.com/assistant-ui/ag-ui)
- **LangGraph:** [Subagents](https://langchain-ai.github.io/langgraph/patterns/subagents/) | [Custom Events](https://langchain-ai.github.io/langgraph/)

---

## 💡 Key Takeaways

✅ **Official LangGraph pattern** - Uses `push_ui_message()` for structured UI data  
✅ **Version-agnostic** - Clients advertise schemas, backend adapts automatically  
✅ **Clean separation** - MCP = backend logic, Client tools = UI rendering  
✅ **Subagent UI propagation** - UI messages bubble up from nested agents  
✅ **AG UI compliant** - Works with existing AG UI tool schemas  
✅ **Streamable** - `streamMode: ['messages', 'custom']` for real-time UI updates  

**Perfect for:** Multi-version clients, agent-driven UIs, dynamic tool binding

**Key insight:** Frontend owns UI schemas → Backend converts them to tools at runtime → No backend changes for new UI features!
