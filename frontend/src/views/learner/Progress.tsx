import { useMemo } from 'react'
import { useOutletContext } from 'react-router'
import { Award, BookOpen, CheckCircle2, Layers, Lock, Target, TrendingUp } from 'lucide-react'
import type { LearnerContext } from '../../shells/LearnerShell'
import { PageContainer } from '../../components/shell/PageContainer'
import { PageSkeleton } from '@/components/ui/skeleton'
import { ErrorBanner } from '@/components/ui/error-banner'
import { formatPercent } from '../../lib/formatters'
import { learnerStage } from '../../lib/copy'
import type { CurriculumResourceProgressSummary } from '../../types'

// ---------------------------------------------------------------------------
// Resource grouping
// ---------------------------------------------------------------------------

interface ResourceGroup {
  label: string
  kind: 'mastered' | 'current' | 'ready' | 'blocked'
  resources: CurriculumResourceProgressSummary[]
}

function groupResources(
  current: CurriculumResourceProgressSummary | null | undefined,
  next: CurriculumResourceProgressSummary | null | undefined,
  ready: CurriculumResourceProgressSummary[],
  blocked: CurriculumResourceProgressSummary[],
  masteredCount: number,
): ResourceGroup[] {
  const groups: ResourceGroup[] = []

  // Mastered: we don't have individual mastered resources in the contract,
  // but we can synthesize a placeholder count section
  if (masteredCount > 0) {
    groups.push({ label: 'Mastered', kind: 'mastered', resources: [] })
  }

  // Current focus
  if (current) {
    groups.push({ label: 'Current focus', kind: 'current', resources: [current] })
  }

  // Ready resources (deduplicated against current and next)
  const currentId = current?.resource_id
  const readyDeduped = [
    ...(next && next.resource_id !== currentId ? [next] : []),
    ...ready.filter((r) => r.resource_id !== next?.resource_id && r.resource_id !== currentId),
  ]
  if (readyDeduped.length > 0) {
    groups.push({ label: 'Ready to start', kind: 'ready', resources: readyDeduped })
  }

  // Blocked
  if (blocked.length > 0) {
    groups.push({ label: 'Blocked', kind: 'blocked', resources: blocked })
  }

  return groups
}

export function Progress() {
  const { progression, summary, flow, loading, error } = useOutletContext<LearnerContext>()

  const resourceGroups = useMemo(
    () =>
      groupResources(
        progression.current_resource,
        progression.next_resource,
        progression.ready_resources ?? [],
        progression.blocked_resources ?? [],
        progression.mastered_resource_count,
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
  const readyResources = progression.ready_resources ?? []
  const nextResource = progression.next_resource

  return (
    <PageContainer size="narrow" className="flex flex-col gap-8 py-4">
      <ErrorBanner message={error} />

      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Your progress</h1>
        <p className="mt-1 text-muted-foreground">See how far you've come and what's ahead.</p>
      </header>

      {/* Current concept progress */}
      {progression.current_resource && (
        <section className="rounded-xl border bg-white p-6 shadow-sm">
          <div className="flex items-center gap-3 mb-4">
            <Target className="h-5 w-5 text-muted-foreground" />
            <h2 className="font-semibold">Current focus</h2>
          </div>
          <ResourceCard resource={progression.current_resource} highlight />
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
            ratio={progression.mastered_resource_ratio}
            detail={`${progression.mastered_resource_count} of ${progression.resource_count} mastered`}
          />
          <div className="grid grid-cols-3 gap-3">
            <StatBox label="Stage" value={learnerStage(progression.current_stage, progression.stage_display_label)} />
            <StatBox label="Ready" value={String(progression.ready_resource_count)} />
            <StatBox label="Blocked" value={String(progression.blocked_resource_count)} />
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
      {(nextResource || readyResources.length > 0) && (
        <section className="rounded-xl border bg-white p-6 shadow-sm">
          <div className="flex items-center gap-3 mb-4">
            <BookOpen className="h-5 w-5 text-muted-foreground" />
            <h2 className="font-semibold">What to practice next</h2>
          </div>
          <div className="flex flex-col gap-3">
            {nextResource && <ResourceCard resource={nextResource} />}
            {readyResources
              .filter((r) => r.resource_id !== nextResource?.resource_id)
              .slice(0, 3)
              .map((resource) => (
                <ResourceCard key={resource.resource_id} resource={resource} />
              ))}
          </div>
          {flow.rationale && (
            <p className="mt-3 text-sm text-muted-foreground">{flow.rationale}</p>
          )}
        </section>
      )}

      {/* All resources breakdown */}
      {resourceGroups.length > 0 && (
        <section className="rounded-xl border bg-white p-6 shadow-sm">
          <div className="flex items-center gap-3 mb-4">
            <Layers className="h-5 w-5 text-muted-foreground" />
            <h2 className="font-semibold">All resources</h2>
            <span className="ml-auto text-xs text-muted-foreground">
              {progression.resource_count} total
            </span>
          </div>
          <div className="flex flex-col gap-5">
            {resourceGroups.map((group) => (
              <ResourceGroupSection key={group.kind} group={group} masteredCount={progression.mastered_resource_count} />
            ))}
          </div>
        </section>
      )}
    </PageContainer>
  )
}

// ---------------------------------------------------------------------------
// Resource group section for "All resources"
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

function ResourceGroupSection({ group, masteredCount }: { group: ResourceGroup; masteredCount: number }) {
  const Icon = groupIcons[group.kind]
  const colorClass = groupColors[group.kind]

  return (
    <div>
      <div className="flex items-center gap-2 mb-2">
        <Icon className={`h-4 w-4 ${colorClass}`} />
        <span className={`text-sm font-medium ${colorClass}`}>{group.label}</span>
        <span className="text-xs text-muted-foreground">
          {group.kind === 'mastered' ? masteredCount : group.resources.length}
        </span>
      </div>
      {group.kind === 'mastered' ? (
        <div className="rounded-lg bg-emerald-50 px-4 py-3">
          <p className="text-sm font-medium text-emerald-700">
            {masteredCount} resource{masteredCount !== 1 ? 's' : ''} mastered
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {group.resources.map((resource) => (
            <ResourceCard
              key={resource.resource_id}
              resource={resource}
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
// Resource card
// ---------------------------------------------------------------------------

function ResourceCard({
  resource,
  highlight = false,
  blocked = false,
}: {
  resource: CurriculumResourceProgressSummary
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
          <p className={`font-medium truncate ${blocked ? 'text-slate-500' : ''}`}>{resource.title}</p>
        </div>
        <span className="shrink-0 text-sm text-muted-foreground">{formatPercent(resource.mastery_ratio)}</span>
      </div>
      <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-slate-200">
        <div
          className={`h-full rounded-full transition-all ${barClass}`}
          style={{ width: `${Math.round(resource.mastery_ratio * 100)}%` }}
        />
      </div>
      <div className="mt-1 flex items-center gap-2">
        <span className={`text-xs ${blocked ? 'text-slate-400' : 'text-muted-foreground'}`}>
          {learnerStage(resource.target_stage)}
        </span>
        {blocked && resource.rationale && (
          <span className="text-xs text-slate-400 truncate" title={resource.rationale}>
            {resource.rationale}
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
