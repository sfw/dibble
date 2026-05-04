import { AlertTriangle, Cloud, ShieldAlert, Siren, Sparkles, TriangleAlert } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import type { ReleaseReadinessSnapshot } from '@/types'

function countLabel(value: number, singular: string, plural: string) {
  return `${value} ${value === 1 ? singular : plural}`
}

export function ReleaseReadinessPanel({
  readiness,
  loading = false,
}: {
  readiness: ReleaseReadinessSnapshot | null
  loading?: boolean
}) {
  if (loading) {
    return (
      <Card className="border-slate-200 bg-white/95">
        <CardHeader>
          <CardTitle>Trust readiness</CardTitle>
          <CardDescription>Loading degraded-mode and blocked-review signals.</CardDescription>
        </CardHeader>
      </Card>
    )
  }

  if (!readiness) {
    return null
  }

  return (
    <Card className="border-slate-200 bg-white/95">
      <CardHeader>
        <CardTitle>Trust readiness</CardTitle>
        <CardDescription>Operator-facing blockers, degraded services, and review queues from the observability layer.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <StatusStat
            icon={TriangleAlert}
            label="Degraded operations"
            value={String(readiness.degraded_trace_count)}
            detail={`${readiness.total_recent_traces} recent traces`}
            tone={readiness.degraded_trace_count > 0 ? 'warning' : 'neutral'}
          />
          <StatusStat
            icon={ShieldAlert}
            label="Kill switches"
            value={String(readiness.active_kill_switches.length)}
            detail={countLabel(readiness.active_kill_switches.length, 'switch active', 'switches active')}
            tone={readiness.active_kill_switches.length > 0 ? 'warning' : 'neutral'}
          />
          <StatusStat
            icon={Sparkles}
            label="Blocked reviews"
            value={String(readiness.blocked_review_previews.length)}
            detail={countLabel(readiness.pending_review_queues.length, 'queue live', 'queues live')}
            tone={readiness.blocked_review_previews.length > 0 ? 'warning' : 'neutral'}
          />
          <StatusStat
            icon={Siren}
            label="Stale suggestions"
            value={String(readiness.stale_autonomous_suggestions.length)}
            detail={countLabel(readiness.stale_autonomous_suggestions.length, 'household stalled', 'households stalled')}
            tone={readiness.stale_autonomous_suggestions.length > 0 ? 'warning' : 'neutral'}
          />
        </div>

        <section className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
          <div className="flex items-center gap-2 text-sm font-medium text-slate-900">
            <Cloud className="h-4 w-4 text-sky-700" />
            Cloud library
            <Badge
              variant="secondary"
              className={readiness.cloud_library.degraded ? 'bg-amber-100 text-amber-900' : 'bg-emerald-100 text-emerald-800'}
            >
              {readiness.cloud_library.degraded ? 'Degraded' : readiness.cloud_library.remote_enabled ? 'Remote ready' : 'Local only'}
            </Badge>
          </div>
          <p className="mt-2 text-sm text-slate-700">
            {readiness.cloud_library.remote_enabled
              ? readiness.cloud_library.degraded
                ? readiness.cloud_library.last_degraded_reason ?? 'Remote access is degraded and may fall back to local-only behavior.'
                : 'Remote lookup is available under the current rollout policy.'
              : 'Remote cloud-library access is still disabled by rollout policy.'}
          </p>
          <p className="mt-2 text-xs text-slate-500">
            Lookup failures: {readiness.cloud_library.recent_lookup_failures} • Publish failures: {readiness.cloud_library.recent_publish_failures}
          </p>
        </section>

        {readiness.active_kill_switches.length > 0 ? (
          <section className="grid gap-2">
            <h3 className="text-sm font-semibold text-slate-900">Active kill switches</h3>
            {readiness.active_kill_switches.map((item) => (
              <article key={item.capability} className="rounded-2xl border border-amber-200 bg-amber-50/70 p-3">
                <p className="text-sm font-medium text-slate-900">{item.capability.replaceAll('_', ' ')}</p>
                <p className="mt-1 text-sm text-slate-700">{item.reason ?? 'No operator note recorded.'}</p>
              </article>
            ))}
          </section>
        ) : null}

        {readiness.blocked_review_previews.length > 0 ? (
          <section className="grid gap-2">
            <h3 className="text-sm font-semibold text-slate-900">Blocked review previews</h3>
            {readiness.blocked_review_previews.slice(0, 4).map((item) => (
              <article key={`${item.item_kind}-${item.item_id}`} className="rounded-2xl border border-slate-200 bg-white p-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium text-slate-900">{item.summary}</p>
                    <p className="mt-1 text-sm text-slate-700">{item.explanation}</p>
                    <p className="mt-2 text-xs font-medium uppercase tracking-[0.18em] text-slate-500">Next step: {item.next_step}</p>
                  </div>
                  <Badge variant="secondary" className="bg-amber-100 text-amber-900">
                    {item.risk_level}
                  </Badge>
                </div>
              </article>
            ))}
          </section>
        ) : null}

        {readiness.recent_degraded_operations.length > 0 ? (
          <section className="grid gap-2">
            <h3 className="text-sm font-semibold text-slate-900">Recent degraded operations</h3>
            {readiness.recent_degraded_operations.slice(0, 3).map((trace) => (
              <article key={trace.trace_id} className="rounded-2xl border border-slate-200 bg-white p-3">
                <div className="flex items-start gap-2">
                  <AlertTriangle className="mt-0.5 h-4 w-4 text-amber-700" />
                  <div>
                    <p className="text-sm font-medium text-slate-900">{trace.summary}</p>
                    <p className="mt-1 text-xs text-slate-500">
                      {trace.harness.replaceAll('_', ' ')} • {trace.operation}
                    </p>
                  </div>
                </div>
              </article>
            ))}
          </section>
        ) : null}
      </CardContent>
    </Card>
  )
}

function StatusStat({
  icon: Icon,
  label,
  value,
  detail,
  tone,
}: {
  icon: typeof TriangleAlert
  label: string
  value: string
  detail: string
  tone: 'neutral' | 'warning'
}) {
  return (
    <div className={`rounded-2xl border p-4 ${tone === 'warning' ? 'border-amber-200 bg-amber-50/70' : 'border-slate-200 bg-white'}`}>
      <div className="flex items-center gap-2 text-sm font-medium text-slate-900">
        <Icon className={`h-4 w-4 ${tone === 'warning' ? 'text-amber-700' : 'text-slate-500'}`} />
        {label}
      </div>
      <p className="mt-3 text-2xl font-semibold text-slate-900">{value}</p>
      <p className="mt-1 text-xs text-slate-500">{detail}</p>
    </div>
  )
}
