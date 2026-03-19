import { useMemo } from 'react'
import { useOutletContext } from 'react-router'
import { Award, BookOpen, CheckCircle2, Layers, Lock, Target, TrendingUp } from 'lucide-react'
import type { LearnerContext } from '../../shells/LearnerShell'
import { PageContainer } from '../../components/shell/PageContainer'
import { PageSkeleton } from '@/components/ui/skeleton'
import { ErrorBanner } from '@/components/ui/error-banner'
import { formatPercent } from '../../lib/formatters'
import { learnerStage } from '../../lib/copy'
import type { OutcomeProgressSummary } from '../../types'

// ---------------------------------------------------------------------------
// Outcome grouping
// ---------------------------------------------------------------------------

interface OutcomeGroup {
  label: string
  kind: 'mastered' | 'current' | 'ready' | 'blocked'
  outcomes: OutcomeProgressSummary[]
}

function groupOutcomes(
  current: OutcomeProgressSummary | null | undefined,
  next: OutcomeProgressSummary | null | undefined,
  ready: OutcomeProgressSummary[],
  blocked: OutcomeProgressSummary[],
  masteredCount: number,
): OutcomeGroup[] {
  const groups: OutcomeGroup[] = []

  // Mastered: we don't have individual mastered outcomes in the contract,
  // but we can synthesize a placeholder count section
  if (masteredCount > 0) {
    groups.push({ label: 'Mastered', kind: 'mastered', outcomes: [] })
  }

  // Current focus
  if (current) {
    groups.push({ label: 'Current focus', kind: 'current', outcomes: [current] })
  }

  // Ready outcomes (deduplicated against current and next)
  const currentId = current?.outcome_id
  const readyDeduped = [
    ...(next && next.outcome_id !== currentId ? [next] : []),
    ...ready.filter((r) => r.outcome_id !== next?.outcome_id && r.outcome_id !== currentId),
  ]
  if (readyDeduped.length > 0) {
    groups.push({ label: 'Ready to start', kind: 'ready', outcomes: readyDeduped })
  }

  // Blocked
  if (blocked.length > 0) {
    groups.push({ label: 'Blocked', kind: 'blocked', outcomes: blocked })
  }

  return groups
}

export function Progress() {
  const { progression, summary, flow, loading, error } = useOutletContext<LearnerContext>()

  const outcomeGroups = useMemo(
    () =>
      groupOutcomes(
        progression.current_outcome,
        progression.next_outcome,
        progression.ready_outcomes ?? [],
        progression.blocked_outcomes ?? [],
        progression.mastered_outcome_count,
      ),
    [progression],
  )

  if (loading && !summary.student_id) {
    return (
      <PageContainer size="narrow" className="py-4">
        <PageSkeleton cards={4} />
      </PageContainer>
    )
  }

  const recentActivity = summary.recent_activity
  const readyOutcomes = progression.ready_outcomes ?? []
  const nextOutcome = progression.next_outcome

  return (
    <PageContainer size="narrow" className="flex flex-col gap-8 py-4">
      <ErrorBanner message={error} />

      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Your progress</h1>
        <p className="mt-1 text-muted-foreground">See how far you've come and what's ahead.</p>
      </header>

      {/* Current concept progress */}
      {progression.current_outcome && (
        <section className="rounded-xl border bg-white p-6 shadow-sm">
          <div className="flex items-center gap-3 mb-4">
            <Target className="h-5 w-5 text-muted-foreground" />
            <h2 className="font-semibold">Current focus</h2>
          </div>
          <OutcomeCard outcome={progression.current_outcome} highlight />
        </section>
      )}

      {/* Overall progress */}
      <section className="rounded-xl border bg-white p-6 shadow-sm">
        <div className="flex items-center gap-3 mb-4">
          <TrendingUp className="h-5 w-5 text-muted-foreground" />
          <h2 className="font-semibold">Overall</h2>
        </div>
        <div className="space-y-4">
          <ProgressBar
            label="Course progress"
            ratio={progression.mastered_outcome_ratio}
            detail={`${progression.mastered_outcome_count} of ${progression.outcome_count} mastered`}
          />
          <div className="grid grid-cols-3 gap-3">
            <StatBox label="Stage" value={learnerStage(progression.current_stage, progression.stage_display_label)} />
            <StatBox label="Ready" value={String(progression.ready_outcome_count)} />
            <StatBox label="Blocked" value={String(progression.blocked_outcome_count)} />
          </div>
        </div>
      </section>

      {/* Recent wins */}
      {(recentActivity.generation_count > 0 || recentActivity.socratic_assessment_count > 0) && (
        <section className="rounded-xl border bg-white p-6 shadow-sm">
          <div className="flex items-center gap-3 mb-4">
            <Award className="h-5 w-5 text-muted-foreground" />
            <h2 className="font-semibold">Recent activity</h2>
          </div>
          <div className="grid grid-cols-2 gap-3">
            {recentActivity.generation_count > 0 && (
              <StatBox label="Lessons completed" value={String(recentActivity.generation_count)} />
            )}
            {recentActivity.socratic_assessment_count > 0 && (
              <StatBox label="Checks completed" value={String(recentActivity.socratic_assessment_count)} />
            )}
          </div>
        </section>
      )}

      {/* What to practice next */}
      {(nextOutcome || readyOutcomes.length > 0) && (
        <section className="rounded-xl border bg-white p-6 shadow-sm">
          <div className="flex items-center gap-3 mb-4">
            <BookOpen className="h-5 w-5 text-muted-foreground" />
            <h2 className="font-semibold">What to practice next</h2>
          </div>
          <div className="flex flex-col gap-3">
            {nextOutcome && <OutcomeCard outcome={nextOutcome} />}
            {readyOutcomes
              .filter((r) => r.outcome_id !== nextOutcome?.outcome_id)
              .slice(0, 3)
              .map((outcome) => (
                <OutcomeCard key={outcome.outcome_id} outcome={outcome} />
              ))}
          </div>
          {flow.rationale && (
            <p className="mt-3 text-sm text-muted-foreground">{flow.rationale}</p>
          )}
        </section>
      )}

      {/* All outcomes breakdown */}
      {outcomeGroups.length > 0 && (
        <section className="rounded-xl border bg-white p-6 shadow-sm">
          <div className="flex items-center gap-3 mb-4">
            <Layers className="h-5 w-5 text-muted-foreground" />
            <h2 className="font-semibold">All outcomes</h2>
            <span className="ml-auto text-xs text-muted-foreground">
              {progression.outcome_count} total
            </span>
          </div>
          <div className="flex flex-col gap-5">
            {outcomeGroups.map((group) => (
              <OutcomeGroupSection key={group.kind} group={group} masteredCount={progression.mastered_outcome_count} />
            ))}
          </div>
        </section>
      )}
    </PageContainer>
  )
}

// ---------------------------------------------------------------------------
// Outcome group section for "All outcomes"
// ---------------------------------------------------------------------------

const groupIcons = {
  mastered: CheckCircle2,
  current: Target,
  ready: BookOpen,
  blocked: Lock,
}

const groupColors = {
  mastered: 'text-emerald-600',
  current: 'text-blue-600',
  ready: 'text-slate-500',
  blocked: 'text-slate-400',
}

function OutcomeGroupSection({ group, masteredCount }: { group: OutcomeGroup; masteredCount: number }) {
  const Icon = groupIcons[group.kind]
  const colorClass = groupColors[group.kind]

  return (
    <div>
      <div className="flex items-center gap-2 mb-2">
        <Icon className={`h-4 w-4 ${colorClass}`} />
        <span className={`text-sm font-medium ${colorClass}`}>{group.label}</span>
        <span className="text-xs text-muted-foreground">
          {group.kind === 'mastered' ? masteredCount : group.outcomes.length}
        </span>
      </div>
      {group.kind === 'mastered' ? (
        <div className="rounded-lg bg-emerald-50 px-4 py-3">
          <p className="text-sm font-medium text-emerald-700">
            {masteredCount} outcome{masteredCount !== 1 ? 's' : ''} mastered
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {group.outcomes.map((outcome) => (
            <OutcomeCard
              key={outcome.outcome_id}
              outcome={outcome}
              highlight={group.kind === 'current'}
              blocked={group.kind === 'blocked'}
            />
          ))}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Outcome card
// ---------------------------------------------------------------------------

function OutcomeCard({
  outcome,
  highlight = false,
  blocked = false,
}: {
  outcome: OutcomeProgressSummary
  highlight?: boolean
  blocked?: boolean
}) {
  const bgClass = blocked
    ? 'bg-slate-50 opacity-75'
    : highlight
      ? 'bg-blue-50 border border-blue-200'
      : 'bg-slate-50'

  const barClass = blocked
    ? 'bg-slate-300'
    : highlight
      ? 'bg-blue-500'
      : 'bg-slate-400'

  return (
    <div className={`rounded-lg px-4 py-3 ${bgClass}`}>
      <div className="flex items-baseline justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          {blocked && <Lock className="h-3.5 w-3.5 shrink-0 text-slate-400" />}
          <p className={`font-medium truncate ${blocked ? 'text-slate-500' : ''}`}>{outcome.title}</p>
        </div>
        <span className="shrink-0 text-sm text-muted-foreground">{formatPercent(outcome.mastery_ratio)}</span>
      </div>
      <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-slate-200">
        <div
          className={`h-full rounded-full transition-all ${barClass}`}
          style={{ width: `${Math.round(outcome.mastery_ratio * 100)}%` }}
        />
      </div>
      <div className="mt-1 flex items-center gap-2">
        <span className={`text-xs ${blocked ? 'text-slate-400' : 'text-muted-foreground'}`}>
          {learnerStage(outcome.target_stage)}
        </span>
        {outcome.mastery_quality === 'support_dependent' && (
          <span className="inline-flex items-center rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
            Needs independent practice
          </span>
        )}
        {outcome.mastery_quality === 'fragile' && (
          <span className="inline-flex items-center rounded-full bg-orange-100 px-2 py-0.5 text-xs font-medium text-orange-700">
            Unstable mastery
          </span>
        )}
        {(blocked || outcome.mastery_quality) && outcome.rationale && (
          <span className="text-xs text-slate-400 truncate" title={outcome.rationale}>
            {outcome.rationale}
          </span>
        )}
      </div>
    </div>
  )
}

function ProgressBar({ label, ratio, detail }: { label: string; ratio: number; detail: string }) {
  return (
    <div>
      <div className="flex items-baseline justify-between text-sm">
        <span className="font-medium">{label}</span>
        <span className="text-muted-foreground">{formatPercent(ratio)}</span>
      </div>
      <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-slate-100">
        <div
          className="h-full rounded-full bg-blue-500 transition-all"
          style={{ width: `${Math.round(ratio * 100)}%` }}
        />
      </div>
      <p className="mt-1 text-xs text-muted-foreground">{detail}</p>
    </div>
  )
}

function StatBox({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-slate-50 px-3 py-2 text-center">
      <p className="text-lg font-semibold">{value}</p>
      <p className="text-xs text-muted-foreground">{label}</p>
    </div>
  )
}
