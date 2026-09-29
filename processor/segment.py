"""Split one continuous ramble into discrete, unrelated items.

A single ambient capture often contains several unrelated things said back
to back. AssemblyAI's own turn boundaries (pause-based) don't reliably line
up with *topic* boundaries, so this does a semantic re-segmentation pass
with an LLM instead of trusting pauses.
"""

from __future__ import annotations

import json

from processor import llm_gateway

SYSTEM_PROMPT = """You split a transcript of someone rambling out loud into \
discrete, self-contained items. Each item is one thought: a bug, an idea, a \
reminder, a decision, a note - anything that could stand alone.

Rules:
- If the whole transcript is really just one thought, return one item.
- Don't invent content. Every item's text must be lifted from the transcript, \
  lightly cleaned up (remove filler words like "um" and false starts), never \
  rewritten or embellished.
- Preserve the original wording and meaning as closely as possible.
- CRITICAL: the transcript given to you is the ONLY source of content. Never \
  reuse or reproduce any wording from these instructions themselves - every \
  word in your output must come from what the speaker actually said.

Respond with ONLY a JSON array of strings, nothing else, matching this shape:
["<first distinct thought, in the speaker's own words>", "<second distinct thought, in the speaker's own words>"]
"""

def split(transcript: str) -> list[str]:
    transcript = transcript.strip()
    if not transcript:
        return []
    content = llm_gateway.chat(SYSTEM_PROMPT, transcript, max_tokens=1000)
    try:
        items = json.loads(content)
    except json.JSONDecodeError as err:
        raise ValueError(
            f"Segmentation model didn't return valid JSON. Raw response:\n{content}"
        ) from err
    if not isinstance(items, list):
        raise ValueError(f"Expected a JSON array of strings, got: {content}")
    return [str(item).strip() for item in items if str(item).strip()]


if __name__ == "__main__":
    import sys
    from lib import load_env, required  # noqa: E402

    sys.path.insert(0, ".")
    load_env()
    required("ASSEMBLYAI_API_KEY")

    sample = (
        "okay so first thing the checkout button is broken on mobile, "
        "someone reported it yesterday um also I need to remember to email "
        "sara about the contract renewal before friday and actually one "
        "more thing what if we added a dark mode toggle, could be a nice "
        "quick win"
    )
    for i, item in enumerate(split(sample), 1):
        print(f"{i}. {item}")