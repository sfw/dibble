# Dibble Live Household Proof Report

- Generated: 2026-05-04T15:26:53.006304+00:00
- Base URL: http://localhost:8000
- Household ID: c00ebdfc-bae1-4069-921d-aed04ad08336
- Run stamp: 29ab12ff

## Readiness

- Status: degraded
- Deployment mode: household_container
- LLM provider: warn (No LLM key is configured; deterministic mock fallback is active.)
- Mock fallback enabled: True
- Cloud library enabled: False
- Warning checks: llm_provider

Next steps from `/ready`:
- Configure a real LLM provider before running pilot learners.

## Canonical Scenarios

- shared_library_reuse_without_privacy_leakage: reuse_source generation=c53b15d6-7c02-4178-9587-c5afcf28060d; reuse_peer cache_hit=True; audit_entries=3

## Operator Review Checklist

- Confirm `/ready` is acceptable for the intended run posture.
- Confirm real-provider proof has mock fallback disabled.
- Review generated content samples for curriculum fit and privacy.
- Confirm restart and restore evidence are present before learner use.
