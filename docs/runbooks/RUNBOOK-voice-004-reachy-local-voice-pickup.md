# Runbook: FEAT-VOICE-004 — Reachy Local Voice, GB10 + Robot Pickup

**Status:** Code plane **DONE** (fleet-gateway, this repo) — operator plane **PENDING** (this doc).
**Purpose:** Pick up FEAT-VOICE-004 on the GB10 + Reachy Mini: stand up the local
speech-to-speech (s2s) unit, re-point the robot off HF-cloud Realtime, and prove the
tutoring loop goes **direct to the study-tutor** (no Jarvis). Closes the D3 exception
(a minor's voice transiting a third-party cloud).

**Execution model:** R-track = **Operator + Opus** (build-plan §0a). The code artefacts
below are already merged here; this runbook is the hardware/attended remainder.

**Authoritative sources — read before starting:**
- Scope + build plan: `study-tutor/docs/research/ideas/voice-tutor-and-reachy-scope-and-build-plan.md` (§5 waves, §8 smokes)
- Design §7: `study-tutor/docs/design/voice-tutor-and-reachy-design.md`
- Recon deltas D1–D7: `study-tutor/docs/research/ideas/reachy-local-backend-recon-deltas-2026-07-06.md`
- **W0-R evidence pins (consume verbatim):** `study-tutor/docs/runbooks/evidence/voice-w0r-reachy-feasibility-2026-07-06/EVIDENCE.md`
- Existing deploy mechanics: `reachy/RUNBOOK-deploy-scholar-reachy-mini.md`
- Task specs: `study-tutor/tasks/backlog/reachy-local-voice-migration/` (TASK-VOX-R01..R09, SMK-R)

**Operational guardrails (build-plan §8):** quiet-GPU rule (no LPA extraction / tutor
sessions mid-flight); **never** `GET :9000/unload` (unloads everything); check
`systemctl status llama-swap-keepalive.timer` before assuming self-revival. The audio
pair (`parakeet-tdt-0.6b-v3`, `qwen3-tts-0.6b`) behind llama-swap `:9000` is live — consume,
don't restart.

---

## 0. What the code plane already delivered (merged in this repo)

| Task | Artefact | Notes |
|---|---|---|
| R04 | `reachy/external_content/external_tools/query_student_model.py` | Conformant Pollen ABC (`parameters_schema` + async `__call__`, dict return). Loads/fires. |
| R05 | same file + `common/tutor_client.py` | Reads the durable record via study-tutor `:8100` — **Graphiti read removed**. ⚠️ See §6: the `:8100` read endpoint is **pending study-tutor**; until it ships this degrades to an honest "no data yet". |
| R06 | `common/subject.py` | Single source of truth `DEFAULT_SUBJECT = "english"`. `query_student_model` + `ask_tutor` both resolve from it. |
| R07 | `reachy/external_content/external_tools/ask_tutor.py` + `common/tutor_client.py` | `ask_tutor` tool → `POST /api/sessions/start` (`resume_if_active`) then `.../turn`; subject never empty; every failure → one neutral offline string. |
| R08 | `reachy/external_content/external_profiles/scholar/{tools.txt,instructions.txt}` | Tutoring routes to `ask_tutor` (no Jarvis in the loop); `emotion` dropped; `task_cancel`/`task_status` added; slow-turn filler + tutor-unavailable copy. |

New env vars (see `reachy/.env.example`): `STUDY_TUTOR_HTTP_URL`, `STUDY_TUTOR_TOKEN`.
New runtime dep: **`httpx`** (added to `pyproject.toml`) — must be installed into the Pi's
`apps_venv` (§5, Phase B).

**Gates green here:** `mypy` strict, `ruff check` (changed files), `pytest` 112 passed
(7 seam). `ask_jarvis.py:148` E501 is pre-existing and out of scope.

---

## R01 — Stand up the local s2s unit on GB10 `:8765` (operator)

**Task:** TASK-VOX-R01. Productionize the **passing** W0-R throwaway config into a durable
unit (systemd/docker), digest-pinned, non-loopback bind.

**Target config (from design §7 + W0-R gates — take exact pins from the EVIDENCE file):**
- HuggingFace **speech-to-speech Realtime** server on `:8765`.
- Silero VAD (in-process endpointing).
- `--stt parakeet-tdt` (the live `:9000` model).
- `--tts qwen3` with the **0.6B** checkpoint (R-G2). **Fallback pre-approved:** auto-accept
  the **1.7B** checkpoint if the 0.6B fails at load — no consult (ASSUM-003).
- **Ryan voice flag** located and set **server-side** (per W0-R: the app-side `MODEL_VOICE`
  pin is the reliable one; server voice flag was unreliable — verify against EVIDENCE).
- `--llm_backend responses-api` pointed at **llama-swap `:9000`** with the resident-set
  posture from R-G5 (`tutor` set standing default, `gemma4-tutor` ttl raised).
- `--num_pipelines 2` (R-G6 supersedes the two-instance fallback for the two-robot fleet).
- Pins to carry verbatim from EVIDENCE: resolve-URL wheel, numba floors, `OPENAI_API_KEY`,
  user-mode `systemctl --user restart llama-swap`.

**Known defect to fix here (W0-R):** tool-call text is spoken aloud. Apply the two identified
fixes — template tool-call support + a TTS strip filter — so tool-call JSON is not narrated.

**Gate:** unit runs on GB10 aarch64/CUDA-13; `:8765` reachable from the robot; a bare turn
round-trips; Ryan voice audible; memory arithmetic holds at live steady state (R-G4).
Mirror the unit files/scripts to `dgx-spark` (standing config-mirror discipline).

---

## R02 — Verify the Pi app supports the re-point keys (operator, D3)

**Task:** TASK-VOX-R02. The `HF_REALTIME_CONNECTION_MODE` / `HF_REALTIME_WS_URL` keys were
verified against **upstream** docs, **not** the version installed on the Pi (~2026-05-20).
`grep -rn "HF_REALTIME"` across this repo → zero hits (they live upstream only).

**Do:**
```bash
ssh pollen@<ROBOT_LOCAL_IP>
source /venvs/apps_venv/bin/activate
pip show reachy_mini_conversation_app | grep -E 'Version|Location'
# Confirm the installed version reads HF_REALTIME_CONNECTION_MODE + HF_REALTIME_WS_URL.
python - <<'PY'
import reachy_mini_conversation_app as a, pathlib, subprocess
root = pathlib.Path(a.__file__).parent
hits = subprocess.run(["grep","-rn","HF_REALTIME",str(root)],capture_output=True,text=True).stdout
print(hits or "NO HF_REALTIME SUPPORT IN INSTALLED VERSION")
PY
```

**Gate:** keys present in the installed version. **If absent:** plan an app upgrade step
**and** re-verify the Personality-Studio profile survives the upgrade before proceeding to R03.

---

## R03 — Re-point the robot + verify the tool round-trip (operator)

**Task:** TASK-VOX-R03. Depends on R01 + R02. This is the **R-G3 proof** and the **source of
Pi truth** for R08's profile reconcile.

**Deploy the code plane to the Pi (delta over `RUNBOOK-deploy-scholar-reachy-mini.md`):**

Ship via a **clean re-clone**, not `git pull` (recon D7 — the Pi clone is hand-edited:
NATS creds hardcoded in `ask_jarvis.py`). See R09 for the deploy sequence.

**A. Extend `sitecustomize.py`** (Phase 6 of the deploy runbook) — inject the re-point +
tutor keys (the daemon passes no env; `os.environ.setdefault` is the only channel):
```python
# /venvs/apps_venv/lib/python3.12/site-packages/sitecustomize.py
import os
os.environ.setdefault("REACHY_MINI_EXTERNAL_TOOLS_DIRECTORY", "/home/pollen/fleet-gateway/reachy/external_content/external_tools")
os.environ.setdefault("NATS_URL", "nats://rich:YOUR_NATS_PASSWORD_HERE@promaxgb10-41b1:4222")
# FEAT-VOICE-004 — re-point off HF cloud onto the local s2s unit:
os.environ.setdefault("HF_REALTIME_CONNECTION_MODE", "local")
os.environ.setdefault("HF_REALTIME_WS_URL", "ws://promaxgb10-41b1:8765")
# FEAT-VOICE-004 — ask_tutor / query_student_model direct to the study-tutor:
os.environ.setdefault("STUDY_TUTOR_HTTP_URL", "http://promaxgb10-41b1:8100")
os.environ.setdefault("STUDY_TUTOR_TOKEN", "token-lilymay")  # interim single-user token
# App-side voice pin (reliable per W0-R):
os.environ.setdefault("MODEL_VOICE", "Ryan")
```

**B. Belt-and-braces the bearer token** (D7 pattern, mirrors the hardcoded NATS creds):
if `sitecustomize` env isn't read in time, `TutorClient` falls back to `STUDY_TUTOR_TOKEN`
then `""` — so ALSO set it in the clone if needed, or confirm the env path works.

**Verify tool round-trip (R-G3):**
```bash
journalctl --no-pager --since "5 min ago" | grep -E "ask_tutor|query_student_model|tool"
```
- Open-mic ask a tutoring question → `ask_tutor` fires → tutor answer spoken (not tool JSON).
- Ask "how's my revision going?" → `query_student_model` fires (see §6 caveat on live data).

**Gate:** robot converses locally end-to-end; **no HF-cloud Realtime session** established;
tool calls round-trip without narrating tool-call text.

---

## R08 — Reconcile the Scholar profile to Pi truth (code, but confirm at R03)

**Task:** TASK-VOX-R08. The profile in this repo was authored from the recon-D4 drift list
(`emotion` absent; `task_cancel`/`task_status` present; `ask_tutor` added). **At R03, diff the
repo profile against the live Pi state** and reconcile any residual drift *to the Pi where the
Pi is right*. Copy the reconciled `instructions.txt` + `tools.txt` into Personality Studio
(deploy runbook Phase 8). `voice.txt` (`Kore`) is OpenAI-only — not copied; Ryan is set at R01/§A.

---

## R09 — Ship to the Pi via clean re-clone (operator, D7)

**Task:** TASK-VOX-R09. Depends on R05 + R07 + R08. **Do not `git pull`** on the Pi — it will
conflict with the hand-edited `ask_jarvis.py`.

**Sequence:**
```bash
# On the Pi
mv /home/pollen/fleet-gateway /home/pollen/fleet-gateway.bak
git clone https://github.com/<org>/fleet-gateway.git /home/pollen/fleet-gateway
# Re-apply the hand-edits: hardcode NATS creds in ask_jarvis.py (Phase 7),
# recreate .pth (Phase 5) + sitecustomize.py (§A above).
source /venvs/apps_venv/bin/activate
pip install httpx            # NEW runtime dep (R05/R07)
python -c "from common.tutor_client import TutorClient; from reachy.external_content.external_tools.ask_tutor import AskTutorTool; print('OK')"
```

**Gate:** clean clone runs; `httpx` importable in `apps_venv`; local config preserved.

---

## SMK-R — Live smoke AC-R1..R4 (operator handoff, build-plan §8)

**Task:** TASK-VOX-SMK-R. Depends on R03 + R09. Write EVIDENCE + a RESULTS file into
`study-tutor/docs/runbooks/evidence/`.

1. **AC-R1:** open-mic conversation against local s2s — **no HF-cloud Realtime session**
   (connection sampling on Pi and GB10).
2. **AC-R2:** `query_student_model` and `ask_tutor` fire through the local session; a tutor
   session **started on the phone is resumed by the robot** (D8 pickup — requires `ask_tutor`
   to send the app's exact subject string `english`; `resume_if_active` matches on
   `(student, subject)`).
3. **AC-R3:** no raw audio at rest on Pi or GB10; transcripts only in the tutor's session store.
4. **AC-R4:** open-mic latency recorded (simple turn vs `ask_tutor` turn) against design §7.5
   (~1–2.5 s simple; `ask_tutor` adds the tutor's ~5 s+ critical path, covered by persona filler).

**Gate:** ACs hold; RESULTS + evidence written; **D3 residency exception closed**.

---

## 6. ⚠️ Known dependency — R05 live read is pending a study-tutor endpoint

`query_student_model` now reads via `:8100`, but the study-tutor adapter registers only the
six session verbs + voice — **there is no student-model read route yet**. The tool degrades
gracefully (Scholar says "I have not got any study data yet — has the tutor session run
today?") until study-tutor ships it. Endpoint target is a single constant
(`common.tutor_client.STUDENT_MODEL_PATH = "/api/student-model"`), so reconciliation is
one line if study-tutor chooses a different path. **Handoff prompt:**
`docs/handoffs/study-tutor-student-model-read-endpoint.md`.

`ask_tutor` (R07) does **not** depend on that endpoint — it uses the live `start`/`turn`
verbs — so the tutoring loop (AC-R2 `ask_tutor` path, AC-R4) works fully at smoke time; only
the `query_student_model` progress-report path waits on the endpoint.
