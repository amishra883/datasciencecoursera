"""Analyst — daily metrics join. Reads feature_records that are >=48h old and
have no performance_metrics row yet, pulls platform stats, writes one row
to performance_metrics, and appends the joined record to
/data/learnings.jsonl (the Optimizer's input).

Per CLAUDE.md "Architecture / Agent topology" — Analyst step 10, and
"Self-improvement loop / Continuous (per-clip)".

Live platform-analytics API calls are deferred to Phase 2.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from agents.db import connect
from agents.events import log

REPO_ROOT = Path(__file__).resolve().parent.parent
LEARNINGS_PATH = REPO_ROOT / "data" / "learnings.jsonl"

# A feature_record is eligible for metrics joining once this many hours have
# passed since posted_at — matches the spec's 48h window.
METRICS_AGE_HOURS = 48


# ---------- Platform metrics stubs ----------

async def _pull_youtube_metrics(platform_post_id: str) -> dict:
    # TODO(phase2): wire YouTube Analytics API v2 (reports.query).
    # Needs: OAuth refresh token, channel id, the video id (platform_post_id).
    raise NotImplementedError("live mode not implemented in Phase 1 scaffold")


async def _pull_tiktok_metrics(platform_post_id: str) -> dict:
    # TODO(phase2): wire TikTok Research API or Content Posting API analytics
    # endpoint (depends on Phase 0.3 outcome).
    raise NotImplementedError("live mode not implemented in Phase 1 scaffold")


async def _pull_instagram_metrics(platform_post_id: str) -> dict:
    # TODO(phase2): wire Instagram Graph API media insights endpoint
    # (GET /{ig-media-id}/insights).
    raise NotImplementedError("live mode not implemented in Phase 1 scaffold")


_DISPATCH = {
    "youtube_shorts": _pull_youtube_metrics,
    "tiktok": _pull_tiktok_metrics,
    "instagram_reels": _pull_instagram_metrics,
}


# ---------- Helpers ----------

def _due_records() -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT fr.*
              FROM feature_records fr
         LEFT JOIN performance_metrics pm ON pm.feature_record_id = fr.id
             WHERE pm.id IS NULL
               AND julianday('now') - julianday(fr.posted_at) >= ?/24.0
            """,
            (METRICS_AGE_HOURS,),
        ).fetchall()
    return [dict(r) for r in rows]


def _platform_post_id_for(clip_id: str, target_platform: str) -> str | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT platform_post_id FROM clips_ready
             WHERE clip_id = ? AND target_platform = ? AND status = 'posted'
             ORDER BY posted_at DESC LIMIT 1
            """,
            (clip_id, target_platform),
        ).fetchone()
    return row["platform_post_id"] if row else None


def _insert_metrics(feature_record_id: int, metrics: dict, hours_since_post: float) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO performance_metrics
              (feature_record_id, views, watch_time_pct, likes, shares,
               follows_gained, click_throughs, comments, hours_since_post)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                feature_record_id,
                metrics.get("views"),
                metrics.get("watch_time_pct"),
                metrics.get("likes"),
                metrics.get("shares"),
                metrics.get("follows_gained"),
                metrics.get("click_throughs"),
                metrics.get("comments"),
                hours_since_post,
            ),
        )


def _append_learning(feature: dict, metrics: dict) -> None:
    LEARNINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "logged_at": datetime.now(timezone.utc).isoformat(),
        "feature": feature,
        "metrics": metrics,
    }
    with LEARNINGS_PATH.open("a") as fh:
        fh.write(json.dumps(record, default=str) + "\n")


# ---------- Public entry point ----------

async def run_analyst() -> None:
    """Join feature_records (>=48h old) with platform metrics. Append a learning
    row per join. Phase 1 stubs every API call; records that can't be filled
    are skipped and re-tried on the next run.
    """
    records = _due_records()
    if not records:
        log(agent="analyst", event_type="run_complete",
            payload={"joined": 0, "due": 0}, rationale="no records due")
        return

    joined = 0
    for feature in records:
        platform = feature["target_platform"]
        clip_id = feature["clip_id"]
        platform_post_id = _platform_post_id_for(clip_id, platform)
        if not platform_post_id:
            log(agent="analyst", event_type="missing_platform_post_id",
                level="warn", clip_id=clip_id,
                payload={"platform": platform},
                rationale="feature_record has no matching posted clips_ready row")
            continue

        dispatch = _DISPATCH.get(platform)
        if dispatch is None:
            log(agent="analyst", event_type="unsupported_platform",
                level="warn", clip_id=clip_id, payload={"platform": platform},
                rationale="no metrics dispatch")
            continue

        try:
            metrics = await dispatch(platform_post_id)
        except NotImplementedError:
            log(agent="analyst", event_type="phase1_scaffold",
                clip_id=clip_id, payload={"platform": platform},
                rationale="metrics API stubbed in Phase 1; will retry next run")
            continue

        posted_at = datetime.fromisoformat(feature["posted_at"].replace("Z", "+00:00"))
        if posted_at.tzinfo is None:
            posted_at = posted_at.replace(tzinfo=timezone.utc)
        hours_since = (datetime.now(timezone.utc) - posted_at).total_seconds() / 3600.0

        _insert_metrics(feature["id"], metrics, hours_since)
        _append_learning(feature, metrics)
        joined += 1
        log(agent="analyst", event_type="metrics_joined", clip_id=clip_id,
            payload={"platform": platform, "views": metrics.get("views")},
            rationale=f"feature_record_id={feature['id']}")

    log(agent="analyst", event_type="run_complete",
        payload={"joined": joined, "due": len(records)},
        rationale=f"joined {joined}/{len(records)} records")
