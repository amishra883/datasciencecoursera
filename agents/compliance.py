"""Compliance — hard gate. Sole legal defense under the operator's
fair-use-only posture (see docs/fair_use_position.md).

A clip ships only if every rule below passes. A failure routes the clip to
/data/quarantine/ rather than the publish queue. Compliance never silently
warns; every rule produces a structured result for the audit log.

Rules are derived from CLAUDE.md "Operating principles", "Hard constraints",
"Legal & risk register", and the operational summary in
docs/fair_use_position.md.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Callable

from agents.events import log
from agents.models import CompositedClip, ComplianceResult


# ---------- Individual rule implementations ----------

def _rule_source_max_30s(clip: CompositedClip) -> tuple[bool, str]:
    ok = clip.source_segment_duration_s <= 30.0
    return ok, (
        f"source_segment={clip.source_segment_duration_s:.2f}s "
        f"(cap=30.00s)"
    )


def _rule_total_max_60s(clip: CompositedClip) -> tuple[bool, str]:
    # CLAUDE.md says "<=60s for Shorts/Reels/TikTok" but persona caps at 58s
    # for algorithm sensitivity. Compliance enforces the spec hard cap of 60s;
    # the 58s target is a softer Writer/Compositor constraint enforced upstream.
    ok = clip.final_duration_s <= 60.0
    return ok, (
        f"final_duration={clip.final_duration_s:.2f}s (hard_cap=60.00s)"
    )


def _rule_commentary_at_least_50pct(clip: CompositedClip) -> tuple[bool, str]:
    if clip.final_duration_s <= 0:
        return False, "final_duration is zero or negative"
    ratio = clip.commentary_audio_duration_s / clip.final_duration_s
    ok = ratio >= 0.50
    return ok, (
        f"commentary_ratio={ratio:.3f} "
        f"(commentary={clip.commentary_audio_duration_s:.2f}s, "
        f"total={clip.final_duration_s:.2f}s, floor=0.500)"
    )


def _rule_no_music_in_source(clip: CompositedClip) -> tuple[bool, str]:
    ok = clip.has_music_in_source_segment is False
    return ok, (
        "music_detected=False" if ok
        else "music_detected=True — must mute or replace before re-submission"
    )


def _rule_no_real_face_seedance_reference(clip: CompositedClip) -> tuple[bool, str]:
    ok = clip.has_real_face_reference is False
    return ok, (
        "real_face_reference=False" if ok
        else "real_face_reference=True — Seedance reference image must be "
             "non-human-real (cartoon-coded avatar only)"
    )


def _rule_attribution_present(clip: CompositedClip) -> tuple[bool, str]:
    desc = (clip.description or "").lower()
    creator = (clip.source_creator or "").lower().strip()
    if not creator:
        return False, "source_creator missing on CompositedClip"
    ok = creator in desc
    return ok, (
        f"attribution_contains('{clip.source_creator}')={ok}"
    )


def _rule_transformative_purpose_disclosed(clip: CompositedClip) -> tuple[bool, str]:
    """Description must surface that this is commentary/reaction, not raw upload.

    Look for any of the transformative-purpose markers. The Publisher prepares
    the description from a template that includes one of these by default —
    this rule guards against template drift.
    """
    desc = (clip.description or "").lower()
    markers = ("commentary", "reaction", "analysis", "critique", "review")
    found = [m for m in markers if m in desc]
    ok = bool(found)
    return ok, (
        f"transformative_markers_found={found}"
    )


def _rule_ai_content_label(clip: CompositedClip) -> tuple[bool, str]:
    """If any generated visual is in the output, description must signal AI involvement.

    Platforms (TikTok / YouTube / Instagram) require an AI-content label on the
    platform side; Publisher applies that. We additionally require an
    in-description note to keep the audit trail tight.
    """
    has_generated = bool(clip.visuals_used)
    if not has_generated:
        return True, "no_generated_visuals — label not required"
    desc = (clip.description or "").lower()
    markers = ("ai-generated", "ai generated", "synthetic", "ai visuals", "ai-assisted", "ai assisted")
    found = [m for m in markers if m in desc]
    ok = bool(found)
    return ok, f"generated_visuals_present=True, ai_markers_found={found}"


def _rule_no_voice_clone_of_source_creator(clip: CompositedClip) -> tuple[bool, str]:
    """We only support neutral AI personas. The audio track's engine field is
    informational. The structural check: voice engine is Coqui or ElevenLabs
    on an approved-persona voice ID — never a cloned-from-source voice.
    This rule is a placeholder that asserts the engine field is set; the
    deeper "is this a source-creator clone" check belongs in the Voice agent
    itself (which is the only stage that could introduce such a clone).
    """
    engine = (clip.audio_track.engine or "").lower() if clip.audio_track else ""
    ok = engine in {"coqui_xtts_v2", "elevenlabs"}
    return ok, f"voice_engine='{engine}'"


def _rule_finite_durations(clip: CompositedClip) -> tuple[bool, str]:
    if clip.final_duration_s <= 0:
        return False, "final_duration_s <= 0"
    if clip.source_segment_duration_s < 0:
        return False, "source_segment_duration_s < 0"
    if clip.commentary_audio_duration_s < 0:
        return False, "commentary_audio_duration_s < 0"
    return True, "durations_finite_and_nonneg"


# ---------- Rule registry ----------

# Order matters only for human-readable rationale; all rules are evaluated.
RULES: list[tuple[str, Callable[[CompositedClip], tuple[bool, str]]]] = [
    ("finite_durations", _rule_finite_durations),
    ("source_max_30s", _rule_source_max_30s),
    ("total_max_60s", _rule_total_max_60s),
    ("commentary_at_least_50pct", _rule_commentary_at_least_50pct),
    ("no_music_in_source_segment", _rule_no_music_in_source),
    ("no_real_face_seedance_reference", _rule_no_real_face_seedance_reference),
    ("attribution_present", _rule_attribution_present),
    ("transformative_purpose_disclosed", _rule_transformative_purpose_disclosed),
    ("ai_content_label_when_applicable", _rule_ai_content_label),
    ("no_voice_clone_of_source_creator", _rule_no_voice_clone_of_source_creator),
]


# ---------- Public API ----------

def evaluate(clip: CompositedClip) -> ComplianceResult:
    """Evaluate every rule. Return ComplianceResult.

    Pure function — does not touch the DB. Callers should persist the result
    via `record(clip, result)` if running under the live pipeline.
    """
    rule_results: dict[str, dict] = {}
    failures: list[str] = []
    for rule_id, fn in RULES:
        passed, detail = fn(clip)
        rule_results[rule_id] = {"passed": passed, "detail": detail}
        if not passed:
            failures.append(rule_id)

    passed_all = not failures
    blocked_reason = None if passed_all else "; ".join(failures)
    return ComplianceResult(
        passed=passed_all,
        blocked_reason=blocked_reason,
        rule_results=rule_results,
    )


def record(clip: CompositedClip, result: ComplianceResult) -> None:
    """Persist a ComplianceResult to compliance_results + emit an event."""
    from agents.db import connect  # local import to keep evaluate() pure

    with connect() as conn:
        conn.execute(
            """
            INSERT INTO compliance_results
              (clip_id, passed, rule_results_json, blocked_reason)
            VALUES (?, ?, ?, ?)
            """,
            (
                clip.clip_id,
                1 if result.passed else 0,
                json.dumps(result.rule_results),
                result.blocked_reason,
            ),
        )

    log(
        agent="compliance",
        event_type="clip_evaluated",
        level="info" if result.passed else "blocked",
        clip_id=clip.clip_id,
        payload={"rule_results": result.rule_results},
        rationale=(
            "all rules passed" if result.passed
            else f"blocked: {result.blocked_reason}"
        ),
    )


def gate(clip: CompositedClip) -> ComplianceResult:
    """Evaluate + record. Returns the result; caller decides routing."""
    result = evaluate(clip)
    record(clip, result)
    return result
