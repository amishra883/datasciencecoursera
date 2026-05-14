"""Editor — downloads the source clip and identifies the punch segment.

Reads a curated `clips_candidate` row, downloads via yt-dlp, runs faster-whisper
to get a transcript, then picks the 15–30s segment most likely to land as a
short. Live yt-dlp/whisper integration is deferred to Phase 2.

Per CLAUDE.md "Architecture / Agent topology" — Editor step 3 in the data flow.
"""

from __future__ import annotations

import json
from pathlib import Path

from agents.db import connect
from agents.events import log
from agents.models import TranscriptSegment

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_CLIP_DIR = REPO_ROOT / "data" / "clips" / "raw"

# Placeholder bounds. The real picker uses transcript-energy + chat velocity.
PLACEHOLDER_PUNCH_START_S = 0.0
PLACEHOLDER_PUNCH_END_S = 25.0


async def _download_source(source_url: str, dest_path: Path) -> None:
    # TODO(phase2): wire yt-dlp via subprocess or python-yt-dlp.
    # Needs: cookies file for age-gated content; format selector for
    # mp4+aac under 30s when possible.
    raise NotImplementedError("live mode not implemented in Phase 1 scaffold")


async def _transcribe(local_path: Path) -> list[TranscriptSegment]:
    # TODO(phase2): wire faster-whisper (GPU if CUDA available, CPU fallback).
    # Return word-level timestamps; caption burn-in in the Compositor depends
    # on the `words` field per TranscriptSegment.
    raise NotImplementedError("live mode not implemented in Phase 1 scaffold")


def _pick_punch_segment(
    transcript: list[TranscriptSegment],
) -> tuple[float, float]:
    # TODO(phase2): replace with Claude+heuristic scoring of the 25s window
    # whose laugh density + caption-friendliness is highest.
    return PLACEHOLDER_PUNCH_START_S, PLACEHOLDER_PUNCH_END_S


def _load_candidate(clip_id: str) -> dict:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM clips_candidate WHERE id = ?", (clip_id,)
        ).fetchone()
    if row is None:
        raise KeyError(f"no clips_candidate row with id={clip_id}")
    return dict(row)


def _persist_artifact(
    clip_id: str,
    *,
    source_local_path: str,
    transcript: list[TranscriptSegment],
    start_s: float,
    end_s: float,
) -> None:
    payload = [
        {"start_s": s.start_s, "end_s": s.end_s, "text": s.text, "words": s.words}
        for s in transcript
    ]
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO clip_artifacts
              (clip_id, source_local_path, transcript_json,
               punch_segment_start_s, punch_segment_end_s, updated_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(clip_id) DO UPDATE SET
              source_local_path = excluded.source_local_path,
              transcript_json   = excluded.transcript_json,
              punch_segment_start_s = excluded.punch_segment_start_s,
              punch_segment_end_s   = excluded.punch_segment_end_s,
              updated_at        = datetime('now')
            """,
            (clip_id, source_local_path, json.dumps(payload), start_s, end_s),
        )
        conn.execute(
            "UPDATE clips_candidate SET status = 'processing' WHERE id = ?",
            (clip_id,),
        )


async def run_editor(clip_id: str) -> None:
    """Download + transcribe + segment one candidate. Writes to clip_artifacts.

    Phase 1 scaffold: skips the live yt-dlp/whisper calls and stores an empty
    transcript + placeholder punch segment so downstream agents can still be
    smoke-tested end-to-end.
    """
    candidate = _load_candidate(clip_id)
    RAW_CLIP_DIR.mkdir(parents=True, exist_ok=True)
    dest_path = RAW_CLIP_DIR / f"{clip_id}.mp4"

    transcript: list[TranscriptSegment] = []
    try:
        await _download_source(candidate["source_url"], dest_path)
        transcript = await _transcribe(dest_path)
    except NotImplementedError:
        log(
            agent="editor",
            event_type="phase1_scaffold",
            clip_id=clip_id,
            payload={"source_url": candidate["source_url"]},
            rationale="yt-dlp + whisper stubbed in Phase 1; using placeholder transcript",
        )

    start_s, end_s = _pick_punch_segment(transcript)
    _persist_artifact(
        clip_id,
        source_local_path=str(dest_path),
        transcript=transcript,
        start_s=start_s,
        end_s=end_s,
    )

    log(
        agent="editor",
        event_type="clip_edited",
        clip_id=clip_id,
        payload={
            "punch_start_s": start_s,
            "punch_end_s": end_s,
            "transcript_segments": len(transcript),
        },
        rationale=f"selected punch segment {start_s:.1f}-{end_s:.1f}s",
    )
