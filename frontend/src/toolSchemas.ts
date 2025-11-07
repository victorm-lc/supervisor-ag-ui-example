/**
 * AG UI Tool Schema Definitions (AG UI Protocol Compliant)
 * 
 * These tool schemas follow the official AG UI Protocol specification:
 * https://docs.ag-ui.com/concepts/tools
 * 
 * HOW IT WORKS (LangGraph Generative UI Pattern):
 * 1. Frontend advertises these tool schemas to backend
 * 2. Backend dynamically creates LangChain tools from schemas
 * 3. When agent calls tool (e.g., play_video), the tool:
 *    - Pushes UI message through dedicated UI channel via push_ui_message()
 *    - Returns text confirmation to agent
 * 4. Frontend receives UI messages and renders components
 * 
 * MULTI-CLIENT SUPPORT (Version-Agnostic):
 * - Web app: Advertises all tools ['play_video', 'network_status']
 * - Mobile app: Advertises subset ['play_video'] only
 * - CLI: Advertises none [] (text only)
 * Backend creates tools based on what each client supports.
 * 
 * This pattern allows:
 * - Frontend teams to own UI tool definitions
 * - Backend to be version-agnostic (works with any tool schema)
 * - New app versions to add tools without backend changes
 * - Clean separation: messages vs UI data
 * - No JSON parsing needed - props are structured objects
 * 
 * AG UI Spec Compliance:
 * ✅ name, description, parameters follow official AG UI Tool interface
 * ✅ Agents call tools normally (no special syntax)
 * ✅ Works with any AG UI-compliant tool definition
 * 
 * Extensions to AG UI spec:
 * - domains: Frontend-owned domain mapping for version-agnostic tool filtering
 */

/**
 * JSON Schema property definition (AG UI standard)
 */
export interface JSONSchemaProperty {
  type: 'string' | 'number' | 'boolean' | 'object' | 'array'
  description: string
  enum?: any[]  // For constrained values (e.g., ["low", "medium", "high"])
  items?: JSONSchemaProperty  // For array types
  properties?: Record<string, JSONSchemaProperty>  // For object types
}

/**
 * AG UI Tool Schema (following official protocol)
 */
export interface AGUIToolSchema {
  name: string
  description: string
  parameters: {
    type: 'object'
    properties: Record<string, JSONSchemaProperty>
    required: string[]
  }
  // Extensions:
  domains: string[]  // Frontend-owned: which domain agents can use this tool
}

/**
 * CLIENT TOOL SCHEMAS
 * 
 * All UI tools that this frontend can render.
 * The frontend advertises which of these it wants to use (via ADVERTISED_CLIENT_TOOLS).
 */
export const CLIENT_TOOL_SCHEMAS: AGUIToolSchema[] = [
  {
    name: 'play_video',
    description: 'Play a video in the frontend YouTube player. Pushes UI message to render VideoPlayer React component.',
    parameters: {
      type: 'object',
      properties: {
        video_url: {
          type: 'string',
          description: 'YouTube embed URL (e.g., https://www.youtube.com/embed/VIDEO_ID)',
        },
        title: {
          type: 'string',
          description: 'Title of the video',
        },
      },
      required: ['video_url', 'title'],
    },
    domains: ['video'],
  },
  {
    name: 'network_status_display',
    description: 'Display a network status card in the frontend. This tool triggers the NetworkStatusCard React component.',
    parameters: {
      type: 'object',
      properties: {
        status_data: {
          type: 'object',
          description: 'Network status data to display',
        },
      },
      required: ['status_data'],
    },
    domains: ['wifi'],
  },
]

/**
 * VERSION COMPATIBILITY EXAMPLE
 * 
 * App Version 1.0 (older):
 * - Advertises: ['play_video'] with domains: ['video']
 * - Backend receives 1 schema and creates 1 tool for video agent
 * - Works perfectly ✅
 * 
 * App Version 2.0 (newer):
 * - Advertises: ['play_video', 'network_status_display']
 * - Each tool specifies which domains can use it
 * - Backend receives 2 schemas and filters by domain automatically
 * - Works automatically ✅ (no backend changes needed!)
 * 
 * App Version 3.0 (future):
 * - Advertises: ['play_video', 'network_status_display', 'advanced_video_controls']
 * - New tool includes domain metadata (e.g., domains: ['video'])
 * - Backend receives 3 schemas, filters by domain, creates tools
 * - New tool works automatically ✅
 * 
 * DOMAIN MAPPING (Frontend-Owned):
 * - Frontend controls which tools belong to which domain agents
 * - Tools can belong to multiple domains (e.g., error_display)
 * - No backend code changes needed when reassigning domains
 */

