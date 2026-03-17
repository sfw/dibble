import type { Dispatch, SetStateAction } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import type { GenerationFormState } from '../app/workspace'
import { FormActions, FormField, FormGrid, InlineError } from '../components/form-primitives'
import { EmptyState, FlowSummaryCard, JsonPanel, MetricList, SectionHeader } from '../components/primitives'
import type { GeneratedBlock, GeneratedContent, GenerationStreamEvent } from '../types'
import { formatContractLabel, formatPercent } from '../lib/formatters'

export function GenerationView(props: {
  form: GenerationFormState
  onFormChange: Dispatch<SetStateAction<GenerationFormState>>
  loading: boolean
  error: string
  result: GeneratedContent
  streaming: boolean
  streamEvents: GenerationStreamEvent[]
  streamedBlocks: GeneratedBlock[]
  showDebugPanels?: boolean
  onGenerate: () => void
  onStream: () => void
}) {
  const {
    form,
    onFormChange,
    loading,
    error,
    result,
    streaming,
    streamEvents,
    streamedBlocks,
    showDebugPanels = false,
    onGenerate,
    onStream,
  } =
    props

  const blocksToRender = streamedBlocks.length > 0 ? streamedBlocks : result.response.blocks

  return (
    <section className="view-grid">
      <div className="main-column">
        <div className="panel">
          <SectionHeader
            eyebrow="Generated content workflow"
            title="Create grounded lesson moves"
            description="This screen uses the backend’s generation and workflow summary contracts, including route decision, grounding, moderation, and next-step metadata."
          />
          <FormGrid>
            <FormField label="Learning session ID" htmlFor="generation-learning-session-id">
              <Input
                id="generation-learning-session-id"
                value={form.learning_session_id}
                onChange={(event) =>
                  onFormChange((current) => ({ ...current, learning_session_id: event.target.value }))
                }
              />
            </FormField>
            <FormField label="Intent" htmlFor="generation-intent">
              <Select
                value={form.intent}
                onValueChange={(value) => onFormChange((current) => ({ ...current, intent: value }))}
              >
                <SelectTrigger id="generation-intent" aria-label="Intent">
                  <SelectValue placeholder="Choose intent" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="explanation">explanation</SelectItem>
                  <SelectItem value="practice">practice</SelectItem>
                  <SelectItem value="remediation">remediation</SelectItem>
                  <SelectItem value="assessment">assessment</SelectItem>
                </SelectContent>
              </Select>
            </FormField>
            <FormField label="Requested content type" htmlFor="generation-content-type">
              <Select
                value={form.requested_content_type}
                onValueChange={(value) =>
                  onFormChange((current) => ({
                    ...current,
                    requested_content_type: value,
                  }))
                }
              >
                <SelectTrigger id="generation-content-type" aria-label="Requested content type">
                  <SelectValue placeholder="Choose content type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="micro_explanation">micro_explanation</SelectItem>
                  <SelectItem value="worked_example">worked_example</SelectItem>
                  <SelectItem value="practice_problem">practice_problem</SelectItem>
                  <SelectItem value="remedial_micro_module">remedial_micro_module</SelectItem>
                  <SelectItem value="assessment_probe">assessment_probe</SelectItem>
                </SelectContent>
              </Select>
            </FormField>
            <FormField label="Target KCs" htmlFor="generation-target-kcs">
              <Input
                id="generation-target-kcs"
                value={form.target_kc_ids}
                onChange={(event) =>
                  onFormChange((current) => ({ ...current, target_kc_ids: event.target.value }))
                }
              />
            </FormField>
            <FormField label="Target LOs" htmlFor="generation-target-los">
              <Input
                id="generation-target-los"
                value={form.target_lo_ids}
                onChange={(event) =>
                  onFormChange((current) => ({ ...current, target_lo_ids: event.target.value }))
                }
              />
            </FormField>
            <FormField
              label="Curriculum context"
              htmlFor="generation-curriculum-context"
              className="md:col-span-2"
            >
              <Input
                id="generation-curriculum-context"
                value={form.curriculum_context}
                onChange={(event) =>
                  onFormChange((current) => ({
                    ...current,
                    curriculum_context: event.target.value,
                  }))
                }
              />
            </FormField>
            <FormField
              label="Learner / teacher prompt"
              htmlFor="generation-learner-prompt"
              className="md:col-span-2"
            >
              <Textarea
                id="generation-learner-prompt"
                value={form.learner_prompt}
                onChange={(event) =>
                  onFormChange((current) => ({ ...current, learner_prompt: event.target.value }))
                }
              />
            </FormField>
          </FormGrid>
          <FormActions className="mt-4">
            <Button onClick={onGenerate} disabled={loading || streaming}>
              {loading ? 'Generating...' : 'Generate response'}
            </Button>
            <Button variant="secondary" onClick={onStream} disabled={loading || streaming}>
              {streaming ? 'Streaming...' : 'Stream via SSE'}
            </Button>
          </FormActions>
          {error ? <InlineError message={error} /> : null}
        </div>

        <div className="panel">
          <SectionHeader
            eyebrow="Workflow summary"
            title="Response-local contract"
            description="This is the compact shape the frontend can trust without unpacking internal request context."
          />
          {result.workflow_summary ? <FlowSummaryCard summary={result.workflow_summary} /> : null}
          <div className="two-column-grid">
            <MetricList
              title="Route decision"
              items={[
                { label: 'Intervention', value: formatContractLabel(result.response.route.intervention_type) },
                { label: 'Delivery mode', value: formatContractLabel(result.response.route.delivery_mode) },
                { label: 'Scaffolding', value: formatContractLabel(result.response.route.scaffolding_level) },
                {
                  label: 'Latency',
                  value: `${result.quality.generation_latency_ms} ms`,
                },
                {
                  label: 'Cache hit',
                  value: String(result.quality.cache_hit),
                },
              ]}
            />
            <MetricList
              title="Safety and quality"
              items={[
                { label: 'Validation passed', value: String(result.quality.validation_passed) },
                { label: 'Quality score', value: formatPercent(result.quality.quality_score) },
                { label: 'Moderation', value: formatContractLabel(result.quality.moderation.status) },
                {
                  label: 'Template',
                  value:
                    `${result.quality.prompt_template_name ?? 'unknown'} / ${result.quality.prompt_template_variant ?? 'n/a'}`,
                },
                {
                  label: 'Grounding count',
                  value: String(result.response.grounding.length),
                },
              ]}
            />
          </div>
          <div className="reason-list">
            {result.response.route.reasons.map((reason) => (
              <div key={reason} className="reason-pill">
                {formatContractLabel(reason)}
              </div>
            ))}
          </div>
        </div>

        <div className="panel">
          <SectionHeader
            eyebrow="Generated blocks"
            title="Delivered content"
            description="Blocks are rendered as extensible cards so they can later support richer artifact kinds."
          />
          <div className="block-list">
            {blocksToRender.map((block, index) => (
              <article key={`${block.title}-${index}`} className="content-block">
                <p className="content-block__kind">{formatContractLabel(block.kind)}</p>
                <h3>{block.title}</h3>
                <p>{block.body}</p>
              </article>
            ))}
          </div>
        </div>
      </div>

      <aside className="side-column">
        <div className="panel">
          <SectionHeader
            eyebrow="Grounding"
            title="Curriculum support"
            description="The revised system depends on grounded, inspectable generation."
          />
          <div className="stack">
            {result.response.grounding.map((grounding) => (
              <article key={grounding.resource_id} className="grounding-card">
                <div className="grounding-card__header">
                  <strong>{grounding.title}</strong>
                  <span>{formatPercent(grounding.score)}</span>
                </div>
                <p>{grounding.excerpt ?? 'No excerpt provided.'}</p>
                <p className="muted">
                  {grounding.subject ?? 'unknown subject'} • grade {grounding.grade_level}
                </p>
              </article>
            ))}
          </div>
        </div>
        <div className="panel">
          <SectionHeader
            eyebrow="Streaming trace"
            title="SSE events"
            description="Useful for perceived responsiveness and debugging workflow progression during streaming generation."
          />
          <div className="stream-log">
            {streamEvents.length === 0 ? (
              <EmptyState
                title="No stream events yet"
                description="Run the SSE path to inspect progressive delivery and workflow progression events."
              />
            ) : (
              streamEvents.map((event, index) => (
                <div key={`${event.event}-${index}`} className="stream-log__item">
                  <strong>{formatContractLabel(event.event)}</strong>
                  <span>
                    {event.chunk?.title ??
                      event.moderation?.status ??
                      event.response?.generation_id ??
                      'Event received'}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
        {showDebugPanels ? <JsonPanel title="Debug generation payload" value={result} /> : null}
      </aside>
    </section>
  )
}
