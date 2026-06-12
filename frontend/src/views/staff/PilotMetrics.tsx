import { useEffect, useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card'
import { ErrorBanner } from '../../components/ui/error-banner'
import { useConfigContext } from '../../contexts/ConfigContext'
import { getPilotMetrics } from '../../api'
import type { PilotMetricsResponse } from '../../types'
import { useStaffApiConfig } from './useStaffApiConfig'

function formatRate(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return '—'
  }
  return `${Math.round(value * 100)}%`
}

function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return '—'
  }
  return value.toLocaleString()
}

function StatCard({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardDescription>{label}</CardDescription>
        <CardTitle className="text-3xl">{value}</CardTitle>
      </CardHeader>
      {hint ? <CardContent className="pt-0 text-sm text-slate-500">{hint}</CardContent> : null}
    </Card>
  )
}

export function PilotMetrics() {
  const { baseUrl } = useConfigContext()
  const { apiKey, bearerToken } = useStaffApiConfig()
  const [metrics, setMetrics] = useState<PilotMetricsResponse | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    void (async () => {
      try {
        const result = await getPilotMetrics({
          baseUrl,
          apiKey,
          bearerToken,
          useDemoFallback: false,
          showDebugPanels: false,
        })
        setMetrics(result)
        setError('')
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Could not load pilot metrics')
      } finally {
        setLoading(false)
      }
    })()
  }, [apiKey, baseUrl, bearerToken])

  if (loading) {
    return <p className="text-sm text-slate-500">Loading pilot metrics…</p>
  }

  if (error) {
    return <ErrorBanner message={error} />
  }

  if (!metrics) {
    return <p className="text-sm text-slate-500">No pilot metrics available.</p>
  }

  const { cohort, baseline, learners } = metrics

  return (
    <div className="flex flex-col gap-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Pilot metrics</h1>
        <p className="text-sm text-slate-500">
          Cohort and per-learner numbers for the weekly pilot review (last {metrics.days} days).
        </p>
      </header>

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Learners" value={formatNumber(cohort.learner_count)} />
        <StatCard
          label="Sessions"
          value={`${formatNumber(cohort.sessions_completed)} / ${formatNumber(cohort.sessions_started)}`}
          hint={`Completion rate ${formatRate(cohort.completion_rate)}`}
        />
        <StatCard
          label="Avg mastery delta"
          value={
            cohort.average_kc_mastery_delta === null || cohort.average_kc_mastery_delta === undefined
              ? '—'
              : cohort.average_kc_mastery_delta.toFixed(2)
          }
          hint="Overall KC mastery, earliest vs latest snapshot"
        />
        <StatCard
          label="Content defects"
          value={formatNumber(cohort.defect_report_count)}
          hint={`${formatNumber(cohort.verification_failed_count)} verification failures`}
        />
        <StatCard
          label="Baseline agreement"
          value={formatRate(baseline.agreement_rate)}
          hint={`${formatNumber(baseline.total_decisions)} shadow decisions`}
        />
        <StatCard
          label="Generations"
          value={formatNumber(cohort.generation_count)}
          hint={`${formatNumber(cohort.cache_hits)} cache hits · avg ${formatNumber(cohort.average_latency_ms)} ms`}
        />
        <StatCard
          label="Tokens"
          value={formatNumber(cohort.total_prompt_tokens + cohort.total_completion_tokens)}
          hint={`${formatNumber(cohort.total_prompt_tokens)} prompt · ${formatNumber(cohort.total_completion_tokens)} completion`}
        />
        <StatCard
          label="Interventions"
          value={formatNumber(
            Object.values(cohort.intervention_decision_counts).reduce((sum, count) => sum + count, 0),
          )}
          hint={Object.entries(cohort.intervention_decision_counts)
            .map(([decision, count]) => `${decision}: ${count}`)
            .join(' · ')}
        />
      </section>

      <Card>
        <CardHeader>
          <CardTitle>Per-learner breakdown</CardTitle>
          <CardDescription>One row per learner with profile or activity in the window.</CardDescription>
        </CardHeader>
        <CardContent>
          {learners.length === 0 ? (
            <p className="text-sm text-slate-500">No learner activity recorded yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-border text-xs uppercase tracking-wide text-slate-500">
                    <th className="py-2 pr-4">Learner</th>
                    <th className="py-2 pr-4">Sessions</th>
                    <th className="py-2 pr-4">Return (d/d)</th>
                    <th className="py-2 pr-4">Mastery Δ</th>
                    <th className="py-2 pr-4">Defects</th>
                    <th className="py-2 pr-4">Baseline agree</th>
                    <th className="py-2 pr-4">Generations</th>
                    <th className="py-2">Tokens</th>
                  </tr>
                </thead>
                <tbody>
                  {learners.map((learner) => (
                    <tr key={learner.student_id} className="border-b border-border/60">
                      <td className="py-2 pr-4 font-mono text-xs">{learner.student_id}</td>
                      <td className="py-2 pr-4">
                        {learner.sessions.sessions_completed}/{learner.sessions.sessions_started}
                      </td>
                      <td className="py-2 pr-4">{formatRate(learner.sessions.day_over_day_return_rate)}</td>
                      <td className="py-2 pr-4">
                        {learner.mastery.kc_mastery_delta === null || learner.mastery.kc_mastery_delta === undefined
                          ? '—'
                          : learner.mastery.kc_mastery_delta.toFixed(2)}
                      </td>
                      <td className="py-2 pr-4">{learner.defect_report_count}</td>
                      <td className="py-2 pr-4">{formatRate(learner.baseline_agreement_rate)}</td>
                      <td className="py-2 pr-4">{learner.generation.generation_count}</td>
                      <td className="py-2">
                        {formatNumber(
                          learner.generation.total_prompt_tokens + learner.generation.total_completion_tokens,
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Baseline divergences</CardTitle>
          <CardDescription>
            Most recent points where the production stack and the naive baseline disagreed.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {baseline.divergences.length === 0 ? (
            <p className="text-sm text-slate-500">No divergences recorded.</p>
          ) : (
            <ul className="space-y-2 text-sm">
              {baseline.divergences.slice(0, 20).map((divergence, index) => (
                <li key={`${divergence.inputs_digest ?? index}`} className="rounded-lg border border-border p-3">
                  <span className="font-medium">{divergence.decision_point}</span>
                  <span className="text-slate-500"> · learner </span>
                  <span className="font-mono text-xs">{divergence.student_id ?? 'unknown'}</span>
                  <div className="mt-1 grid gap-1 text-xs text-slate-600 sm:grid-cols-2">
                    <span>production: {JSON.stringify(divergence.production_decision)}</span>
                    <span>baseline: {JSON.stringify(divergence.baseline_decision)}</span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
