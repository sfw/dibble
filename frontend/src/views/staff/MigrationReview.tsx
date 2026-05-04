import { useMemo, useState } from 'react'
import { Beaker, CheckCheck, FileDiff, ShieldAlert } from 'lucide-react'
import { useAuthContext } from '@/contexts/AuthContext'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { ErrorBanner } from '@/components/ui/error-banner'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { ReleaseReadinessPanel } from '@/components/app/ReleaseReadinessPanel'
import { useMigrationReview } from '@/hooks/useMigrationReview'
import { useReleaseReadiness } from '@/hooks/useReleaseReadiness'
import type {
  CurriculumImpactAnalysis,
  CurriculumMigrationPlan,
  CurriculumSnapshotDiff,
} from '@/types'
import { useStaffApiConfig } from './useStaffApiConfig'

export function MigrationReview() {
  const apiConfig = useStaffApiConfig()
  const auth = useAuthContext()
  const review = useMigrationReview(apiConfig)
  const readiness = useReleaseReadiness(apiConfig)
  const [requestedDiffId, setRequestedDiffId] = useState('')
  const [requestedPlanId, setRequestedPlanId] = useState('')
  const selectedDiffId = requestedDiffId || review.diffs[0]?.diff_id || ''
  const selectedPlanId = requestedPlanId || review.plans[0]?.plan_id || ''

  const selectedDiff = useMemo(
    () => review.diffs.find((diff) => diff.diff_id === selectedDiffId) ?? null,
    [review.diffs, selectedDiffId],
  )

  const selectedPlan = useMemo(() => {
    if (selectedPlanId) {
      return review.plans.find((plan) => plan.plan_id === selectedPlanId) ?? null
    }
    if (!selectedDiffId) {
      return null
    }
    return review.plans.find((plan) => plan.diff_id === selectedDiffId) ?? null
  }, [review.plans, selectedDiffId, selectedPlanId])

  const selectedImpact = useMemo(
    () => review.impactAnalyses.find((item) => item.diff_id === selectedDiffId) ?? null,
    [review.impactAnalyses, selectedDiffId],
  )

  if (review.loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Loading migration review</CardTitle>
          <CardDescription>Fetching diffs, dry-run state, and migration plans.</CardDescription>
        </CardHeader>
      </Card>
    )
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1.4fr)_380px]">
      <div className="grid gap-6">
        <section className="rounded-[2rem] border border-border bg-[radial-gradient(circle_at_top_left,_rgba(16,185,129,0.12),_transparent_45%),linear-gradient(135deg,#ffffff_0%,#f8fafc_55%,#fefce8_100%)] p-8 shadow-[0_24px_80px_rgba(56,46,24,0.08)]">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="space-y-3">
              <Badge variant="secondary" className="w-fit bg-emerald-100 text-emerald-900">
                Curriculum migration review
              </Badge>
              <div className="space-y-2">
                <h1 className="text-3xl font-semibold tracking-tight text-slate-900">Review dry runs before curriculum changes touch runtime state.</h1>
                <p className="max-w-3xl text-sm leading-6 text-slate-600">
                  This page is intentionally narrow: pick a diff, inspect the proposed migration plan, review blocked items, and run a dry-run preview before anyone executes a migration.
                </p>
              </div>
            </div>
            <div className="flex flex-wrap gap-3">
              <Button
                variant="outline"
                onClick={() => {
                  if (!selectedDiff) {
                    return
                  }
                  void review.createPlan(selectedDiff.diff_id).then((plan) => {
                    if (plan) {
                      setRequestedPlanId(plan.plan_id)
                    }
                  })
                }}
                disabled={!selectedDiff || review.working}
              >
                <FileDiff className="h-4 w-4" />
                Generate migration plan
              </Button>
              <Button
                variant="outline"
                onClick={() => {
                  if (!selectedPlan) {
                    return
                  }
                  void review.approvePlan(selectedPlan.plan_id, auth.identity?.principal_id).then((plan) => {
                    if (plan) {
                      setRequestedPlanId(plan.plan_id)
                    }
                  })
                }}
                disabled={!selectedPlan || review.working}
              >
                <CheckCheck className="h-4 w-4" />
                Approve low risk
              </Button>
              <Button
                onClick={() => {
                  if (!selectedPlan) {
                    return
                  }
                  void review.previewPlanExecution(selectedPlan.plan_id, auth.identity?.principal_id)
                }}
                disabled={!selectedPlan || review.working}
              >
                <Beaker className="h-4 w-4" />
                Preview dry run
              </Button>
            </div>
          </div>
        </section>

        <ErrorBanner message={review.error || readiness.error} />

        <section className="grid gap-4 md:grid-cols-4">
          <MetricCard label="Diffs" value={String(review.diffs.length)} detail="Published snapshot comparisons" />
          <MetricCard label="Plans" value={String(review.plans.length)} detail="Migration plans on record" />
          <MetricCard label="Review items" value={String(selectedPlan?.review_items.length ?? 0)} detail="Manual decisions still required" warning={(selectedPlan?.review_items.length ?? 0) > 0} />
          <MetricCard label="Dry-run blocked" value={review.preview?.rollout_blocked ? 'Yes' : 'No'} detail={review.preview?.rollout_reason ?? 'No rollout block detected in the latest preview.'} warning={review.preview?.rollout_blocked === true} />
        </section>

        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <Card className="border-slate-200 bg-white/95">
            <CardHeader>
              <CardTitle>Snapshot diff</CardTitle>
              <CardDescription>Select the curriculum diff you want to inspect.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4">
              <div className="space-y-2">
                <Select value={selectedDiffId} onValueChange={setRequestedDiffId}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select a diff" />
                  </SelectTrigger>
                  <SelectContent>
                    {review.diffs.map((diff) => (
                      <SelectItem key={diff.diff_id} value={diff.diff_id}>
                        {diff.diff_id}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              {selectedDiff ? <DiffSummary diff={selectedDiff} impact={selectedImpact} /> : <p className="text-sm text-slate-600">No diff selected.</p>}
            </CardContent>
          </Card>

          <Card className="border-slate-200 bg-white/95">
            <CardHeader>
              <CardTitle>Migration plan</CardTitle>
              <CardDescription>Choose an existing plan or inspect the plan linked to the current diff.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4">
              <Select value={selectedPlan?.plan_id ?? 'none'} onValueChange={(value) => setRequestedPlanId(value === 'none' ? '' : value)}>
                <SelectTrigger>
                  <SelectValue placeholder="Select a migration plan" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">Latest plan for selected diff</SelectItem>
                  {review.plans.map((plan) => (
                    <SelectItem key={plan.plan_id} value={plan.plan_id}>
                      {plan.plan_id}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {selectedPlan ? <PlanSummary plan={selectedPlan} /> : <p className="text-sm text-slate-600">No migration plan yet for this diff. Generate one to review dry-run behavior.</p>}
            </CardContent>
          </Card>
        </div>

        {selectedPlan ? (
          <Card className="border-slate-200 bg-white/95">
            <CardHeader>
              <CardTitle>Blocked and manual-review items</CardTitle>
              <CardDescription>These items still require operator judgment before execution should proceed.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3">
              {selectedPlan.review_items.length === 0 ? (
                <p className="text-sm text-slate-600">No manual-review items are attached to this plan.</p>
              ) : (
                selectedPlan.review_items.map((item) => (
                  <article key={item.review_item_id} className="rounded-2xl border border-amber-200 bg-amber-50/70 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-slate-900">{item.entity_kind.replaceAll('_', ' ')} • {item.entity_id}</p>
                        <p className="mt-1 text-sm text-slate-700">{item.rationale}</p>
                        <p className="mt-2 text-xs font-medium uppercase tracking-[0.18em] text-amber-700">
                          Recommended: {item.recommended_action.replaceAll('_', ' ')}
                        </p>
                      </div>
                      <Badge variant="secondary" className="bg-amber-100 text-amber-900">
                        {item.risk_level}
                      </Badge>
                    </div>
                  </article>
                ))
              )}
            </CardContent>
          </Card>
        ) : null}

        {selectedPlan ? (
          <Card className="border-slate-200 bg-white/95">
            <CardHeader>
              <CardTitle>Plan actions</CardTitle>
              <CardDescription>Each action remains backend-authored; the UI just organizes status, risk, and rationale for review.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3">
              {selectedPlan.actions.map((action) => (
                <article key={action.action_id} className="rounded-2xl border border-slate-200 bg-slate-50/60 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-slate-900">{action.entity_kind.replaceAll('_', ' ')} • {action.entity_id}</p>
                      <p className="mt-1 text-sm text-slate-700">{action.rationale}</p>
                      <p className="mt-2 text-xs text-slate-500">
                        {action.action_type.replaceAll('_', ' ')} • {Math.round(action.confidence * 100)}% confidence
                      </p>
                    </div>
                    <div className="flex flex-col items-end gap-2">
                      <Badge variant="secondary" className={riskClassName(action.risk_level)}>
                        {action.risk_level}
                      </Badge>
                      <Badge variant="secondary" className="bg-slate-100 text-slate-700">
                        {action.status.replaceAll('_', ' ')}
                      </Badge>
                    </div>
                  </div>
                </article>
              ))}
            </CardContent>
          </Card>
        ) : null}

        <Card className="border-slate-200 bg-white/95">
          <CardHeader>
            <CardTitle>Dry-run preview</CardTitle>
            <CardDescription>Preview what would execute, what stays blocked, and which rollout rules still constrain the plan.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3">
            {!review.preview ? (
              <p className="text-sm text-slate-600">Run a dry-run preview to inspect execution consequences.</p>
            ) : (
              <>
                {review.preview.rollout_blocked ? (
                  <article className="rounded-2xl border border-amber-200 bg-amber-50/70 p-4">
                    <div className="flex items-start gap-2">
                      <ShieldAlert className="mt-0.5 h-4 w-4 text-amber-700" />
                      <div>
                        <p className="text-sm font-semibold text-slate-900">Rollout policy is still blocking execution.</p>
                        <p className="mt-1 text-sm text-slate-700">{review.preview.rollout_reason ?? 'Migration execution is held by rollout policy.'}</p>
                      </div>
                    </div>
                  </article>
                ) : null}
                {review.preview.action_previews.map((action) => (
                  <article key={action.action_id} className="rounded-2xl border border-slate-200 bg-slate-50/60 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-slate-900">{action.summary}</p>
                        <p className="mt-1 text-sm text-slate-700">{action.explanation.rationale}</p>
                        <p className="mt-2 text-xs font-medium uppercase tracking-[0.18em] text-slate-500">
                          Next: {action.explanation.next_expected_consequence}
                        </p>
                        {action.explanation.rollout_effect ? (
                          <p className="mt-2 text-xs text-slate-500">
                            Rollout effect: {action.explanation.rollout_effect.mode.replaceAll('_', ' ')} via {action.explanation.rollout_effect.source.replaceAll('_', ' ')}
                          </p>
                        ) : null}
                      </div>
                      <div className="flex flex-col items-end gap-2">
                        <Badge variant="secondary" className={action.would_execute ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-900'}>
                          {action.would_execute ? 'Would execute' : 'Blocked'}
                        </Badge>
                        <Badge variant="secondary" className={riskClassName(action.explanation.risk_level)}>
                          {action.explanation.risk_level}
                        </Badge>
                      </div>
                    </div>
                  </article>
                ))}
              </>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6">
        <ReleaseReadinessPanel readiness={readiness.readiness} loading={readiness.loading} />
      </div>
    </div>
  )
}

function DiffSummary({
  diff,
  impact,
}: {
  diff: CurriculumSnapshotDiff
  impact: CurriculumImpactAnalysis | null
}) {
  const highRiskCount = diff.entity_deltas.filter((item) => item.risk_level === 'high').length

  return (
      <div className="grid gap-4">
        <div className="rounded-2xl border border-slate-200 bg-slate-50/60 p-4">
          <p className="text-sm font-semibold text-slate-900">{diff.source_snapshot_id} {'->'} {diff.target_snapshot_id}</p>
          <p className="mt-1 text-sm text-slate-600">
            {diff.entity_deltas.length} entity deltas • {highRiskCount} high-risk changes • framework {diff.framework_id ?? 'unknown'}
          </p>
          <p className="mt-2 text-xs text-slate-500">
            Versions: {diff.source_framework_version ?? 'n/a'} {'->'} {diff.target_framework_version ?? 'n/a'}
          </p>
        </div>
      {impact ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-4">
          <p className="text-sm font-semibold text-slate-900">Runtime impact analysis</p>
          <p className="mt-1 text-sm text-slate-600">{impact.impacts.length} runtime entities would need attention across goals, trajectories, assignments, or library artifacts.</p>
        </div>
      ) : null}
      {diff.entity_deltas.slice(0, 5).map((delta) => (
        <article key={delta.delta_id} className="rounded-2xl border border-slate-200 bg-white p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-slate-900">{delta.artifact_kind.replaceAll('_', ' ')} • {delta.artifact_id}</p>
              <p className="mt-1 text-sm text-slate-700">{delta.rationale}</p>
              <p className="mt-2 text-xs text-slate-500">
                {delta.change_kind.replaceAll('_', ' ')} • suggested action {delta.suggested_action?.replaceAll('_', ' ') ?? 'none'}
              </p>
            </div>
            <Badge variant="secondary" className={riskClassName(delta.risk_level)}>
              {delta.risk_level}
            </Badge>
          </div>
        </article>
      ))}
    </div>
  )
}

function PlanSummary({ plan }: { plan: CurriculumMigrationPlan }) {
  const approvedCount = plan.actions.filter((item) => item.status === 'approved').length
  const failedCount = plan.actions.filter((item) => item.status === 'execution_failed').length

  return (
    <div className="grid gap-4">
      <div className="rounded-2xl border border-slate-200 bg-slate-50/60 p-4">
        <p className="text-sm font-semibold text-slate-900">{plan.plan_id}</p>
        <p className="mt-1 text-sm text-slate-600">
          {plan.actions.length} actions • {plan.review_items.length} review items • status {plan.status.replaceAll('_', ' ')}
        </p>
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        <MetricCard label="Approved" value={String(approvedCount)} detail="Ready to execute" />
        <MetricCard label="Needs review" value={String(plan.review_items.length)} detail="Manual follow-up required" warning={plan.review_items.length > 0} />
        <MetricCard label="Failures" value={String(failedCount)} detail="Partial-failure signals" warning={failedCount > 0} />
      </div>
    </div>
  )
}

function MetricCard({
  label,
  value,
  detail,
  warning = false,
}: {
  label: string
  value: string
  detail: string
  warning?: boolean
}) {
  return (
    <div className={`rounded-2xl border p-4 ${warning ? 'border-amber-200 bg-amber-50/70' : 'border-slate-200 bg-white/95'}`}>
      <p className="text-xs font-medium uppercase tracking-[0.18em] text-slate-500">{label}</p>
      <p className="mt-3 text-2xl font-semibold text-slate-900">{value}</p>
      <p className="mt-1 text-sm text-slate-600">{detail}</p>
    </div>
  )
}

function riskClassName(riskLevel: string) {
  if (riskLevel === 'high') {
    return 'bg-rose-100 text-rose-800'
  }
  if (riskLevel === 'medium' || riskLevel === 'moderate') {
    return 'bg-amber-100 text-amber-900'
  }
  return 'bg-emerald-100 text-emerald-800'
}
