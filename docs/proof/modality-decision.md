# Modality Sufficiency Decision

Decision: `text`, `narrative`, and `diagram` are sufficient for the POC proof phase. Do not add `audio` or `widget` in this pivot unless scenario rehearsal shows a specific proof blocker.

## Why This Is Enough

- `text` covers direct explanation, worked examples, practice prompts, and Socratic-style language.
- `narrative` changes the learning experience materially by embedding the same curriculum target in story structure, theme, and character context.
- `diagram` changes the representation materially by making spatial or visual structure inspectable.
- The routing harness can already select among these modalities and apply rollout fallback when non-text modalities are constrained.
- The adaptive modality scenario can show a clear before/after: a learner stalls in text or narrative, then receives a diagram or a policy-constrained fallback.

## Why Not Add One More Now

`audio` would strengthen accessibility and engagement, but it introduces provider, transcript, duration, and caption-alignment obligations that are not necessary to prove the household-first thesis.

`widget` would strengthen active manipulation, but it adds sandboxing, generated-code verification, frontend iframe/runtime hardening, and a much larger pilot support surface.

For this phase, those costs would move attention away from deployment proof, scenario proof, and parent/operator readiness.

## Revisit Trigger

Reopen the modality decision only if one of these happens during scenario rehearsal:

- Non-technical observers cannot tell the difference between text and narrative/diagram routes.
- The adaptive modality scenario cannot produce a visible representation change with current plugins.
- A pilot learner need requires audio accessibility before the first cohort can responsibly proceed.
- A pilot success criterion explicitly requires interactive manipulation rather than explanation or static representation.

Until then, the POC modality set is intentionally capped at the existing three modalities.
