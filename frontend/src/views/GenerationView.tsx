import type { Dispatch, SetStateAction } from 'react'
import { FlowSummaryCard, JsonPanel, MetricList, SectionHeader } from '../components/primitives'
import type { GeneratedBlock, GeneratedContent, GenerationStreamEvent } from '../types'
import { formatPercent } from '../lib/formatters'

export interface GenerationFormState {
  learning_session_id: string
  target_kc_ids: string
  target_lo_ids: string
  intent: string
  requested_content_type: string
  learner_prompt: string
  curriculum_context: string
}

export function GenerationView(props: {
  form: GenerationFormState
  onFormChange: Dispatch<SetStateAction<GenerationFormState>>
  loading: boolean
  error: string
  result: GeneratedContent
  streaming: boolean
  streamEvents: GenerationStreamEvent[]
  streamedBlocks: GeneratedBlock[]
  onGenerate: () => void
  onStream: () => void
}) {
  const { form, onFormChange, loading, error, result, streaming, streamEvents, streamedBlocks, onGenerate, onStream } =
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
          <div className="form-grid">
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
              Intent
              <select
                value={form.intent}
                onChange={(event) => onFormChange((current) => ({ ...current, intent: event.target.value }))}
              >
                <option value="explanation">explanation</option>
                <option value="practice">practice</option>
                <option value="remediation">remediation</option>
                <option value="assessment">assessment</option>
              </select>
            </label>
            <label>
              Requested content type
              <select
                value={form.requested_content_type}
                onChange={(event) =>
                  onFormChange((current) => ({
                    ...current,
                    requested_content_type: event.target.value,
                  }))
                }
              >
                <option value="micro_explanation">micro_explanation</option>
                <option value="worked_example">worked_example</option>
                <option value="practice_problem">practice_problem</option>
                <option value="remedial_micro_module">remedial_micro_module</option>
                <option value="assessment_probe">assessment_probe</option>
              </select>
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
            <label className="form-grid__wide">
              Curriculum context
              <input
                value={form.curriculum_context}
                onChange={(event) =>
                  onFormChange((current) => ({
                    ...current,
                    curriculum_context: event.target.value,
                  }))
                }
              />
            </label>
            <label className="form-grid__wide">
              Learner / teacher prompt
              <textarea
                value={form.learner_prompt}
                onChange={(event) =>
                  onFormChange((current) => ({ ...current, learner_prompt: event.target.value }))
                }
              />
            </label>
          </div>
          <div className="action-row">
            <button onClick={onGenerate} disabled={loading || streaming}>
              {loading ? 'Generating...' : 'Generate response'}
            </button>
            <button className="button-secondary" onClick={onStream} disabled={loading || streaming}>
              {streaming ? 'Streaming...' : 'Stream via SSE'}
            </button>
          </div>
          {error ? <p className="inline-error">{error}</p> : null}
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
                { label: 'Intervention', value: result.response.route.intervention_type },
                { label: 'Delivery mode', value: result.response.route.delivery_mode },
                { label: 'Scaffolding', value: result.response.route.scaffolding_level },
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
                { label: 'Moderation', value: result.quality.moderation.status },
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
                {reason}
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
                <p className="content-block__kind">{block.kind}</p>
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
              <p className="muted">No stream events yet.</p>
            ) : (
              streamEvents.map((event, index) => (
                <div key={`${event.event}-${index}`} className="stream-log__item">
                  <strong>{event.event}</strong>
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
        <JsonPanel title="Raw generation payload" value={result} />
      </aside>
    </section>
  )
}
