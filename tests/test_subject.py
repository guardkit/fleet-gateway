"""Seam test: the tutoring default subject is one shared source of truth (R06).

``resume_if_active`` matches on ``(student, subject)``, so every fleet-gateway
consumer must resolve the same default subject string or D8 cross-device
pickup silently misses. The app and Scholar persona live cross-repo; this test
pins the two runtime consumers this repo owns — ``query_student_model``'s
default and ``ask_tutor``'s fallback — to the single constant.
"""

from __future__ import annotations

import pytest

from common.subject import DEFAULT_SUBJECT
from reachy.external_content.external_tools import ask_tutor as ask_tutor_mod
from reachy.external_content.external_tools import query_student_model as qsm_mod


@pytest.mark.seam
@pytest.mark.integration_contract("SUBJECT_DEFAULT")
def test_subject_default_is_single_source() -> None:
    """All fleet-gateway consumers resolve to the same default subject string.

    Contract: one shared default subject; resume_if_active matches on
    (student, subject). Producer: TASK-VOX-R06.
    """
    shared_default = "english"  # resolved value (ASSUM-001)

    assert DEFAULT_SUBJECT == shared_default

    # query_student_model re-exports the same constant (identity, not a copy).
    assert qsm_mod.DEFAULT_SUBJECT is DEFAULT_SUBJECT
    assert (
        qsm_mod.QueryStudentModelTool.parameters_schema["properties"]["subject"]["default"]
        == shared_default
    )

    # ask_tutor's fallback default (schema) is the same shared constant.
    assert (
        ask_tutor_mod.AskTutorTool.parameters_schema["properties"]["subject"]["default"]
        == shared_default
    )


def test_default_subject_is_never_empty() -> None:
    """An empty subject would defeat D8 pickup — guard it at the source."""
    assert DEFAULT_SUBJECT
    assert DEFAULT_SUBJECT.strip() == DEFAULT_SUBJECT
