"""Event log helper. Every autonomous action calls log() with rationale."""

from __future__ import annotations

import json
from typing import Any, Literal

from agents.db import connect

Level = Literal["debug", "info", "warn", "error", "blocked", "autopaused", "autorolledback"]


def log(
    agent: str,
    event_type: str,
    *,
    level: Level = "info",
    clip_id: str | None = None,
    payload: dict[str, Any] | None = None,
    rationale: str | None = None,
) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO events (agent, level, event_type, clip_id, payload_json, rationale)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                agent,
                level,
                event_type,
                clip_id,
                json.dumps(payload) if payload else None,
                rationale,
            ),
        )
