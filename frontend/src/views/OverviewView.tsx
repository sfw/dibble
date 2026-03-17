import { formatPercent, signedPercent } from '../lib/formatters'
import type { LearnerFlowSummary, LearnerProfileV2, ProfileSummary } from '../types'
import { FlowRail, InsightCard, JsonPanel, MetricList, SectionHeader, StatCard } from '../components/primitives'

export function OverviewView({
  summary,
  profile,
  flow,
  showDebugPanels = false,
}: {
  summary: ProfileSummary
  profile: LearnerProfileV2
  flow: LearnerFlowSummary
  showDebugPanels?: boolean
}) {
  return (
    <section className="view-grid">
      <div className="main-column">
        <div className="panel hero-summary">
          <div className="hero-summary__header">
            <div>
              <p className="eyebrow">Learner summary / current flow</p>
              <h2>Current learning posture</h2>
            </div>
            <div className="hero-pills">
              <span className="pill pill--accent">{summary.progress.signal}</span>
              <span className="pill pill--neutral">{flow.status}</span>
              <span className="pill pill--success">{flow.next_step.target_stage}</span>
            </div>
          </div>
          <div className="kpi-grid">
            <StatCard label="Engagement" value={summary.engagement} sublabel="live affective signal" />
            <StatCard label="Frustration" value={summary.frustration} sublabel="intervention timing input" />
            <StatCard label="Total load" value={formatPercent(summary.total_load)} sublabel="current load estimate" />
            <StatCard
              label="Confidence calibration"
              value={formatPercent(summary.confidence_calibration)}
              sublabel="metacognitive reliability"
            />
          </div>
          <FlowRail flow={flow} />
        </div>

        <div className="panel">
          <SectionHeader
            eyebrow="Learner read models"
            title="Why the backend is steering this learner here"
            description="These cards come directly from compact summary contracts rather than reconstructed traces."
          />
          <div className="explanation-grid">
            <InsightCard
              title="Calibration"
              value={summary.calibration.signal}
              detail={`Confidence ${formatPercent(summary.calibration.confidence)} from ${summary.calibration.matched_run_count} runs`}
              rationale={`Source: ${summary.calibration.source}`}
            />
            <InsightCard
              title="Progress"
              value={summary.progress.signal}
              detail={`Delta ${signedPercent(summary.progress.progress_delta)}`}
              rationale={`Recent average ${formatPercent(summary.progress.recent_average_run_outcome_score)}`}
            />
            <InsightCard
              title="Strategy"
              value={summary.strategy.recommended_next_action}
              detail={`Trajectory ${summary.strategy.trajectory_state}`}
              rationale={summary.strategy.rationale ?? 'No rationale returned'}
            />
            <InsightCard
              title="State profile"
              value={summary.state_profile.signal}
              detail={`Overload risk ${formatPercent(summary.state_profile.overload_risk)}`}
              rationale={summary.state_profile.rationale ?? 'No rationale returned'}
            />
          </div>
        </div>

        <div className="panel">
          <SectionHeader
            eyebrow="Profile detail"
            title="Teacher-safe explainability surface"
            description="This is the first-pass transparency dashboard for inferred learner state, KC mastery, preferences, and accommodations."
          />
          <div className="two-column-grid">
            <MetricList
              title="Knowledge state"
              items={[
                ...Object.entries(profile.knowledge_state.kc_mastery).map(([key, value]) => ({
                  label: key,
                  value: formatPercent(value),
                })),
              ]}
            />
            <MetricList
              title="Learning preferences"
              items={[
                { label: 'Scaffolding', value: profile.learning_preferences.scaffolding_preference },
                { label: 'Pace', value: profile.learning_preferences.pace_preference },
                {
                  label: 'Preferred examples',
                  value: profile.learning_preferences.example_domain_preferences.join(', ') || 'None yet',
                },
                {
                  label: 'Accommodations',
                  value: profile.accommodations.join(', ') || 'None recorded',
                },
              ]}
            />
          </div>
        </div>
      </div>

      <aside className="side-column">
        <div className="panel">
          <SectionHeader
            eyebrow="Recent activity"
            title="Session context"
            description="Compact activity packaging from learner summary."
          />
          <MetricList
            title="Activity"
            items={[
              { label: 'Generations', value: String(summary.recent_activity.generation_count) },
              { label: 'Observations', value: String(summary.recent_activity.observation_count) },
              {
                label: 'Socratic turns',
                value: String(summary.recent_activity.socratic_assessment_count),
              },
              {
                label: 'Last session',
                value: summary.recent_activity.last_learning_session_id ?? 'None',
              },
              {
                label: 'Last generation',
                value: summary.recent_activity.last_generation_id ?? 'None',
              },
            ]}
          />
        </div>
        <div className="panel">
          <SectionHeader
            eyebrow="Trait reliability"
            title="Cognitive trait confidence"
            description="Use these values as support for explainability, not as high-stakes truth claims."
          />
          <MetricList
            title="Trait signals"
            items={[
              {
                label: 'Working memory',
                value: profile.cognitive_traits.working_memory
                  ? `${formatPercent(profile.cognitive_traits.working_memory.value)} / ${formatPercent(profile.cognitive_traits.working_memory.confidence)} conf`
                  : 'Unavailable',
              },
              {
                label: 'Processing speed',
                value: profile.cognitive_traits.processing_speed
                  ? `${formatPercent(profile.cognitive_traits.processing_speed.value)} / ${formatPercent(profile.cognitive_traits.processing_speed.confidence)} conf`
                  : 'Unavailable',
              },
              {
                label: 'Trait stability',
                value: formatPercent(summary.trait_profile.trait_stability),
              },
              {
                label: 'Challenge tolerance',
                value: formatPercent(summary.trait_profile.challenge_tolerance),
              },
            ]}
          />
        </div>
        {showDebugPanels ? (
          <JsonPanel
            title="Debug contract payload"
            value={{
              current_flow: flow,
              summary_strategy: summary.strategy,
              state_profile: summary.state_profile,
            }}
          />
        ) : null}
      </aside>
    </section>
  )
}
