# Handoff → study-tutor: add a student-model read endpoint on `:8100`

**From:** fleet-gateway, FEAT-VOICE-004 (Reachy local voice migration), R05.
**Why:** R05 re-pointed the robot's `query_student_model` tool off the **frozen** Graphiti
graph (`student-lilymay`, write path being torn down) onto the durable Postgres store **via
the study-tutor HTTP adapter on `:8100`** (recon D2). But the adapter registers only the six
session verbs + the voice routes — **there is no student-model read route**. Until study-tutor
ships one, the robot degrades gracefully (Scholar says "I have not got any study data yet — has
the tutor session run today?"). `ask_tutor` (the tutoring loop) is unaffected; only the
progress-report path waits on this.

**fleet-gateway is already forward-compatible.** The consumer is
`common.tutor_client.TutorClient.get_student_model()`, called by
`reachy/external_content/external_tools/query_student_model.py`. The path is a single
constant — `STUDENT_MODEL_PATH = "/api/student-model"` — so if you prefer a different
path/shape, reconciling is one line on our side. Tell us the final contract and we'll pin it.

---

## Ready-to-paste prompt

> **Context.** The study-tutor HTTP adapter (`:8100`, Starlette, `src/study_tutor/http/app.py`)
> exposes the six session verbs + the Rev 1 voice routes, but **no student-model read**. The
> Reachy robot's `query_student_model` tool (sibling `fleet-gateway` repo, FEAT-VOICE-004 R05)
> needs to read a student's current learning record over this same bearer-authenticated binding
> — the read path was previously served by the now-frozen Graphiti graph (recon D2).
>
> **Task.** Add a read-only endpoint that returns the student's durable learning record.
>
> - **Verb:** `GET /api/student-model` (query params: `subject` required, `student_name`
>   optional hint — identity is derived server-side from the token, never client-asserted).
> - **Auth:** same as every other verb — `Authorization: Bearer <token>` →
>   `_resolve_student_id(request)` (interim single-user; `STUDY_TUTOR_HTTP_TOKENS`). Unseeded
>   student → `Unauthenticated` (401), never 500 (binding §3, ASSUM-001).
> - **Response body** (the shape the robot narrates — mirror the old
>   `GraphitiClient.search_student_progress` contract so the tool needs no change):
>   ```json
>   {
>     "student_name": "lilymay",
>     "streak_days": 5,
>     "level_name": "Knight",
>     "recent_xp": 240,
>     "near_achievements": ["7-day streak"],
>     "topic_confidence": {"reading": 0.7, "writing": 0.55},
>     "data_available": true
>   }
>   ```
>   On a seeded-but-empty record, return `data_available: false` (the robot renders an honest
>   "no data yet"); never 500 for "nothing logged".
> - **Data source — already in-store, just not exposed over HTTP:**
>   `KnowledgeStore.get_student_state(student_id)` (streak / level / xp) and
>   `get_topic_confidences(student_id)` (`src/study_tutor/knowledge/store/{port,postgres}.py`);
>   the planner already reads these internally (`planner/pipeline.py`, `mcp/adapter.py`). Add a
>   thin projection to the response shape above (achievements/near-achievements from wherever the
>   gamification state lives, or omit `near_achievements` as `[]` if not yet modelled).
> - **Errors:** reuse the closed-set envelope + `_map_error_to_response`; malformed request → 400
>   (no `error_type`, §4.2), consistent with the other handlers.
> - **Contract discipline:** this adds a **read verb to the frozen HTTP binding**
>   (`docs/design/contracts/API-session-http-binding.md` §2) — treat it as a contract addition
>   (the same posture as the voice Rev 1 routes: document the verb + response in the binding,
>   decide whether it warrants a `CONTRACT_SHA`/`BINDING_SHA` touch, and note that the freeze is
>   authoritative). The voice contract SHAs are already frozen and must **not** be disturbed by
>   this; scope any freeze to the binding addition only.
> - **Tests:** mirror the existing handler tests — auth (401 unseeded / rejected bearer), happy
>   projection, seeded-but-empty → `data_available: false`, malformed → 400. Register the
>   `Route("/api/student-model", student_model, methods=["GET"])` in `app.py`'s route list.
>
> **Coordination.** fleet-gateway consumes `GET /api/student-model?subject=&student_name=` and
> maps a non-2xx (incl. the current 404) to a graceful "unavailable". If you change the path or
> body shape, reply with the final contract — fleet-gateway pins it via the one constant
> `common.tutor_client.STUDENT_MODEL_PATH` and adapts `query_student_model`'s projection.

---

## Acceptance (fleet-gateway side, once the endpoint ships)

- `GET /api/student-model` returns the record for the token's student; `query_student_model`
  narrates real progress instead of the degraded "no data yet".
- No fleet-gateway code change needed if the path + body match the above (the seam test
  `tests/test_query_student_model.py::test_query_student_model_reads_via_8100_not_graphiti`
  already pins method/path/bearer). Otherwise: one-line `STUDENT_MODEL_PATH` update + a
  projection tweak.
- Confirms recon D2 closed and lets SMK-R AC-R2's `query_student_model` leg read live data.
