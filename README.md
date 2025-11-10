# LangGraph Generative UI + MCP: Multi-Agent System

## NOTE: Check the `deepagents` branch of this repo for an example implementation using [Deep Agents!](https://docs.langchain.com/oss/python/deepagents/overview)

**Multi-agent architecture with client-advertised UI capabilities, interrupt-based HITL, and dynamic tool binding.**

✨ **LangGraph push_ui_message • MCP servers • Human-in-the-loop middleware • Supervisor routing • Version-agnostic clients**

---

## 🎯 Why This Architecture?

This example demonstrates key patterns for building **maintainable, version-agnostic agent UIs** that scale across multiple clients (web, mobile, CLI) while maintaining security and user control.

### Key Benefits

**1. Interrupt-Based Human-in-the-Loop (Not Prompting)**  
Instead of prompting agents to "ask the user for confirmation," we use **LangGraph's middleware interrupts** for sensitive operations (payments, router restarts). This provides:
- ✅ **Guaranteed user approval** before execution (not LLM-dependent)
- ✅ **Structured confirmation flows** with retry/cancel logic
- ✅ **Audit trail** of approved actions
- ✅ **Agnostic UI Confirmation Modal** frontend component that renders interrupts to the user in a nice modal, and is easily customizable
- ❌ Prompting = unreliable, LLM may skip/hallucinate confirmations

**2. Backend MCP Tools for Sensitive Operations**  
Sensitive tools (rent_movie, restart_router) live in **backend MCP servers with interrupt middleware**, not frontend tools. Why?
- ✅ **Security**: Backend enforces approval before execution
- ✅ **Client-agnostic**: One interrupt definition works for web, mobile, CLI
- ✅ **Maintainability**: No duplicate UI/interrupt logic per client
- ❌ Frontend tool interrupts = hard to maintain across client versions

**3. Version-Agnostic Client Support**  
Clients advertise their UI capabilities → Backend adapts automatically:
- ✅ **v1.0 app** (2 tools): Backend uses only those 2 tools
- ✅ **v2.0 app** (5 tools): Backend uses all 5 tools
- ✅ **CLI** (0 UI tools): Backend falls back to text-only responses
- ❌ Hardcoded tools = backend changes required for every client update

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

## 🏗️ How It Works

```
Frontend → Supervisor → Domain Agents → MCP Servers (with HITL interrupts)
    ↓                          ↓
Advertises schemas    Calls push_ui_message()
                               ↓
    ↑                   Custom event stream
    └───── renders UI ─────────┘
```

**Flow:**
1. **Frontend advertises** AG UI tool schemas via config
2. **Backend converts** schemas → LangGraph tools with `push_ui_message()`
3. **Supervisor routes** to domain agents (WiFi/Video) with filtered tools
4. **Agent calls tool** → `push_ui_message(name, props)` → Custom event
5. **Frontend renders** component from structured props

**Example:**  
User: *"play me the matrix"* → Video agent → `rent_movie` (interrupt for payment) → `play_video` (pushes UI) → YouTube player renders

---

## 🔑 Key Patterns

### LangGraph Generative UI

Frontend-advertised tools use `push_ui_message()` for structured UI updates:

```python
from langgraph.graph.ui import push_ui_message

def dynamic_tool_func(**kwargs):
    push_ui_message(tool_name, kwargs)  # Structured props to frontend
    return f"✅ UI updated successfully"
```

```javascript
streamMode: ['messages', 'custom']  // Subscribe to UI events

if (chunk.event === 'custom' && chunk.data.name === 'play_video') {
  setVideoPlayer(chunk.data.props)  // { video_url, title }
}
```

### Human-in-the-Loop Middleware

Backend MCP tools use interrupt middleware for sensitive operations:

```python
from langchain.agents.middleware import HumanInTheLoopMiddleware

agent = create_agent(
    tools=[rent_movie, restart_router],
    middleware=[
        HumanInTheLoopMiddleware(
            interrupt_on={"rent_movie": True, "restart_router": True}
        )
    ]
)
```

Frontend receives interrupt → Shows confirmation UI → Sends approval → Agent resumes

---

## 📁 Project Structure

```
backend/src/
├── supervisor.py              # Routes to domain agents
├── video_agent.py            # Video domain + HITL for payments
├── wifi_agent.py             # WiFi domain + HITL for router restarts
├── utils/
│   ├── tool_converter.py     # AG UI schemas → LangGraph tools
│   ├── agent_helpers.py      # Dynamic tool filtering
│   └── subagent_utils.py     # UI message propagation
└── mcp_servers/
    ├── video_server.py       # rent_movie, search_content (MCP)
    └── wifi_server.py        # restart_router, diagnostics (MCP)

frontend/src/
├── App.jsx                    # Stream handling + custom events
└── toolSchemas.ts             # AG UI tool schemas
```

---

## 🧪 Try It Out

| Command | What Happens |
|---------|--------------|
| "play me the matrix" | Video agent → **INTERRUPT** for rent_movie payment → Approve → play_video → YouTube player renders |
| "restart my router" | WiFi agent → **INTERRUPT** for restart_router → Approve → Router restarts |

**Test version-agnostic behavior:** Remove `play_video` from `ADVERTISED_CLIENT_TOOLS` → Backend adapts automatically!

---

## 💡 Key Takeaways

**Architecture Decisions:**
- ✅ **Interrupts > Prompting** - Use HITL middleware for reliable user approval (not LLM prompts)
- ✅ **Backend MCP for sensitive ops** - Security + client-agnostic + single source of truth
- ✅ **Frontend tools for UI** - Version-agnostic, no backend changes for new UI features
- ✅ **Generative UI pattern** - `push_ui_message()` for structured props (no JSON parsing)

**Perfect for:**  
Multi-version clients • Agent-driven UIs • Secure operations • Dynamic tool binding

---

## 📚 LangChain Documentation

- **[LangGraph Generative UI](https://docs.langchain.com/langsmith/generative-ui-react)** - Official pattern docs
- **[Human-in-the-Loop Middleware](https://docs.langchain.com/oss/python/langchain/middleware)** - Interrupt-based approval
- **[LangGraph Subagents](https://docs.langchain.com/oss/python/langchain/multi-agent#multi-agent)** - Multi-agent patterns
