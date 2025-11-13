"""
UI State Extension for DeepAgents

This module defines a custom state schema that extends AgentState to include
a 'ui' channel for Generative UI messages, along with middleware functions
that ensure the state schema is applied to the deep agent.

Usage:
    from src.utils.ui_middleware import DeepAgentWithUIState, ui_state_middleware
    
    supervisor = create_deep_agent(
        model="...",
        subagents=[...],
        middleware=[ui_state_middleware],
        system_prompt="..."
    )

This replaces the need for custom wrappers like UIPropagatoingRunnable.
UI messages from subagents will automatically flow through the extended state.
"""

from typing import Annotated, Any, Sequence
from typing_extensions import NotRequired
from langchain.agents.middleware import AgentState, after_model
from langgraph.graph.ui import AnyUIMessage, ui_message_reducer
from langgraph.runtime import Runtime


class DeepAgentWithUIState(AgentState):
    """
    Extended agent state that includes a UI channel for Generative UI.
    
    This state schema extends the base AgentState to add a 'ui' field
    that uses ui_message_reducer for proper UI message handling.
    
    When used with middleware functions decorated with this state schema,
    UI messages from subagents propagate automatically to the supervisor.
    
    Attributes:
        ui: Sequence of UI messages that will be sent to the frontend.
            Uses ui_message_reducer for proper accumulation and deduplication.
    """
    ui: NotRequired[Annotated[Sequence[AnyUIMessage], ui_message_reducer]]


@after_model(state_schema=DeepAgentWithUIState)
def ui_state_middleware(state: DeepAgentWithUIState, runtime: Runtime) -> dict[str, Any] | None:
    """
    Middleware function that ensures the UI state schema is applied.
    
    This middleware is decorated with @after_model and specifies the
    DeepAgentWithUIState schema, which tells the agent to use that
    extended state schema with the UI channel.
    
    The middleware itself doesn't need to do anything - just by being
    present with the state_schema parameter, it ensures the agent uses
    the extended state with the UI field.
    
    Args:
        state: The agent state with UI channel
        runtime: The runtime context
        
    Returns:
        None (no state updates needed, UI propagation happens automatically)
    """
    # No state updates needed - UI messages propagate automatically
    # through the state schema's ui_message_reducer
    return None

