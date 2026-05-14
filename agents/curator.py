"""Curator — ranks Scout output by predicted view-to-effort ratio.

Reads `clips_candidate` rows where status='discovered', scores each by
virality (placeholder heuristic in Phase 1), promotes the top N to
status='curated' with a virality_score.

Per CLAUDE.md "Architecture / Agent topology" — Curator step 2 in the data
flow. LLM-based virality scoring is deferred to Phase 2.
"""

from __future__ import annotations

from agents.config import load
from agents.db import connect
from agents.events import log
from agents.models import CandidateClip


# Creator-weight applied to source view count as a placeholder for the real
# LLM-based virality score. Phase 2 replaces this with a Claude-judgment
# scoring pass that considers the script-friendliness of the moment.
_CREATOR_WEIGHTS: dict[str, float] = {
    "IShowSpeed": 1.20,
    "Kai Cenat": 1.15,
    "Sketch": 1.00,
    "Jynxzi": 1.05,
    "Adin Ross": 0.95,   # elevated Compliance scrutiny per creators.yaml drama_override
}


def _placeholder_virality_score(view_count: int | None, creator: str) -> float:
    # TODO(phase2): replace with Claude-judged virality + retention prediction.
    # Inputs we'll want: transcript-snippet preview, peak-chat-velocity at the
    # moment, audio energy curve, and the trending refs that could attach.
    if not view_count or view_count <= 0:
        return 0.0
    weight = _CREATOR_WEIGHTS.get(creator, 1.0)
    # Squash to 0..1 with a log curve so a 10M-view clip doesn't dominate.
    import math
    raw = math.log10(view_count + 1) / 8.0  # log10(1e8) ≈ 1.0
    return max(0.0, min(1.0, raw * weight))


def _row_to_candidate(row) -> CandidateClip:
    return CandidateClip(
        id=row["id"],
        creator=row["creator"],
        source_platform=row["source_platform"],
        source_url=row["source_url"],
        source_title=row["source_title"],
        source_duration_s=row["source_duration_s"],
        source_view_count=row["source_view_count"],
        virality_score=row["virality_score"],
        predicted_views=row["predicted_views"],
    )


async def run_curator(batch_size: int = 10) -> list[CandidateClip]:
    """Score every discovered candidate, promote top `batch_size` to 'curated'.

    Returns the list of promoted CandidateClip records (with virality_score set).
    """
    # Honour optimizer_bounds drama_override note — keep curation rules untouched.
    load("optimizer_bounds")  # surface load errors early

    with connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM clips_candidate
            WHERE status = 'discovered'
            ORDER BY scouted_at ASC
            """
        ).fetchall()

    if not rows:
        log(agent="curator", event_type="run_complete",
            payload={"considered": 0, "promoted": 0},
            rationale="no candidates in 'discovered' state")
        return []

    scored: list[tuple[float, CandidateClip]] = []
    for row in rows:
        candidate = _row_to_candidate(row)
        score = _placeholder_virality_score(candidate.source_view_count, candidate.creator)
        candidate.virality_score = score
        scored.append((score, candidate))

    scored.sort(key=lambda x: x[0], reverse=True)
    promoted = [c for _, c in scored[:batch_size]]
    skipped = [c for _, c in scored[batch_size:]]

    with connect() as conn:
        for candidate in promoted:
            conn.execute(
                """
                UPDATE clips_candidate
                   SET status = 'curated',
                       virality_score = ?,
                       curated_at = datetime('now')
                 WHERE id = ?
                """,
                (candidate.virality_score, candidate.id),
            )

    for candidate in promoted:
        log(
            agent="curator",
            event_type="clip_curated",
            clip_id=candidate.id,
            payload={
                "creator": candidate.creator,
                "score": candidate.virality_score,
                "view_count": candidate.source_view_count,
            },
            rationale=f"promoted with score {candidate.virality_score:.3f}",
        )

    for candidate in skipped:
        log(
            agent="curator",
            event_type="clip_skipped",
            level="debug",
            clip_id=candidate.id,
            payload={"score": candidate.virality_score},
            rationale="outside curated batch_size",
        )

    log(agent="curator", event_type="run_complete",
        payload={"considered": len(scored), "promoted": len(promoted)},
        rationale=f"curated top {len(promoted)} of {len(scored)}")
    return promoted
