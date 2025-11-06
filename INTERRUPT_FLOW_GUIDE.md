# Interrupt Flow: Backend → Frontend Component Rendering

**A complete technical walkthrough of how interrupts surface and trigger React components**

---

## 🎬 The Complete Flow

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Backend: Agent calls tool that requires approval         │
│    → Middleware intercepts → Creates interrupt              │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. Stream: Interrupt sent via Server-Sent Events (SSE)     │
│    → LangGraph SDK streams chunks to frontend              │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. Frontend: Detects __interrupt__ in stream               │
│    → Extracts tool name & args → Maps to component         │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. React: Renders component based on interruptType         │
│    → User interacts → Sends decision back to backend       │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. Backend: Receives decision → Resumes execution          │
│    → Tool executes with selected_option → Returns result   │
└─────────────────────────────────────────────────────────────┘
```

---

## 📍 Step 1: Backend Creates Interrupt

### Code: `backend/src/video_agent.py`

```python
from langchain.agents.middleware import HumanInTheLoopMiddleware

def create_video_agent(tools: list):
    return create_agent(
        model="anthropic:claude-haiku-4-5",
        tools=tools,
        middleware=[
            HumanInTheLoopMiddleware(
                interrupt_on={
                    "rent_movie": True,  # ← This tool triggers an interrupt
                },
                description_prefix="🚨 Payment confirmation required",
            ),
        ],
    )
```

### What Happens:

1. Agent decides to call `rent_movie(title="The Matrix", video_url="...", rental_price=3.99)`
2. **Before executing the tool**, middleware intercepts the call
3. Middleware creates an **interrupt object**:

```python
{
  "id": "some-uuid",
  "value": {
    "action_requests": [
      {
        "name": "rent_movie",           # ← Tool name
        "args": {                        # ← Tool arguments
          "title": "The Matrix",
          "video_url": "https://...",
          "rental_price": 3.99
        }
      }
    ]
  }
}
```

4. Execution **pauses** (LangGraph saves state to checkpointer)
5. Interrupt is **queued to be sent** to frontend

---

## 📡 Step 2: Stream to Frontend

### Code: `frontend/src/App.jsx`

```javascript
// Frontend initiates stream
const stream = client.runs.stream(threadId, 'supervisor', {
  input: { messages: [{ role: 'user', content: 'play me the matrix' }] },
  streamMode: 'messages',  // ← Stream message events
})

// Consume stream chunks
for await (const chunk of stream) {
  console.log('Stream chunk:', chunk)
}
```

### Stream Events (What You See):

The LangGraph server sends **Server-Sent Events** (SSE) over HTTP:

```javascript
// Event 1: Supervisor thinking
{
  event: 'messages/partial',
  data: [{
    type: 'ai',
    content: 'Let me search for The Matrix...'
  }]
}

// Event 2: Subagent (video_agent) called
{
  event: 'messages/partial',
  data: [{
    type: 'tool',
    name: 'handle_video_request',
    content: 'Searching catalog...'
  }]
}

// Event 3: ⚠️ INTERRUPT DETECTED ⚠️
{
  event: 'messages/complete',
  data: {
    __interrupt__: [
      {
        id: 'some-uuid',
        value: {
          action_requests: [
            {
              name: 'rent_movie',
              args: {
                title: 'The Matrix',
                video_url: 'https://youtube.com/embed/abc123',
                rental_price: 3.99
              }
            }
          ]
        }
      }
    ]
  }
}
```

**Key:** The `__interrupt__` field is a special marker that LangGraph adds to the stream when execution pauses.

---

## 🔍 Step 3: Frontend Detects Interrupt

### Code: `frontend/src/App.jsx` (lines 273-368)

```javascript
// Loop through stream chunks
for await (const chunk of stream) {
  console.log('Stream chunk:', chunk.event, chunk.data)
  
  // 1. Handle normal messages
  if (chunk.event === 'messages/partial' || chunk.event === 'messages/complete') {
    const message = chunk.data?.[0]
    const content = message?.content
    
    if (content && typeof content === 'string') {
      assistantMessage = content  // Display in chat
    }
  }

  // 2. 🔍 CHECK FOR INTERRUPT
  if (chunk.data?.__interrupt__) {
    currentInterrupt = chunk.data.__interrupt__[0]  // ← Save it!
    console.log('Interrupt detected:', currentInterrupt)
  }
}

// After stream completes, process interrupt
if (currentInterrupt) {
  setInterrupt(currentInterrupt)  // Save to React state
  
  // Extract tool name and arguments
  const actionRequest = currentInterrupt.value?.action_requests[0]
  const toolName = actionRequest.name        // 'rent_movie'
  const toolArgs = actionRequest.args        // {title, video_url, rental_price}
  
  console.log('Tool requiring approval:', toolName, toolArgs)
  
  // 👇 Map to React component (next step)
}
```

**What's Happening:**

1. Stream chunks arrive as JavaScript objects
2. Frontend checks each chunk for `chunk.data.__interrupt__`
3. If present, extract `action_requests[0]` to get tool name & args
4. Store interrupt in React state for rendering

---

## 🗺️ Step 4: Map Interrupt to Component

### Code: `frontend/src/App.jsx` (lines 327-368)

This is where you **decide which React component to render** based on the tool name:

```javascript
// Extract tool info from interrupt
const actionRequest = currentInterrupt.value?.action_requests[0]
const toolName = actionRequest.name     // e.g., 'rent_movie'
const toolArgs = actionRequest.args     // e.g., {title: "...", ...}

// 🗺️ MAPPING LOGIC: Tool name → Component type
if (toolName === 'restart_router') {
  // Show generic confirmation dialog
  setInterruptType('confirmation')
  setInterruptData({
    message: 'Are you sure you want to restart your router?',
    options: ['Yes, Restart Router', 'Cancel'],
    details: '<strong>⚠️ This will restart your router</strong>...'
  })
}
else if (toolName === 'rent_movie') {
  // Show custom rental payment component
  setInterruptType('rental_payment')  // ← This determines which component renders
  setInterruptData({
    title: toolArgs.title,              // ← Props from backend
    video_url: toolArgs.video_url,      // ← Props from backend
    rental_price: toolArgs.rental_price,// ← Props from backend
    rental_period: '48 hours'
  })
}
else {
  // Fallback: generic approval UI
  setInterruptType('tool_approval')
  setInterruptData(toolArgs)
}
```

**The Mapping Strategy:**

```javascript
Tool Name (Backend)    →    interruptType (Frontend)    →    Component
───────────────────────────────────────────────────────────────────────
'restart_router'       →    'confirmation'              →    <ConfirmationDialog>
'rent_movie'           →    'rental_payment'            →    <RentalPayment>
'execute_sql'          →    'tool_approval'             →    <GenericApproval>
(any unknown tool)     →    'tool_approval'             →    <GenericApproval>
```

---

## 🎨 Step 5: Render Component

### Code: `frontend/src/App.jsx` (lines 816-837)

React conditionally renders based on `interruptType`:

```javascript
// In the JSX return statement:

{/* Mapping: interruptType === 'confirmation' */}
{interrupt && interruptType === 'confirmation' && (
  <div className="interrupt-panel">
    <ConfirmationDialog
      message={interruptData?.message}
      options={interruptData?.options}
      details={interruptData?.details}
      onConfirm={handleConfirmationSelect}  // User clicks option
      onCancel={handleCancel}               // User cancels
    />
  </div>
)}

{/* Mapping: interruptType === 'rental_payment' */}
{interrupt && interruptType === 'rental_payment' && (
  <div className="interrupt-panel">
    <RentalPayment
      data={interruptData}                  // All props from backend
      onConfirm={handleConfirmationSelect}  // User clicks "Rent Now"
      onCancel={handleCancel}               // User cancels
    />
  </div>
)}

{/* Mapping: interruptType === 'tool_approval' */}
{interrupt && interruptType === 'tool_approval' && (
  <div className="interrupt-panel">
    <div className="approval-card">
      <p>⚠️ This action requires your approval</p>
      <button onClick={handleApprove}>✅ Approve</button>
      <button onClick={handleCancel}>❌ Reject</button>
    </div>
  </div>
)}
```

### Visual Result:

When `rent_movie` interrupt is detected, user sees:

```
┌───────────────────────────────────────┐
│  🎬 Rent Movie                        │
│                                       │
│  The Matrix                           │
│                                       │
│  Rental Period: 48 hours              │
│  Price: $3.99                         │
│                                       │
│  💡 You'll have access for 48 hours  │
│                                       │
│  [ Rent Now - $3.99 ]  [ Cancel ]    │
└───────────────────────────────────────┘
```

---

## 🔄 Step 6: User Decision → Resume Backend

### Code: `frontend/src/App.jsx` (lines 391-430)

When user clicks a button (e.g., "Rent Now"):

```javascript
const handleConfirmationSelect = async (selectedOption) => {
  if (!interrupt) return

  console.log('User selected:', selectedOption)  // "Rent Now"

  // Extract the original interrupt data
  const actionRequest = interrupt.value?.action_requests?.[0]
  
  // Create resume command
  const stream = client.runs.stream(threadId, 'supervisor', {
    command: {
      resume: {
        decisions: [{ 
          type: 'approve',  // User approved the action
          editedAction: {
            name: actionRequest?.name,  // 'rent_movie'
            args: {
              ...actionRequest?.args,   // Original args
              selected_option: selectedOption  // ✅ USER'S CHOICE!
            }
          }
        }],
      },
    },
    config: {
      configurable: {
        client_tool_schemas: filteredSchemas
      }
    },
    streamMode: 'messages',
  })

  // Process response (same as step 3)
  for await (const chunk of stream) {
    // Agent continues execution...
  }
}
```

### What Gets Sent to Backend:

```javascript
{
  command: {
    resume: {
      decisions: [
        {
          type: 'approve',
          editedAction: {
            name: 'rent_movie',
            args: {
              title: 'The Matrix',
              video_url: 'https://...',
              rental_price: 3.99,
              selected_option: 'Rent Now'  // ← USER'S DECISION
            }
          }
        }
      ]
    }
  }
}
```

---

## ⚙️ Step 7: Backend Resumes Execution

### Code: `backend/src/mcp_servers/video_server.py`

The MCP tool now receives the `selected_option`:

```python
@mcp.tool()
def rent_movie(
    title: str,
    video_url: str,
    rental_price: float = 3.99,
    selected_option: str = None  # ← Filled by middleware after approval
) -> str:
    """Rent a movie with payment confirmation."""
    
    # Check if user cancelled
    if selected_option and "cancel" in selected_option.lower():
        return "❌ Rental cancelled by user"
    
    # User approved! Process rental
    rental_id = f"R-{hash(title) % 100000:05d}"
    return f"✅ '{title}' rented successfully! Rental ID: {rental_id}"
```

**Flow:**

1. Middleware receives resume command with `selected_option: "Rent Now"`
2. Middleware **resumes execution** from saved checkpoint
3. Tool is **now executed** with updated args (including `selected_option`)
4. Tool returns result: `"✅ 'The Matrix' rented successfully! Rental ID: R-12345"`
5. Result streams back to frontend and displays in chat

---

## 📊 Complete Data Flow Diagram

```
BACKEND (video_agent.py)
  ↓
  Agent calls rent_movie(title="The Matrix", rental_price=3.99)
  ↓
  Middleware intercepts: "This tool needs approval!"
  ↓
  Creates interrupt object:
  {
    value: {
      action_requests: [{
        name: "rent_movie",
        args: {title: "The Matrix", rental_price: 3.99}
      }]
    }
  }
  ↓
  Execution PAUSES (state saved)
  ↓
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STREAM (Server-Sent Events)
  ↓
  chunk = {
    event: 'messages/complete',
    data: { __interrupt__: [...] }  ← INTERRUPT MARKER
  }
  ↓
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FRONTEND (App.jsx)
  ↓
  for await (const chunk of stream) {
    if (chunk.data?.__interrupt__) {
      currentInterrupt = chunk.data.__interrupt__[0]
    }
  }
  ↓
  Extract tool info:
    toolName = "rent_movie"
    toolArgs = {title: "The Matrix", rental_price: 3.99}
  ↓
  Map to component:
    if (toolName === 'rent_movie') {
      setInterruptType('rental_payment')
      setInterruptData({...toolArgs})
    }
  ↓
  Render component:
    {interruptType === 'rental_payment' && (
      <RentalPayment data={interruptData} onConfirm={...} />
    )}
  ↓
  User clicks "Rent Now"
  ↓
  handleConfirmationSelect('Rent Now')
  ↓
  Send resume command:
  {
    resume: {
      decisions: [{
        type: 'approve',
        editedAction: {
          name: 'rent_movie',
          args: {...toolArgs, selected_option: 'Rent Now'}
        }
      }]
    }
  }
  ↓
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BACKEND RESUMES
  ↓
  Middleware receives resume command
  ↓
  Loads saved state from checkpoint
  ↓
  Executes rent_movie with selected_option='Rent Now'
  ↓
  Tool returns: "✅ 'The Matrix' rented successfully!"
  ↓
  Result streams back to frontend
  ↓
  Displayed in chat
```

---

## 🎯 Key Technical Points

### 1. Interrupt Detection

**The Special Field:**
```javascript
if (chunk.data?.__interrupt__) {
  // Interrupt present!
}
```

This is LangGraph's **standard interrupt marker**. When middleware pauses execution, LangGraph automatically adds this field to the stream.

### 2. Component Mapping Strategy

**Option A: If/Else (Your Current Code)**
```javascript
if (toolName === 'restart_router') {
  setInterruptType('confirmation')
}
else if (toolName === 'rent_movie') {
  setInterruptType('rental_payment')
}
else {
  setInterruptType('tool_approval')
}
```

**Option B: Lookup Table (More Scalable)**
```javascript
const TOOL_TO_COMPONENT = {
  'restart_router': 'confirmation',
  'rent_movie': 'rental_payment',
  'execute_sql': 'sql_approval',
  'cancel_subscription': 'confirmation',
}

const interruptType = TOOL_TO_COMPONENT[toolName] || 'tool_approval'
```

### 3. Resume Command Structure

**Critical format for middleware interrupts:**
```javascript
{
  command: {
    resume: {
      decisions: [
        {
          type: 'approve',        // or 'reject', 'edit'
          editedAction: {
            name: 'tool_name',
            args: {
              ...originalArgs,
              selected_option: 'user_choice'  // ← Pass user's decision
            }
          }
        }
      ]
    }
  }
}
```

The `selected_option` parameter is how you pass the user's choice back to the tool!

---

## 🔧 Adding a New Interrupt Component

Let's walk through adding a new tool with a custom interrupt UI:

### 1. Backend: Create MCP Tool

```python
# backend/src/mcp_servers/wifi_server.py
@mcp.tool()
def schedule_maintenance(
    date: str,
    duration_hours: int,
    selected_option: str = None
) -> str:
    """Schedule network maintenance window."""
    if selected_option and "cancel" in selected_option.lower():
        return "❌ Maintenance cancelled"
    
    return f"✅ Maintenance scheduled for {date} ({duration_hours}h)"
```

### 2. Backend: Configure Middleware

```python
# backend/src/wifi_agent.py
HumanInTheLoopMiddleware(
    interrupt_on={
        "restart_router": True,
        "schedule_maintenance": True,  # ← Add new tool
    }
)
```

### 3. Frontend: Map to Component

```javascript
// frontend/src/App.jsx - In sendMessage() after stream completes
else if (toolName === 'schedule_maintenance') {
  setInterruptType('maintenance_schedule')  // ← New type
  setInterruptData({
    date: toolArgs.date,
    duration_hours: toolArgs.duration_hours,
  })
}
```

### 4. Frontend: Create Component

```javascript
// frontend/src/App.jsx - Add new component definition
function MaintenanceSchedule({ data, onConfirm, onCancel }) {
  return (
    <div className="maintenance-panel">
      <h3>📅 Schedule Maintenance</h3>
      <p>Date: {data.date}</p>
      <p>Duration: {data.duration_hours} hours</p>
      <button onClick={() => onConfirm('Confirm Schedule')}>
        Confirm
      </button>
      <button onClick={onCancel}>Cancel</button>
    </div>
  )
}
```

### 5. Frontend: Render Component

```javascript
// frontend/src/App.jsx - In return JSX
{interrupt && interruptType === 'maintenance_schedule' && (
  <div className="interrupt-panel">
    <MaintenanceSchedule
      data={interruptData}
      onConfirm={handleConfirmationSelect}
      onCancel={handleCancel}
    />
  </div>
)}
```

**Done!** Now `schedule_maintenance` tool interrupts and shows your custom UI.

---

## 🐛 Debugging Tips

### Enable Detailed Logging

```javascript
// frontend/src/App.jsx
for await (const chunk of stream) {
  console.log('📦 Stream chunk:', chunk.event, chunk.data)
  
  if (chunk.data?.__interrupt__) {
    console.log('🚨 INTERRUPT:', JSON.stringify(chunk.data.__interrupt__, null, 2))
  }
}
```

### Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| Interrupt not detected | Wrong stream mode | Use `streamMode: 'messages'` |
| Component not rendering | Typo in toolName check | Check `if (toolName === '...')` |
| Props undefined | Not extracting from toolArgs | Log `toolArgs` and verify keys |
| Resume doesn't work | Wrong command structure | Check `decisions[0].editedAction.args` |

### Inspect Interrupt Structure

```javascript
if (currentInterrupt) {
  console.log('Interrupt ID:', currentInterrupt.id)
  console.log('Action requests:', currentInterrupt.value?.action_requests)
  console.log('Tool name:', currentInterrupt.value?.action_requests?.[0]?.name)
  console.log('Tool args:', currentInterrupt.value?.action_requests?.[0]?.args)
}
```

---

## 📚 Summary

### How Components Get Rendered

1. **Backend:** Middleware intercepts tool → Creates interrupt with `{name, args}`
2. **Stream:** Interrupt sent via SSE with `__interrupt__` marker
3. **Frontend:** Detects `chunk.data.__interrupt__` → Extracts tool name
4. **Frontend:** Maps tool name to component type via if/else or lookup table
5. **Frontend:** Renders component conditionally based on `interruptType`
6. **Frontend:** User interacts → Sends resume command with `selected_option`
7. **Backend:** Receives decision → Executes tool → Returns result

### The Magic Connection

**Backend defines WHAT needs approval:**
```python
interrupt_on={"rent_movie": True}
```

**Frontend defines HOW to ask for approval:**
```javascript
if (toolName === 'rent_movie') {
  return <RentalPayment {...data} />
}
```

**This separation enables:**
- ✅ Backend team controls business logic
- ✅ Frontend team controls UI/UX
- ✅ Platform-agnostic (works on web, mobile, etc.)
- ✅ Easy to add new tools with custom UIs

---

**Your implementation is production-ready!** 🎉 The pattern you've built (backend-owned interrupts + frontend-rendered components) is exactly how modern AG UI systems should work.

