# Reachy Mini SDK — local install (macOS)

Record of the `reachy-mini` SDK install on this MacBook. Follows
[huggingface.co/docs/reachy_mini/SDK/installation](https://huggingface.co/docs/reachy_mini/SDK/installation).

## What's installed

| | |
|---|---|
| Venv | `~/reachy_mini_env` (Python 3.12.4) |
| Package | `reachy-mini==1.7.1` with `[mujoco]` extra |
| Simulator | `mujoco==3.3.0` |
| GStreamer | `gstreamer-python==1.28.2` (wheel — no manual install needed on macOS) |

## Prerequisites (already in place)

| Tool | Version | Source |
|---|---|---|
| Homebrew | 5.1.8 | `brew --version` |
| `uv` | 0.11.2 | Homebrew |
| Git | 2.50.1 (Apple) | system |
| Git LFS | 3.7.0 | Homebrew (initialised with `git lfs install`) |
| Python 3.12.4 | Homebrew (`/opt/homebrew/opt/python@3.12`) | uv picks this up automatically |

## The install steps that ran

```bash
# venv
uv venv ~/reachy_mini_env --python 3.12

# package + simulator
source ~/reachy_mini_env/bin/activate
uv pip install "reachy-mini[mujoco]"
```

## Daily use

```bash
source ~/reachy_mini_env/bin/activate
```

Verify:
```bash
python -c "import reachy_mini, mujoco; print(reachy_mini.__version__, mujoco.__version__)"
# 1.7.1 3.3.0
```

## Console scripts on the venv PATH

| Command | Entry point |
|---|---|
| `reachy-mini-daemon` | `reachy_mini.daemon.app.main:main` |
| `reachy-mini-app-assistant` | `reachy_mini.apps.app:main` |
| `reachy-mini-reflash-motors` | `reachy_mini.tools.reflash_motors:main` |

## macOS-specific notes

Skipped vs. the upstream docs — these are Linux-only:

- ❌ Manual GStreamer install — `gstreamer-python` ships as a wheel.
- ❌ USB udev rules (`/etc/udev/rules.d/99-reachy-mini.rules`) — macOS doesn't use udev.
- ❌ `usermod -aG dialout $USER` — no `dialout` group on macOS.

USB connection to the robot works without extra config on macOS.

## Relationship to other Reachy work in this repo

This venv hosts the **base SDK** (`reachy-mini`). It is independent from the
[`reachy_mini_conversation_app`](https://github.com/pollen-robotics/reachy_mini_conversation_app)
clone described in [README.md](README.md), which is a separate dev install
(`uv sync` inside that repo's own venv) that depends on `reachy-mini`
transitively.

Use this venv when you want to run the daemon or write code directly against
the SDK; use the conversation-app's own venv when working on Scholar's profile
and tools.
