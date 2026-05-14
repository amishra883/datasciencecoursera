"""Scout — discovers candidate clips from source platforms every 4h.

Reads /config/creators.yaml for the top-5 rotation, then queries each source
platform for new clips per creator. Live API integration is deferred to
Phase 2; this module is a structural scaffold only.

Per CLAUDE.md "Architecture / Agent topology" — Scout step 1 in the data flow.

Also implements the "no fresh source in 30d" alert flagged in
config/creators.yaml red_flags (open) — Kai Cenat Twitch supply gap.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from agents.config import load
from agents.db import connect
from agents.events import log
from agents.models import CandidateClip, SourcePlatform

# Days without fresh content before Scout raises a warn-level alert per creator.
NO_FRESH_SOURCE_ALERT_DAYS = 30


# ---------- Source-platform clients (Phase 2 wiring) ----------

async def _discover_twitch_clips(creator_handle: str) -> list[CandidateClip]:
    # TODO(phase2): wire Twitch Helix GET /clips with broadcaster_id + 30d window.
    # Needs: TWITCH_CLIENT_ID, TWITCH_CLIENT_SECRET, app-access-token rotation.
    raise NotImplementedError("live mode not implemented in Phase 1 scaffold")


async def _discover_youtube_clips(creator_handle: str) -> list[CandidateClip]:
    # TODO(phase2): wire YouTube Data API v3 search.list filtered to channelId
    # ordered by viewCount within the 90d window, then videos.list for stats.
    raise NotImplementedError("live mode not implemented in Phase 1 scaffold")


async def _discover_tiktok_trending(creator_handle: str) -> list[CandidateClip]:
    # TODO(phase2): wire TikTok Creative Center scrape (or Research API if approved).
    # Note creators.yaml red_flag — TikTok 30d aggregates are unverified for all 5.
    raise NotImplementedError("live mode not implemented in Phase 1 scaffold")


async def _discover_kick_clips(creator_handle: str) -> list[CandidateClip]:
    # TODO(phase2): wire Kick public clip endpoints (Adin Ross substitution per
    # creators.yaml adin_ross_kick_substitution note).
    raise NotImplementedError("live mode not implemented in Phase 1 scaffold")


_PLATFORM_DISPATCH = {
    "twitch": _discover_twitch_clips,
    "youtube": _discover_youtube_clips,
    "tiktok": _discover_tiktok_trending,
    "kick": _discover_kick_clips,
}


# ---------- Helpers ----------

def _make_clip_id(creator: str, source_url: str) -> str:
    """yyyy-mm-dd-hhmm-<short_hash> — matches schema.sql clips_candidate.id."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M")
    h = hashlib.sha1(f"{creator}|{source_url}".encode()).hexdigest()[:8]
    return f"{ts}-{h}"


def _check_fresh_source(creator: str, latest_seen_at: datetime | None) -> None:
    """Warn if a creator has no new content in NO_FRESH_SOURCE_ALERT_DAYS."""
    if latest_seen_at is None:
        log(
            agent="scout",
            event_type="no_fresh_source_alert",
            level="warn",
            payload={"creator": creator, "latest_seen_at": None},
            rationale=f"no source content ever seen for {creator}",
        )
        return
    cutoff = datetime.now(timezone.utc) - timedelta(days=NO_FRESH_SOURCE_ALERT_DAYS)
    if latest_seen_at < cutoff:
        log(
            agent="scout",
            event_type="no_fresh_source_alert",
            level="warn",
            payload={
                "creator": creator,
                "latest_seen_at": latest_seen_at.isoformat(),
                "threshold_days": NO_FRESH_SOURCE_ALERT_DAYS,
            },
            rationale=f"{creator} has no fresh source content in {NO_FRESH_SOURCE_ALERT_DAYS}d",
        )


def _insert_candidate(clip: CandidateClip) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO clips_candidate
              (id, creator, source_platform, source_url, source_title,
               source_duration_s, source_view_count, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'discovered')
            """,
            (
                clip.id,
                clip.creator,
                clip.source_platform,
                clip.source_url,
                clip.source_title,
                clip.source_duration_s,
                clip.source_view_count,
            ),
        )


# ---------- Public entry point ----------

async def run_scout() -> list[CandidateClip]:
    """Discover candidate clips for every creator in /config/creators.yaml.

    Returns the list of newly-inserted CandidateClip rows. Live source-platform
    calls are NotImplementedError stubs — Phase 1 returns an empty list and
    logs a structured "phase1_scaffold" event for each attempted source.
    """
    creators_cfg = load("creators")
    discovered: list[CandidateClip] = []

    for entry in creators_cfg.get("creators", []):
        creator = entry["creator"]
        primary_platforms: list[SourcePlatform] = entry.get("primary_platforms", [])

        # Fresh-source alert — Phase 1 we have no DB history yet, so this is a
        # placeholder call. Phase 2 will query clips_candidate for max(scouted_at).
        _check_fresh_source(creator, latest_seen_at=None)

        for platform in primary_platforms:
            dispatch = _PLATFORM_DISPATCH.get(platform)
            if dispatch is None:
                log(
                    agent="scout",
                    event_type="unsupported_platform",
                    level="warn",
                    payload={"creator": creator, "platform": platform},
                    rationale=f"no dispatch for source platform '{platform}'",
                )
                continue
            try:
                clips = await dispatch(entry["platforms"][platform]["handle"])
            except NotImplementedError:
                log(
                    agent="scout",
                    event_type="phase1_scaffold",
                    level="info",
                    payload={"creator": creator, "platform": platform},
                    rationale="live source client stubbed in Phase 1",
                )
                continue

            for clip in clips:
                _insert_candidate(clip)
                log(
                    agent="scout",
                    event_type="clip_discovered",
                    clip_id=clip.id,
                    payload={
                        "creator": clip.creator,
                        "platform": clip.source_platform,
                        "url": clip.source_url,
                        "view_count": clip.source_view_count,
                    },
                    rationale=f"scouted from {clip.source_platform}",
                )
                discovered.append(clip)

    log(
        agent="scout",
        event_type="run_complete",
        payload={"discovered_count": len(discovered)},
        rationale=f"scout cycle finished, {len(discovered)} new candidates",
    )
    return discovered
