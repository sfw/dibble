import type { Dispatch, SetStateAction } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import type { RemediationFormState } from '../app/workspace'
import { FormActions, FormField, FormGrid, InlineError } from '../components/form-primitives'
import { FlowSummaryLike, JsonPanel, SectionHeader } from '../components/primitives'
import type { GeneratedContent, RemediationWorkflowAdvanceResponse, RemediationWorkflowSession } from '../types'

export function RemediationView(props: {
  form: RemediationFormState
  onFormChange: Dispatch<SetStateAction<RemediationFormState>>
  loading: boolean
  error: string
  content: GeneratedContent
  session: RemediationWorkflowSession
  advance: RemediationWorkflowAdvanceResponse | null
  advancePrompt: string
  showDebugPanels?: boolean
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
    showDebugPanels = false,
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
          <FormGrid>
            <FormField label="Target KC" htmlFor="remediation-target-kc">
              <Input
                id="remediation-target-kc"
                value={form.target_kc_id}
                onChange={(event) => onFormChange((current) => ({ ...current, target_kc_id: event.target.value }))}
              />
            </FormField>
            <FormField
              label="Misconception description"
              htmlFor="remediation-misconception-description"
              className="md:col-span-2"
            >
              <Textarea
                id="remediation-misconception-description"
                value={form.misconception_description}
                onChange={(event) =>
                  onFormChange((current) => ({
                    ...current,
                    misconception_description: event.target.value,
                  }))
                }
              />
            </FormField>
            <FormField
              label="Learner prompt"
              htmlFor="remediation-learner-prompt"
              className="md:col-span-2"
            >
              <Textarea
                id="remediation-learner-prompt"
                value={form.learner_prompt}
                onChange={(event) =>
                  onFormChange((current) => ({ ...current, learner_prompt: event.target.value }))
                }
              />
            </FormField>
            <FormField
              label="Curriculum context"
              htmlFor="remediation-curriculum-context"
              className="md:col-span-2"
            >
              <Input
                id="remediation-curriculum-context"
                value={form.curriculum_context}
                onChange={(event) =>
                  onFormChange((current) => ({ ...current, curriculum_context: event.target.value }))
                }
              />
            </FormField>
          </FormGrid>
          <FormActions className="mt-4">
            <Button onClick={onTrigger} disabled={loading}>
              {loading ? 'Starting...' : 'Trigger remediation'}
            </Button>
            <Button variant="secondary" onClick={onReload} disabled={loading}>
              Reload session
            </Button>
          </FormActions>
          {error ? <InlineError message={error} /> : null}
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
          <FormField label="Advance prompt" htmlFor="remediation-advance-prompt">
            <Textarea
              id="remediation-advance-prompt"
              value={advancePrompt}
              onChange={(event) => onAdvancePromptChange(event.target.value)}
            />
          </FormField>
          <FormActions className="mt-4">
            <Button onClick={onAdvance} disabled={loading}>
              {loading ? 'Advancing...' : 'Advance remediation session'}
            </Button>
          </FormActions>
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
        {showDebugPanels ? <JsonPanel title="Debug remediation payload" value={session} /> : null}
      </aside>
    </section>
  )
}
