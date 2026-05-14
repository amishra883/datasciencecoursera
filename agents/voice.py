"""Voice — turns a Script into a commentary AudioTrack.

Default engine is local Coqui XTTS-v2 (free). ElevenLabs Creator is an
escalation path gated by persona.escalation_trigger. Audio is normalized
to the persona's target_loudness_lufs. Live TTS + normalization integrations
are deferred to Phase 2.

Per CLAUDE.md "Architecture / Agent topology" — Voice step 5 in the data flow.
"""

from __future__ import annotations

from pathlib import Path

from agents.config import load
from agents.db import connect
from agents.events import log
from agents.models import AudioTrack, Script

REPO_ROOT = Path(__file__).resolve().parent.parent
VOICE_OUT_DIR = REPO_ROOT / "data" / "clips" / "voice"


# ---------- TTS engine stubs ----------

async def _synthesize_coqui(text: str, persona: dict, dest_path: Path) -> float:
    # TODO(phase2): wire coqui XTTS-v2 local inference.
    # Needs: model checkpoint path, speaker reference clip per persona,
    # speaking_rate + pitch_range knobs from persona.voice.
    raise NotImplementedError("live mode not implemented in Phase 1 scaffold")


async def _synthesize_elevenlabs(text: str, persona: dict, dest_path: Path) -> float:
    # TODO(phase2): wire ElevenLabs Creator API (POST /v1/text-to-speech/{voice_id}).
    # Needs: ELEVENLABS_API_KEY, voice_id from persona.voice, cost-cap check
    # against budget.yaml per_clip_caps.elevenlabs_cost_usd_max before call.
    raise NotImplementedError("live mode not implemented in Phase 1 scaffold")


async def _normalize_loudness(audio_path: Path, target_lufs: float) -> float:
    # TODO(phase2): wire ffmpeg loudnorm (two-pass) or pyloudnorm to hit -14 LUFS.
    # Return the measured post-normalization loudness for the AudioTrack record.
    raise NotImplementedError("live mode not implemented in Phase 1 scaffold")


# ---------- Persona / escalation helpers ----------

def _active_persona(persona_cfg: dict) -> dict:
    active_id = persona_cfg["active_persona"]
    for p in persona_cfg["personas"]:
        if p["id"] == active_id:
            return p
    raise KeyError(f"active_persona '{active_id}' not in personas list")


def _should_escalate(persona: dict, curator_score: float | None) -> bool:
    """Persona.voice.escalation_trigger is a string like 'curator_score>=0.85'."""
    trigger = persona["voice"].get("escalation_trigger", "")
    if not trigger or curator_score is None:
        return False
    # Conservative parser: only support the curator_score>=N form for now.
    # TODO(phase2): replace with a generic expression evaluator if more triggers appear.
    prefix = "curator_score>="
    if not trigger.startswith(prefix):
        return False
    try:
        threshold = float(trigger[len(prefix):])
    except ValueError:
        return False
    return curator_score >= threshold


def _load_curator_score(clip_id: str) -> float | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT virality_score FROM clips_candidate WHERE id = ?", (clip_id,)
        ).fetchone()
    return None if row is None else row["virality_score"]


# ---------- Persistence ----------

def _persist_audio(clip_id: str, track: AudioTrack) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO clip_artifacts (clip_id, voice_audio_path, voice_runtime_s, updated_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(clip_id) DO UPDATE SET
              voice_audio_path = excluded.voice_audio_path,
              voice_runtime_s  = excluded.voice_runtime_s,
              updated_at       = datetime('now')
            """,
            (clip_id, track.path, track.runtime_s),
        )


# ---------- Public entry point ----------

async def run_voice(clip_id: str, script: Script) -> AudioTrack:
    """Synthesize commentary audio for a script. Phase 1 returns a placeholder
    AudioTrack so the rest of the pipeline can smoke-test end-to-end.
    """
    persona_cfg = load("persona")
    persona = _active_persona(persona_cfg)
    VOICE_OUT_DIR.mkdir(parents=True, exist_ok=True)
    dest_path = VOICE_OUT_DIR / f"{clip_id}.wav"

    curator_score = _load_curator_score(clip_id)
    escalate = _should_escalate(persona, curator_score)
    engine = "elevenlabs" if escalate else "coqui_xtts_v2"

    runtime_s = script.runtime_s
    loudness_lufs = float(persona["voice"]["target_loudness_lufs"])

    try:
        if escalate:
            runtime_s = await _synthesize_elevenlabs(script.text, persona, dest_path)
        else:
            runtime_s = await _synthesize_coqui(script.text, persona, dest_path)
        loudness_lufs = await _normalize_loudness(
            dest_path, target_lufs=persona["voice"]["target_loudness_lufs"]
        )
    except NotImplementedError:
        log(
            agent="voice",
            event_type="phase1_scaffold",
            clip_id=clip_id,
            payload={"engine": engine, "escalated": escalate},
            rationale="TTS + loudness norm stubbed in Phase 1; using placeholder track",
        )

    track = AudioTrack(
        path=str(dest_path),
        runtime_s=runtime_s,
        loudness_lufs=loudness_lufs,
        engine=engine,
    )
    _persist_audio(clip_id, track)

    log(
        agent="voice",
        event_type="voice_generated",
        clip_id=clip_id,
        payload={
            "engine": engine,
            "runtime_s": track.runtime_s,
            "loudness_lufs": track.loudness_lufs,
            "escalated": escalate,
            "curator_score": curator_score,
        },
        rationale=f"voice synthesized via {engine}",
    )
    return track
