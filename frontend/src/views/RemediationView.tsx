import type { Dispatch, SetStateAction } from 'react'
import { FlowSummaryLike, JsonPanel, SectionHeader } from '../components/primitives'
import type { GeneratedContent, RemediationWorkflowAdvanceResponse, RemediationWorkflowSession } from '../types'

export interface RemediationFormState {
  target_kc_id: string
  misconception_description: string
  learner_prompt: string
  curriculum_context: string
}

export function RemediationView(props: {
  form: RemediationFormState
  onFormChange: Dispatch<SetStateAction<RemediationFormState>>
  loading: boolean
  error: string
  content: GeneratedContent
  session: RemediationWorkflowSession
  advance: RemediationWorkflowAdvanceResponse | null
  advancePrompt: string
  onAdvancePromptChange: (value: string) => void
  onTrigger: () => void
  onReload: () => void
  onAdvance: () => void
}) {
  const {
    form,
    onFormChange,
    loading,
    error,
    content,
    session,
    advance,
    advancePrompt,
    onAdvancePromptChange,
    onTrigger,
    onReload,
    onAdvance,
  } = props

  return (
    <section className="view-grid">
      <div className="main-column">
        <div className="panel">
          <SectionHeader
            eyebrow="Remediation workflow summaries"
            title="Run session-backed repair arcs"
            description="This screen trusts the remediation session summary rather than reconstructing state from step arrays or audit logs."
          />
          <div className="form-grid">
            <label>
              Target KC
              <input
                value={form.target_kc_id}
                onChange={(event) => onFormChange((current) => ({ ...current, target_kc_id: event.target.value }))}
              />
            </label>
            <label className="form-grid__wide">
              Misconception description
              <textarea
                value={form.misconception_description}
                onChange={(event) =>
                  onFormChange((current) => ({
                    ...current,
                    misconception_description: event.target.value,
                  }))
                }
              />
            </label>
            <label className="form-grid__wide">
              Learner prompt
              <textarea
                value={form.learner_prompt}
                onChange={(event) =>
                  onFormChange((current) => ({ ...current, learner_prompt: event.target.value }))
                }
              />
            </label>
            <label className="form-grid__wide">
              Curriculum context
              <input
                value={form.curriculum_context}
                onChange={(event) =>
                  onFormChange((current) => ({ ...current, curriculum_context: event.target.value }))
                }
              />
            </label>
          </div>
          <div className="action-row">
            <button onClick={onTrigger} disabled={loading}>
              {loading ? 'Starting...' : 'Trigger remediation'}
            </button>
            <button className="button-secondary" onClick={onReload} disabled={loading}>
              Reload session
            </button>
          </div>
          {error ? <p className="inline-error">{error}</p> : null}
        </div>

        <div className="panel">
          <SectionHeader
            eyebrow="Session summary"
            title="Current repair state"
            description="This is the canonical workflow state the frontend should use for held, in-progress, and complete remediation arcs."
          />
          <FlowSummaryLike
            title="Remediation summary"
            rows={[
              ['Status', session.summary.status],
              ['Current phase', session.summary.current_phase ?? 'unknown'],
              ['Current step', session.summary.current_step_title ?? 'unknown'],
              ['Next phase', session.summary.next_phase ?? 'unknown'],
              ['Progression decision', session.summary.progression_decision],
            ]}
          />
          <p className="lead-paragraph">{session.summary.progression_rationale ?? session.rationale}</p>
          <div className="timeline">
            {session.steps.map((step) => (
              <article key={`${step.phase}-${step.title}`} className="timeline__item">
                <div className="timeline__meta">
                  <strong>{step.phase}</strong>
                  <span>{step.status}</span>
                </div>
                <h3>{step.title}</h3>
                <p>{step.guidance}</p>
                <p className="muted">
                  Targets: {step.target_kc_ids.join(', ') || 'none'} • {step.recommended_content_type}
                </p>
              </article>
            ))}
          </div>
        </div>

        <div className="panel">
          <SectionHeader
            eyebrow="Advance workflow"
            title="Continue the repair arc"
            description="Advancement stays backend-owned so the UI can remain a renderer of phase transitions rather than the owner of progression rules."
          />
          <label className="form-grid__wide">
            Advance prompt
            <textarea value={advancePrompt} onChange={(event) => onAdvancePromptChange(event.target.value)} />
          </label>
          <div className="action-row">
            <button onClick={onAdvance} disabled={loading}>
              {loading ? 'Advancing...' : 'Advance remediation session'}
            </button>
          </div>
          {advance ? (
            <p className="muted">
              Last executed phase: <strong>{advance.executed_phase}</strong>
            </p>
          ) : null}
        </div>
      </div>

      <aside className="side-column">
        <div className="panel">
          <SectionHeader
            eyebrow="Current content"
            title="Latest generated remediation artifact"
            description="The workflow session and delivered content can be reviewed side by side."
          />
          <div className="block-list compact">
            {content.response.blocks.map((block, index) => (
              <article key={`${block.title}-${index}`} className="content-block">
                <p className="content-block__kind">{block.kind}</p>
                <h3>{block.title}</h3>
                <p>{block.body}</p>
              </article>
            ))}
          </div>
        </div>
        <JsonPanel title="Raw remediation session" value={session} />
      </aside>
    </section>
  )
}
