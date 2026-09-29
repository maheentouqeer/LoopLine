"""Build the recap: everything heard, where it went, with real links.

This is the trust mechanism - see the README's Governance section. Nothing
is filed silently; the digest is proof of exactly what happened.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class FiledItem:
    text: str
    type: str
    destination: str
    confidence: float
    status: str  # "filed", "skipped", "low_confidence", "error"
    url: str | None = None
    detail: str = ""


def build(session_id: str, transcript: str, items: list[FiledItem]) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "transcript": transcript,
        "item_count": len(items),
        "items": [asdict(i) for i in items],
        "summary": {
            "filed": sum(1 for i in items if i.status == "filed"),
            "skipped": sum(1 for i in items if i.status == "skipped"),
            "needs_review": sum(1 for i in items if i.status == "low_confidence"),
            "errors": sum(1 for i in items if i.status == "error"),
        },
    }
