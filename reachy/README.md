# Reachy Mini "Scholar" — Study Companion Profile

## What this is

A custom profile for Pollen Robotics' `reachy_mini_conversation_app` that turns Scholar (Reachy Mini #1) into a gamification companion for the GCSE Study Tutor. Scholar reads from the Graphiti student model and verbally reports progress, achievements, and session suggestions.

## Architecture

Scholar is a **read-only consumer** of the Graphiti student model. The study-tutor agent writes session data (topic confidence, XP, streaks, achievements) to Graphiti during tutoring sessions. Scholar reads that data via the `query_student_model` custom tool and narrates it in character.

```
Study Tutor Agent ──writes──► Graphiti (FalkorDB) ◄──reads── Scholar (Reachy Mini)
                                                                  │
                                                           Gemini Live
                                                           (conversation)
```

Scholar does NOT call the tutor agent. It does NOT go through NATS (for the hackathon; NATS integration is post-hackathon). It's a standalone Pollen conversation app with a custom tool that reads from the shared knowledge graph.

## Prerequisites

- Reachy Mini "Scholar" on home WiFi, Daemon running
- `reachy_mini_conversation_app` installed on MacBook (`uv sync`)
- `GEMINI_API_KEY` set in `.env`
- Graphiti / FalkorDB reachable (Synology via Tailscale)

## How to run

```bash
cd /path/to/reachy_mini_conversation_app

# Set env vars pointing at this repo's external_content
export REACHY_MINI_CUSTOM_PROFILE=scholar
export REACHY_MINI_EXTERNAL_PROFILES_DIRECTORY=/path/to/fleet-gateway/reachy/external_content/external_profiles
export REACHY_MINI_EXTERNAL_TOOLS_DIRECTORY=/path/to/fleet-gateway/reachy/external_content/external_tools
export GEMINI_API_KEY=<your-key>
export MODEL_NAME=gemini-3.1-flash-live-preview

# Run with Gradio UI (for testing without hardware)
python -m reachy_mini_conversation_app --gradio

# Run with hardware
python -m reachy_mini_conversation_app
```

## Files

| File | Purpose |
|---|---|
| `external_profiles/scholar/instructions.txt` | Scholar persona — system prompt |
| `external_profiles/scholar/tools.txt` | Enabled tools (includes `query_student_model`) |
| `external_profiles/scholar/voice.txt` | Gemini voice pin (e.g. "Kore") |
| `external_tools/query_student_model.py` | Graphiti reader — subclasses `core_tools.Tool` |

## Demo scenario (Hackathon)

**Scenario 1 — "How's her revision going?"**

Rich asks the question out loud. Scholar's face tracking has him in frame. The conversation app routes the question to the `query_student_model` tool, which reads from Graphiti. Scholar speaks a progress report with head movement and antenna animation. ~8 seconds.

## Tone reference

The `chess_coach` built-in profile is the closest tonal match — patient, encouraging, mentor-like. Scholar should lean toward calm encouragement rather than excitable hype.
