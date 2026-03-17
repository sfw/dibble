import type { Dispatch, SetStateAction } from 'react'
import { FlowSummaryLike, JsonPanel, SectionHeader } from '../components/primitives'
import type { SocraticAssessmentResponse, SocraticAssessmentSession } from '../types'
import { InsightCard } from '../components/primitives'
import { formatPercent } from '../lib/formatters'

export interface SocraticFormState {
  session_id: string
  learning_session_id: string
  target_kc_ids: string
  target_lo_ids: string
  curriculum_context: string
  learner_response: string
  learner_confidence: string
}

export function SocraticView(props: {
  form: SocraticFormState
  onFormChange: Dispatch<SetStateAction<SocraticFormState>>
  loading: boolean
  error: string
  response: SocraticAssessmentResponse
  session: SocraticAssessmentSession
  onRun: () => void
  onReload: () => void
}) {
  const { form, onFormChange, loading, error, response, session, onRun, onReload } = props

  return (
    <section className="view-grid">
      <div className="main-column">
        <div className="panel">
          <SectionHeader
            eyebrow="Socratic session summaries"
            title="Run conversational understanding checks"
            description="The backend now returns a canonical session summary so the UI can present follow-up state without reconstructing turns."
          />
          <div className="form-grid">
            <label>
              Session ID
              <input
                value={form.session_id}
                onChange={(event) => onFormChange((current) => ({ ...current, session_id: event.target.value }))}
              />
            </label>
            <label>
              Learning session ID
              <input
                value={form.learning_session_id}
                onChange={(event) =>
                  onFormChange((current) => ({ ...current, learning_session_id: event.target.value }))
                }
              />
            </label>
            <label>
              Target KCs
              <input
                value={form.target_kc_ids}
                onChange={(event) =>
                  onFormChange((current) => ({ ...current, target_kc_ids: event.target.value }))
                }
              />
            </label>
            <label>
              Target LOs
              <input
                value={form.target_lo_ids}
                onChange={(event) =>
                  onFormChange((current) => ({ ...current, target_lo_ids: event.target.value }))
                }
              />
            </label>
            <label>
              Learner confidence
              <input
                value={form.learner_confidence}
                onChange={(event) =>
                  onFormChange((current) => ({ ...current, learner_confidence: event.target.value }))
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
            <label className="form-grid__wide">
              Learner response
              <textarea
                value={form.learner_response}
                onChange={(event) =>
                  onFormChange((current) => ({ ...current, learner_response: event.target.value }))
                }
              />
            </label>
          </div>
          <div className="action-row">
            <button onClick={onRun} disabled={loading}>
              {loading ? 'Running...' : 'Run Socratic turn'}
            </button>
            <button className="button-secondary" onClick={onReload} disabled={loading}>
              Load persisted session
            </button>
          </div>
          {error ? <p className="inline-error">{error}</p> : null}
        </div>

        <div className="panel">
          <SectionHeader
            eyebrow="Live response"
            title="Current turn summary"
            description="Prompt style, steering action, evidence strength, and next action are all directly renderable from one response."
          />
          <div className="explanation-grid">
            <InsightCard
              title="Prompt style"
              value={response.prompt_style}
              detail={`Steering: ${response.steering_action}`}
              rationale={response.policy_rationale}
            />
            <InsightCard
              title="Evidence"
              value={response.evaluation.evidence_strength}
              detail={`Score ${formatPercent(response.evaluation.evidence_score)}`}
              rationale={response.evaluation.rationale}
            />
            <InsightCard
              title="Next action"
              value={response.evaluation.next_action}
              detail={`Session status ${response.summary.status}`}
              rationale={response.summary.next_step.rationale ?? 'No rationale returned'}
            />
            <InsightCard
              title="Transfer readiness"
              value={response.summary.next_step.target_stage}
              detail={`Next content ${response.summary.next_step.content_type ?? 'unknown'}`}
              rationale={`Target KCs: ${response.summary.next_step.target_kc_ids.join(', ') || 'none'}`}
            />
          </div>
          <article className="prompt-card">
            <p className="content-block__kind">Prompt</p>
            <h3>{response.prompt}</h3>
          </article>
        </div>

        <div className="panel">
          <SectionHeader
            eyebrow="Persisted session"
            title="Conversation summary"
            description="The frontend can use the canonical summary and turn list without replaying audit history."
          />
          <FlowSummaryLike
            title="Session summary"
            rows={[
              ['Status', session.summary.status],
              ['Turns', String(session.summary.turn_count)],
              ['Latest prompt style', session.summary.latest_prompt_style ?? 'unknown'],
              ['Latest steering action', session.summary.latest_steering_action],
              ['Latest next action', session.summary.latest_next_action],
            ]}
          />
          <div className="timeline">
            {session.turns.map((turn) => (
              <article key={turn.turn_id} className="timeline__item">
                <div className="timeline__meta">
                  <strong>{turn.prompt_style}</strong>
                  <span>{turn.steering_action}</span>
                </div>
                <p>{turn.prompt}</p>
                {turn.learner_response ? <p className="muted">Learner: {turn.learner_response}</p> : null}
              </article>
            ))}
          </div>
        </div>
      </div>

      <aside className="side-column">
        <div className="panel">
          <SectionHeader
            eyebrow="Generated support"
            title="Response blocks"
            description="The Socratic flow can still return generated content and grounding alongside the turn summary."
          />
          <div className="block-list compact">
            {response.generated_blocks.map((block, index) => (
              <article key={`${block.title}-${index}`} className="content-block">
                <p className="content-block__kind">{block.kind}</p>
                <h3>{block.title}</h3>
                <p>{block.body}</p>
              </article>
            ))}
          </div>
        </div>
        <JsonPanel title="Raw Socratic response" value={response} />
      </aside>
    </section>
  )
}
