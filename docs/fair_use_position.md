# Fair-use position — Phase 0.4

> Captured 2026-05-14. Re-evaluate quarterly per CLAUDE.md "Legal & risk register". Next review due: 2026-08-14.

## Operator posture (2026-05-14)

**Fair use is now the SOLE legal defense.** On 2026-05-14 the operator chose to operate fair-use-only — no clipper programs engaged, no Whop campaigns joined, no creator-licensing relationships. This document is therefore not the backup defense (as the CLAUDE.md spec originally contemplated, with clipper-program licenses as the primary shield); it is the only defense.

Implications:
- Compliance is the load-bearing wall. If the gate fails to enforce any rule below, the pipeline pauses publishing — there is no "we have a license" fallback.
- Strike risk is materially higher than in a licensed posture. Backup accounts and the per-account strike monitor are no longer redundancy; they are operationally required.
- A creator who publicly objects to unlicensed clip channels is a higher-priority drop signal under this posture (we cannot point at their program enrollment).

## Bottom line

This operation's fair-use posture rests on **substantive transformative commentary** plus a set of **enforced operational rules** (length cap, commentary ratio, attribution, no music passthrough). Fair use is a defense, not an immunity — even with this posture we expect occasional Content ID claims and we maintain backup accounts to limit blast radius. The posture is strongest against U.S. 17 U.S.C. § 107 and weakest against platform-level enforcement (Content ID, Rights Manager, TikTok copyright tools), which operate independently of the legal doctrine.

## Scope of this analysis

This document covers the U.S. fair-use defense (17 U.S.C. § 107) for derivative short-form videos that combine ≤30s of source footage with AI-generated commentary, captions, and visuals. It does **not** cover:

- Clipper-program license terms — those are tracked in `/config/clipper_programs.yaml` and govern us when present
- Non-U.S. jurisdictions (UK fair dealing, EU exceptions, etc.) — flagged below
- Right-of-publicity and likeness rights — covered separately under "Risk register" in CLAUDE.md
- Platform ToS — covered in `/docs/posting_apis.md`

## Four-factor analysis

### Factor 1 — Purpose and character of the use

**The most important factor post-*Warhol v. Goldsmith* (2023).** Courts now ask whether the use has a "further purpose or different character" than the original.

**Our posture:** Commentary is the product. The source clip is reference material that grounds the commentary the way a quoted passage grounds a book review. Specifically:

- Every script is structured **hook → take → payoff** with a substantive observation (prediction, comparison, counter-take, contextual fact, character analysis, or pattern observation). Pure narration is rejected at the Writer stage.
- AI commentary occupies **≥50% of the audio runtime** (hard gate in Compliance). The source's audio is ducked under the commentary; ambient creator audio is not the dominant track.
- The **purpose differs from the original**: the source is entertainment in its own right (a streamer's gameplay, reaction, IRL moment); our output is *meta-commentary about that moment* — analysis, parody, critique, or absurdist riff.
- Captions and avatar reactions add a separate creative layer that exists only in our output.
- The use is **commercial** (we monetize via ad-rev share and affiliate links). Commerciality weighs against fair use but does not defeat it where the use is sufficiently transformative (*Campbell v. Acuff-Rose*, 1994; *Warhol*, 2023).

**Operational rules that enforce Factor 1:**

| Rule | Enforced by | Where |
|---|---|---|
| Hook in first 1.5s; never "today we're looking at..." | Writer prompt + Compliance check | `config/persona.yaml` |
| ≥1 substance tag per script (prediction/comparison/counter-take/etc.) | Writer | `config/persona.yaml` |
| Commentary ≥50% of audio runtime | Compliance (hard gate) | `agents/compliance.py` (Phase 1) |
| Punch density ≥0.10 punches/sec | Writer self-score → rewrite if low | `config/persona.yaml` |
| Description discloses transformative-commentary purpose + #ad if affiliate | Publisher | `agents/publisher.py` (Phase 1) |

### Factor 2 — Nature of the copyrighted work

**Our posture:** Source works are typically published, performance/entertainment content (streams, podcasts, reaction videos). Published works receive less fair-use protection than unpublished, but published entertainment is squarely in fair-use case law for commentary and criticism. We do not clip unpublished material.

We avoid clipping creators' personal IRL footage where the subject is in a private setting; we focus on stream broadcasts and clips already curated by the creator's community.

**Operational rules that enforce Factor 2:**

- Scout pulls from public Twitch clips, public YouTube uploads, public TikTok posts. No private streams, no leaked content.
- Anything flagged "unlisted" or "members-only" is rejected at ingestion.

### Factor 3 — Amount and substantiality of the portion used

**Our posture:** We use ≤30s of source footage per output (hard cap). Total output is ≤60s. We never clip the "heart of the work" in the sense of an entire monetizable highlight; we clip a moment *to react to it*, not to substitute for the original.

The amount is small both in absolute terms and relative to source works that typically run 4-12 hours (streams) or 5-30 minutes (YouTube uploads).

**Operational rules that enforce Factor 3:**

| Rule | Enforced by | Where |
|---|---|---|
| Source clip ≤30s | Editor + Compliance | hard gate |
| Total output ≤60s | Compositor + Compliance | hard gate |
| Commentary ≥50% of audio | Compliance | hard gate |
| No music-only passthrough segment | Compliance music detector | hard gate |

### Factor 4 — Effect on the market for the original

**Our posture:** Our output does not substitute for the source. A viewer who watches our 50-second commentary clip is **not** thereby satisfied of any desire to watch the original 6-hour stream — if anything, the commentary acts as discovery, driving traffic back to the named creator.

We mitigate market harm further by:

- Naming and crediting the source creator in every description
- Linking back to the source where the platform allows
- Operating under a clipper-program license where one is verified open (`config/clipper_programs.yaml`) — many of these programs explicitly contemplate and welcome derivative clipping
- Never re-uploading raw clips with no commentary (those would substitute for the original; we don't do that)

**Operational rules that enforce Factor 4:**

- Attribution required in every description (Publisher template)
- Source link in description where the destination platform permits
- Operate inside clipper-program terms when the creator has one
- Pause a creator immediately if their program closes (re-evaluate market-effect under no-license posture)

## Defamation, likeness, and adjacent risks

Fair use does not cover defamation or right-of-publicity violations — those are independent torts. We address them with separate operational rules:

- **Defamation**: opinion-framed or fact-based commentary only. No false statements of fact. No accusations of crimes. Writer prompt enforces a "lines to not cross" list (race, sexuality, mental health, family, appearance — no roasting on those axes).
- **Likeness / right of publicity**: AI-cloning a creator's voice or generating the creator's face into Seedance is forbidden. Compliance enforces. Several U.S. states (CA, NY, TN, others) restrict commercial use of a person's likeness.
- **Trademark**: we do not use creator logos, brand marks, or registered show names in our titles or thumbnails. Brand mentions are referential only ("from <stream name>").

## What this posture does NOT defend us against

Be explicit so we don't kid ourselves:

- **Platform copyright tools (YouTube Content ID, Meta Rights Manager, TikTok's tools)** operate independently of legal fair use. Expect occasional claims; have a calm dispute template; do not dispute frivolously (escalation risk).
- **Music in source footage** triggers Content ID instantly. Compliance must detect and mute or replace music segments before publishing.
- **Non-U.S. legal regimes**. UK uses "fair dealing" with narrower categories. EU has specific exceptions per directive. We operate primarily in U.S.-coded markets; non-U.S. exposure is residual.
- **Creators who actively dislike clip channels** can file individual takedowns regardless of fair use. Our defense is operational: pause that creator, route the strike, move on.
- **AI-content disclosure obligations**. Each platform requires labeling of AI-generated visuals/voice in some contexts. Publisher applies platform-specific labels; this is a separate compliance axis from copyright fair use.

## Operational summary — the rules that matter

The fair-use posture lives or dies by these enforced rules:

1. Source clip ≤30s (Editor + Compliance)
2. Total output ≤60s (Compositor + Compliance)
3. Commentary ≥50% of audio runtime (Compliance hard gate)
4. ≥1 substance tag per script (Writer)
5. Hook in first 1.5s, no generic narration (Writer)
6. No music passthrough in source segment (Compliance music detector)
7. Attribution + transformative-purpose disclosure in every description (Publisher)
8. Affiliate disclosure ("#ad") when applicable (Publisher)
9. Clipper-program terms respected when one is verified open (Compliance reads `config/clipper_programs.yaml`)
10. AI-content label applied per platform (Publisher)
11. No AI voice cloning of source creator; no creator-face references to Seedance (Compliance)
12. No defamatory or harassing personal commentary (Writer prompt enforced)

If any of these rules cannot be enforced in production (e.g., Compliance agent fails closed and we cannot detect music passthrough), the pipeline pauses publishing rather than ship a clip outside the posture.

## Re-evaluation triggers

Re-evaluate this position immediately if any of:

- *Warhol*-line of cases extends to AI-derived commentary in a way that narrows transformative-use scope
- A platform's copyright tool changes behavior in a way that affects our fair-use defenses (e.g., Content ID starts auto-claiming on ≤30s clips regardless of overlay)
- A clipper-program creator we depend on closes the program AND we want to keep clipping them under fair use alone (changes Factor 4 calculus)
- A new federal AI-content statute changes the disclosure or licensing landscape
- We exceed 5 successful copyright claims in any 30-day window across all primary accounts (signal that the posture is failing in practice)

Otherwise: full re-review every 90 days. Next: 2026-08-14.

## Sources cited above

- 17 U.S.C. § 107 — Limitations on exclusive rights: Fair use
- *Andy Warhol Foundation v. Goldsmith*, 598 U.S. ___ (2023)
- *Campbell v. Acuff-Rose Music, Inc.*, 510 U.S. 569 (1994)

(This document is not legal advice. If we cross $5k MRR or face an active takedown dispute, retain copyright counsel.)
