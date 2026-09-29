"""Pull the transcript for a finished Voice Agent session.

The Voice Agent API stores every call as a "session" and hands back
pre-signed download URLs for its artifacts (audio, timeline, metadata) from

    GET https://agents.assemblyai.com/v1/sessions/{session_id}

The `timeline` artifact is the conversation as JSON. AssemblyAI's own docs
describe it as "each turn pairing user_transcript with agent_text" - but the
exact key names can vary by account/version, so this module is written to be
tolerant: it prints the raw shape the first time it sees something
unexpected, instead of silently guessing wrong. If extraction ever looks off,
run this file directly against a real session id and read what it prints.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib import ApiError, aai, load_env, required  # noqa: E402


def _download(url: str) -> Any:
    """Artifact URLs are pre-signed - no Authorization header, and they expire,
    so fetch promptly after the session ends."""
    resp = httpx.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _extract_transcript(timeline: Any) -> str:
    """Best-effort extraction of just the user's spoken words, concatenated
    in order. Handles a few plausible shapes; falls back to dumping the raw
    JSON into the error so you can see exactly what came back and adjust."""
    turns = None
    if isinstance(timeline, list):
        turns = timeline
    elif isinstance(timeline, dict):
        for key in ("turns", "conversation", "messages", "events"):
            if isinstance(timeline.get(key), list):
                turns = timeline[key]
                break
    if turns is None:
        raise ValueError(
            "Could not find a list of turns in the timeline artifact. "
            "Raw shape was:\n" + json.dumps(timeline, indent=2)[:2000]
        )

    pieces: list[str] = []
    for turn in turns:
        if not isinstance(turn, dict):
            continue
        # Try the documented field name first, then a couple of plausible
        # alternates so this keeps working even if the exact key differs.
        text = (
            turn.get("user_transcript")
            or turn.get("transcript")
            or (turn.get("role") == "user" and turn.get("text"))
            or None
        )
        if text:
            pieces.append(str(text).strip())

    transcript = " ".join(p for p in pieces if p)
    if not transcript:
        raise ValueError(
            "Found turns but extracted no user speech. Raw timeline was:\n"
            + json.dumps(timeline, indent=2)[:2000]
        )
    return transcript


def get_transcript(session_id: str) -> str:
    """Fetch a session's artifacts and return the user's speech as one
    string, ready to hand to segment.split()."""
    session = aai(f"/sessions/{session_id}")
    artifacts = session.get("artifacts", [])
    timeline_url = next(
        (a["url"] for a in artifacts if a.get("type") == "timeline"), None
    )
    if not timeline_url:
        raise ValueError(
            f"Session {session_id} has no timeline artifact yet - it may "
            "still be processing. Wait a few seconds and retry, or check "
            f"`status` in: {json.dumps(session, indent=2)[:500]}"
        )
    timeline = _download(timeline_url)
    return _extract_transcript(timeline)


if __name__ == "__main__":
    # Run directly to sanity-check a real session before wiring it into the
    # full pipeline:  python processor/fetch_session.py <session_id>
    load_env()
    required("ASSEMBLYAI_API_KEY", "get one at https://www.assemblyai.com/dashboard/api-keys")
    if len(sys.argv) < 2:
        sys.exit("Usage: python processor/fetch_session.py <session_id>")
    try:
        print(get_transcript(sys.argv[1]))
    except ApiError as err:
        sys.exit(str(err))
