# Architecture Decision: Where Should Interrupts Live?

**Date:** November 6, 2024  
**Context:** Comcast multi-agent system with multiple client platforms (Web, Kotlin, iOS, Android)  
**Team Structure:** Backend-focused (agent logic), Frontend-focused (UI rendering)

---

## 🎯 The Question

**Should human-approval interrupts live in:**
- **Option A:** Backend tools (MCP servers) ← **RECOMMENDED**
- **Option B:** Client tools (frontend schemas)

---

## ✅ Recommendation: Backend-Owned Interrupts (Option A)

**Your instinct is correct.** For your use case, interrupts should be **backend tools with middleware-based HITL**, and client tools should be **pure UI rendering**.

---

## 📊 Decision Matrix

| Criterion | Backend Interrupts | Client Interrupts |
|-----------|-------------------|-------------------|
| **Security** | ✅ Server-validated | ❌ Client can bypass |
| **Platform Support** | ✅ Works with Kotlin/iOS/Android | ⚠️ Requires JS SDK |
| **Team Ownership** | ✅ Backend team controls logic | ❌ Frontend team controls logic |
| **Audit Trail** | ✅ Server-side logging | ⚠️ Requires extra work |
| **Business Rules** | ✅ Centralized | ❌ Duplicated per client |
| **Version Consistency** | ✅ Same rules for all versions | ❌ Varies by client version |
| **Deployment** | ✅ Backend deploy = instant update | ❌ Requires client update |

---

## 🏗️ Recommended Architecture

### Pattern: "Backend Logic, Frontend Presentation"

```
┌─────────────────────────────────────────────────────────────┐
│ BACKEND (Business Logic + Interrupts)                       │
│                                                              │
│ MCP Tool: rent_movie(title, video_url, rental_price)       │
│   ├─ Business logic: validate, check inventory              │
│   ├─ Middleware HITL: pause for approval                    │
│   └─ Returns: success/failure message                       │
│                                                              │
│ Interrupt Data: {                                           │
│   type: "rent_movie",                                       │
│   title: "The Matrix",                                      │
│   rental_price: 3.99,                                       │
│   rental_period: "48 hours"                                 │
│ }                                                            │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ FRONTEND (UI Rendering Only)                                │
│                                                              │
│ Client Tool Schema: play_video (pure UI)                   │
│   └─ No business logic, just renders component              │
│                                                              │
│ Interrupt Handler:                                          │
│   if (toolName === 'rent_movie') {                         │
│     return <RentalPayment                                   │
│       title={args.title}              ← Props from backend │
│       price={args.rental_price}       ← Props from backend │
│       onConfirm={handleConfirm}       ← Send decision back │
│     />                                                       │
│   }                                                          │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔐 Security Implications

### ⚠️ Why Client-Side Interrupts Are Dangerous

**Scenario:** Payment approval in frontend

```typescript
// ❌ DANGEROUS: Client-side interrupt
const clientTools = [{
  name: 'rent_movie',
  interrupt: true,  // Frontend decides if approval needed
  handler: async (args) => {
    if (shouldInterrupt()) {  // Client logic!
      await getUserApproval()
    }
    return processPayment(args)  // Client initiates payment
  }
}]
```

**Attack Vector:**
1. Malicious user modifies client code
2. Sets `shouldInterrupt = () => false`
3. Bypasses payment approval
4. Charges go through without user consent

### ✅ Backend-Owned Interrupts Are Secure

```python
# ✅ SECURE: Backend controls approval
@mcp.tool()
def rent_movie(title: str, rental_price: float, selected_option: str = None):
    """Backend owns the business logic"""
    # This runs on YOUR server, not client
    if not selected_option:
        # Middleware catches this and creates interrupt
        pass
    
    # Validate payment server-side
    validate_payment_method()
    charge_customer(rental_price)
    grant_access(title)
```

**Backend Middleware:**
```python
HumanInTheLoopMiddleware(
    interrupt_on={"rent_movie": True},  # You control this
    description_prefix="Payment confirmation required"
)
```

---

## 🌍 Platform-Agnostic Benefits

### Works with ANY Client

Your customer plans to deploy on:
- **Web (JavaScript)** ✅
- **iOS (Swift)** ✅
- **Android (Kotlin)** ✅
- **Ruby backend-for-frontend** ✅

**Backend-owned interrupts:** Work with all platforms via REST API or LangGraph SDK

**Client-owned interrupts:** Require each platform to:
- Implement interrupt logic
- Handle approval UI
- Maintain consistent business rules
- Risk divergence between platforms

---

## 👥 Team Workflow

### Backend-Focused Team (Your Case)

**Backend Team Owns:**
- ✅ Business logic (payment validation)
- ✅ Approval policies (what needs approval)
- ✅ Security (server-side validation)
- ✅ Audit logs (who approved what)
- ✅ Interrupt triggers (middleware configuration)

**Frontend Team Owns:**
- ✅ UI components (RentalPayment, ConfirmationDialog)
- ✅ Styling and UX
- ✅ Component props mapping
- ✅ Loading states

**Clear Contract:**
```typescript
// Backend sends interrupt data
interface RentalInterrupt {
  title: string           // From backend
  rental_price: number    // From backend
  rental_period: string   // From backend
}

// Frontend renders component
<RentalPayment {...interruptData} onConfirm={handleConfirm} />
```

---

## 📦 Tool Classification Guide

### Backend Tools (MCP) → Business Logic + Interrupts

**Use MCP tools when:**
- ✅ Requires human approval/confirmation
- ✅ Interacts with external services (payment, database)
- ✅ Has security implications
- ✅ Needs audit logging
- ✅ Contains business rules that change frequently

**Examples:**
```python
@mcp.tool()  # Backend MCP tool
def rent_movie(...):
    """Rental + payment requires approval"""
    
@mcp.tool()  # Backend MCP tool
def restart_router(...):
    """Network change requires approval"""

@mcp.tool()  # Backend MCP tool
def execute_sql(...):
    """Database access requires approval"""
```

### Client Tools (Schemas) → Pure UI Rendering

**Use client tool schemas when:**
- ✅ Pure UI rendering (no business logic)
- ✅ No approval needed (instant display)
- ✅ No external side effects
- ✅ Frontend team fully owns implementation

**Examples:**
```typescript
// Client tool schema (frontend)
{
  name: 'play_video',
  description: 'Render video player component',
  parameters: { video_url: string, title: string },
  returnDirect: true,  // Instant UI, no approval
  domains: ['video']
}

// Client tool schema (frontend)
{
  name: 'display_chart',
  description: 'Render analytics chart',
  parameters: { data: array, chartType: string },
  returnDirect: true
}
```

---

## 🎬 Your Current Implementation (Perfect!)

### Example: `rent_movie` (Backend MCP Tool with Interrupt)

**Backend (`video_server.py`):**
```python
@mcp.tool()
def rent_movie(
    title: str,
    video_url: str,
    rental_price: float = 3.99,
    selected_option: str = None  # ← Filled after approval
) -> str:
    """
    Rent a movie with payment confirmation.
    Uses middleware-based HITL pattern.
    """
    if selected_option and "cancel" in selected_option.lower():
        return "❌ Rental cancelled by user"
    
    # Process rental
    rental_id = f"R-{hash(title) % 100000:05d}"
    return f"✅ '{title}' rented successfully! Rental ID: {rental_id}"
```

**Backend Middleware (`video_agent.py`):**
```python
HumanInTheLoopMiddleware(
    interrupt_on={
        "rent_movie": True,  # ← Backend controls this
    },
    description_prefix="🚨 Payment confirmation required",
)
```

**Frontend (`App.jsx`):**
```javascript
// Frontend ONLY renders, doesn't control approval logic
if (toolName === 'rent_movie') {
  setInterruptType('rental_payment')
  setInterruptData({
    title: toolArgs.title,           // ← From backend
    rental_price: toolArgs.rental_price,  // ← From backend
    rental_period: '48 hours'        // ← From backend
  })
}

// Renders custom component with backend data
<RentalPayment
  data={interruptData}
  onConfirm={handleConfirmationSelect}  // Sends decision back
  onCancel={handleCancel}
/>
```

**This is the CORRECT pattern!** ✅

---

## 🎓 When Would Client Interrupts Make Sense?

### Frontend-First Teams (NOT Your Case)

**Scenario:** Frontend team is primary, backend is thin API layer

**Example: Vercel AI SDK**
```typescript
// Frontend-heavy pattern (Vercel AI SDK)
const clientTools = [{
  name: 'confirm_action',
  interrupt: async (args) => {
    // Frontend controls everything
    const approved = await showDialog(args)
    return { approved }
  }
}]
```

**This works when:**
- Frontend team owns all business logic
- Single platform (web only, not mobile)
- Low security requirements (no payments)
- Rapid prototyping / MVPs

**NOT suitable for:**
- ❌ Multi-platform (mobile apps)
- ❌ Financial transactions
- ❌ Backend-focused teams
- ❌ Enterprise security requirements

---

## 📈 Scaling Considerations

### Adding New Approval Workflows

**With Backend Interrupts (Easy):**
```python
# 1. Add new MCP tool
@mcp.tool()
def cancel_subscription(reason: str, selected_option: str = None):
    """Cancellation requires approval"""
    # Business logic here
    
# 2. Configure middleware
HumanInTheLoopMiddleware(
    interrupt_on={
        "rent_movie": True,
        "cancel_subscription": True,  # ← Add one line
    }
)

# 3. Deploy backend → DONE! All clients get it instantly
```

**With Client Interrupts (Hard):**
1. Update Web client → deploy
2. Update iOS app → App Store review (1-2 weeks)
3. Update Android app → Play Store review (1-2 days)
4. Update Ruby BFF → deploy
5. Hope all clients implement consistently ❌

---

## 🔒 Compliance & Audit

### Backend-Owned Advantages

**Regulatory Requirements (PCI DSS, SOC 2, GDPR):**

```python
# Server-side audit log
@mcp.tool()
def rent_movie(..., selected_option: str = None):
    # Log approval event
    audit_log.record(
        action="rental_payment",
        user_id=get_current_user(),
        decision=selected_option,
        timestamp=datetime.now(),
        ip_address=request.client_ip,
        amount=rental_price
    )
```

**Client-side:** Would require:
- Each platform to implement logging
- Trust client to send logs (unreliable)
- Risk of incomplete audit trail

---

## 🎯 Final Recommendation

### For Your Customer (Comcast)

**DO THIS (Current Implementation):**

| Component | Ownership | Example |
|-----------|-----------|---------|
| **Business Logic** | Backend (MCP) | Payment validation, inventory check |
| **Approval Policies** | Backend (Middleware) | `rent_movie`, `restart_router` |
| **Interrupt Data** | Backend → Frontend | `{title, price, period}` |
| **UI Components** | Frontend | `<RentalPayment>`, `<ConfirmationDialog>` |
| **Pure UI Tools** | Frontend (Schemas) | `play_video`, `display_chart` |

**DON'T DO THIS:**

| Anti-Pattern | Why Not |
|-------------|---------|
| Client-side payment approval | Security risk |
| Business logic in frontend schemas | Platform divergence |
| Approval policies in client code | Can't update instantly |
| Interrupts in client tools | Doesn't work with Kotlin/iOS |

---

## 📝 Summary

### ✅ Your Instinct is Correct

**Backend-owned interrupts are the right choice because:**

1. **Security First:** Payment/approval logic MUST be server-validated
2. **Platform Agnostic:** Works with Kotlin, iOS, Android, Ruby, Web
3. **Team Structure:** Backend team owns business logic (their strength)
4. **Maintainability:** One source of truth, instant deployment
5. **Compliance:** Server-side audit logs, regulatory requirements
6. **Separation of Concerns:** Backend = logic, Frontend = presentation

**Your current architecture is production-ready!** 🎉

### 📐 The Pattern

```
Backend (MCP Tools):
  - Business logic ✅
  - Approval workflows ✅
  - Security validation ✅
  - Audit logging ✅
  
  ↓ (sends interrupt data)
  
Frontend (Components):
  - Render UI ✅
  - User interaction ✅
  - Send decisions back ✅
  - Loading states ✅

Client Tools (Schemas):
  - Pure UI rendering ✅
  - No business logic ✅
  - Instant display ✅
  - Frontend team owns ✅
```

---

## 🚀 Next Steps

1. ✅ **Keep current architecture** (backend interrupts)
2. ✅ **Document pattern** for customer team
3. ✅ **Add more MCP tools** with interrupts as needed
4. ✅ **Client tools** only for pure UI (play_video, charts, etc.)
5. ✅ **Deploy confidently** knowing it scales to mobile

**Your demo is ready to show!** 🎬

