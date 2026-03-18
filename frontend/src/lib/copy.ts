/**
 * Vocabulary translation layer.
 *
 * Maps backend contract terms into role-appropriate display strings
 * so that learner and teacher surfaces never expose raw contract vocabulary.
 *
 * BACKEND-OWNED DECISION: Display labels are pedagogical framing decisions
 * (e.g. "repair" → "Building foundations") that should be owned by the backend.
 * The backend should provide `display_label` fields alongside machine-readable
 * keys on all learner-facing and teacher-facing contracts.
 *
 * The backend now provides `display_label` on `LearnerContinueAction` and
 * `stage_display_label` on `LearnerCurriculumProgressionSummary`. Callers
 * should pass the backend-provided label as the second argument so it takes
 * precedence. These local tables serve as backwards-compatible fallbacks.
 */

// ---------------------------------------------------------------------------
// Continue-action kinds
// ---------------------------------------------------------------------------

const learnerContinueActionLabels: Record<string, string> = {
  idle: 'All caught up',
  generate_follow_up: 'Continue your lesson',
  advance_remediation: 'Keep practicing',
  continue_socratic: 'Check your understanding',
}

const teacherContinueActionLabels: Record<string, string> = {
  idle: 'No pending action',
  generate_follow_up: 'Next generated lesson',
  advance_remediation: 'Remediation in progress',
  continue_socratic: 'Socratic check in progress',
}

// ---------------------------------------------------------------------------
// Flow types
// ---------------------------------------------------------------------------

const learnerFlowTypeLabels: Record<string, string> = {
  generation: 'Lesson',
  socratic: 'Understanding check',
  remediation: 'Practice session',
  idle: 'Ready',
}

const teacherFlowTypeLabels: Record<string, string> = {
  generation: 'Generation',
  socratic: 'Socratic assessment',
  remediation: 'Remediation',
  idle: 'Idle',
}

// ---------------------------------------------------------------------------
// Progression stages
// ---------------------------------------------------------------------------

const learnerStageLabels: Record<string, string> = {
  repair: 'Building foundations',
  bridge: 'Connecting ideas',
  target: 'Learning new skills',
  transfer: 'Applying what you know',
  mastered: 'Mastered',
}

const teacherStageLabels: Record<string, string> = {
  repair: 'Repair',
  bridge: 'Bridge',
  target: 'Target',
  transfer: 'Transfer',
  mastered: 'Mastered',
}

// ---------------------------------------------------------------------------
// Artifact kinds
// ---------------------------------------------------------------------------

const learnerArtifactLabels: Record<string, string> = {
  generated_content: 'Lesson',
  socratic_session: 'Understanding check',
  remediation_session: 'Practice session',
}

const teacherArtifactLabels: Record<string, string> = {
  generated_content: 'Generated content',
  socratic_session: 'Socratic session',
  remediation_session: 'Remediation session',
}

// ---------------------------------------------------------------------------
// Content types
// ---------------------------------------------------------------------------

const learnerContentTypeLabels: Record<string, string> = {
  practice_problem: 'Practice problem',
  worked_example: 'Worked example',
  conceptual_explanation: 'Explanation',
  visual_representation: 'Visual',
  scaffolded_steps: 'Step-by-step guide',
}

// ---------------------------------------------------------------------------
// Signal levels (engagement, frustration, etc.)
// ---------------------------------------------------------------------------

const learnerSignalLabels: Record<string, string> = {
  none: 'Not enough data yet',
  low: 'Getting started',
  medium: 'On track',
  high: 'Going strong',
}

// ---------------------------------------------------------------------------
// Attention levels (teacher)
// ---------------------------------------------------------------------------

const teacherAttentionLabels: Record<string, string> = {
  none: 'On track',
  low: 'Monitor',
  medium: 'Needs attention',
  high: 'Urgent',
}

// ---------------------------------------------------------------------------
// Remediation phases
// ---------------------------------------------------------------------------

const learnerRemediationPhaseLabels: Record<string, string> = {
  diagnose: 'Understanding the challenge',
  instruct: 'Learning a new approach',
  practice: 'Practicing',
  verify: 'Checking your understanding',
}

const teacherRemediationPhaseLabels: Record<string, string> = {
  diagnose: 'Diagnosis',
  instruct: 'Instruction',
  practice: 'Practice',
  verify: 'Verification',
}

// ---------------------------------------------------------------------------
// Progression actions
// ---------------------------------------------------------------------------

const learnerProgressionActionLabels: Record<string, string> = {
  hold_repair_target: 'Still working on foundations',
  hold_bridge_target: 'Still connecting ideas',
  hold_target: 'Still learning',
  advance_to_bridge: 'Moving to connections',
  advance_to_target: 'Ready for new skills',
  advance_to_transfer: 'Ready to apply',
  advance_to_mastered: 'Almost there',
  completed: 'Complete',
}

const teacherProgressionActionLabels: Record<string, string> = {
  hold_repair_target: 'Held at repair',
  hold_bridge_target: 'Held at bridge',
  hold_target: 'Held at target',
  advance_to_bridge: 'Advancing to bridge',
  advance_to_target: 'Advancing to target',
  advance_to_transfer: 'Advancing to transfer',
  advance_to_mastered: 'Advancing to mastered',
  completed: 'Completed',
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/**
 * Looks up a display label from a local table.
 *
 * When the backend provides display_label fields, callers should pass the
 * backend label as a fourth argument and this function should prefer it:
 *   lookup(table, key, nullFallback, backendLabel)
 */
function lookup(
  table: Record<string, string>,
  key: string | null | undefined,
  nullFallback?: string,
  backendLabel?: string | null,
): string {
  if (backendLabel) return backendLabel
  if (!key) return nullFallback ?? ''
  if (key in table) return table[key]
  return formatFallback(key)
}

function formatFallback(value: string): string {
  return value
    .split(/[_-]/g)
    .filter(Boolean)
    .map((t) => t.charAt(0).toUpperCase() + t.slice(1))
    .join(' ')
}

// ---------------------------------------------------------------------------
// Public API — Learner-facing labels
// ---------------------------------------------------------------------------

export function learnerContinueAction(kind: string | null | undefined, backendLabel?: string | null): string {
  return lookup(learnerContinueActionLabels, kind, 'All caught up', backendLabel)
}

export function learnerFlowType(flowType: string | null | undefined, backendLabel?: string | null): string {
  return lookup(learnerFlowTypeLabels, flowType, 'Activity', backendLabel)
}

export function learnerStage(stage: string | null | undefined, backendLabel?: string | null): string {
  return lookup(learnerStageLabels, stage, 'Learning', backendLabel)
}

export function learnerArtifact(kind: string | null | undefined, backendLabel?: string | null): string {
  return lookup(learnerArtifactLabels, kind, 'Activity', backendLabel)
}

export function learnerContentType(contentType: string | null | undefined, backendLabel?: string | null): string {
  return lookup(learnerContentTypeLabels, contentType, 'Lesson', backendLabel)
}

export function learnerSignal(signal: string | null | undefined, backendLabel?: string | null): string {
  return lookup(learnerSignalLabels, signal, '', backendLabel)
}

export function learnerRemediationPhase(phase: string | null | undefined, backendLabel?: string | null): string {
  return lookup(learnerRemediationPhaseLabels, phase, 'Working', backendLabel)
}

export function learnerProgressionAction(action: string | null | undefined, backendLabel?: string | null): string {
  return lookup(learnerProgressionActionLabels, action, '', backendLabel)
}

// ---------------------------------------------------------------------------
// Public API — Teacher-facing labels
// ---------------------------------------------------------------------------

export function teacherContinueAction(kind: string | null | undefined, backendLabel?: string | null): string {
  return lookup(teacherContinueActionLabels, kind, 'No pending action', backendLabel)
}

export function teacherFlowType(flowType: string | null | undefined, backendLabel?: string | null): string {
  return lookup(teacherFlowTypeLabels, flowType, 'Unknown', backendLabel)
}

export function teacherStage(stage: string | null | undefined, backendLabel?: string | null): string {
  return lookup(teacherStageLabels, stage, undefined, backendLabel)
}

export function teacherArtifact(kind: string | null | undefined, backendLabel?: string | null): string {
  return lookup(teacherArtifactLabels, kind, 'Artifact', backendLabel)
}

export function teacherAttention(level: string | null | undefined, backendLabel?: string | null): string {
  return lookup(teacherAttentionLabels, level, 'Unknown', backendLabel)
}

export function teacherRemediationPhase(phase: string | null | undefined, backendLabel?: string | null): string {
  return lookup(teacherRemediationPhaseLabels, phase, undefined, backendLabel)
}

export function teacherProgressionAction(action: string | null | undefined, backendLabel?: string | null): string {
  return lookup(teacherProgressionActionLabels, action, undefined, backendLabel)
}
