# Dibble Diagram Quality Direction

**Date:** June 8, 2026  
**Source risk:** `R16` in [2026-05-05-risk-register.md](/Users/sfw/Development/dibble/planning/2026-05-05-risk-register.md)  
**Related plan:** [2026-05-07-risk-reduction-execution-plan.md](/Users/sfw/Development/dibble/planning/2026-05-07-risk-reduction-execution-plan.md)

## Decision

Choose **narrow SVG hardening now**, with a **documented migration path** to structured diagram targets later if pilot evidence shows the current path is insufficient.

Do **not** switch immediately to a DSL-backed diagram system in this slice.

## Why this is the right call now

### 1. The current diagram path is already narrower than the original risk wording implied

The codebase is not in a pure "arbitrary diagram generation" posture.

Current behavior:

- [diagram.py](/Users/sfw/Development/dibble/src/dibble/plugins/modalities/diagram.py) constrains the modality to a simple labeled visual representation plus caption and text companion block.
- [content_provider.py](/Users/sfw/Development/dibble/src/dibble/services/content_provider.py) already contains a deterministic fallback SVG template rather than a broad free-form renderer.
- [rules.py](/Users/sfw/Development/dibble/src/dibble/services/validation/rules.py) already enforces some diagram accessibility and text-composition checks.

So the live risk is real, but the system is already on a narrow path rather than a fully unconstrained multimodal renderer.

### 2. The current proof/pilot story does not require a full diagram DSL yet

Per [modality-decision.md](/Users/sfw/Development/dibble/docs/proof/modality-decision.md), the current modality thesis is intentionally capped at:

- `text`
- `narrative`
- `diagram`

The role of `diagram` in the current proof is:

- show a visibly different representation
- support explanation/worked-example flows
- stay inspectable and safe for a household-first pilot

That does **not** yet require:

- algebra graphing primitives
- interactive manipulatives
- rich authored geometry layout
- generalized chart grammars

A structured DSL would be a larger investment than the current proof needs.

### 3. A DSL-backed shift would reopen more surface area than this plan is trying to touch

Moving now to a structured diagram target would imply new work across:

- authoring constraints
- generation contracts
- rendering/runtime format
- validation semantics
- fallback generation
- artifact provenance
- likely frontend rendering assumptions later

That is the kind of change we should make only when the current narrow path demonstrably blocks pilot quality or product truthfulness.

## What is weak in the current path

The current path is still limited.

### 1. Prompt-side diagram generation is only lightly constrained

The diagram plugin still asks for:

- one simple labeled visual representation
- inline SVG
- short caption

That leaves the provider-side output shape broader than ideal when the real provider is generating content rather than the deterministic fallback.

### 2. Validation is composition/accessibility-heavy, not semantic

Current validation mainly checks:

- there is an instructional companion block
- SVG has an `aria-label`
- text guidance exists alongside the visual

It does **not** yet check:

- whether the visual structure actually matches the intended math/concept relation
- whether labels correspond to the grounded concept
- whether the visual is malformed in subtler ways
- whether the representation is pedagogically appropriate for the KC

### 3. The fallback template is safe but generic

The fallback SVG template is useful for proof and degraded mode, but it is still a generic two-box-and-caption representation. It is not a deep concept-specific diagram system.

That means the current ceiling is not immediate breakage. The current ceiling is **limited representational richness**.

## Recommended near-term direction

For the current pilot/proof phase, the right move is:

### Step 1. Harden the narrow SVG contract

Constrain diagrams more explicitly around a tiny supported family such as:

- compare / what-stays-the-same
- target-plus-invariant
- step / relationship / transformation

This keeps diagrams readable and easier to verify.

### Step 2. Strengthen validation around structural expectations

Add checks for things like:

- required titles/captions/labels
- bounded SVG element set
- maximum complexity
- no unsupported scripting/styling constructs
- concept-to-label consistency where detectable

This still stays far smaller than a DSL migration.

### Step 3. Keep deterministic fallback as the safety floor

The deterministic SVG template should remain the degraded-mode truth path.

That gives Dibble:

- predictable accessibility
- safe fallback
- visible modality differentiation

even if provider output is rejected or simplified.

## When to migrate to structured diagram targets

We should reopen the structured-rendering decision only if one of these becomes true:

- proof/pilot observers cannot tell whether the diagram is meaningfully better than text
- math/visual quality reviews repeatedly flag provider-generated SVG as too generic or too error-prone
- we need domain-specific visuals such as number lines, fraction bars, coordinate graphs, or geometry layouts that cannot be safely represented through the current narrow SVG contract
- interactive diagram behavior becomes part of the actual product claim

At that point, the best next move would likely be a structured family, not general free-form SVG:

- number-line / fraction / bar-model renderers
- function/graph renderers
- geometry renderer

## Migration shape for later

If we later move beyond the current path, the migration should be incremental:

1. keep the `diagram` modality id stable
2. introduce a structured intermediate diagram payload alongside raw SVG
3. support a few renderer families first
4. preserve text companion and accessibility metadata requirements
5. keep deterministic fallback available underneath

That path avoids breaking the current modality thesis while letting the rendering engine mature.

## Bottom line

For this plan, the right answer is:

- **now:** narrow SVG hardening
- **later if needed:** structured diagram targets

That keeps the pilot story honest, improves safety and inspectability, and avoids reopening a much larger multimodal architecture change before the current household-first proof actually demands it.
