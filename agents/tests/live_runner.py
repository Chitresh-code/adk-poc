"""Shared helper for running an agent live, the way `adk web` would.

InMemoryRunner is the same runner ADK's own CLI and web UI sit on top of, so
driving it directly from a script exercises real model calls and real tool
calls, session state included, without needing the web UI or a terminal
chat loop. Every test under agents/tests/ that talks to a real model or a
real emulator goes through this.
"""

from __future__ import annotations

from google.adk.agents import BaseAgent
from google.adk.events import Event
from google.adk.runners import InMemoryRunner
from google.genai import types

_APP_NAME = "adk-poc-live-test"
_USER_ID = "live-test-user"


async def run_agent_live(
    agent: BaseAgent,
    user_text: str,
    *,
    inline_file: tuple[bytes, str] | None = None,
) -> tuple[list[Event], dict]:
    """Runs agent to completion against a real model, returns (events, final_state).

    Args:
        agent: the root agent to run, e.g. rfp_agent.agent.root_agent.
        user_text: the user's chat message for this turn.
        inline_file: optional (data, mime_type), mirroring a file attached
            to the same turn in adk web.

    Returns:
        (events, final_state): every event yielded by the run, and the
        session's state dict once the run completes.
    """
    runner = InMemoryRunner(agent=agent, app_name=_APP_NAME)
    session = await runner.session_service.create_session(
        app_name=_APP_NAME, user_id=_USER_ID
    )

    parts = [types.Part(text=user_text)]
    if inline_file is not None:
        data, mime_type = inline_file
        parts.append(
            types.Part(inline_data=types.Blob(data=data, mime_type=mime_type))
        )

    events: list[Event] = []
    async for event in runner.run_async(
        user_id=_USER_ID,
        session_id=session.id,
        new_message=types.Content(role="user", parts=parts),
    ):
        events.append(event)

    final_session = await runner.session_service.get_session(
        app_name=_APP_NAME, user_id=_USER_ID, session_id=session.id
    )
    return events, dict(final_session.state)
