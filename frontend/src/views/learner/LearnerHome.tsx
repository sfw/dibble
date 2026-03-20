import { useNavigate, useOutletContext } from 'react-router'
import { ArrowRight, BookOpen, Sparkles, Target } from 'lucide-react'
import type { LearnerContext } from '../../shells/LearnerShell'
import { PageContainer } from '../../components/shell/PageContainer'
import { PageSkeleton } from '@/components/ui/skeleton'
import { ErrorBanner } from '@/components/ui/error-banner'
import { Button } from '@/components/ui/button'
import { formatPercent } from '../../lib/formatters'
import {
  learnerContinueAction,
  learnerFlowType,
  learnerStage,
  learnerArtifact,
  learnerContentType,
} from '../../lib/copy'

export function LearnerHome() {
  const { workspace, flow, progression, summary, loading, error } = useOutletContext<LearnerContext>()
  const navigate = useNavigate()

  if (loading && !workspace.student_id) {
    return (
      <PageContainer size="narrow" className="py-4">
        <PageSkeleton cards={3} />
      </PageContainer>
    )
  }

  const artifact = workspace.active_artifact
  const continueAction = workspace.continue_action
  const isIdle = continueAction.kind === 'idle'
  const activeOutcome = progression.current_outcome ?? progression.next_outcome

  function handleResume() {
    if (continueAction.kind === 'continue_socratic' && flow.socratic_session_id) {
      navigate(`/learn/socratic/${flow.socratic_session_id}`)
    } else if (continueAction.kind === 'advance_remediation' && flow.remediation_session_id) {
      navigate(`/learn/remediation/${flow.remediation_session_id}`)
    } else {
      navigate('/learn/continue')
    }
  }

  return (
    <PageContainer size="narrow" className="flex flex-col gap-8 py-4">
      <ErrorBanner message={error} />

      {/* Greeting */}
      <section className="text-center animate-fade-in-up">
        <h1 className="text-2xl font-semibold tracking-tight">
          {isIdle ? 'Great work today!' : 'Welcome back'}
        </h1>
        <p className="mt-1 text-muted-foreground">
          {isIdle
            ? "You're all caught up. Check your progress or review past work."
            : activeOutcome?.title
              ? `Your ${learnerFlowType(flow.flow_type).toLowerCase()} on ${activeOutcome.title} is ready.`
              : `You have a ${learnerFlowType(flow.flow_type).toLowerCase()} ready to continue.`}
        </p>
      </section>

      {/* Current lesson card */}
      {!isIdle && (
        <section className="rounded-xl border bg-white p-6 shadow-sm animate-fade-in-up" style={{ animationDelay: '80ms' }}>
          <div className="flex items-start gap-4">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-blue-100 text-blue-600">
              <BookOpen className="h-5 w-5" />
            </div>
            <div className="flex-1">
              <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                {learnerArtifact(artifact.kind)}
              </p>
              <h2 className="mt-1 text-lg font-semibold">
                {learnerContinueAction(continueAction.kind, continueAction.display_label)}
              </h2>
              {activeOutcome?.title && (
                <p className="mt-0.5 text-sm text-muted-foreground">
                  {activeOutcome.title}
                  {artifact.content_type ? ` \u2022 ${learnerContentType(artifact.content_type)}` : ''}
                </p>
              )}
              {!activeOutcome?.title && artifact.content_type && (
                <p className="mt-0.5 text-sm text-muted-foreground">
                  {learnerContentType(artifact.content_type)}
                </p>
              )}
            </div>
          </div>
          <Button
            className="mt-4 w-full transition-all"
            size="lg"
            onClick={handleResume}
            disabled={loading}
          >
            Resume
            <ArrowRight className="ml-2 h-4 w-4" />
          </Button>
        </section>
      )}

      {/* Today's focus */}
      <section className="rounded-xl border bg-white p-6 shadow-sm animate-fade-in-up" style={{ animationDelay: '160ms' }}>
        <div className="flex items-center gap-3">
          <Target className="h-5 w-5 text-muted-foreground" />
          <h2 className="font-semibold">Today's focus</h2>
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <FocusItem
            label="Current stage"
            value={learnerStage(progression.current_stage, progression.stage_display_label)}
          />
          <FocusItem
            label="Working on"
            value={activeOutcome?.title ?? 'No active outcome'}
          />
        </div>
        {flow.rationale && (
          <p className="mt-3 text-sm text-muted-foreground">{flow.rationale}</p>
        )}
      </section>

      {/* Progress summary */}
      <section className="rounded-xl border bg-white p-6 shadow-sm animate-fade-in-up" style={{ animationDelay: '240ms' }}>
        <div className="flex items-center gap-3">
          <Sparkles className="h-5 w-5 text-muted-foreground" />
          <h2 className="font-semibold">Your progress</h2>
        </div>
        <div className="mt-4 space-y-3">
          <ProgressBar
            label="Overall"
            ratio={progression.mastered_outcome_ratio}
            detail={`${progression.mastered_outcome_count} of ${progression.outcome_count} mastered`}
          />
          {summary.recent_activity.generation_count > 0 && (
            <p className="text-sm text-muted-foreground">
              {summary.recent_activity.generation_count} lesson{summary.recent_activity.generation_count === 1 ? '' : 's'} completed recently
            </p>
          )}
        </div>
      </section>
    </PageContainer>
  )
}

function FocusItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-slate-50 px-4 py-3">
      <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">{label}</p>
      <p className="mt-0.5 font-medium">{value}</p>
    </div>
  )
}

function ProgressBar({ label, ratio, detail }: { label: string; ratio: number; detail: string }) {
  const percent = Math.round(ratio * 100)
  return (
    <div>
      <div className="flex items-baseline justify-between text-sm">
        <span className="font-medium">{label}</span>
        <span className="text-muted-foreground">{formatPercent(ratio)}</span>
      </div>
      <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-slate-100">
        <div
          className="h-full rounded-full bg-blue-500 animate-progress-fill transition-all"
          style={{ width: `${percent}%` }}
        />
      </div>
      <p className="mt-1 text-xs text-muted-foreground">{detail}</p>
    </div>
  )
}
