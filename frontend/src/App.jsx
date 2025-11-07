import { useState, useEffect, useRef } from 'react'
import { Client } from '@langchain/langgraph-sdk'
import { CLIENT_TOOL_SCHEMAS } from './toolSchemas'
import './App.css'

/*
 * AG UI + LANGGRAPH GENERATIVE UI PATTERN
 * 
 * This frontend follows the AG UI Protocol with LangGraph's Generative UI:
 * 
 * 1. TOOL ADVERTISEMENT (AG UI Protocol)
 *    Frontend advertises which UI tools it can render via tool schemas.
 *    Backend dynamically creates tools from these schemas.
 * 
 * 2. TOOL EXECUTION → UI MESSAGES
 *    When agent calls a client tool (e.g., play_video):
 *    - Tool calls push_ui_message() with props
 *    - UI message flows through dedicated UI channel
 *    - Frontend receives structured props (no JSON parsing!)
 * 
 * 3. COMPONENT RENDERING
 *    Frontend maps UI message names to React components.
 *    Props are already structured objects ready to render.
 * 
 * 4. INTERRUPT-BASED INTERACTION
 *    Some tools trigger HITL interrupts (e.g., rent_movie).
 *    User interacts with UI, then execution resumes.
 * 
 * 5. VERSION-AGNOSTIC MULTI-CLIENT SUPPORT ✨
 *    Each client advertises its UI capabilities:
 *    - Web app: ['play_video', 'network_status']
 *    - Mobile app: ['play_video'] only
 *    - CLI: [] (text only)
 *    Backend adapts based on what client supports.
 * 
 * Flow: 
 *   1. Frontend advertises tool schemas → 
 *   2. Backend creates tools, filters by domain → 
 *   3. Agent calls tool (e.g., play_video) → 
 *   4. Tool pushes UI message → 
 *   5. Frontend receives via UI channel →
 *   6. Component renders with structured props → 
 *   7. User sees UI
 * 
 * Benefits:
 *   ✅ Clean separation: messages vs UI data
 *   ✅ No JSON parsing or tool message inspection
 *   ✅ Official LangGraph pattern
 *   ✅ Full AG UI Protocol compliance
 */

// =============================================================================
// CLIENT TOOL ADVERTISEMENT
// =============================================================================
// These are the UI tools this client can render. The backend will dynamically
// filter which tools are available to each domain agent based on this list.
// 
// Example versioning:
// - v1.0 app: ['play_video']
// - v2.0 app: ['play_video', 'network_status_display']
// - Backend works with both versions automatically!
const ADVERTISED_CLIENT_TOOLS = [
  'play_video',  // Pure UI client tool - return_direct=True
]

// =============================================================================
// AG UI COMPONENT: Confirmation Dialog
// Generic confirmation component for backend MCP tools (restart_router, rent_movie)
// =============================================================================
function ConfirmationDialog({ message, options, details, onConfirm, onCancel }) {
  return (
    <div className="confirmation-card">
      <div className="confirmation-header">
        <span className="confirmation-icon">⚠️</span>
        <h3>Confirmation Required</h3>
      </div>
      
      <p className="confirmation-message">{message}</p>
      
      {/* Optional details section for warnings or additional info */}
      {details && (
        <div className="warning-box">
          <p dangerouslySetInnerHTML={{ __html: details }} />
        </div>
      )}
      
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

function RentalPayment({ data, onConfirm, onCancel }) {
  return (
    <div className="rental-payment-panel">
      <div className="rental-payment-card">
        <div className="rental-header">
          <span>🎬</span>
          <h3>Rent Movie</h3>
        </div>
        <div className="rental-details">
          <p className="movie-title">{data.title}</p>
          <div className="rental-info">
            <div className="info-row">
              <span className="label">Rental Period:</span>
              <span className="value">{data.rental_period || '48 hours'}</span>
            </div>
            <div className="info-row">
              <span className="label">Price:</span>
              <span className="value price">${data.rental_price?.toFixed(2)}</span>
            </div>
          </div>
          <p className="rental-note">
            💡 You'll have access to this movie for 48 hours after purchase
          </p>
        </div>
        <div className="rental-actions">
          <button onClick={() => onConfirm('Rent Now')} className="rent-btn">
            Rent Now - ${data.rental_price?.toFixed(2)}
          </button>
          <button onClick={onCancel} className="cancel-btn">
            Cancel
          </button>
        </div>
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
  const [videoPlayer, setVideoPlayer] = useState(null)  // For play_video
  const messagesEndRef = useRef(null)

  const client = new Client({ apiUrl: 'http://localhost:2024' })

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
      // DYNAMIC TOOL ADVERTISEMENT: Send tool schemas from frontend
      const filteredSchemas = CLIENT_TOOL_SCHEMAS.filter(s => 
        ADVERTISED_CLIENT_TOOLS.includes(s.name)
      )
      const stream = client.runs.stream(threadId, 'supervisor', {
        input: { messages: [{ role: 'user', content: userMessage }] },
        config: {
          configurable: {
            client_tool_schemas: filteredSchemas
          }
        },
        streamMode: ['messages', 'custom'],  // Stream messages + custom events (for UI)
      })

      let assistantMessage = ''
      let currentInterrupt = null

      for await (const chunk of stream) {
        console.log('📦 Stream chunk:', chunk.event)
        
        // Handle custom events (UI messages from push_ui_message)
        if (chunk.event === 'custom') {
          const customData = chunk.data
          console.log('🎨 Custom event received:', customData)
          
          // UI messages come through as custom events
          if (customData.name === 'play_video') {
            console.log('🎬 Video player custom event:', customData.props)
            setVideoPlayer({
              video_url: customData.props?.video_url,
              title: customData.props?.title
            })
          }
        }
        
        // Handle regular messages
        if (chunk.event === 'messages/partial' || chunk.event === 'messages/complete') {
          const messages = chunk.data || []
          
          for (const message of messages) {
            const content = message?.content
            
            // Extract text from AI messages for display
            if (message?.type === 'ai' && content) {
              if (typeof content === 'string') {
            assistantMessage = content
          } else if (Array.isArray(content)) {
                const text = content.map(c => c.text || '').join('')
                if (text) {
                  assistantMessage = text
                }
              }
            }
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
        
        /*
         * AG UI INTERRUPT PATTERNS
         * 
         * Middleware-based HITL interrupts (both restart_router and rent_movie)
         * Structure: interrupt.value.action_requests[0] = {name, args}
         * Configured in agent middleware via HumanInTheLoopMiddleware
         * 
         * Note: interrupt() cannot be called inside MCP tools because they run in 
         * a separate process without access to the LangGraph runnable context.
         */
        
        // Check for middleware HITL interrupt
        if (currentInterrupt.value?.action_requests) {
          const actionRequest = currentInterrupt.value.action_requests[0]
          console.log('Middleware HITL interrupt detected:', actionRequest)
          
          if (actionRequest) {
            const toolName = actionRequest.name
            const toolArgs = actionRequest.args
            
            // Restart router: Generic ConfirmationDialog
            if (toolName === 'restart_router') {
              setInterruptType('confirmation')
              setInterruptData({
                message: 'Are you sure you want to restart your router?',
                options: ['Yes, Restart Router'],
                details: '<strong>⚠️ This will restart your router</strong><br/>Your internet connection will be offline for approximately 2 minutes.'
              })
            }
            // Rent movie: Custom RentalPayment component
            else if (toolName === 'rent_movie') {
              setInterruptType('rental_payment')
              setInterruptData({
                title: toolArgs.title,
                video_url: toolArgs.video_url,
                rental_price: toolArgs.rental_price,
                rental_period: '48 hours'
              })
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


  // Handle confirmation dialog selection (middleware HITL)
  const handleConfirmationSelect = async (selectedOption) => {
    if (!interrupt) return

    setIsLoading(true)
    setMessages((prev) => [
      ...prev,
      { role: 'system', content: `✅ Selected: ${selectedOption}` },
    ])

    try {
      // Resume with the selected option
      // For middleware HITL, send editedAction with selected_option
      const actionRequest = interrupt.value?.action_requests?.[0]
      const filteredSchemas = CLIENT_TOOL_SCHEMAS.filter(s => 
        ADVERTISED_CLIENT_TOOLS.includes(s.name)
      )
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
            client_tool_schemas: filteredSchemas
          }
        },
        streamMode: ['messages', 'custom'],  // Stream messages + custom events (for UI)
      })

      let assistantMessage = ''
      let currentInterrupt = null

      for await (const chunk of stream) {
        console.log('📦 Resume stream chunk:', chunk.event)
        
        // Handle custom events (UI messages from push_ui_message)
        if (chunk.event === 'custom') {
          const customData = chunk.data
          console.log('🎨 Custom event received during resume:', customData)
          
          // UI messages come through as custom events
          if (customData.name === 'play_video') {
            console.log('🎬 Video player custom event:', customData.props)
            setVideoPlayer({
              video_url: customData.props?.video_url,
              title: customData.props?.title
            })
          }
        }
        
        // Handle regular messages
        if (chunk.event === 'messages/partial' || chunk.event === 'messages/complete') {
          const messages = chunk.data || []
          
          for (const message of messages) {
            const content = message?.content
            
            // Extract text from AI messages for display
            if (message?.type === 'ai' && content) {
              if (typeof content === 'string') {
            assistantMessage = content
          } else if (Array.isArray(content)) {
                const text = content.map(c => c.text || '').join('')
                if (text) {
                  assistantMessage = text
                }
              }
            }
          }
        }
        
        // Check for NEW interrupts
        if (chunk.data?.__interrupt__) {
          currentInterrupt = chunk.data.__interrupt__[0]
          console.log('New interrupt detected during resume:', currentInterrupt)
        }
      }

      if (assistantMessage) {
        setMessages((prev) => [...prev, { role: 'assistant', content: assistantMessage }])
      }

      // Handle new interrupt if one appeared
      if (currentInterrupt) {
        setInterrupt(currentInterrupt)
        
        const actionRequest = currentInterrupt.value?.action_requests?.[0]
        
        if (actionRequest) {
          const toolName = actionRequest.name
          const toolArgs = actionRequest.args
          
          // Backend MCP tools that use generic ConfirmationDialog
          if (toolName === 'restart_router' || toolName === 'rent_movie') {
            setInterruptType('confirmation')
            let confirmationData = {
              message: toolArgs.message || `Confirm ${toolName}?`,
              options: toolArgs.options || ['Confirm'],
            }
            
            if (toolName === 'restart_router') {
              confirmationData.details = '<strong>⚠️ This will restart your router</strong><br/>Your internet connection will be offline for approximately 2 minutes.'
              confirmationData.message = 'Are you sure you want to restart your router?'
              confirmationData.options = ['Yes, Restart Router']
            }
            
            if (toolName === 'rent_movie') {
              confirmationData.message = `Rent "${toolArgs.title}" for $${toolArgs.rental_price?.toFixed(2)}?`
              confirmationData.options = ['Rent Now']
              confirmationData.details = `You'll have access to this movie for 48 hours after purchase.`
            }
            
            setInterruptData(confirmationData)
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
      const filteredSchemas = CLIENT_TOOL_SCHEMAS.filter(s => 
        ADVERTISED_CLIENT_TOOLS.includes(s.name)
      )
      
      // All interrupts now use middleware format
      const resumeCommand = { decisions: [{ type: 'reject', message: 'User cancelled this action' }] }
      
      const stream = client.runs.stream(threadId, 'supervisor', {
        command: {
          resume: resumeCommand,
        },
        config: {
          configurable: {
            client_tool_schemas: filteredSchemas
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
      const filteredSchemas = CLIENT_TOOL_SCHEMAS.filter(s => 
        ADVERTISED_CLIENT_TOOLS.includes(s.name)
      )
      const stream = client.runs.stream(threadId, 'supervisor', {
        command: {
          resume: { decisions: [{ type: 'approve' }] },
        },
        config: {
          configurable: {
            client_tool_schemas: filteredSchemas
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
          
          // Backend MCP tools that use generic ConfirmationDialog
          if (toolName === 'restart_router' || toolName === 'rent_movie') {
            setInterruptType('confirmation')
            let confirmationData = {
              message: toolArgs.message || `Confirm ${toolName}?`,
              options: toolArgs.options || ['Confirm'],
            }
            
            if (toolName === 'restart_router') {
              confirmationData.details = '<strong>⚠️ This will restart your router</strong><br/>Your internet connection will be offline for approximately 2 minutes.'
              confirmationData.message = 'Are you sure you want to restart your router?'
              confirmationData.options = ['Yes, Restart Router']
            }
            
            if (toolName === 'rent_movie') {
              confirmationData.message = `Rent "${toolArgs.title}" for $${toolArgs.rental_price?.toFixed(2)}?`
              confirmationData.options = ['Rent Now']
              confirmationData.details = `You'll have access to this movie for 48 hours after purchase.`
            }
            
            setInterruptData(confirmationData)
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
        
        {/* Middleware HITL: Generic ConfirmationDialog for backend MCP tools (restart_router) */}
        {interrupt && interruptType === 'confirmation' && (
          <div className="interrupt-panel">
            <ConfirmationDialog
              message={interruptData?.message || 'Please confirm this action'}
              options={interruptData?.options || ['Confirm']}
              details={interruptData?.details}
              onConfirm={handleConfirmationSelect}
              onCancel={handleCancel}
            />
          </div>
        )}

        {/* Middleware HITL: Custom RentalPayment component (rent_movie) */}
        {interrupt && interruptType === 'rental_payment' && (
          <div className="interrupt-panel">
            <RentalPayment
              data={interruptData}
              onConfirm={handleConfirmationSelect}
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
