import { useOutletContext } from 'react-router'
import { Award, BookOpen, Target, TrendingUp } from 'lucide-react'
import type { LearnerContext } from '../../shells/LearnerShell'
import { PageContainer } from '../../components/shell/PageContainer'
import { PageSkeleton } from '@/components/ui/skeleton'
import { ErrorBanner } from '@/components/ui/error-banner'
import { formatPercent } from '../../lib/formatters'
import { learnerStage } from '../../lib/copy'
import type { CurriculumResourceProgressSummary } from '../../types'

export function Progress() {
  const { progression, summary, flow, loading, error } = useOutletContext<LearnerContext>()

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
            <StatBox label="Stage" value={learnerStage(progression.current_stage)} />
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
    </PageContainer>
  )
}

function ResourceCard({
  resource,
  highlight = false,
}: {
  resource: CurriculumResourceProgressSummary
  highlight?: boolean
}) {
  return (
    <div className={`rounded-lg px-4 py-3 ${highlight ? 'bg-blue-50 border border-blue-200' : 'bg-slate-50'}`}>
      <div className="flex items-baseline justify-between">
        <p className="font-medium">{resource.title}</p>
        <span className="text-sm text-muted-foreground">{formatPercent(resource.mastery_ratio)}</span>
      </div>
      <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-slate-200">
        <div
          className={`h-full rounded-full transition-all ${highlight ? 'bg-blue-500' : 'bg-slate-400'}`}
          style={{ width: `${Math.round(resource.mastery_ratio * 100)}%` }}
        />
      </div>
      <p className="mt-1 text-xs text-muted-foreground">
        {learnerStage(resource.target_stage)}
      </p>
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
