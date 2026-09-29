# Loopline

Ambient voice triage. Open a tab, talk — a bug, a reminder, a stray idea, all
in one breath — stop, and Loopline splits what you said into discrete items,
classifies each one, and actually files it: a real GitHub issue, a real
Notion page. Then it hands you back a digest with links to what it did.

Built for the AssemblyAI - Voice Agent Hackathon (lablab.ai).

This is **not a phone-based agent** — there's no Twilio, no phone number, no
per-minute call cost. Capture happens entirely in the browser, which is a
better fit for "ambient, while you work" anyway, and it means the whole
thing runs on free tiers.

## How it actually works (read this first)

Two things happen, and they are **deliberately separate**:

1. **Live**: you open the page, talk, AssemblyAI's Voice Agent API
   transcribes it in real time. The agent barely talks back — it's designed
   to listen, not converse.
2. **After you stop**: your own backend fetches the full transcript, splits
   it into discrete items, classifies each one, and — only then — creates
   real GitHub issues (and optionally Notion pages) via MCP. This all
   happens in the few seconds after you click "Process this capture."

Nothing about GitHub/Notion can break your live capture, because they're
never touched while you're actually talking.

```
Browser mic → AssemblyAI Voice Agent → session ends → fetch transcript
  → segment into items → classify each (type + destination + confidence)
  → file via MCP (GitHub / Notion) → digest with real links
```

## What's in here

```
loopline/
├── agents/ambient.jsonc          # the capture agent - listens, barely talks
├── deployment/browser/
│   ├── server.py                 # serves the page, mints tokens, runs /process
│   ├── index.html                # Start/Stop, live transcript, Digest tab
│   └── app.js                    # WebSocket capture + digest rendering
├── processor/
│   ├── fetch_session.py          # pulls the finished session's transcript
│   ├── segment.py                # LLM call → list of discrete items
│   ├── classify.py               # LLM call → type/destination/confidence per item
│   ├── digest.py                 # builds the final recap
│   ├── pipeline.py               # orchestrates all of the above
│   └── mcp_clients/
│       ├── github_client.py      # MCP client → GitHub (build this first)
│       └── notion_client.py      # MCP client → Notion (stretch goal)
├── lib.py, publish.py            # from AssemblyAI's own starter, unmodified
├── requirements.txt
├── .env.example
└── render.yaml                   # one-click-ish deploy config
```

## Prerequisites

- Python 3.10+
- An AssemblyAI account with hackathon credits — sign up through the
  hackathon's own link (not a generic signup) so the credits attach, and
  accept cookies during sign-up.
- A GitHub account and **one scratch/test repository** you don't mind
  filling with test issues.
- (Only for the Notion stretch goal) Node.js/npx installed, and a Notion
  account.

## Setup

```bash
cd loopline
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Open `.env` and fill in:
- `ASSEMBLYAI_API_KEY` — from your dashboard
- `GITHUB_PAT` — a **fine-grained** token
  (github.com/settings/personal-access-tokens/new), scoped to **one repo
  only**, with Issues: Read and write. Never use a broad classic token here.
- `GITHUB_REPO` — `owner/repo` of that same scratch repo

Leave the Notion lines commented out for now.

## Run it

```bash
python publish.py                # publishes agents/ambient.jsonc, prints its id
python deployment/browser/server.py
```

Open the printed `http://localhost:3000` URL. Click **Start call**, talk for
20-30 seconds mixing a few unrelated things (a bug, a reminder, a stray
idea), click **End call**, then click **Process this capture**. Watch the
Digest tab.

## Test in this order — don't skip to the end

Each layer here can fail for a different reason. Testing them in isolation
means when something breaks, you know exactly where, instead of debugging
"the whole pipeline doesn't work."

**1. GitHub MCP client, alone, with fake data:**
```bash
python -m processor.mcp_clients.github_client <owner> <repo>
```
This should create a real issue titled "Loopline test issue - safe to
delete" on your scratch repo. Go check that it's actually there. If it
errors with a tool-not-found message, the error message itself lists every
tool the server actually offers — update `CREATE_ISSUE_CANDIDATES` at the
top of `github_client.py` with the real name and try again.

**2. Segmentation, on canned text, not live audio:**
```bash
python -m processor.segment
```
Prints a numbered list from a hardcoded sample ramble. Confirm it actually
splits into separate items before trusting it on real speech.

**3. Classification, on canned text:**
```bash
python -m processor.classify
```

**4. A real session's transcript, once you've done at least one live call:**
```bash
python processor/fetch_session.py <session_id>
```
Get `<session_id>` from the browser page's Events tab (it's logged on
`session.ready`), or from your own terminal output.

**5. The full pipeline, end to end, on a real session:**
```bash
python -m processor.pipeline <session_id>
```
Prints the full digest as JSON. Once this looks right, the "Process this
capture" button in the browser is just this same code path.

**6. Bluejay simulations** (AssemblyAI's own tool for running simulated
callers against your agent and scoring the results) — use this once the
above all work, to throw a wider variety of synthetic rambles at the
capture step and catch edge cases before you demo live:
https://www.assemblyai.com/docs/voice-agents/voice-agent-api/test-with-bluejay

**Edge cases worth checking on purpose:** a capture with only one item (not
four), a long silence, something genuinely ambiguous (low confidence), and
speech with a lot of filler words.

## Deploy

```bash
git init && git add -A && git commit -m "Loopline"
git remote add origin <your-empty-github-repo-url>
git push -u origin main
```

Then on Render: **New → Blueprint**, point it at this repo — `render.yaml`
handles the rest. It will prompt for `ASSEMBLYAI_API_KEY`, `GITHUB_PAT`, and
`GITHUB_REPO`. Free tier cold-starts after inactivity, so open the deployed
URL yourself a few minutes before you demo it to judges.

**Notion on Render:** the Notion client spawns `npx` as a subprocess, which
needs Node available in the runtime. Render's plain Python service doesn't
include it. If you build the Notion stretch goal, it'll work locally (where
you already have Node) but needs a Docker-based Render service to deploy —
don't burn time on this unless GitHub is completely solid first.

## Governance (why some things are deliberately conservative)

- Nothing is filed silently. Processing only runs when you click the
  button, and the digest shows exactly what happened to every item.
- Anything below `CONFIDENCE_THRESHOLD` (0.4, in `pipeline.py`) is filed
  nowhere and flagged "needs review" instead of guessed at.
- The GitHub PAT is scoped to one repo's issues only, on purpose. Don't
  widen it.
- `classify.py`'s prompt explicitly tells the model to mark anything that
  looks like a password or secret as `skip` rather than filing it anywhere.

## Honest notes on things I couldn't verify for you

- **The exact MCP tool names GitHub and Notion expose** aren't hardcoded
  blindly — both clients look at what the server actually lists and pick a
  matching name from a short candidate list (see `CREATE_ISSUE_CANDIDATES`
  / `CREATE_PAGE_CANDIDATES`). If a server updates and renames its tool,
  the error message tells you the real name so you can fix one line.
- **The exact shape of the session `timeline` artifact** — AssemblyAI's own
  docs describe it as "each turn pairing `user_transcript` with
  `agent_text`," but `fetch_session.py` is written to tolerate a couple of
  plausible variations, and to print the raw JSON if it genuinely can't
  find the transcript, rather than silently extracting nothing.

If either of those needs adjusting, the error messages are written to tell
you exactly what to change and where.
#
