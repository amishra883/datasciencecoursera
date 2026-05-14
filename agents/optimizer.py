"""Optimizer — reads /data/learnings.jsonl, proposes config changes.

Auto-applies low-risk changes within optimizer_bounds.yaml.auto_apply.
Higher-risk changes are surfaced as diffs in /proposals/ for human review.
Rollback policy: a change that underperforms baseline by >15% over a 72h
window is automatically rolled back (marked rolled_back=1 in auto_changes).

Per CLAUDE.md "Architecture / Agent topology" — Optimizer step 11, and
"Self-improvement loop".

Live regression / bandit math is deferred to Phase 2. Phase 1 returns a
no-shift placeholder and writes an empty digest.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from agents.config import load
from agents.db import connect
from agents.events import log

REPO_ROOT = Path(__file__).resolve().parent.parent
LEARNINGS_PATH = REPO_ROOT / "data" / "learnings.jsonl"
AUTO_CHANGES_PATH = REPO_ROOT / "data" / "auto_changes.jsonl"
PROPOSALS_DIR = REPO_ROOT / "proposals"


# ---------- Learnings ingest ----------

def _read_learnings() -> list[dict]:
    if not LEARNINGS_PATH.exists():
        return []
    with LEARNINGS_PATH.open() as fh:
        return [json.loads(line) for line in fh if line.strip()]


# ---------- Auto-apply candidates ----------

def _propose_posting_time_shift(learnings: list[dict], bounds: dict) -> dict | None:
    """Placeholder regression. Phase 2: regress engagement on posted_at hour
    per platform, propose a shift up to bounds.max_minutes."""
    # TODO(phase2): actual regression — group by hour of day per platform,
    # compute mean watch_time_pct, propose shift toward the local maximum.
    cfg = bounds.get("posting_time_shift", {})
    if not cfg.get("enabled"):
        return None
    if len(learnings) < cfg.get("min_data_points", 50):
        return None
    return None  # no shift in Phase 1


# ---------- Persistence ----------

def _apply_auto_change(change: dict) -> str:
    """Insert an auto_changes row + append the same record to the JSONL log.
    Returns the generated change id."""
    change_id = change.get("id") or str(uuid.uuid4())
    before_json = json.dumps(change.get("before", {}))
    after_json = json.dumps(change.get("after", {}))
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO auto_changes
              (id, change_type, before_json, after_json, rationale)
            VALUES (?, ?, ?, ?, ?)
            """,
            (change_id, change["change_type"], before_json, after_json,
             change.get("rationale", "")),
        )
    AUTO_CHANGES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with AUTO_CHANGES_PATH.open("a") as fh:
        fh.write(json.dumps({
            "id": change_id,
            "applied_at": datetime.now(timezone.utc).isoformat(),
            **change,
        }) + "\n")
    return change_id


def _write_proposal(proposal: dict) -> Path:
    PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{datetime.now(timezone.utc).strftime('%Y-%m-%d-%H%M')}-{proposal['change_type']}.json"
    path = PROPOSALS_DIR / name
    path.write_text(json.dumps(proposal, indent=2))
    return path


# ---------- Rollback ----------

def _check_rollbacks(bounds: dict) -> list[str]:
    """Mark auto_changes rolled_back=1 if their post-change performance is
    >rollback_threshold_pct% worse than baseline over rollback_window_hours.

    Phase 1: stub. The real check needs a baseline window before each change
    and a post-change window — both joined against performance_metrics.
    """
    # TODO(phase2): compute baseline vs post-change watch_time_pct per change
    # and roll back if (baseline - post) / baseline > rollback_threshold.
    _ = bounds
    return []


# ---------- Public entry point ----------

async def run_optimizer() -> dict:
    """Return a digest dict of what was proposed and applied this run."""
    bounds = load("optimizer_bounds")
    auto_bounds = bounds.get("auto_apply", {})
    learnings = _read_learnings()

    applied: list[str] = []
    proposed: list[str] = []

    # --- Auto-apply: posting-time shift (Phase 1 returns None) ---
    shift = _propose_posting_time_shift(learnings, auto_bounds)
    if shift is not None:
        change_id = _apply_auto_change(shift)
        applied.append(change_id)
        log(agent="optimizer", event_type="auto_change_applied",
            payload={"change_id": change_id, "change_type": shift["change_type"]},
            rationale=shift.get("rationale", ""))

    # --- Human-review proposals (Phase 1: none generated yet) ---
    # TODO(phase2): emit proposals for: new persona, new hook template,
    # creator rotation changes, Seedance Pro threshold changes, budget shifts.

    # --- Rollback sweep ---
    rolled_back = _check_rollbacks(bounds.get("rollback", {}))
    for change_id in rolled_back:
        with connect() as conn:
            conn.execute(
                """
                UPDATE auto_changes
                   SET rolled_back = 1,
                       rolled_back_at = datetime('now'),
                       rollback_reason = ?
                 WHERE id = ?
                """,
                ("underperformed baseline > threshold", change_id),
            )
        log(agent="optimizer", event_type="auto_change_rolled_back",
            level="autorolledback", payload={"change_id": change_id},
            rationale="post-change performance below rollback threshold")

    digest = {
        "learnings_count": len(learnings),
        "applied": applied,
        "proposed": proposed,
        "rolled_back": rolled_back,
    }
    log(agent="optimizer", event_type="run_complete",
        payload=digest,
        rationale=f"applied={len(applied)} proposed={len(proposed)} "
                  f"rolled_back={len(rolled_back)}")
    return digest
