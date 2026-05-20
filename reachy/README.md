# Reachy Mini — Jarvis Gateway Profiles

## What this is

Custom profiles for Pollen Robotics' `reachy_mini_conversation_app` that connect
Scholar and Bridge to the Jarvis agent fleet via NATS. Both profiles use the
`ask_jarvis` tool to route questions through Jarvis to specialist agents
(study-tutor, architect, forge, product-owner) — the same routing that powers
the OpenWebUI interface.

**Status:** Working end-to-end as of 13 May 2026. Scholar successfully routes
voice questions through Jarvis to the architect and study-tutor agents, with
responses narrated through the Reachy Mini speaker.

## Architecture

```
                        ┌─── Study Tutor (Socratic tutoring)
User speaks             │
    ↓                   ├─── Architect (ADR review, design)
HF Realtime backend     │
    ↓                   ├─── Forge (build queuing, status)
ask_jarvis tool         │
    ↓                   └─── Product Owner (feature planning)
JarvisClient
    ↓
NATS request-reply ──► Jarvis ──► routes to agent ──► response
    ↓
HF narrates response through Reachy speaker
```

The HF backend also handles simple conversational turns locally (greetings,
follow-up questions, Socratic tutoring dialogue) without routing through Jarvis,
using the Scholar persona from `instructions.txt`.

## Quick Start

### 1. Clone the conversation app (one-time)

```bash
cd /Users/richardwoollcott/Projects/appmilla_github/
git clone https://github.com/pollen-robotics/reachy_mini_conversation_app.git
cd reachy_mini_conversation_app
uv sync
```

### 2. Install NATS client (one-time)

```bash
source .venv/bin/activate
pip install nats-py
```

### 3. Create .env file (one-time)

```bash
cp ../fleet-gateway/reachy/.env.example .env
```

Edit `.env` and set your NATS password:

```
NATS_URL=nats://rich:YOUR_PASSWORD_HERE@promaxgb10-41b1:4222
```

### 4. Launch Scholar

**Option A — launch script (recommended):**

```bash
cd /Users/richardwoollcott/Projects/appmilla_github/fleet-gateway/reachy/scripts
chmod +x launch_scholar.sh
./launch_scholar.sh              # headless (robot mic/speaker)
./launch_scholar.sh --gradio     # with Gradio UI (testing)
```

**Option B — manual:**

```bash
cd /Users/richardwoollcott/Projects/appmilla_github/reachy_mini_conversation_app
source .venv/bin/activate
export PYTHONPATH=/Users/richardwoollcott/Projects/appmilla_github/fleet-gateway:$PYTHONPATH
python -c "from reachy_mini_conversation_app.main import main; main()"
```

### 5. Verify

Watch the logs for:

```
✓ Loaded external tool: ask_jarvis
tool registered: ask_jarvis - Send a question to Jarvis...
Tools to be used in conversation: ['ask_jarvis', ...]
```

Then say: "Please ask Jarvis which agents are available."

## Prerequisites

- **Reachy Mini** on home WiFi, daemon running (verified via Reachy Mini Control app)
- **reachy_mini_conversation_app** cloned alongside fleet-gateway
- **nats-py** installed in the conversation app venv
- **Jarvis** running on GB10: `uv run jarvis serve-nats --nats nats://localhost:4222`
- **NATS server** running on GB10 (Docker: `ships-computer-nats`)
- **Tailscale** — MacBook and GB10 on the same tailnet

## .env Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `BACKEND_PROVIDER` | Yes | — | `huggingface` (free) or `openai` |
| `REACHY_MINI_CUSTOM_PROFILE` | Yes | — | `scholar` or `bridge` |
| `REACHY_MINI_EXTERNAL_PROFILES_DIRECTORY` | Yes | — | Path to `fleet-gateway/reachy/external_content/external_profiles` |
| `REACHY_MINI_EXTERNAL_TOOLS_DIRECTORY` | Yes | — | Path to `fleet-gateway/reachy/external_content/external_tools` |
| `NATS_URL` | Yes | — | NATS server with credentials, e.g. `nats://rich:pass@host:4222` |
| `HF_TOKEN` | No | — | HuggingFace token for gated models |

**Note:** `PYTHONPATH` must include the fleet-gateway root directory so external
tools can `from common.jarvis_client import JarvisClient`. This cannot go in `.env`
(python-dotenv doesn't modify sys.path). The launch script handles this automatically.

## Tools

### Shared (both profiles)

| Tool | Purpose | Backend |
|------|---------|---------|
| `ask_jarvis` | Route any question to Jarvis → specialist agent | NATS → JarvisClient |
| `camera` | Access Reachy camera (built-in) | Pollen SDK |
| `dance` | Dance animations (built-in) | Pollen SDK |
| `head_tracking` | Track faces (built-in) | Pollen SDK |

### Scholar only

| Tool | Purpose | Backend |
|------|---------|---------|
| `query_student_model` | Read student progress from Graphiti | HTTP → GraphitiClient |
| `celebrate_achievement` | Celebration scaffolds + motion | Local |

### Bridge only

| Tool | Purpose | Backend |
|------|---------|---------|
| `agent_status` | Quick fleet status check | NATS → JarvisClient |

## Demo Scenarios (Proven)

### Agent discovery (proven 13 May 2026)

> "Please ask Jarvis which agents are available."
>
> Scholar: "Right now we've got Architect, Product Owner, GCSE Tutor,
> Ideation, Forge, and Frontier for attended escalations."

### Architecture evaluation (proven 13 May 2026)

> "Ask Jarvis whether adding Claude Opus 4.7 as an escalation path
> is architecturally sound."
>
> Scholar routes to architect agent → narrates verdict through robot.

### GCSE tutoring — An Inspector Calls (proven 13 May 2026)

> "Help with An Inspector Calls for a Year 11 student."
>
> Scholar runs Socratic dialogue: asks what they know → builds to exam
> sentence → offers to add quotes. Natural back-and-forth via voice.

## Known Issues

| Issue | Workaround |
|-------|------------|
| `emotion` tool not found | Tool name mismatch in this version. Remove from `tools.txt` or find correct name. |
| Voice fragmentation on long questions | HF VAD cuts too aggressively. Keep questions to one sentence per turn. |
| Duplicate tool calls on complex questions | HF treats each pause as end-of-utterance. Use short atomic turns. |
| SDK version mismatch warning (1.7.1 vs 1.7.2) | Cosmetic — works fine. |
| GStreamer plugin warning on macOS | Cosmetic — WebRTC fallback works. |

## File Structure

```
fleet-gateway/
├── common/                          # Shared NATS client (used by both gateways)
│   ├── envelope.py                  # build_command_envelope(), parse_result_payload()
│   ├── jarvis_client.py             # JarvisClient: NATS request-reply
│   └── graphiti_client.py           # GraphitiClient: Graphiti HTTP queries
├── openwebui/
│   └── nats_fleet_pipe.deploy.py    # OpenWebUI pipe (deployed on GB10)
├── reachy/
│   ├── .env.example                 # Template — copy to conversation app dir
│   ├── README.md                    # This file
│   ├── SDK_SETUP.md                 # Reachy SDK installation guide
│   ├── scripts/
│   │   └── launch_scholar.sh        # Launch script (sets PYTHONPATH, activates venv)
│   └── external_content/
│       ├── external_profiles/
│       │   ├── scholar/
│       │   │   ├── instructions.txt # GCSE tutor persona + Jarvis routing
│       │   │   ├── tools.txt        # ask_jarvis, query_student_model, etc.
│       │   │   └── voice.txt        # Voice pin (Kore for OpenAI, ignored by HF)
│       │   └── bridge/
│       │       ├── instructions.txt # Ship's Computer persona + Jarvis routing
│       │       ├── tools.txt        # ask_jarvis, agent_status, etc.
│       │       └── voice.txt        # Different voice to Scholar
│       └── external_tools/
│           ├── ask_jarvis.py        # Routes through Jarvis → any agent (NATS)
│           ├── query_student_model.py  # Direct Graphiti read (Scholar)
│           ├── celebrate_achievement.py # Celebration animations (Scholar)
│           └── agent_status.py      # Fleet status shortcut (Bridge)
└── docs/
    ├── architecture.md              # Fleet gateway design principles
    ├── FEAT-FG-001-scope.md         # Feature spec
    └── FEAT-FG-001-build-plan.md    # Build plan
```

## Pollen Tool Interface

External tools must match the Pollen `Tool` ABC:

```python
from reachy_mini_conversation_app.tools.core_tools import Tool

class MyTool(Tool):
    name = "my_tool"
    description = "What this tool does."
    parameters_schema = {                    # NOT "parameters"
        "type": "object",
        "properties": { ... },
        "required": [...]
    }

    async def __call__(self, deps, **kwargs):  # NOT "run()"
        result = kwargs.get("my_param")
        return {"response": "..."}            # Must return dict
```

Key gotchas (discovered 13 May 2026):
- Use `parameters_schema` not `parameters`
- Use `async def __call__(self, deps, **kwargs)` not `async def run()`
- Return `dict[str, Any]` not `str`
- Extract kwargs: `message = kwargs.get("message", "")`
