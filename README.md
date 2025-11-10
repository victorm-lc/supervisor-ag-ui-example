# LangGraph Generative UI + MCP + DeepAgents

**Production-ready multi-agent architecture using DeepAgents with client-advertised UI capabilities, interrupt-based HITL, and dynamic tool binding.**

✨ **DeepAgents • Context Quarantine • push_ui_message • MCP servers • Human-in-the-loop middleware • Version-agnostic clients**

---

## 🎯 Why This Architecture?

This example demonstrates key patterns for building **maintainable, version-agnostic agent UIs** using LangChain's official DeepAgents pattern. The architecture scales across multiple clients (web, mobile, CLI) while maintaining security, user control, and clean context management through built-in context quarantine.

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

**4. DeepAgents Context Quarantine**  
Using LangChain's official DeepAgents pattern provides:
- ✅ **Clean supervisor context**: Main agent doesn't see subagent internals or intermediate tool calls
- ✅ **Better observability**: Clear delegation boundaries in LangSmith traces
- ✅ **Official pattern**: LangChain's recommended approach for multi-agent systems
- ✅ **Built-in task() tool**: Automatic delegation with natural subagent routing
- ❌ Manual subagent tools = complex state management and context bloat

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

### High-Level Flow

```
Frontend → DeepAgent Supervisor → Domain Agents → MCP Servers (with HITL)
    ↓                                   ↓
Advertises schemas           Calls push_ui_message()
                                        ↓
    ↑                            Custom event stream
    └────── renders UI ──────────────────┘
```

**Request Flow:**
1. **Frontend advertises** AG UI tool schemas via config
2. **Backend filters** schemas by domain → LangGraph tools with `push_ui_message()`
3. **DeepAgent delegates** to domain subagents via `task()` tool
4. **Subagent calls tool** → `push_ui_message(name, props)` → Custom event
5. **UI propagation wrapper** re-pushes messages to supervisor context
6. **Frontend renders** component from structured props

**Example:**  
User: *"play me the matrix"* → DeepAgent → Video subagent → `rent_movie` (interrupt) → `play_video` (UI) → YouTube player

### Dual-Channel Communication (Context Quarantine + UI)

DeepAgents provides context quarantine while our wrapper ensures UI messages reach the frontend:

```
┌─────────────────────────────────────────────────────┐
│ Subagent Execution                                  │
│                                                     │
│ 1. play_video tool calls push_ui_message()         │
│ 2. UI message stored in subagent's state["ui"]     │
│ 3. Subagent returns result (with ui in state)      │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│ UIPropagatingRunnable Wrapper                       │
│                                                     │
│ 1. Intercepts result (sees ui in state)            │
│ 2. Calls push_ui_message() AGAIN in parent context │
│ 3. Sends custom events to streaming API            │
│ 4. Returns result to DeepAgent                     │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│ DeepAgent (Supervisor)                              │
│                                                     │
│ • Receives tool message (with ui visible in JSON)  │
│ • Does NOT merge ui into its own state             │
│ • Context quarantine preserved ✓                   │
└─────────────────────────────────────────────────────┘
                   │
                   ├─────────────┬──────────────────┐
                   ▼             ▼                  ▼
           State Updates    UI Stream          Custom Events
           (messages only)  (isolated)         (push_ui_message)
                                                    │
                                                    ▼
                                              Frontend 🎥
```

**Two Separate Channels:**
- **State channel**: Messages only (context quarantine, no UI clutter)
- **Streaming channel**: UI events via `push_ui_message()` (reaches frontend directly)

This architecture provides both DeepAgents' context isolation AND generative UI capabilities!

---

## 🔑 Key Patterns

### DeepAgents + CompiledSubAgent

Using LangChain's official multi-agent pattern with dynamic tool filtering:

```python
from deepagents import create_deep_agent, CompiledSubAgent
from src.utils.subagent_utils import UIPropagatingRunnable

# Create subagent with filtered tools
def create_video_subagent(runtime_config: dict) -> CompiledSubAgent:
    all_tools = get_filtered_tools("video", video_mcp_tools, runtime_config)
    video_agent = create_video_agent(all_tools)
    
    # Wrap for UI propagation
    wrapped_agent = UIPropagatingRunnable(video_agent)
    
    return CompiledSubAgent(
        name="video-specialist",
        description="Handles video content and streaming",
        runnable=wrapped_agent
    )

# Create DeepAgent supervisor
supervisor = create_deep_agent(
    model="anthropic:claude-haiku-4-5",
    subagents=[wifi_subagent, video_subagent],
    system_prompt="You are a helpful assistant..."
)
```

**Benefits**: Context quarantine, automatic task() delegation, clean separation

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
├── deepagent.py              # DeepAgent supervisor with CompiledSubAgents
├── video_agent.py            # Video domain subagent + HITL for payments
├── wifi_agent.py             # WiFi domain subagent + HITL for router restarts
├── utils/
│   ├── subagent_utils.py     # Tool filtering + UI propagation + AgentContext
│   └── tool_converter.py     # AG UI schemas → LangGraph tools
└── mcp_servers/
    ├── video_server.py       # rent_movie, search_content (MCP)
    └── wifi_server.py        # restart_router, diagnostics (MCP)

frontend/src/
├── App.jsx                    # Stream handling + custom events
└── toolSchemas.ts             # AG UI tool schemas
```

**Key Files:**
- `deepagent.py`: DeepAgent supervisor using `create_deep_agent()` with subagent factories
- `video_agent.py`, `wifi_agent.py`: CompiledSubAgent factories with dynamic tool filtering
- `subagent_utils.py`: All-in-one utilities (tool filtering, UI propagation, context)
- `UIPropagatingRunnable`: Wrapper class that bridges context quarantine and generative UI

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
- ✅ **DeepAgents pattern** - Official LangChain multi-agent approach with context quarantine
- ✅ **Dual-channel communication** - State isolation + UI propagation via custom wrapper
- ✅ **Interrupts > Prompting** - Use HITL middleware for reliable user approval (not LLM prompts)
- ✅ **Backend MCP for sensitive ops** - Security + client-agnostic + single source of truth
- ✅ **Frontend tools for UI** - Version-agnostic, no backend changes for new UI features
- ✅ **Generative UI pattern** - `push_ui_message()` for structured props (no JSON parsing)

**Perfect for:**  
Multi-version clients • Agent-driven UIs • Secure operations • Dynamic tool binding • Context-efficient systems

**Key Innovation:**  
Combining DeepAgents' context quarantine with generative UI through the `UIPropagatingRunnable` wrapper—getting both clean context management AND rich UI updates!

---

## 📚 Documentation

- **[DeepAgents](https://docs.langchain.com/oss/python/deepagents)** - LangChain's official multi-agent pattern
- **[LangGraph Generative UI](https://docs.langchain.com/langsmith/generative-ui-react)** - Official pattern docs
- **[Human-in-the-Loop Middleware](https://docs.langchain.com/oss/python/langchain/middleware)** - Interrupt-based approval
