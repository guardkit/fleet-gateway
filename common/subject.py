"""Single source of truth for the tutoring default subject (recon D6 / ASSUM-001).

``resume_if_active`` on the study-tutor session store matches on
``(student, subject)`` — not student alone (study-tutor
``session/service.py``). Any consumer that talks to the tutor with a
*different* subject string silently creates a parallel session and defeats
D8 cross-device pickup (phone-started session resumed on the robot).

To make that impossible by construction, every fleet-gateway consumer of a
tutoring subject resolves its default from :data:`DEFAULT_SUBJECT` here:

* ``reachy…external_tools.query_student_model`` — progress read default.
* ``reachy…external_tools.ask_tutor`` — the subject it sends on
  ``/api/sessions/start`` when the persona omits it (**never empty**).

**Resolved value (ASSUM-001, 2026-07-07): ``english``.** The tutor is an
English tutor end to end — the Scholar persona (AQA English Language 8700 /
Literature 8702), the fine-tune, the student model, and this default all
agree. The Flutter app's former ``maths`` placeholder was moved to
``english`` to match (study-tutor ``app/lib/ui/home_screen.dart``).

This is a **v1 default**, not a hard pin. The whole stack is already
subject-parameterised — ``ask_tutor`` exposes ``subject`` as a tool
parameter and the session store keys on it — so multi-subject needs only an
app subject picker plus persona awareness later, with no rework here.
"""

from __future__ import annotations

#: The v1 default tutoring subject shared across every fleet-gateway
#: consumer. Falls back here whenever a caller omits an explicit subject;
#: must never be sent empty (an empty subject defeats D8 pickup).
DEFAULT_SUBJECT = "english"

__all__ = ["DEFAULT_SUBJECT"]
