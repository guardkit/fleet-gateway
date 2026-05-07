# Open WebUI NATS Pipe Function

## What this is

A single Python file that registers as a Pipe Function in Open WebUI, exposing fleet agents as selectable models in the model dropdown. When a user sends a message, the Pipe Function publishes it to the selected agent's NATS command topic and returns the response.

## How to deploy

### Option A: Workspace Function (quickest for demo)

1. Open WebUI → Admin → Workspace → Functions
2. Click "+" to create a new Function
3. Paste the contents of `nats_fleet_pipe.py`
4. Save — the agents appear in the model selector immediately

### Option B: Pipelines container (repeatable for production)

1. Copy `nats_fleet_pipe.py` into the Pipelines container's `/pipelines/` volume
2. The file auto-loads on container startup
3. In Open WebUI Admin → Connections → OpenAI, add `http://pipelines:9099` with key `0p3n-w3bu!`

## Prerequisites

- NATS server running and reachable from Open WebUI (localhost on GB10)
- `nats-py` installed in the Open WebUI / Pipelines Python environment (`pip install nats-py`)
- Fleet agents running in `serve-nats` mode (specialist-agent, study-tutor)

## Configuration

The Pipe Function exposes Valves (configurable in Admin → Settings → Pipelines):

| Valve | Default | Description |
|---|---|---|
| `NATS_URL` | `nats://localhost:4222` | NATS server URL |
| `REQUEST_TIMEOUT` | `120` | NATS request timeout in seconds |
