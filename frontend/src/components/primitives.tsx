import type {
  GeneratedContent,
  LearnerFlowSummary,
} from '../types'
import { Badge, type BadgeProps } from '@/components/ui/badge'

export function Pill({
  label,
  tone,
}: {
  label: string
  tone: 'accent' | 'success' | 'warning' | 'danger' | 'neutral'
}) {
  const variant: BadgeProps['variant'] =
    tone === 'success'
      ? 'default'
      : tone === 'warning'
        ? 'warning'
        : tone === 'danger'
          ? 'destructive'
          : tone === 'neutral'
            ? 'outline'
            : 'secondary'

  return <Badge variant={variant}>{label}</Badge>
}

export function SectionHeader({
  eyebrow,
  title,
  description,
}: {
  eyebrow: string
  title: string
  description: string
}) {
  return (
    <div className="section-header">
      <p className="eyebrow">{eyebrow}</p>
      <h2>{title}</h2>
      <p className="lead-paragraph">{description}</p>
    </div>
  )
}

export function StatCard({
  label,
  value,
  sublabel,
}: {
  label: string
  value: string
  sublabel: string
}) {
  return (
    <article className="stat-card">
      <span>{label}</span>
      <strong>{value}</strong>
      <p>{sublabel}</p>
    </article>
  )
}

export function InsightCard({
  title,
  value,
  detail,
  rationale,
}: {
  title: string
  value: string
  detail: string
  rationale: string
}) {
  return (
    <article className="insight-card">
      <p className="content-block__kind">{title}</p>
      <h3>{value}</h3>
      <p className="muted">{detail}</p>
      <p>{rationale}</p>
    </article>
  )
}

export function MetricList({
  title,
  items,
}: {
  title: string
  items: Array<{ label: string; value: string }>
}) {
  return (
    <div className="metric-list-card">
      <h3>{title}</h3>
      <div className="metric-list">
        {items.map((item) => (
          <div key={`${item.label}-${item.value}`} className="metric-list__row">
            <span>{item.label}</span>
            <strong>{item.value}</strong>
          </div>
        ))}
      </div>
    </div>
  )
}

export function JsonPanel({ title, value }: { title: string; value: unknown }) {
  return (
    <details className="panel json-panel">
      <summary>{title}</summary>
      <pre>{JSON.stringify(value, null, 2)}</pre>
    </details>
  )
}

export function FlowRail({ flow }: { flow: LearnerFlowSummary }) {
  return (
    <div className="flow-rail">
      <div className="flow-step active">
        <span>Phase</span>
        <strong>{flow.current_phase}</strong>
      </div>
      <div className="flow-step active">
        <span>Action</span>
        <strong>{flow.progression_action}</strong>
      </div>
      <div className="flow-step active">
        <span>Stage</span>
        <strong>{flow.target_stage}</strong>
      </div>
      <div className="flow-step">
        <span>Next</span>
        <strong>{flow.next_step.content_type ?? 'monitor'}</strong>
      </div>
    </div>
  )
}

export function FlowSummaryCard({
  summary,
}: {
  summary: NonNullable<GeneratedContent['workflow_summary']>
}) {
  return (
    <div className="summary-card">
      <div className="summary-card__topline">
        <Pill label={summary.status} tone="success" />
        <Pill label={summary.flow_type} tone="neutral" />
        <Pill label={summary.target_stage} tone="accent" />
      </div>
      <h3>{summary.delivered_content_type ?? 'generated content'}</h3>
      <p>{summary.rationale ?? 'No workflow rationale returned.'}</p>
      <div className="summary-card__grid">
        <div>
          <span>Delivered phase</span>
          <strong>{summary.delivered_phase}</strong>
        </div>
        <div>
          <span>Progression action</span>
          <strong>{summary.progression_action}</strong>
        </div>
        <div>
          <span>Active targets</span>
          <strong>{summary.active_target_kc_ids.join(', ') || 'none'}</strong>
        </div>
        <div>
          <span>Next content</span>
          <strong>{summary.next_step.content_type ?? 'monitor'}</strong>
        </div>
      </div>
    </div>
  )
}

export function FlowSummaryLike({
  title,
  rows,
}: {
  title: string
  rows: Array<[string, string]>
}) {
  return (
    <div className="summary-card">
      <h3>{title}</h3>
      <div className="metric-list">
        {rows.map(([label, value]) => (
          <div key={label} className="metric-list__row">
            <span>{label}</span>
            <strong>{value}</strong>
          </div>
        ))}
      </div>
    </div>
  )
}
