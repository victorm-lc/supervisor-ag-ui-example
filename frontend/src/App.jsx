import { useState, useEffect, useRef } from 'react'
import { Client } from '@langchain/langgraph-sdk'
import './App.css'

/*
 * AG UI ARCHITECTURE PATTERN
 * 
 * This frontend follows the AG UI (Agent-Generated UI) pattern:
 * 
 * 1. AGENT TOOL CALLS → FRONTEND COMPONENTS
 *    When the agent calls a "client tool" (e.g., confirmation_dialog),
 *    the frontend detects it and renders the corresponding React component.
 * 
 * 2. TOOL-TO-COMPONENT REGISTRY
 *    We map tool names to React components that render the UI.
 * 
 * 3. INTERRUPT-BASED INTERACTION
 *    Client tools trigger HITL interrupts, pausing agent execution.
 *    User interacts with the UI component, then execution resumes.
 * 
 * 4. DYNAMIC CLIENT TOOL ADVERTISEMENT ✨
 *    Frontend advertises which UI tools it can render in each request.
 *    Backend middleware dynamically filters tools per domain.
 *    This makes the backend version-agnostic:
 *    - Old app version with 2 tools? Works!
 *    - New app version with 5 tools? Works!
 *    - No backend changes needed when adding new client tools!
 * 
 * Flow: 
 *   1. Frontend advertises available tools → 
 *   2. Backend middleware filters by domain → 
 *   3. Agent calls tool → 
 *   4. HITL interrupt → 
 *   5. Frontend renders component →
 *   6. User interacts → 
 *   7. Resume with user's input → 
 *   8. Agent continues
 */

// =============================================================================
// CLIENT TOOL ADVERTISEMENT
// =============================================================================
// These are the UI tools this client can render. The backend will dynamically
// filter which tools are available to each domain agent based on this list.
// 
// Example versioning:
// - v1.0 app: ['confirmation_dialog', 'error_display']
// - v2.0 app: ['confirmation_dialog', 'error_display', 'network_status_display', 'play_video']
// - Backend works with both versions automatically!
const ADVERTISED_CLIENT_TOOLS = [
  'confirmation_dialog',
  'error_display',
  'network_status_display',
  'play_video',  // return_direct=True - renders video player immediately!
]

// =============================================================================
// AG UI COMPONENT: Confirmation Dialog
// Triggered by: confirmation_dialog tool call
// =============================================================================
function ConfirmationDialog({ message, options, onConfirm, onCancel }) {
  return (
    <div className="confirmation-card">
      <div className="confirmation-header">
        <span className="confirmation-icon">⚠️</span>
        <h3>Confirmation Required</h3>
      </div>
      
      <p className="confirmation-message">{message}</p>
      
      <div className="confirmation-buttons">
        {options.map((option, idx) => (
          <button 
            key={idx}
            onClick={() => onConfirm(option)} 
            className="btn btn-primary"
          >
            {option}
          </button>
        ))}
        <button onClick={onCancel} className="btn btn-secondary">
          Cancel
        </button>
      </div>
    </div>
  )
}

// =============================================================================
// AG UI COMPONENT: Router Restart Confirmation
// Triggered by: restart_router tool call (shows detailed confirmation)
// =============================================================================
function RouterRestartConfirmation({ onConfirm, onCancel }) {
  return (
    <div className="confirmation-card router-restart">
      <div className="confirmation-header">
        <span className="confirmation-icon">🔄</span>
        <h3>Router Restart Confirmation</h3>
      </div>
      
      <div className="warning-box">
        <p><strong>⚠️ This will restart your router</strong></p>
        <p>Your internet connection will be offline for approximately 2 minutes.</p>
        <ul>
          <li>All devices will be disconnected</li>
          <li>Active downloads will be interrupted</li>
          <li>Video streams will pause</li>
        </ul>
      </div>
      
      <div className="confirmation-buttons">
        <button onClick={onConfirm} className="btn btn-primary">
          Yes, Restart Router
        </button>
        <button onClick={onCancel} className="btn btn-secondary">
          Cancel
        </button>
      </div>
    </div>
  )
}

// =============================================================================
// AG UI COMPONENT: Video Player
// Triggered by: play_video tool call (return_direct=True)
// =============================================================================
function VideoPlayer({ videoUrl, title, onClose }) {
  return (
    <div className="video-player-card">
      <div className="video-player-header">
        <h3>🎬 Now Playing: {title}</h3>
        <button onClick={onClose} className="video-close-btn">✕</button>
      </div>
      <div className="video-player-container">
        <iframe 
          width="100%" 
          height="400"
          src={videoUrl}
          title={title}
          frameBorder="0"
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
          allowFullScreen
        />
      </div>
    </div>
  )
}

// =============================================================================
// MAIN APP COMPONENT
// =============================================================================
function App() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [threadId, setThreadId] = useState(null)
  const [interrupt, setInterrupt] = useState(null)
  const [interruptType, setInterruptType] = useState(null)
  const [interruptData, setInterruptData] = useState(null)
  const [videoPlayer, setVideoPlayer] = useState(null)  // For play_video return_direct
  const messagesEndRef = useRef(null)

  const client = new Client({ apiUrl: 'http://localhost:2024' })

  // Helper: Parse video player data from tool messages
  const parseVideoPlayer = (content) => {
    if (typeof content === 'string') {
      try {
        const parsed = JSON.parse(content)
        if (parsed?.type === 'video_player') return parsed
      } catch (e) {
        // Not JSON, ignore
      }
    } else if (typeof content === 'object' && content?.type === 'video_player') {
      return content
    }
    return null
  }

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Initialize thread on mount (with persistence)
  useEffect(() => {
    const initThread = async () => {
      try {
        // Check if we have a stored thread ID
        const storedThreadId = localStorage.getItem('langgraph_thread_id')
        
        if (storedThreadId) {
          // Reuse existing thread
          setThreadId(storedThreadId)
          console.log('Restored thread:', storedThreadId)
        } else {
          // Create new thread
          const thread = await client.threads.create()
          setThreadId(thread.thread_id)
          localStorage.setItem('langgraph_thread_id', thread.thread_id)
          console.log('Thread created:', thread.thread_id)
        }
      } catch (error) {
        console.error('Failed to create thread:', error)
        setMessages([
          {
            role: 'system',
            content: '❌ Failed to connect to LangGraph server. Make sure it\'s running on port 2024.',
          },
        ])
      }
    }
    initThread()
  }, [])

  const sendMessage = async (userMessage) => {
    if (!userMessage.trim() || !threadId) return

    // Add user message to chat
    const newUserMessage = { role: 'user', content: userMessage }
    setMessages((prev) => [...prev, newUserMessage])
    setInput('')
    setIsLoading(true)
    setInterrupt(null)
    setInterruptType(null)
    setInterruptData(null)

    try {
      // Stream the agent's response
      // DYNAMIC TOOL ADVERTISEMENT: Send available client tools via config
      const stream = client.runs.stream(threadId, 'supervisor', {
        input: { messages: [{ role: 'user', content: userMessage }] },
        config: {
          configurable: {
            advertised_client_tools: ADVERTISED_CLIENT_TOOLS
          }
        },
        streamMode: 'messages',
      })

      let assistantMessage = ''
      let currentInterrupt = null

      for await (const chunk of stream) {
        console.log('Stream chunk:', chunk.event, chunk.data) // Debug log
        
        // Handle different event types
        if (chunk.event === 'messages/partial' || chunk.event === 'messages/complete') {
          const message = chunk.data?.[0]
          const content = message?.content
          
          // Check if this is a tool message with return_direct (like play_video)
          if (message?.type === 'tool') {
            const videoData = parseVideoPlayer(content)
            if (videoData) {
              console.log('Video player detected:', videoData)
              setVideoPlayer(videoData)
            }
          } else if (content && typeof content === 'string') {
            assistantMessage = content
          } else if (Array.isArray(content)) {
            assistantMessage = content.map(c => c.text || '').join('')
          }
        }

        // Check for interrupts
        if (chunk.data?.__interrupt__) {
          currentInterrupt = chunk.data.__interrupt__[0]
          console.log('Interrupt detected:', currentInterrupt)
        }
      }

      // Add assistant message to chat if we got one
      if (assistantMessage) {
        setMessages((prev) => [...prev, { role: 'assistant', content: assistantMessage }])
      }

      // Handle interrupt if present
      if (currentInterrupt) {
        setInterrupt(currentInterrupt)
        
        // All interrupts come from HITL middleware
        const actionRequest = currentInterrupt.value?.action_requests?.[0]
        console.log('Action request:', actionRequest)
        
        if (actionRequest) {
          const toolName = actionRequest.name
          const toolArgs = actionRequest.args
          console.log('Tool name:', toolName, 'Tool args:', toolArgs)
          
          /*
           * AG UI TOOL-TO-COMPONENT MAPPING
           * 
           * Here we map tool names to interrupt types, which determine
           * which React component to render. This is the core of AG UI:
           * the agent's tool call directly triggers a UI component.
           */
          
          // Confirmation Dialog - AG UI client tool
          if (toolName === 'confirmation_dialog') {
            setInterruptType('confirmation')
            setInterruptData(toolArgs)
            // Don't show raw tool args - the ConfirmationDialog component will render below
          } 
          // Router Restart - Special confirmation with detailed warning
          else if (toolName === 'restart_router') {
            setInterruptType('router_restart')
            setInterruptData(toolArgs)
            // Don't show raw tool args - the RouterRestartConfirmation component will render below
          }
          // Generic tool approval fallback
          else {
            setInterruptType('tool_approval')
            setInterruptData(toolArgs)
            setMessages((prev) => [
              ...prev,
              {
                role: 'system',
                content: `🚨 Approval Required: ${toolName}`,
                toolCall: { tool: toolName, args: toolArgs },
              },
            ])
          }
        }
      }
    } catch (error) {
      console.error('Error sending message:', error)
      
      // Friendly message for 404 (thread not found - server restarted)
      if (error.message?.includes('404') || error.status === 404) {
        setMessages((prev) => [
          ...prev,
          { role: 'system', content: '❌ Thread not found. The server may have been restarted. Try clicking "Clear Chat" to start fresh.' },
        ])
      } else {
        setMessages((prev) => [
          ...prev,
          { role: 'system', content: `❌ Error: ${error.message}` },
        ])
      }
    } finally {
      setIsLoading(false)
    }
  }

  // Handle confirmation dialog selection
  const handleConfirmationSelect = async (selectedOption) => {
    if (!interrupt) return

    setIsLoading(true)
    setMessages((prev) => [
      ...prev,
      { role: 'system', content: `✅ Selected: ${selectedOption}` },
    ])

    try {
      // Resume with the selected option
      // CRITICAL: Send the user's actual choice to the backend!
      const actionRequest = interrupt.value?.action_requests?.[0]
      const stream = client.runs.stream(threadId, 'supervisor', {
        command: {
          resume: {
            decisions: [{ 
              type: 'approve',
              // Include the user's selected option in the tool input
              editedAction: {
                name: actionRequest?.name,
                args: {
                  ...actionRequest?.args,
                  selected_option: selectedOption  // ✅ Send user's choice!
                }
              }
            }],
          },
        },
        config: {
          configurable: {
            advertised_client_tools: ADVERTISED_CLIENT_TOOLS
          }
        },
        streamMode: 'messages',
      })

      let assistantMessage = ''
      let currentInterrupt = null

      for await (const chunk of stream) {
        console.log('Resume stream chunk:', chunk.event, chunk.data) // Debug log
        
        if (chunk.event === 'messages/partial') {
          const content = chunk.data?.[0]?.content
          if (content && typeof content === 'string') {
            assistantMessage = content
          } else if (Array.isArray(content)) {
            assistantMessage = content.map(c => c.text || '').join('')
          }
        } else if (chunk.event === 'messages/complete') {
          const content = chunk.data?.[0]?.content
          if (content && typeof content === 'string') {
            assistantMessage = content
          } else if (Array.isArray(content)) {
            assistantMessage = content.map(c => c.text || '').join('')
          }
        }
        
        // Check for NEW interrupts (like restart_router after confirmation_dialog)
        if (chunk.data?.__interrupt__) {
          currentInterrupt = chunk.data.__interrupt__[0]
          console.log('New interrupt detected during resume:', currentInterrupt)
        }
      }

      if (assistantMessage) {
        setMessages((prev) => [...prev, { role: 'assistant', content: assistantMessage }])
      }

      // Handle new interrupt if one appeared (e.g., restart_router approval)
      if (currentInterrupt) {
        setInterrupt(currentInterrupt)
        
        const actionRequest = currentInterrupt.value?.action_requests?.[0]
        if (actionRequest) {
          const toolName = actionRequest.name
          const toolArgs = actionRequest.args
          
          if (toolName === 'restart_router') {
            setInterruptType('router_restart')
            setInterruptData(toolArgs)
          } else if (toolName === 'confirmation_dialog') {
            setInterruptType('confirmation')
            setInterruptData(toolArgs)
          } else {
            setInterruptType('tool_approval')
            setInterruptData(toolArgs)
            setMessages((prev) => [
              ...prev,
              {
                role: 'system',
                content: `🚨 Approval Required: ${toolName}`,
                toolCall: { tool: toolName, args: toolArgs },
              },
            ])
          }
        }
      } else {
        // No new interrupt - clear everything
        setInterrupt(null)
        setInterruptType(null)
        setInterruptData(null)
      }
    } catch (error) {
      console.error('Error confirming:', error)
      
      // Friendly message for 404
      if (error.message?.includes('404') || error.status === 404) {
        setMessages((prev) => [
          ...prev,
          { role: 'system', content: '❌ Thread not found. The server may have been restarted. Try clicking "Clear Chat" to start fresh.' },
        ])
      } else {
        setMessages((prev) => [
          ...prev,
          { role: 'system', content: `❌ Error: ${error.message}` },
        ])
      }
    } finally {
      setIsLoading(false)
    }
  }

  // Handle cancel/reject
  const handleCancel = async () => {
    if (!interrupt) return

    setIsLoading(true)
    setMessages((prev) => [
      ...prev,
      { role: 'system', content: '❌ Action cancelled' },
    ])

    try {
      // Resume with rejection
      const stream = client.runs.stream(threadId, 'supervisor', {
        command: {
          resume: {
            decisions: [{ type: 'reject', message: 'User cancelled this action' }],
          },
        },
        config: {
          configurable: {
            advertised_client_tools: ADVERTISED_CLIENT_TOOLS
          }
        },
        streamMode: 'messages',
      })

      let assistantMessage = ''

      for await (const chunk of stream) {
        if (chunk.event === 'messages/partial') {
          const content = chunk.data?.[0]?.content
          if (content && typeof content === 'string') {
            assistantMessage = content
          } else if (Array.isArray(content)) {
            assistantMessage = content.map(c => c.text || '').join('')
          }
        } else if (chunk.event === 'messages/complete') {
          const content = chunk.data?.[0]?.content
          if (content && typeof content === 'string') {
            assistantMessage = content
          } else if (Array.isArray(content)) {
            assistantMessage = content.map(c => c.text || '').join('')
          }
        }
      }

      if (assistantMessage) {
        setMessages((prev) => [...prev, { role: 'assistant', content: assistantMessage }])
      }

      setInterrupt(null)
      setInterruptType(null)
      setInterruptData(null)
    } catch (error) {
      console.error('Error cancelling:', error)
      
      // Friendly message for 404
      if (error.message?.includes('404') || error.status === 404) {
        setMessages((prev) => [
          ...prev,
          { role: 'system', content: '❌ Thread not found. The server may have been restarted. Try clicking "Clear Chat" to start fresh.' },
        ])
      } else {
        setMessages((prev) => [
          ...prev,
          { role: 'system', content: `❌ Error: ${error.message}` },
        ])
      }
    } finally {
      setIsLoading(false)
    }
  }

  // Generic approve handler for non-confirmation tools  
  const handleApprove = async () => {
    if (!interrupt) return

    setIsLoading(true)
    setMessages((prev) => [
      ...prev,
      { role: 'system', content: '✅ Action approved, resuming agent...' },
    ])

    try {
      const stream = client.runs.stream(threadId, 'supervisor', {
        command: {
          resume: {
            decisions: [{ type: 'approve' }],
          },
        },
        config: {
          configurable: {
            advertised_client_tools: ADVERTISED_CLIENT_TOOLS
          }
        },
        streamMode: 'messages',
      })

      let assistantMessage = ''
      let currentInterrupt = null

      for await (const chunk of stream) {
        console.log('Approve stream chunk:', chunk.event, chunk.data) // Debug log
        
        if (chunk.event === 'messages/partial') {
          const content = chunk.data?.[0]?.content
          if (content && typeof content === 'string') {
            assistantMessage = content
          } else if (Array.isArray(content)) {
            assistantMessage = content.map(c => c.text || '').join('')
          }
        } else if (chunk.event === 'messages/complete') {
          const content = chunk.data?.[0]?.content
          if (content && typeof content === 'string') {
            assistantMessage = content
          } else if (Array.isArray(content)) {
            assistantMessage = content.map(c => c.text || '').join('')
          }
        }
        
        // Check for NEW interrupts
        if (chunk.data?.__interrupt__) {
          currentInterrupt = chunk.data.__interrupt__[0]
          console.log('New interrupt detected during approval:', currentInterrupt)
        }
      }

      if (assistantMessage) {
        setMessages((prev) => [...prev, { role: 'assistant', content: assistantMessage }])
      }

      // Handle new interrupt if present
      if (currentInterrupt) {
        setInterrupt(currentInterrupt)
        
        const actionRequest = currentInterrupt.value?.action_requests?.[0]
        if (actionRequest) {
          const toolName = actionRequest.name
          const toolArgs = actionRequest.args
          
          if (toolName === 'restart_router') {
            setInterruptType('router_restart')
            setInterruptData(toolArgs)
          } else if (toolName === 'confirmation_dialog') {
            setInterruptType('confirmation')
            setInterruptData(toolArgs)
          } else {
            setInterruptType('tool_approval')
            setInterruptData(toolArgs)
            setMessages((prev) => [
              ...prev,
              {
                role: 'system',
                content: `🚨 Approval Required: ${toolName}`,
                toolCall: { tool: toolName, args: toolArgs },
              },
            ])
          }
        }
      } else {
        // No new interrupt - clear everything
        setInterrupt(null)
        setInterruptType(null)
        setInterruptData(null)
      }
    } catch (error) {
      console.error('Error approving action:', error)
      
      // Friendly message for 404
      if (error.message?.includes('404') || error.status === 404) {
        setMessages((prev) => [
          ...prev,
          { role: 'system', content: '❌ Thread not found. The server may have been restarted. Try clicking "Clear Chat" to start fresh.' },
        ])
      } else {
        setMessages((prev) => [
          ...prev,
          { role: 'system', content: `❌ Error: ${error.message}` },
        ])
      }
    } finally {
      setIsLoading(false)
    }
  }

  // Clear chat and start new thread
  const clearChat = async () => {
    try {
      const thread = await client.threads.create()
      setThreadId(thread.thread_id)
      localStorage.setItem('langgraph_thread_id', thread.thread_id)
      setMessages([])
      setInterrupt(null)
      setInterruptType(null)
      setInterruptData(null)
      setVideoPlayer(null)
      console.log('New thread created:', thread.thread_id)
    } catch (error) {
      console.error('Failed to create new thread:', error)
    }
  }

  return (
    <div className="app">
      <header className="header">
        <div>
          <h1>🏠 Example Everything App</h1>
          <p>Powered by LangGraph + AG UI | Supervisor + Domain Subagents</p>
        </div>
        <button onClick={clearChat} className="clear-btn" disabled={!threadId}>
          🗑️ Clear Chat
        </button>
      </header>

      <div className="chat-container">
        <div className="messages">
          {messages.length === 0 && (
            <div className="welcome-message">
              <h2>👋 Welcome to Example Support</h2>
              <p>I can help you with:</p>
              <ul>
                <li>📶 <strong>WiFi & Internet:</strong> "My WiFi is slow" or "Run network diagnostics"</li>
                <li>🎬 <strong>Video & Streaming:</strong> "I want to watch The Matrix" or "Find action movies"</li>
              </ul>
              <p className="tip">💡 Try: "My internet is really slow, can you help?"</p>
            </div>
          )}
          
          {messages.map((msg, idx) => (
            <div key={idx} className={`message ${msg.role}`}>
              <div className="message-content">
                {msg.toolCall ? (
                  <div className="tool-call">
                    <strong>{msg.content}</strong>
                    <div className="tool-details">
                      <code>{JSON.stringify(msg.toolCall.args, null, 2)}</code>
                    </div>
                  </div>
                ) : (
                  msg.content
                )}
              </div>
            </div>
          ))}
          {isLoading && (
            <div className="message assistant">
              <div className="message-content loading">
                <span className="dot"></span>
                <span className="dot"></span>
                <span className="dot"></span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* AG UI COMPONENT RENDERING - Based on interrupt type */}
        
        {interrupt && interruptType === 'confirmation' && (
          <div className="interrupt-panel">
            <ConfirmationDialog
              message={interruptData?.message || 'Please confirm this action'}
              options={interruptData?.options || ['Confirm', 'Cancel']}
              onConfirm={handleConfirmationSelect}
              onCancel={handleCancel}
            />
          </div>
        )}

        {interrupt && interruptType === 'router_restart' && (
          <div className="interrupt-panel">
            <RouterRestartConfirmation
              onConfirm={() => handleConfirmationSelect('Yes, restart')}
              onCancel={handleCancel}
            />
          </div>
        )}

        {interrupt && interruptType === 'tool_approval' && (
          <div className="interrupt-panel">
            <div className="approval-card">
              <p>⚠️ This action requires your approval</p>
              <div className="approval-buttons">
                <button onClick={handleApprove} className="btn btn-primary" disabled={isLoading}>
                  ✅ Approve
                </button>
                <button onClick={handleCancel} className="btn btn-secondary" disabled={isLoading}>
                  ❌ Reject
                </button>
              </div>
            </div>
          </div>
        )}

        {/* VIDEO PLAYER - return_direct tool (play_video) */}
        {videoPlayer && (
          <div className="video-player-panel">
            <VideoPlayer
              videoUrl={videoPlayer.video_url}
              title={videoPlayer.title}
              onClose={() => setVideoPlayer(null)}
            />
          </div>
        )}

        <form
          className="input-form"
          onSubmit={(e) => {
            e.preventDefault()
            sendMessage(input)
          }}
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about WiFi, internet, or video content..."
            disabled={isLoading || !threadId}
            className="input-field"
          />
          <button type="submit" disabled={isLoading || !threadId || !input.trim()} className="send-btn">
            Send
          </button>
        </form>
      </div>
    </div>
  )
}

export default App
