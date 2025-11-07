"""
Shared utilities for subagent invocation.

Provides helpers for common subagent patterns like UI message propagation.
"""

from typing import Any, Dict
from langgraph.graph.ui import push_ui_message


def propagate_ui_messages(subagent_result: Dict[str, Any]) -> None:
    """
    Propagate UI messages from a subagent's state to the parent supervisor's state.
    
    LangGraph subagents have their own UI state channel, but UI messages don't
    automatically bubble up to the parent. This helper re-pushes them to the
    supervisor's context so they reach the frontend.
    
    Args:
        subagent_result: The result dict from subagent.ainvoke(), containing
                        'messages' and 'ui' keys.
    
    Example:
        result = await video_agent.ainvoke({"messages": [...]}, config=runtime.config)
        propagate_ui_messages(result)  # ← Makes UI messages reach frontend
        return result["messages"][-1].content
    """
    ui_messages = subagent_result.get("ui", [])
    
    if not ui_messages:
        return
    
    print(f"🎨 [SUBAGENT] Propagating {len(ui_messages)} UI messages to supervisor")
    
    for ui_msg in ui_messages:
        name = ui_msg.get("name")
        props = ui_msg.get("props", {})
        
        if not name:
            print(f"⚠️ [SUBAGENT] Skipping UI message with no name: {ui_msg}")
            continue
        
        print(f"  ↳ Pushing UI message: {name} with props {props}")
        push_ui_message(name, props)

