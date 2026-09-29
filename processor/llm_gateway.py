"""Shared AssemblyAI LLM Gateway request helper, with retry-on-rate-limit.
segment.py and classify.py both go through this - one place to get retry
behavior right instead of two copies that could drift.
"""

from __future__ import annotations

import os
import re
import time

import httpx

URL = "https://llm-gateway.assemblyai.com/v1/chat/completions"


def _model() -> str:
    return os.environ.get("LOOPLINE_LLM_MODEL", "qwen3.5-4b-32k-fast")


def chat(system_prompt: str, user_content: str, max_tokens: int, max_retries: int = 4) -> str:
    """POST to the LLM Gateway, retrying on 429 with backoff (honoring
    Retry-After when the server sends one). Returns the assistant's raw text."""
    api_key = os.environ["ASSEMBLYAI_API_KEY"]
    last_err = None

    for attempt in range(max_retries):
        resp = httpx.post(
            URL,
            headers={"authorization": api_key, "content-type": "application/json"},
            json={
                "model": _model(),
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                "max_tokens": max_tokens,
            },
            timeout=60,
        )
        if resp.status_code == 429:
            wait = float(resp.headers.get("retry-after", 2 ** attempt))
            last_err = f"429 rate limited (attempt {attempt + 1}/{max_retries}), waiting {wait}s"
            print(f"[llm_gateway] {last_err}")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return re.sub(r"^```(json)?|```$", "", content.strip(), flags=re.MULTILINE).strip()

    raise RuntimeError(
        f"LLM Gateway still rate-limited after {max_retries} retries. {last_err}. "
        "Wait a minute before retrying, or check your rate limit in the dashboard."
    )