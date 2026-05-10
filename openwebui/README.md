# Open WebUI NATS Pipe Function

## What this is

A Python Pipe Function for Open WebUI that exposes the fleet's intent
router (Jarvis) as a single selectable model. When a user sends a
message, the Pipe Function publishes a canonical command envelope
(`common.envelope.build_command_envelope`) to `agents.command.jarvis`
over NATS, awaits the reply, and returns the response text.

## Source-of-truth vs. deployable file (read this first)

This directory ships **two** files and they are deliberately different:

| File | Audience | Imports `common/`? | Size |
|---|---|---|---|
| `nats_fleet_pipe.py` | tests, source review, IDE | **yes** | ~150 LOC |
| `nats_fleet_pipe.deploy.py` | Open WebUI Workspace UI | **no** (self-contained) | ~600 LOC |

### Why two files?

Open WebUI's Workspace Functions Python interpreter **cannot**
`pip install fleet-gateway-common` (verified by `docker exec` against the
running container — see scope §7 Q4). The pipe file pasted into the
Workspace UI must therefore inline every dependency it uses from
`common/`. We refuse to maintain a single divergent inline copy by hand,
so the workflow is:

* **Source-of-truth**: `nats_fleet_pipe.py` imports
  `common.jarvis_client.JarvisClient`. Tests run against this file and
  exercise the real shared library code.
* **Deployable artifact**: `nats_fleet_pipe.deploy.py` is generated from
  `nats_fleet_pipe.py` + `common/envelope.py` + `common/jarvis_client.py`
  by `openwebui/build_pipe.py`. It is committed to the repo so reviewers
  can diff it. No runtime `from common` imports — paste-ready.

### Regenerating the deployable file

After any change to `common/envelope.py`, `common/jarvis_client.py`, or
`openwebui/nats_fleet_pipe.py`, regenerate the deploy file:

```bash
python openwebui/build_pipe.py
```

This rewrites `openwebui/nats_fleet_pipe.deploy.py` deterministically
(identical inputs → identical bytes), so a clean `git diff` after the
build means everything is in sync.

CI / pre-merge guidance: re-run `python openwebui/build_pipe.py` and
ensure `git diff --exit-code openwebui/nats_fleet_pipe.deploy.py` is
clean before merging changes that touch the source pipe or `common/`.

### Running the tests

```bash
pytest tests/test_openwebui_pipe.py -v
```

Tests mock `JarvisClient` — zero NATS connections, zero network calls.

## How to deploy

### Option A: Workspace Function (quickest for demo)

1. Open WebUI → Admin → Workspace → Functions
2. Click "+" to create a new Function
3. Paste the contents of **`nats_fleet_pipe.deploy.py`** (NOT
   `nats_fleet_pipe.py` — that one imports from `common/` and will fail
   inside the Workspace interpreter).
4. Save — Jarvis appears in the model selector immediately.

### Option B: Pipelines container (repeatable for production)

1. Copy **`nats_fleet_pipe.deploy.py`** into the Pipelines container's
   `/pipelines/` volume.
2. The file auto-loads on container startup.
3. In Open WebUI Admin → Connections → OpenAI, add
   `http://pipelines:9099` with key `0p3n-w3bu!`.

## Prerequisites (Open WebUI environment)

- NATS server running and reachable from Open WebUI (localhost on GB10)
- `nats-py` installed in the Open WebUI / Pipelines Python environment
  (`pip install nats-py`)
- Fleet agents running in `serve-nats` mode (Jarvis at minimum;
  specialist agents as needed)

> Note: `fleet-gateway-common` is **not** installable in the Workspace
> Functions interpreter. That is precisely why the deploy file is
> self-contained — do not add a `pip install fleet-gateway-common`
> instruction here, it will not work.

## Configuration

The Pipe Function exposes Valves (configurable in Admin → Settings →
Pipelines):

| Valve | Default | Description |
|---|---|---|
| `NATS_URL` | `nats://localhost:4222` | NATS server URL |
| `REQUEST_TIMEOUT` | `120` | NATS request timeout in seconds |
