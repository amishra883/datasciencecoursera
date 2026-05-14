# agentic-clipper

Autonomous clipping & AI-commentary pipeline for short-form video distribution.

**The source of truth for this project is [`CLAUDE.md`](./CLAUDE.md).** Read it before doing anything else.

This repo is currently in **Phase 0** (research & validation). No pipeline code is scaffolded yet — that waits for human approval of the digest in `docs/phase0_digest.md`.

## Repo layout

```
/agents/         (not yet scaffolded)
/config/         clipper_programs.yaml, creators.yaml, persona.yaml,
                 avatar_reactions.yaml, avatars/
/docs/           phase0_digest.md, fair_use_position.md, posting_apis.md,
                 exit_strategy.md, backup_warming.md, seedance_access.md
/data/           (empty; populated by pipeline once scaffolded)
/proposals/      (empty; Optimizer writes weekly diffs here)
/scripts/        (not yet scaffolded)
/tests/          (not yet scaffolded)
CLAUDE.md        spec / source of truth
```
