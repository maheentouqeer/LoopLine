"""Classify every segmented item - type, destination, confidence, and a
ready-to-file title/body for each.

Tries ONE batched call first (fast, lower rate-limit risk). If the model
ever returns the wrong number of results for that batch - which happens
occasionally with smaller/faster models - falls back to classifying each
item individually instead of silently failing the whole batch. Slower, but
each individual call is guaranteed to produce exactly one result.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from processor import llm_gateway

BATCH_PROMPT = """You triage a numbered list of items from someone's spoken \
notes and decide where each one belongs.

Valid "type" values: "bug", "idea", "reminder", "decision", "note".
Valid "destination" values: "github", "notion", "skip".
- "github": something actionable and technical - a bug, a task, a feature idea.
- "notion": a decision or note worth keeping but not actionable as a ticket.
- "skip": too vague to be a real item, or anything that looks like a \
  password/secret/token - never file credentials anywhere, mark them "skip".

Give each item a "confidence" from 0 to 1 - lower it if genuinely ambiguous.
For "github", include "title" (short, imperative) and "body" (1-2 sentences).
For "notion", include "title" (short) and "body" (the content, cleaned up).
For "skip", omit title/body.

CRITICAL: you MUST return exactly as many objects as there are numbered \
items below, one each, in the SAME ORDER. Never merge two items into one \
object. Never omit an item, even if it seems similar to another.

Respond with ONLY a JSON array, nothing else:
[{"type": "...", "destination": "...", "confidence": 0.0, "title": "...", "body": "..."}, ...]
"""

SINGLE_PROMPT = """You triage ONE item from someone's spoken notes and decide \
where it belongs. Same rules as batch triage:

Valid "type": "bug", "idea", "reminder", "decision", "note".
Valid "destination": "github" (actionable/technical), "notion" (a note or \
decision, not actionable), "skip" (too vague, or looks like a credential - \
never file secrets).
Include "confidence" (0-1), and for github/notion a "title" and "body".

Respond with ONLY a JSON object, nothing else:
{"type": "...", "destination": "...", "confidence": 0.0, "title": "...", "body": "..."}
"""


@dataclass
class ClassifiedItem:
    text: str
    type: str
    destination: str
    confidence: float
    title: str = ""
    body: str = ""
    error: str = ""


def _build_item(text: str, data: dict) -> ClassifiedItem:
    return ClassifiedItem(
        text=text,
        type=data.get("type", "note"),
        destination=data.get("destination", "skip"),
        confidence=float(data.get("confidence") or 0),
        title=data.get("title", ""),
        body=data.get("body", ""),
    )


def _classify_one(text: str) -> ClassifiedItem:
    content = llm_gateway.chat(SINGLE_PROMPT, text, max_tokens=300)
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            return _build_item(text, data)
    except json.JSONDecodeError:
        pass
    return ClassifiedItem(text=text, type="note", destination="skip", confidence=0.0,
                           error=f"classification failed. Raw: {content[:200]}")


def classify_all(items: list[str]) -> list[ClassifiedItem]:
    if not items:
        return []

    numbered = "\n".join(f"{i + 1}. {text}" for i, text in enumerate(items))
    content = llm_gateway.chat(BATCH_PROMPT, numbered, max_tokens=250 * len(items) + 200)

    try:
        results = json.loads(content)
    except json.JSONDecodeError:
        results = None

    if isinstance(results, list) and len(results) == len(items):
        return [
            _build_item(text, data) if isinstance(data, dict) else _classify_one(text)
            for text, data in zip(items, results)
        ]

    got = len(results) if isinstance(results, list) else "invalid JSON"
    print(f"[classify] batch returned {got} results for {len(items)} items - "
          f"falling back to one call per item")
    return [_classify_one(text) for text in items]


if __name__ == "__main__":
    import sys
    from lib import load_env, required  # noqa: E402

    sys.path.insert(0, ".")
    load_env()
    required("ASSEMBLYAI_API_KEY")

    samples = [
        "Bug: the login button doesn't work on Safari",
        "Remind me to email Sara about the contract renewal before Friday",
        "What if we added a dark mode toggle, could be a nice quick win",
    ]
    for item in classify_all(samples):
        print(item)