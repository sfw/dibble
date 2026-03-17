import type { Dispatch, SetStateAction } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import type { SocraticFormState } from '../app/workspace'
import { FormActions, FormField, FormGrid, InlineError } from '../components/form-primitives'
import { FlowSummaryLike, JsonPanel, SectionHeader } from '../components/primitives'
import type { SocraticAssessmentResponse, SocraticAssessmentSession } from '../types'
import { InsightCard } from '../components/primitives'
import { formatContentType, formatContractLabel, formatPercent } from '../lib/formatters'

export function SocraticView(props: {
  form: SocraticFormState
  onFormChange: Dispatch<SetStateAction<SocraticFormState>>
  loading: boolean
  error: string
  response: SocraticAssessmentResponse
  session: SocraticAssessmentSession
  showDebugPanels?: boolean
  onRun: () => void
  onReload: () => void
}) {
  const {
    form,
    onFormChange,
    loading,
    error,
    response,
    session,
    showDebugPanels = false,
    onRun,
    onReload,
  } = props

  return (
    <section className="view-grid">
      <div className="main-column">
        <div className="panel">
          <SectionHeader
            eyebrow="Socratic session summaries"
            title="Run conversational understanding checks"
            description="The backend now returns a canonical session summary so the UI can present follow-up state without reconstructing turns."
          />
          <FormGrid>
            <FormField label="Session ID" htmlFor="socratic-session-id">
              <Input
                id="socratic-session-id"
                value={form.session_id}
                onChange={(event) => onFormChange((current) => ({ ...current, session_id: event.target.value }))}
              />
            </FormField>
            <FormField label="Learning session ID" htmlFor="socratic-learning-session-id">
              <Input
                id="socratic-learning-session-id"
                value={form.learning_session_id}
                onChange={(event) =>
                  onFormChange((current) => ({ ...current, learning_session_id: event.target.value }))
                }
              />
            </FormField>
            <FormField label="Target KCs" htmlFor="socratic-target-kcs">
              <Input
                id="socratic-target-kcs"
                value={form.target_kc_ids}
                onChange={(event) =>
                  onFormChange((current) => ({ ...current, target_kc_ids: event.target.value }))
                }
              />
            </FormField>
            <FormField label="Target LOs" htmlFor="socratic-target-los">
              <Input
                id="socratic-target-los"
                value={form.target_lo_ids}
                onChange={(event) =>
                  onFormChange((current) => ({ ...current, target_lo_ids: event.target.value }))
                }
              />
            </FormField>
            <FormField label="Learner confidence" htmlFor="socratic-learner-confidence">
              <Input
                id="socratic-learner-confidence"
                value={form.learner_confidence}
                onChange={(event) =>
                  onFormChange((current) => ({ ...current, learner_confidence: event.target.value }))
                }
              />
            </FormField>
            <FormField
              label="Curriculum context"
              htmlFor="socratic-curriculum-context"
              className="md:col-span-2"
            >
              <Input
                id="socratic-curriculum-context"
                value={form.curriculum_context}
                onChange={(event) =>
                  onFormChange((current) => ({ ...current, curriculum_context: event.target.value }))
                }
              />
            </FormField>
            <FormField
              label="Learner response"
              htmlFor="socratic-learner-response"
              className="md:col-span-2"
            >
              <Textarea
                id="socratic-learner-response"
                value={form.learner_response}
                onChange={(event) =>
                  onFormChange((current) => ({ ...current, learner_response: event.target.value }))
                }
              />
            </FormField>
          </FormGrid>
          <FormActions className="mt-4">
            <Button onClick={onRun} disabled={loading}>
              {loading ? 'Running...' : 'Run Socratic turn'}
            </Button>
            <Button variant="secondary" onClick={onReload} disabled={loading}>
              Load persisted session
            </Button>
          </FormActions>
          {error ? <InlineError message={error} /> : null}
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
              value={formatContractLabel(response.prompt_style)}
              detail={`Steering: ${formatContractLabel(response.steering_action)}`}
              rationale={response.policy_rationale}
            />
            <InsightCard
              title="Evidence"
              value={formatContractLabel(response.evaluation.evidence_strength)}
              detail={`Score ${formatPercent(response.evaluation.evidence_score)}`}
              rationale={response.evaluation.rationale}
            />
            <InsightCard
              title="Next action"
              value={formatContractLabel(response.evaluation.next_action)}
              detail={`Session status ${formatContractLabel(response.summary.status)}`}
              rationale={response.summary.next_step.rationale ?? 'No rationale returned'}
            />
            <InsightCard
              title="Transfer readiness"
              value={formatContractLabel(response.summary.next_step.target_stage)}
              detail={`Next content ${formatContentType(response.summary.next_step.content_type)}`}
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
              ['Status', formatContractLabel(session.summary.status)],
              ['Turns', String(session.summary.turn_count)],
              ['Latest prompt style', formatContractLabel(session.summary.latest_prompt_style, 'Unknown')],
              ['Latest steering action', formatContractLabel(session.summary.latest_steering_action)],
              ['Latest next action', formatContractLabel(session.summary.latest_next_action)],
            ]}
          />
          <div className="timeline">
            {session.turns.map((turn) => (
              <article key={turn.turn_id} className="timeline__item">
                <div className="timeline__meta">
                  <strong>{formatContractLabel(turn.prompt_style)}</strong>
                  <span>{formatContractLabel(turn.steering_action)}</span>
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
        {showDebugPanels ? <JsonPanel title="Debug Socratic payload" value={response} /> : null}
      </aside>
    </section>
  )
}
