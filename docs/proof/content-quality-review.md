# Content Quality Review For Proof Runs

This is the lightweight review method for generated proof samples. It is not an
annotation platform. It is an operator checklist that makes content review
repeatable across households and proof runs.

## When To Review

Review generated samples after each live proof or longitudinal rehearsal report.
The report lists captured samples under `Content samples captured`.

For final POC proof, review at least:

- every longitudinal sample in the live proof report
- the reusable source and peer samples that demonstrate cache/library reuse
- samples from the additional operator household when multi-household evidence
  is enabled
- any sample attached to weak learner evidence, recovery, fallback, or parent
  approval confusion

## Review Categories

Use these categories for each sample:

- `curriculum_fit`: The content teaches the named KC/outcome and does not drift
  into unrelated material.
- `misconception_targeting`: The content addresses the intended misconception or
  evidence need, especially denominator-size confusion in the fraction proof.
- `age_fit`: The wording, task shape, and assumed background fit the seeded
  grade and household posture.
- `privacy`: The content contains no learner identity, household facts,
  credentials, private history, or session-specific profile detail.
- `actionability`: A parent/operator can tell whether to approve, retry,
  inspect, or pause after seeing the sample and surrounding report context.

## Suggested Notes Format

For each reviewed sample, record:

```text
sample: session-2-recovery-plan/avery gen-...
curriculum_fit: pass
misconception_targeting: pass
age_fit: watch - vocabulary may be dense
privacy: pass
actionability: pass
operator_note: Acceptable for proof; simplify wording before unsupervised use.
```

Use `pass`, `watch`, or `fail`. A `watch` item does not invalidate the POC by
itself, but it should be named in the final proof summary. A `fail` item blocks
pilot use until fixed or excluded.

## What Counts As Broadened Review

Broadened review means more than a single curated checkpoint. A credible proof
package should include samples from:

- baseline practice
- recovery or remediation
- confirmation practice
- reusable source content
- reusable peer/cache-hit content
- at least one additional household seed or proof run

The review can remain operator-managed and seeded. Do not describe this as
large-scale content QA or efficacy validation.
