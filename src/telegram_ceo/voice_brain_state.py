"""
🧠 Voice Brain Dump — FSM State Management

Dict-based per-user state for voice brain dump pipeline.
Pattern matches existing _conditions_state, _new_task_state, etc.
"""

from dataclasses import dataclass, field


@dataclass
class VoiceBrainSession:
    """State for a single voice brain dump session."""
    raw_text: str = ""
    parsed_tasks: list = field(default_factory=list)
    proposals: list = field(default_factory=list)
    summary_text: str = ""
    message_id: int = 0
    iteration: int = 0


# Per-user state: user_id → VoiceBrainSession
_voice_brain_state: dict[int, VoiceBrainSession] = {}

MAX_ITERATIONS = 5


def is_in_voice_brain_mode(user_id: int) -> bool:
    """Check if user is currently in voice brain dump mode."""
    return user_id in _voice_brain_state


def get_voice_brain_session(user_id: int) -> VoiceBrainSession | None:
    """Get current session or None."""
    return _voice_brain_state.get(user_id)


def start_voice_brain_session(
    user_id: int,
    raw_text: str,
    parsed_tasks: list | None = None,
    proposals: list | None = None,
    summary_text: str = "",
    message_id: int = 0,
) -> VoiceBrainSession:
    """Start or restart a voice brain dump session."""
    session = VoiceBrainSession(
        raw_text=raw_text,
        parsed_tasks=parsed_tasks or [],
        proposals=proposals or [],
        summary_text=summary_text,
        message_id=message_id,
        iteration=0,
    )
    _voice_brain_state[user_id] = session
    return session


def update_voice_brain_session(
    user_id: int,
    raw_text: str | None = None,
    parsed_tasks: list | None = None,
    proposals: list | None = None,
    summary_text: str | None = None,
    message_id: int | None = None,
) -> VoiceBrainSession | None:
    """Update existing session fields. Increments iteration. Returns None if no session."""
    session = _voice_brain_state.get(user_id)
    if not session:
        return None
    if raw_text is not None:
        session.raw_text = raw_text
    if parsed_tasks is not None:
        session.parsed_tasks = parsed_tasks
    if proposals is not None:
        session.proposals = proposals
    if summary_text is not None:
        session.summary_text = summary_text
    if message_id is not None:
        session.message_id = message_id
    session.iteration += 1
    return session


def end_voice_brain_session(user_id: int) -> VoiceBrainSession | None:
    """End session and return it (or None if not active)."""
    return _voice_brain_state.pop(user_id, None)


def can_iterate(user_id: int) -> bool:
    """Check if session hasn't exceeded max iterations."""
    session = _voice_brain_state.get(user_id)
    if not session:
        return False
    return session.iteration < MAX_ITERATIONS
