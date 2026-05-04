import { useMemo, useState } from 'react'
import { ArrowUpRight, Beaker, Save, ShieldAlert, Sparkles } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { ErrorBanner } from '@/components/ui/error-banner'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { ReleaseReadinessPanel } from '@/components/app/ReleaseReadinessPanel'
import { useReleaseReadiness } from '@/hooks/useReleaseReadiness'
import { useRolloutGovernance } from '@/hooks/useRolloutGovernance'
import type { RolloutPolicy, RolloutSimulationSubject } from '@/types'
import { useStaffApiConfig } from './useStaffApiConfig'

const capabilityLabels: Record<string, string> = {
  autonomous_session_suggestions: 'Autonomous session suggestions',
  parent_approval_enforcement: 'Parent approval enforcement',
  cloud_library_remote_read: 'Cloud library remote read',
  cloud_library_remote_publish: 'Cloud library remote publish',
  non_text_modalities: 'Non-text modalities',
  outcome_driven_adaptation: 'Outcome-driven adaptation',
  migration_execution: 'Migration execution',
  autonomous_teacher_outbound_actions: 'Autonomous outbound actions',
}

const gateOptions: Record<string, string[]> = {
  autonomous_session_suggestions: ['disabled', 'guided'],
  parent_approval_enforcement: ['disabled', 'guided', 'strict'],
  cloud_library_remote_read: ['local_only', 'remote_preferred'],
  cloud_library_remote_publish: ['local_only', 'remote_verified'],
  non_text_modalities: ['text_only', 'full_multimodal'],
  outcome_driven_adaptation: ['off', 'conservative', 'standard', 'aggressive'],
  migration_execution: ['manual_only', 'approved_low_risk_only'],
  autonomous_teacher_outbound_actions: ['disabled', 'notifications_only'],
}

function updateGate(policy: RolloutPolicy, capability: string, mode: string) {
  return {
    ...policy,
    behavior_gates: policy.behavior_gates.map((gate) => (
      gate.capability === capability ? { ...gate, mode } : gate
    )),
  }
}

function updateCohortPercentage(policy: RolloutPolicy, cohortId: string, rolloutPercentage: number) {
  return {
    ...policy,
    cohorts: policy.cohorts.map((cohort) => (
      cohort.cohort_id === cohortId ? { ...cohort, rollout_percentage: rolloutPercentage } : cohort
    )),
  }
}

function updateCohortBucket(policy: RolloutPolicy, cohortId: string, bucketId: string | null) {
  return {
    ...policy,
    cohorts: policy.cohorts.map((cohort) => (
      cohort.cohort_id === cohortId ? { ...cohort, pinned_evaluation_bucket_id: bucketId } : cohort
    )),
  }
}

function updateBucketWeight(policy: RolloutPolicy, bucketId: string, weight: number) {
  return {
    ...policy,
    evaluation_buckets: policy.evaluation_buckets.map((bucket) => (
      bucket.bucket_id === bucketId ? { ...bucket, weight } : bucket
    )),
  }
}

function updateKillSwitch(
  policy: RolloutPolicy,
  capability: string,
  patch: Partial<{ active: boolean; reason: string | null }>,
) {
  return {
    ...policy,
    kill_switches: policy.kill_switches.map((item) => (
      item.capability === capability ? { ...item, ...patch } : item
    )),
  }
}

export function RolloutConsole() {
  const apiConfig = useStaffApiConfig()
  const rollout = useRolloutGovernance(apiConfig)
  const readiness = useReleaseReadiness(apiConfig)
  const [subjectDraft, setSubjectDraft] = useState<RolloutSimulationSubject[] | null>(null)

  const activeKillSwitchCount = useMemo(
    () => rollout.draftPolicy?.kill_switches.filter((item) => item.active).length ?? 0,
    [rollout.draftPolicy],
  )

  const dirty = useMemo(() => (
    rollout.policy !== null
    && rollout.draftPolicy !== null
    && JSON.stringify(rollout.policy) !== JSON.stringify(rollout.draftPolicy)
  ), [rollout.draftPolicy, rollout.policy])

  if (rollout.loading || !rollout.draftPolicy) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Loading rollout console</CardTitle>
          <CardDescription>Fetching the current policy, cohorts, evaluation buckets, and simulation baselines.</CardDescription>
        </CardHeader>
      </Card>
    )
  }

  const draftPolicy = rollout.draftPolicy
  const livePolicy = rollout.policy ?? draftPolicy
  const subjects = subjectDraft ?? rollout.defaultSubjects

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1.45fr)_380px]">
      <div className="grid gap-6">
        <section className="rounded-[2rem] border border-border bg-[radial-gradient(circle_at_top_left,_rgba(14,165,233,0.12),_transparent_45%),linear-gradient(135deg,#ffffff_0%,#f8fafc_55%,#fff7ed_100%)] p-8 shadow-[0_24px_80px_rgba(56,46,24,0.08)]">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="space-y-3">
              <Badge variant="secondary" className="w-fit bg-sky-100 text-sky-900">
                Rollout control
              </Badge>
              <div className="space-y-2">
                <h1 className="text-3xl font-semibold tracking-tight text-slate-900">Simulate policy changes before they touch live households.</h1>
                <p className="max-w-3xl text-sm leading-6 text-slate-600">
                  This console keeps the trust layer review-first: edit constrained rollout settings, inspect cohort and bucket effects, then save once the simulated blast radius feels acceptable.
                </p>
              </div>
            </div>
            <div className="flex flex-wrap gap-3">
              <Button variant="outline" onClick={() => void rollout.runSimulation(subjects.filter(hasSubjectId))} disabled={rollout.simulating}>
                <Beaker className="h-4 w-4" />
                {rollout.simulating ? 'Simulating...' : 'Run simulation'}
              </Button>
              <Button variant="outline" onClick={() => setSubjectDraft(rollout.defaultSubjects)}>
                <Sparkles className="h-4 w-4" />
                Reset samples
              </Button>
              <Button onClick={() => void rollout.savePolicy()} disabled={!dirty || rollout.saving}>
                <Save className="h-4 w-4" />
                {rollout.saving ? 'Saving...' : 'Save policy'}
              </Button>
            </div>
          </div>
        </section>

        <ErrorBanner message={rollout.error || readiness.error} />

        <section className="grid gap-4 md:grid-cols-4">
          <MetricCard label="Behavior gates" value={String(draftPolicy.behavior_gates.length)} detail="Top-level release controls" />
          <MetricCard label="Cohorts" value={String(draftPolicy.cohorts.length)} detail="Deterministic audience slices" />
          <MetricCard label="Eval buckets" value={String(draftPolicy.evaluation_buckets.length)} detail={`${rollout.evaluationSummary?.total_samples ?? 0} tracked samples`} />
          <MetricCard label="Active kill switches" value={String(activeKillSwitchCount)} detail="Immediate fallbacks in force" warning={activeKillSwitchCount > 0} />
        </section>

        <Card className="border-slate-200 bg-white/95">
          <CardHeader>
            <CardTitle>Behavior gates</CardTitle>
            <CardDescription>Constrained modes for each rollout capability. The frontend renders these backend-owned gates directly and never recomputes policy logic.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4">
            {draftPolicy.behavior_gates.map((gate) => (
              <article key={gate.capability} className="rounded-2xl border border-slate-200 bg-slate-50/60 p-4">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div className="space-y-1">
                    <h2 className="text-sm font-semibold text-slate-900">{capabilityLabels[gate.capability] ?? gate.capability}</h2>
                    <p className="text-sm text-slate-600">{gate.description ?? 'No description provided by the policy contract.'}</p>
                    <p className="text-xs font-medium uppercase tracking-[0.18em] text-slate-500">Fallback: {gate.fallback_behavior}</p>
                  </div>
                  <div className="w-full max-w-[240px] space-y-2">
                    <Label htmlFor={`gate-${gate.capability}`}>Mode</Label>
                    <Select
                      value={gate.mode}
                      onValueChange={(mode) => rollout.setDraftPolicy((current) => (
                        current ? updateGate(current, gate.capability, mode) : current
                      ))}
                    >
                      <SelectTrigger id={`gate-${gate.capability}`}>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {(gateOptions[gate.capability] ?? [gate.mode]).map((option) => (
                          <SelectItem key={option} value={option}>
                            {option.replaceAll('_', ' ')}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              </article>
            ))}
          </CardContent>
        </Card>

        <div className="grid gap-6 lg:grid-cols-2">
          <Card className="border-slate-200 bg-white/95">
            <CardHeader>
              <CardTitle>Cohorts</CardTitle>
              <CardDescription>Review rollout percentages, pinned buckets, and current deterministic membership.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4">
              {draftPolicy.cohorts.map((cohort) => (
                <article key={cohort.cohort_id} className="rounded-2xl border border-slate-200 bg-slate-50/60 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h2 className="text-sm font-semibold text-slate-900">{cohort.label}</h2>
                      <p className="mt-1 text-sm text-slate-600">{cohort.description ?? 'No cohort description.'}</p>
                      <p className="mt-2 text-xs text-slate-500">
                        {cohort.assignment_unit} assignment • {cohort.learner_ids.length} learners • {cohort.household_ids.length} households
                      </p>
                    </div>
                    <Badge variant="secondary" className="bg-slate-100 text-slate-700">
                      {cohort.rollout_percentage}%
                    </Badge>
                  </div>
                  <div className="mt-4 grid gap-3 sm:grid-cols-2">
                    <div className="space-y-2">
                      <Label htmlFor={`cohort-${cohort.cohort_id}-percentage`}>Rollout percentage</Label>
                      <Input
                        id={`cohort-${cohort.cohort_id}-percentage`}
                        type="number"
                        min={0}
                        max={100}
                        value={String(cohort.rollout_percentage)}
                        onChange={(event) => rollout.setDraftPolicy((current) => (
                          current
                            ? updateCohortPercentage(current, cohort.cohort_id, clampPercent(event.target.value))
                            : current
                        ))}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor={`cohort-${cohort.cohort_id}-bucket`}>Pinned evaluation bucket</Label>
                      <Select
                        value={cohort.pinned_evaluation_bucket_id ?? 'none'}
                        onValueChange={(value) => rollout.setDraftPolicy((current) => (
                          current
                            ? updateCohortBucket(current, cohort.cohort_id, value === 'none' ? null : value)
                            : current
                        ))}
                      >
                        <SelectTrigger id={`cohort-${cohort.cohort_id}-bucket`}>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="none">No pinned bucket</SelectItem>
                          {draftPolicy.evaluation_buckets.map((bucket) => (
                            <SelectItem key={bucket.bucket_id} value={bucket.bucket_id}>
                              {bucket.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                </article>
              ))}
            </CardContent>
          </Card>

          <Card className="border-slate-200 bg-white/95">
            <CardHeader>
              <CardTitle>Evaluation buckets</CardTitle>
              <CardDescription>Bucket weights and recent run outcomes for the current rollout.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4">
              {draftPolicy.evaluation_buckets.map((bucket) => {
                const summary = rollout.evaluationSummary?.buckets.find((item) => item.bucket_id === bucket.bucket_id)
                return (
                  <article key={bucket.bucket_id} className="rounded-2xl border border-slate-200 bg-slate-50/60 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <h2 className="text-sm font-semibold text-slate-900">{bucket.label}</h2>
                        <p className="mt-1 text-sm text-slate-600">{bucket.description ?? 'No bucket description.'}</p>
                      </div>
                      <Badge variant="secondary" className="bg-slate-100 text-slate-700">
                        {bucket.weight}%
                      </Badge>
                    </div>
                    <div className="mt-3 grid gap-3 sm:grid-cols-2">
                      <div className="space-y-2">
                        <Label htmlFor={`bucket-${bucket.bucket_id}-weight`}>Weight</Label>
                        <Input
                          id={`bucket-${bucket.bucket_id}-weight`}
                          type="number"
                          min={0}
                          max={100}
                          value={String(bucket.weight)}
                          onChange={(event) => rollout.setDraftPolicy((current) => (
                            current
                              ? updateBucketWeight(current, bucket.bucket_id, clampPercent(event.target.value))
                              : current
                          ))}
                        />
                      </div>
                      <div className="rounded-2xl border border-white bg-white p-3 text-sm text-slate-600 shadow-sm">
                        <p>Samples: {summary?.sample_count ?? 0}</p>
                        <p>Learners: {summary?.learner_count ?? 0}</p>
                        <p>Positive run rate: {formatPercent(summary?.positive_run_rate)}</p>
                      </div>
                    </div>
                  </article>
                )
              })}
            </CardContent>
          </Card>
        </div>

        <Card className="border-slate-200 bg-white/95">
          <CardHeader>
            <CardTitle>Kill switches</CardTitle>
            <CardDescription>Emergency controls stay explicit, operator-readable, and simulation-visible.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4">
            {draftPolicy.kill_switches.map((item) => (
              <article key={item.capability} className="rounded-2xl border border-slate-200 bg-slate-50/60 p-4">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <ShieldAlert className={`h-4 w-4 ${item.active ? 'text-amber-700' : 'text-slate-400'}`} />
                      <h2 className="text-sm font-semibold text-slate-900">{capabilityLabels[item.capability] ?? item.capability}</h2>
                    </div>
                    <p className="text-xs text-slate-500">Updated at {new Date(item.updated_at).toLocaleString()}</p>
                  </div>
                  <Switch
                    checked={item.active}
                    onCheckedChange={(active) => rollout.setDraftPolicy((current) => (
                      current ? updateKillSwitch(current, item.capability, { active }) : current
                    ))}
                  />
                </div>
                <div className="mt-3 space-y-2">
                  <Label htmlFor={`kill-switch-${item.capability}`}>Operator reason</Label>
                  <Input
                    id={`kill-switch-${item.capability}`}
                    value={item.reason ?? ''}
                    placeholder="Why is this switch active?"
                    onChange={(event) => rollout.setDraftPolicy((current) => (
                      current ? updateKillSwitch(current, item.capability, { reason: event.target.value || null }) : current
                    ))}
                  />
                </div>
              </article>
            ))}
          </CardContent>
        </Card>

        <Card className="border-slate-200 bg-white/95">
          <CardHeader>
            <CardTitle>Simulation subjects</CardTitle>
            <CardDescription>Choose real learner or household IDs to review rollout diffs before you save.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4">
            {subjects.length === 0 ? (
              <p className="text-sm text-slate-600">No sample subjects loaded yet. Add a learner or household below to make the simulation concrete.</p>
            ) : (
              subjects.map((subject, index) => (
                <div key={`${subject.learner_id ?? 'none'}-${subject.household_id ?? 'none'}-${index}`} className="grid gap-3 rounded-2xl border border-slate-200 bg-slate-50/60 p-4 lg:grid-cols-[1fr_1fr_1fr_auto]">
                  <div className="space-y-2">
                    <Label htmlFor={`subject-${index}-label`}>Label</Label>
                    <Input
                      id={`subject-${index}-label`}
                      value={subject.label ?? ''}
                      placeholder="Cohort sample"
                      onChange={(event) => setSubjectDraft(subjects.map((item, itemIndex) => (
                        itemIndex === index ? { ...item, label: event.target.value || null } : item
                      )))}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor={`subject-${index}-learner`}>Learner ID</Label>
                    <Input
                      id={`subject-${index}-learner`}
                      value={subject.learner_id ?? ''}
                      placeholder="learner-123"
                      onChange={(event) => setSubjectDraft(subjects.map((item, itemIndex) => (
                        itemIndex === index ? { ...item, learner_id: event.target.value || null } : item
                      )))}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor={`subject-${index}-household`}>Household ID</Label>
                    <Input
                      id={`subject-${index}-household`}
                      value={subject.household_id ?? ''}
                      placeholder="household-123"
                      onChange={(event) => setSubjectDraft(subjects.map((item, itemIndex) => (
                        itemIndex === index ? { ...item, household_id: event.target.value || null } : item
                      )))}
                    />
                  </div>
                  <div className="flex items-end">
                    <Button variant="ghost" onClick={() => setSubjectDraft(subjects.filter((_, itemIndex) => itemIndex !== index))}>
                      Remove
                    </Button>
                  </div>
                </div>
              ))
            )}
            <Button
              variant="outline"
              className="w-fit"
              onClick={() => setSubjectDraft([...subjects, { learner_id: null, household_id: null, label: '' }])}
            >
              Add subject
            </Button>
          </CardContent>
        </Card>

        <Card className="border-slate-200 bg-white/95">
          <CardHeader>
            <CardTitle>Simulation results</CardTitle>
            <CardDescription>Review changed cohorts, bucket assignment shifts, and newly risky capabilities before saving.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4">
            {!rollout.simulation ? (
              <p className="text-sm text-slate-600">Run a simulation to inspect rollout diffs and risk counts.</p>
            ) : (
              <>
                <div className="grid gap-4 md:grid-cols-4">
                  <MetricCard label="Changed subjects" value={String(rollout.simulation.summary.changed_subject_count)} detail={`${rollout.simulation.summary.total_subject_count} sampled`} />
                  <MetricCard label="Changed learners" value={String(rollout.simulation.summary.changed_learner_count)} detail="Learner-level assignment shifts" />
                  <MetricCard label="Changed households" value={String(rollout.simulation.summary.changed_household_count)} detail="Household-level assignment shifts" />
                  <MetricCard
                    label="Newly risky"
                    value={String(rollout.simulation.summary.newly_risky_subject_count)}
                    detail="Subjects exposed to riskier capabilities"
                    warning={rollout.simulation.summary.newly_risky_subject_count > 0}
                  />
                </div>

                {rollout.simulation.diffs.map((diff) => (
                  <article key={`${diff.subject.learner_id ?? diff.subject.household_id ?? 'subject'}-${diff.subject.label ?? ''}`} className="rounded-2xl border border-slate-200 bg-slate-50/60 p-4">
                    <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                      <div>
                        <h3 className="text-sm font-semibold text-slate-900">{diff.subject.label ?? diff.subject.learner_id ?? diff.subject.household_id ?? 'Unnamed subject'}</h3>
                        <p className="mt-1 text-sm text-slate-600">
                          Cohort changed: {diff.cohort_changed ? 'yes' : 'no'} • Evaluation bucket changed: {diff.evaluation_bucket_changed ? 'yes' : 'no'}
                        </p>
                      </div>
                      {diff.newly_risky_capabilities.length > 0 ? (
                        <Badge variant="secondary" className="bg-amber-100 text-amber-900">
                          {diff.newly_risky_capabilities.length} newly risky
                        </Badge>
                      ) : null}
                    </div>
                    <div className="mt-4 grid gap-3">
                      {diff.capability_deltas.filter((item) => item.changed).map((delta) => (
                        <div key={delta.capability} className="rounded-2xl border border-white bg-white p-3 shadow-sm">
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <p className="text-sm font-medium text-slate-900">{capabilityLabels[delta.capability] ?? delta.capability}</p>
                            <div className="flex items-center gap-2 text-xs text-slate-500">
                              <span>{delta.current_decision.mode.replaceAll('_', ' ')}</span>
                              <ArrowUpRight className="h-3.5 w-3.5" />
                              <span>{delta.proposed_decision.mode.replaceAll('_', ' ')}</span>
                            </div>
                          </div>
                          <p className="mt-2 text-xs text-slate-500">
                            Source: {delta.current_decision.source.replaceAll('_', ' ')} {'->'} {delta.proposed_decision.source.replaceAll('_', ' ')}
                          </p>
                          {delta.proposed_decision.rationale.length > 0 ? (
                            <p className="mt-2 text-sm text-slate-700">{delta.proposed_decision.rationale[0]}</p>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  </article>
                ))}
              </>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6">
        <Card className="border-slate-200 bg-white/95">
          <CardHeader>
            <CardTitle>Current policy</CardTitle>
            <CardDescription>Live metadata for the rollout configuration you are editing.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-slate-600">
            <p className="font-medium text-slate-900">{livePolicy.label}</p>
            <p>{livePolicy.description}</p>
            <p>Assignment salt: <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs">{livePolicy.assignment_salt}</code></p>
            <p>Updated: {new Date(livePolicy.updated_at).toLocaleString()}</p>
          </CardContent>
        </Card>

        <Card className="border-slate-200 bg-white/95">
          <CardHeader>
            <CardTitle>Evaluation snapshot</CardTitle>
            <CardDescription>Outcome samples already gathered for the current bucket mix.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3">
            {(rollout.evaluationSummary?.buckets ?? []).map((bucket) => (
              <article key={bucket.bucket_id} className="rounded-2xl border border-slate-200 bg-slate-50/60 p-3">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-medium text-slate-900">{bucket.label}</p>
                  <Badge variant="secondary" className="bg-slate-100 text-slate-700">
                    {bucket.sample_count} samples
                  </Badge>
                </div>
                <p className="mt-2 text-xs text-slate-500">
                  Positive run rate {formatPercent(bucket.positive_run_rate)} • Avg outcome {formatPercent(bucket.average_run_outcome_score)}
                </p>
              </article>
            ))}
          </CardContent>
        </Card>

        <ReleaseReadinessPanel readiness={readiness.readiness} loading={readiness.loading} />
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

function clampPercent(value: string) {
  const numeric = Number(value)
  if (Number.isNaN(numeric)) {
    return 0
  }
  return Math.max(0, Math.min(100, numeric))
}

function formatPercent(value?: number) {
  return `${Math.round((value ?? 0) * 100)}%`
}

function hasSubjectId(subject: RolloutSimulationSubject) {
  return Boolean(subject.learner_id || subject.household_id)
}
