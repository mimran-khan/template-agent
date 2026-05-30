"""Non-blocking context injection and HITL interaction controls.

Provides three interaction modes for deep agents:
- /btw: Non-blocking context injection via Redis side-channel
- Tool approval: Blocking gates for dangerous tool execution
- Plan review: Blocking review for multi-step plans
"""
