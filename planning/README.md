# Planning Package Map

This directory contains five related planning packages for the adaptive learning platform. They were produced in sequence, but they do not all serve the same purpose.

## Recommended Reading Order

1. `1- adaptive-ed-platform-research/`
2. `2 - adaptive-ed-platform-dev-handoff/`
3. `3 - platform-root/`
4. `4 - revised-spec/`
5. `5 - dev-handoff-revised-spec/`

## What Each Package Is

### 1. Initial Research
Path: `planning/1- adaptive-ed-platform-research/`

Purpose:
- Original research, evidence, architecture ideas, UX concepts, and early technical specification.
- Best treated as the discovery and evidence base for the original product direction.

Status:
- Reference material.
- Helpful for rationale, learning science, compliance, and initial requirements.
- Not the final implementation spec.

## 2. Original Development Handoff
Path: `planning/2 - adaptive-ed-platform-dev-handoff/`

Purpose:
- Structured engineering handoff for the original product concept.
- Includes architecture, API, schema, UX, security, implementation plan, and devops setup.

Status:
- Authoritative only for the original selection-based adaptive platform.
- Superseded once the revised spec was produced.

Key point:
- This package assumes the original architecture centered on recommendation from pre-authored content pools.

## 3. Deeper Development Analysis and Existing Implementation Context
Path: `planning/3 - platform-root/`

Purpose:
- A second-pass analysis of the original system and its implementation context.
- Documents the state of the platform, validates requirements, inventories handoff materials, and captures architecture and tool/source context.

Status:
- Transitional analysis package.
- Useful for understanding what the original system actually was, how complete it was, and where its assumptions broke down.
- Not the current source of product truth.

Key point:
- This package bridges the gap between the original handoff and the later revised-spec effort.

## 4. Revised Specification
Path: `planning/4 - revised-spec/`

Purpose:
- The corrected product specification after recognizing that the original spec did not include enough of the intended functionality.
- Reframes the platform from a recommendation-first system into a more fully adaptive, generative, LLM-powered architecture.

Status:
- Primary product source of truth for the revised platform.
- Use this package to understand what the product is supposed to become.

Key files:
- `adaptive-platform-analysis-report.md`
- `adaptive-learning-architecture.md`
- `gap-analysis.md`
- `implementation-roadmap.md`

## 5. Revised Development Handoff
Path: `planning/5 - dev-handoff-revised-spec/`

Purpose:
- Development handoff package for implementing the revised spec.
- Consolidates migration strategy, impact analysis, traceability, and rollout guidance.

Status:
- Engineering handoff for the revised spec, but with a strong migration framing.
- Best understood as "how to move from package 2 and the original implementation toward package 4."

Key point:
- This is not just a clean-room handoff for the revised platform.
- It is a revised handoff written through the lens of migration from the original handoff and architecture.

## Authority Guide

Use the packages this way:

- Product vision and revised requirements: `planning/4 - revised-spec/`
- Engineering transition and implementation sequencing for the revised platform: `planning/5 - dev-handoff-revised-spec/`
- Original system details and historical assumptions: `planning/2 - adaptive-ed-platform-dev-handoff/`
- Research evidence and supporting rationale: `planning/1- adaptive-ed-platform-research/`
- Transitional analysis of the original platform and implementation context: `planning/3 - platform-root/`

## Practical Summary

If we are building the current intended product:

- Read `4` to understand the target system.
- Read `5` to understand how engineering should execute it.
- Use `2` and `3` only to understand what existed before and what must be migrated or discarded.
- Use `1` as supporting evidence, not as the final spec.
