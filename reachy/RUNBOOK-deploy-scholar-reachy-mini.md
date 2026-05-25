# Runbook: Deploy Scholar on Reachy Mini Wireless

**Status:** Verified (20 May 2026 — working on first Reachy Mini "Scholar")
**Purpose:** Deploy the Scholar GCSE study tutor profile on a Reachy Mini Wireless robot, connected to the Jarvis agent fleet via NATS. Lilymay starts Scholar from the Reachy Mini Control app on her laptop — no MacBook or terminal needed.

**End state:** Scholar voice profile running on the Pi, `ask_jarvis` tool registered, NATS routing to GB10 Jarvis, selectable from Personality Studio.

**Expected wall-clock:** ~30 minutes for a fresh robot.

**Prerequisites:**
- Reachy Mini Wireless powered on, on home WiFi (`whitestocks`)
- GB10 running: NATS (`ships-computer-nats`), Jarvis (`jarvis serve-nats`), llama-swap
- `fleet-gateway` repo pushed to GitHub with `ask_jarvis.py` in `reachy/external_content/external_tools/`
- NATS credentials known (user: `rich`, password from `nats-infrastructure/.env`)
- Tailscale account (richardwoollcott@hotmail.com)

**Outputs:**
- Scholar appears in Personality Studio dropdown
- `ask_jarvis` tool registered and routing through NATS to Jarvis
- Robot responds to voice with Socratic tutoring

---

## Phase 1 — SSH Access

**Goal:** Establish SSH access to the Reachy Mini's Raspberry Pi CM4.

```bash
# From your MacBook/laptop. Robot's local IP visible in Reachy Mini Control app settings.
ssh pollen@<ROBOT_LOCAL_IP>
# Password: root
```

**Pass criterion:** Shell prompt `pollen@reachy-mini:~$`

**Note:** Change the default password on first login:
```bash
passwd
```

---

## Phase 2 — Install Tailscale

**Goal:** Give the robot a stable Tailscale IP reachable from the GB10 (which hosts NATS/Jarvis).

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

The second command prints a URL. Open it in a browser and log in with the Tailscale account to approve the device. The robot appears in the Tailscale admin console.

**Pass criterion:** Robot visible in Tailscale devices list with a green dot and a stable IP (e.g. `100.x.x.x`). Verify with:
```bash
tailscale ip -4
```

---

## Phase 3 — Clone fleet-gateway

**Goal:** Get the Scholar profiles, tools, and common NATS client code onto the Pi.

```bash
cd /home/pollen
git clone https://github.com/guardkit/fleet-gateway.git
```

**Pass criterion:**
```bash
ls /home/pollen/fleet-gateway/reachy/external_content/external_tools/ask_jarvis.py
# File exists
```

---

## Phase 4 — Install nats-py

**Goal:** Install the NATS Python client in the conversation app's venv.

```bash
source /venvs/apps_venv/bin/activate
pip install nats-py
```

**Pass criterion:**
```bash
python -c "import nats; print('OK')"
# Prints: OK
```

---

## Phase 5 — Create .pth file for fleet-gateway imports

**Goal:** Allow the conversation app to import `common.jarvis_client` from fleet-gateway without modifying PYTHONPATH (which the daemon launcher doesn't pass through).

```bash
echo "/home/pollen/fleet-gateway" > /venvs/apps_venv/lib/python3.12/site-packages/fleet-gateway.pth
```

**Pass criterion:**
```bash
source /venvs/apps_venv/bin/activate
python -c "from common.jarvis_client import JarvisClient; print('OK')"
# Prints: OK
```

---

## Phase 6 — Create sitecustomize.py for env vars

**Goal:** Inject environment variables into every Python process using the apps venv. The Reachy daemon launcher doesn't pass through env vars from `.bashrc`, `/etc/environment`, or `.env` files. `sitecustomize.py` runs automatically at Python startup.

```bash
cat > /venvs/apps_venv/lib/python3.12/site-packages/sitecustomize.py << 'EOF'
import os
os.environ.setdefault("REACHY_MINI_EXTERNAL_TOOLS_DIRECTORY", "/home/pollen/fleet-gateway/reachy/external_content/external_tools")
os.environ.setdefault("NATS_URL", "nats://rich:YOUR_NATS_PASSWORD_HERE@promaxgb10-41b1:4222")
EOF
```

**⚠️ Replace `YOUR_NATS_PASSWORD_HERE` with the actual NATS password.**

**Pass criterion:**
```bash
source /venvs/apps_venv/bin/activate
python -c "import os; print(os.environ.get('REACHY_MINI_EXTERNAL_TOOLS_DIRECTORY', 'NOT SET'))"
# Prints: /home/pollen/fleet-gateway/reachy/external_content/external_tools
```

---

## Phase 7 — Hardcode NATS credentials in ask_jarvis.py

**Goal:** Belt-and-braces — ensure NATS credentials work even if `sitecustomize.py` env var isn't read by the async nats client.

```bash
nano /home/pollen/fleet-gateway/reachy/external_content/external_tools/ask_jarvis.py
```

Find:
```python
_DEFAULT_NATS_URL = "nats://promaxgb10-41b1:4222"
```

Change to:
```python
_DEFAULT_NATS_URL = "nats://rich:YOUR_NATS_PASSWORD_HERE@promaxgb10-41b1:4222"
```

Save and exit (Ctrl+O, Enter, Ctrl+X).

**⚠️ Replace `YOUR_NATS_PASSWORD_HERE` with the actual NATS password.**

---

## Phase 8 — Create Scholar user personality

**Goal:** Create the Scholar profile in the Personality Studio's user_personalities directory so it appears in the dropdown.

```bash
mkdir -p /venvs/apps_venv/lib/python3.12/site-packages/reachy_talk_data/profiles/user_personalities/scholar
```

Copy profile files from fleet-gateway:
```bash
cp /home/pollen/fleet-gateway/reachy/external_content/external_profiles/scholar/instructions.txt \
   /venvs/apps_venv/lib/python3.12/site-packages/reachy_talk_data/profiles/user_personalities/scholar/
```

Create tools.txt with external tools included:
```bash
cat > /venvs/apps_venv/lib/python3.12/site-packages/reachy_talk_data/profiles/user_personalities/scholar/tools.txt << 'EOF'
ask_jarvis
query_student_model
celebrate_achievement
camera
dance
head_tracking
task_cancel
task_status
EOF
```

**Pass criterion:**
```bash
ls /venvs/apps_venv/lib/python3.12/site-packages/reachy_talk_data/profiles/user_personalities/scholar/
# instructions.txt  tools.txt
```

---

## Phase 9 — Start and verify from Control App

**Goal:** Scholar runs on the robot, started from the Reachy Mini Control app.

1. Open the **Reachy Mini Control app** on the laptop
2. Navigate to the **Personality Studio**
3. Select **user_personalities/scholar** from the dropdown
4. Click **Use on startup** then **Apply**
5. Stop and restart the app (or reboot the robot)

**Verify from SSH:**
```bash
journalctl --no-pager --since "5 min ago" | grep -E "tool|ask_jarvis|scholar"
```

**Pass criteria (all must appear):**
```
Environment variable 'REACHY_MINI_EXTERNAL_TOOLS_DIRECTORY' is set. External tools will be loaded from /home/pollen/fleet-gateway/reachy/external_content/external_tools.
✓ Loaded external tool: ask_jarvis
tool registered: ask_jarvis - Send a question to Jarvis...
Tools to be used in conversation: ['ask_jarvis', ...]
Loading prompt from profile 'user_personalities/scholar'
Realtime session initialized with profile='user_personalities/scholar'
```

---

## Phase 10 — Voice test

**Goal:** Confirm end-to-end voice → Jarvis → agent → narration.

Say to the robot: **"Please ask Jarvis which agents are available."**

**Pass criterion:** Scholar narrates the agent list (Architect, Product Owner, GCSE Tutor, Ideation, Forge, Frontier).

Then say: **"Let's revise An Inspector Calls."**

**Pass criterion:** Scholar begins a Socratic tutoring dialogue.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `ask_jarvis not found in profile or shared tools` | tools.txt doesn't list ask_jarvis | Update tools.txt per Phase 8 |
| `Authorization Violation` from NATS | NATS_URL missing credentials | Check sitecustomize.py and ask_jarvis.py default URL |
| `circular import` on background_tool_manager | Tool .py files copied into wrong directory | Remove any .py files from `user_personalities/scholar/` and from `/venvs/apps_venv/lib/python3.12/site-packages/reachy_mini_conversation_app/tools/`. Tools must ONLY live in fleet-gateway external_tools. |
| `Profile has no instructions.txt` | EXTERNAL_PROFILES_DIRECTORY set, conflicts with Personality Studio | Do NOT set REACHY_MINI_EXTERNAL_PROFILES_DIRECTORY in sitecustomize.py — let Personality Studio handle profiles |
| Scholar talks but doesn't call Jarvis | Tool loaded but not in HF session tool list | Full stop and restart from Control app (not just Apply) |
| `Lost connection with the server` spam | Robot daemon WiFi drop | Restart Reachy from Control app before use |

---

## Key file locations on the Pi

| File | Purpose |
|------|---------|
| `/home/pollen/fleet-gateway/` | Cloned repo with tools and profiles |
| `/home/pollen/fleet-gateway/reachy/external_content/external_tools/ask_jarvis.py` | NATS → Jarvis routing tool |
| `/venvs/apps_venv/lib/python3.12/site-packages/sitecustomize.py` | Env var injection at Python startup |
| `/venvs/apps_venv/lib/python3.12/site-packages/fleet-gateway.pth` | Python path for common/ imports |
| `/venvs/apps_venv/lib/python3.12/site-packages/reachy_talk_data/profiles/user_personalities/scholar/` | Scholar profile (instructions + tools list) |
| `/venvs/apps_venv/lib/python3.12/site-packages/reachy_mini_conversation_app/tools/` | Core tools dir — do NOT put external tools here |

---

## What NOT to do

- **Do NOT** copy tool .py files into `reachy_mini_conversation_app/tools/` — causes circular import crash
- **Do NOT** copy tool .py files into `user_personalities/scholar/` — causes circular import crash
- **Do NOT** set `REACHY_MINI_EXTERNAL_PROFILES_DIRECTORY` in sitecustomize.py — conflicts with Personality Studio profile path
- **Do NOT** rely on `.env`, `.bashrc`, or `/etc/environment` for env vars — the daemon launcher doesn't pass them through
