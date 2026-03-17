import { InsightCard, JsonPanel, MetricList, Pill, SectionHeader } from '../components/primitives'
import { formatPercent } from '../lib/formatters'
import type { LearnerFlowSummary, LearnerProfileV2, ProfileSummary, TeacherContractGap } from '../types'

export function TeacherView({
  summary,
  profile,
  flow,
  gaps,
  dataSource,
}: {
  summary: ProfileSummary
  profile: LearnerProfileV2
  flow: LearnerFlowSummary
  gaps: TeacherContractGap[]
  dataSource: 'live' | 'demo'
}) {
  return (
    <section className="view-grid">
      <div className="main-column">
        <div className="panel">
          <SectionHeader
            eyebrow="Teacher-facing explainability"
            title="Intervention readiness and rationale"
            description="This surface is intentionally centered on what the backend can explain today without requiring admin telemetry access."
          />
          <div className="teacher-scoreboard">
            <InsightCard
              title="Current recommendation"
              value={flow.next_step.content_type ?? 'monitor'}
              detail={`Action ${flow.next_step.action} on ${flow.next_step.target_stage}`}
              rationale={flow.next_step.rationale ?? flow.rationale ?? 'No rationale returned'}
            />
            <InsightCard
              title="Why now"
              value={summary.strategy.recommended_next_action}
              detail={`Recovery focus ${summary.strategy.recovery_focus}`}
              rationale={summary.strategy.rationale ?? 'No rationale returned'}
            />
            <InsightCard
              title="Risk posture"
              value={flow.session_stuck_loop_risk}
              detail={`Relapse risk ${formatPercent(summary.strategy.relapse_risk)}`}
              rationale={`Volatility ${formatPercent(summary.strategy.volatility_index)}`}
            />
            <InsightCard
              title="Trust level"
              value={dataSource === 'live' ? 'backend-connected' : 'demo-fallback'}
              detail={`Profile completeness ${formatPercent(profile.profile_metadata.completeness_score)}`}
              rationale="The teacher view should expose confidence and missing seams, not hide them."
            />
          </div>
        </div>

        <div className="panel">
          <SectionHeader
            eyebrow="Contract gaps"
            title="What the frontend still cannot delegate cleanly to the backend"
            description="These gaps came from comparing the revised spec’s teacher and intervention surfaces to the currently implemented backend contracts."
          />
          <div className="gap-list">
            {gaps.map((gap) => (
              <article key={gap.title} className="gap-card">
                <div className="gap-card__header">
                  <Pill
                    label={gap.severity}
                    tone={gap.severity === 'P0' ? 'danger' : gap.severity === 'P1' ? 'warning' : 'neutral'}
                  />
                  <h3>{gap.title}</h3>
                </div>
                <p><strong>Why it matters:</strong> {gap.why_it_matters}</p>
                <p><strong>Current backend:</strong> {gap.current_backend}</p>
                <p><strong>Frontend stance:</strong> {gap.frontend_response}</p>
              </article>
            ))}
          </div>
        </div>
      </div>

      <aside className="side-column">
        <div className="panel">
          <SectionHeader
            eyebrow="Intervention summary"
            title="What a teacher can safely see"
            description="Compact, stable, and learner-specific read models."
          />
          <MetricList
            title="Teacher snapshot"
            items={[
              { label: 'Progress signal', value: summary.progress.signal },
              { label: 'Strategy signal', value: summary.strategy.signal },
              { label: 'Flow type', value: flow.flow_type },
              { label: 'Current phase', value: flow.current_phase },
              { label: 'Next content', value: flow.next_step.content_type ?? 'monitor' },
            ]}
          />
        </div>
        <JsonPanel
          title="Compact explainability payload"
          value={{
            summary: {
              progress: summary.progress,
              strategy: summary.strategy,
              state_profile: summary.state_profile,
            },
            current_flow: flow,
          }}
        />
      </aside>
    </section>
  )
}
