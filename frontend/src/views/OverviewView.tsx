import { Button } from '@/components/ui/button'

import type { ViewKey } from '../app/workspace'
import { FlowRail, InsightCard, JsonPanel, MetricList, SectionHeader, StatCard } from '../components/primitives'
import { formatPercent, formatTimestamp, signedPercent, titleCase } from '../lib/formatters'
import type {
  LearnerGenerationHistoryEntry,
  LearnerCurriculumProgressionSummary,
  LearnerFlowSummary,
  LearnerProfileV2,
  LearnerRemediationSessionHistoryEntry,
  LearnerSocraticSessionHistoryEntry,
  LearnerWorkspace,
  ProfileSummary,
} from '../types'

export function OverviewView({
  summary,
  profile,
  flow,
  workspace,
  progression,
  generationHistory,
  socraticHistory,
  remediationHistory,
  contractsLoading = false,
  contractsError = '',
  onSelectView,
  showDebugPanels = false,
}: {
  summary: ProfileSummary
  profile: LearnerProfileV2
  flow: LearnerFlowSummary
  workspace: LearnerWorkspace
  progression: LearnerCurriculumProgressionSummary
  generationHistory: LearnerGenerationHistoryEntry[]
  socraticHistory: LearnerSocraticSessionHistoryEntry[]
  remediationHistory: LearnerRemediationSessionHistoryEntry[]
  contractsLoading?: boolean
  contractsError?: string
  onSelectView: (view: ViewKey) => void
  showDebugPanels?: boolean
}) {
  const resumeView = resolveResumeView(workspace)

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
            eyebrow="Learner workspace"
            title="Resume from the backend-owned workspace"
            description="This panel uses the canonical workspace payload so the frontend can reopen the active learner artifact without reconstructing state from multiple endpoints."
          />
          <div className="resume-card">
            <div className="resume-card__header">
              <div>
                <p className="content-block__kind">Active artifact</p>
                <h3>{titleCase(workspace.active_artifact.kind)}</h3>
              </div>
              <div className="hero-pills">
                <span className="pill pill--neutral">{workspace.active_artifact.flow_type}</span>
                <span className="pill pill--accent">{workspace.active_artifact.current_phase}</span>
                <span className="pill pill--success">{workspace.continue_action.target_stage}</span>
              </div>
            </div>
            <p>{workspace.active_artifact.rationale ?? workspace.continue_action.rationale ?? 'No workspace rationale returned.'}</p>
            <div className="summary-card__grid">
              <div>
                <span>Content type</span>
                <strong>{workspace.active_artifact.content_type ?? 'n/a'}</strong>
              </div>
              <div>
                <span>Continue action</span>
                <strong>{titleCase(workspace.continue_action.kind)}</strong>
              </div>
              <div>
                <span>Target KCs</span>
                <strong>{workspace.continue_action.target_kc_ids.join(', ') || 'none'}</strong>
              </div>
              <div>
                <span>Resource</span>
                <strong>{workspace.continue_action.resource_id ?? workspace.active_artifact.resource_id ?? 'n/a'}</strong>
              </div>
            </div>
            <div className="action-row">
              {resumeView ? (
                <Button type="button" onClick={() => onSelectView(resumeView)}>
                  Open {resumeView} workspace
                </Button>
              ) : null}
              {contractsLoading ? <span className="muted">Refreshing workspace contracts…</span> : null}
              {contractsError ? <span className="inline-error">{contractsError}</span> : null}
            </div>
          </div>
        </div>

        <div className="panel">
          <SectionHeader
            eyebrow="Curriculum progression"
            title="Where this learner sits in the broader curriculum"
            description="This surface uses the backend-owned curriculum progression contract so the frontend can show current resource focus and blocked-next context without inventing sequencing logic."
          />
          <div className="two-column-grid">
            <div className="summary-card">
              <div className="summary-card__topline">
                <span className="pill pill--neutral">{progression.status}</span>
                <span className="pill pill--accent">{progression.current_stage}</span>
              </div>
              <h3>{progression.current_resource?.title ?? 'No active curriculum resource'}</h3>
              <p>{progression.rationale ?? 'No curriculum progression rationale returned.'}</p>
              <div className="summary-card__grid">
                <div>
                  <span>Progression action</span>
                  <strong>{progression.progression_action}</strong>
                </div>
                <div>
                  <span>Active targets</span>
                  <strong>{progression.active_target_kc_ids.join(', ') || 'none'}</strong>
                </div>
                <div>
                  <span>Next resource</span>
                  <strong>{progression.next_resource?.title ?? 'None queued'}</strong>
                </div>
                <div>
                  <span>Blocked resources</span>
                  <strong>{String(progression.blocked_resource_count)}</strong>
                </div>
              </div>
            </div>
            <MetricList
              title="Resource posture"
              items={[
                { label: 'Total resources', value: String(progression.resource_count) },
                { label: 'Mastered', value: String(progression.mastered_resource_count) },
                { label: 'Ready', value: String(progression.ready_resource_count) },
                { label: 'Active', value: String(progression.active_resource_count) },
                { label: 'Blocked', value: String(progression.blocked_resource_count) },
              ]}
            />
          </div>
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
            eyebrow="Workflow history"
            title="Recent generated, Socratic, and remediation work"
            description="History surfaces let the frontend review prior learner work without manual session-ID lookups."
          />
          <div className="history-grid">
            <HistoryColumn
              title="Generated content"
              emptyLabel="No generation history returned."
              items={generationHistory.map((entry) => ({
                key: entry.generation_id,
                headline: `${entry.content_type} • ${entry.target_stage}`,
                timestamp: formatTimestamp(entry.created_at),
                detail: entry.rationale ?? `${entry.progression_action} on ${entry.active_target_kc_ids.join(', ') || 'no targets'}`,
                buttonLabel: 'Open generation',
                onOpen: () => onSelectView('generation'),
              }))}
            />
            <HistoryColumn
              title="Socratic sessions"
              emptyLabel="No Socratic history returned."
              items={socraticHistory.map((entry) => ({
                key: entry.session_id,
                headline: `${entry.latest_prompt_style ?? 'session'} • ${entry.latest_evidence_strength}`,
                timestamp: formatTimestamp(entry.updated_at),
                detail: entry.rationale ?? `${entry.turn_count} turns on ${entry.target_kc_ids.join(', ') || 'no targets'}`,
                buttonLabel: 'Open Socratic',
                onOpen: () => onSelectView('socratic'),
              }))}
            />
            <HistoryColumn
              title="Remediation sessions"
              emptyLabel="No remediation history returned."
              items={remediationHistory.map((entry) => ({
                key: entry.session_id,
                headline: `${entry.current_phase ?? 'session'} • ${entry.progression_decision}`,
                timestamp: formatTimestamp(entry.updated_at),
                detail:
                  entry.progression_rationale ??
                  `${entry.completed_step_count}/${entry.step_count} steps completed for ${entry.target_kc_id}`,
                buttonLabel: 'Open remediation',
                onOpen: () => onSelectView('remediation'),
              }))}
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
            eyebrow="Contract health"
            title="Resume and history status"
            description="These statuses help us see whether the newer learner contract surfaces are connected."
          />
          <MetricList
            title="Contract snapshot"
            items={[
              { label: 'Active artifact', value: workspace.active_artifact.kind },
              { label: 'Workspace action', value: workspace.continue_action.kind },
              { label: 'Curriculum status', value: progression.status },
              { label: 'Generation history', value: String(generationHistory.length) },
              { label: 'Socratic history', value: String(socraticHistory.length) },
              { label: 'Remediation history', value: String(remediationHistory.length) },
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
              workspace,
              curriculum_progression: progression,
              generation_history: generationHistory,
              socratic_history: socraticHistory,
              remediation_history: remediationHistory,
              summary_strategy: summary.strategy,
              state_profile: summary.state_profile,
            }}
          />
        ) : null}
      </aside>
    </section>
  )
}

function HistoryColumn({
  title,
  items,
  emptyLabel,
}: {
  title: string
  items: Array<{
    key: string
    headline: string
    timestamp: string
    detail: string
    buttonLabel?: string | null
    onOpen?: () => void
  }>
  emptyLabel: string
}) {
  return (
    <div className="metric-list-card">
      <h3>{title}</h3>
      <div className="history-list">
        {items.length === 0 ? <p className="muted">{emptyLabel}</p> : null}
        {items.map((item) => (
          <article key={item.key} className="history-card">
            <div className="history-card__meta">
              <strong>{item.headline}</strong>
              <span>{item.timestamp}</span>
            </div>
            <p>{item.detail}</p>
            {item.buttonLabel && item.onOpen ? (
              <Button type="button" variant="outline" size="sm" onClick={item.onOpen}>
                {item.buttonLabel}
              </Button>
            ) : null}
          </article>
        ))}
      </div>
    </div>
  )
}

function resolveResumeView(workspace: LearnerWorkspace): ViewKey | null {
  const continueActionView = resolveViewKey(workspace.continue_action.kind)
  if (continueActionView) {
    return continueActionView
  }

  return resolveArtifactView(workspace.active_artifact.kind)
}

function resolveViewKey(kind: string | null | undefined): ViewKey | null {
  if (!kind) {
    return null
  }

  if (kind === 'continue_socratic') {
    return 'socratic'
  }
  if (kind === 'advance_remediation') {
    return 'remediation'
  }
  if (kind === 'generate_follow_up') {
    return 'generation'
  }

  return null
}

function resolveArtifactView(kind: string | null | undefined): ViewKey | null {
  if (!kind) {
    return null
  }

  if (kind === 'generated_content') {
    return 'generation'
  }
  if (kind === 'socratic_session') {
    return 'socratic'
  }
  if (kind === 'remediation_session') {
    return 'remediation'
  }

  return null
}
