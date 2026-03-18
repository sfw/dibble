import { BookOpen, Code, Image, Lightbulb, PenTool, HelpCircle } from 'lucide-react'
import type { GeneratedBlock } from '../../types'

/**
 * Renders a GeneratedBlock according to its `kind`.
 *
 * Block kinds defined in the spec:
 * - exposition / conceptual_explanation: concept introduction
 * - worked_example: step-by-step demo with explanation
 * - practice_problem: interactive skill application
 * - visual_representation / diagram: SVG, Mermaid, or image
 * - scaffolded_steps: step-by-step guide
 * - code_example: syntax-highlighted code
 * - remediation: alternative explanation for struggling learners
 * - enrichment: extension for mastered learners
 *
 * Falls back to prose rendering for unknown kinds.
 */
export function ContentBlock({ block }: { block: GeneratedBlock }) {
  const renderer = blockRenderers[block.kind] ?? blockRenderers['default']
  return renderer(block)
}

// ---------------------------------------------------------------------------
// Block renderers by kind
// ---------------------------------------------------------------------------

const blockRenderers: Record<string, (block: GeneratedBlock) => React.JSX.Element> = {
  // Code blocks
  code_example: (block) => (
    <article className="rounded-xl border bg-slate-900 p-5 shadow-sm">
      {block.title && (
        <div className="mb-3 flex items-center gap-2 text-slate-300">
          <Code className="h-4 w-4" />
          <h2 className="text-sm font-medium">{block.title}</h2>
        </div>
      )}
      <pre className="overflow-x-auto rounded-lg bg-slate-950 p-4 text-sm leading-relaxed text-slate-100">
        <code>{block.body}</code>
      </pre>
    </article>
  ),

  // Diagrams / visuals — render SVG inline if body looks like SVG, otherwise as an image description
  visual_representation: (block) => (
    <article className="rounded-xl border bg-white p-6 shadow-sm">
      {block.title && (
        <div className="mb-3 flex items-center gap-2">
          <Image className="h-4 w-4 text-muted-foreground" />
          <h2 className="text-lg font-semibold">{block.title}</h2>
        </div>
      )}
      {block.body.trim().startsWith('<svg') ? (
        <div
          className="flex justify-center [&_svg]:max-w-full [&_svg]:h-auto"
          dangerouslySetInnerHTML={{ __html: block.body }}
        />
      ) : (
        <div className="rounded-lg bg-slate-50 p-4 text-sm leading-relaxed">
          {renderParagraphs(block.body)}
        </div>
      )}
    </article>
  ),

  diagram: (block) => blockRenderers['visual_representation'](block),

  // Worked examples — step-by-step with distinct styling
  worked_example: (block) => (
    <article className="rounded-xl border-l-4 border-l-blue-400 bg-white p-6 shadow-sm">
      {block.title && (
        <div className="mb-3 flex items-center gap-2">
          <PenTool className="h-4 w-4 text-blue-500" />
          <h2 className="text-lg font-semibold">{block.title}</h2>
        </div>
      )}
      <div className="text-base leading-relaxed">{renderParagraphs(block.body)}</div>
    </article>
  ),

  // Practice problems — interactive feel
  practice_problem: (block) => (
    <article className="rounded-xl border-l-4 border-l-emerald-400 bg-white p-6 shadow-sm">
      {block.title && (
        <div className="mb-3 flex items-center gap-2">
          <HelpCircle className="h-4 w-4 text-emerald-500" />
          <h2 className="text-lg font-semibold">{block.title}</h2>
        </div>
      )}
      <div className="text-base leading-relaxed">{renderParagraphs(block.body)}</div>
    </article>
  ),

  // Scaffolded steps
  scaffolded_steps: (block) => (
    <article className="rounded-xl border bg-white p-6 shadow-sm">
      {block.title && (
        <div className="mb-3 flex items-center gap-2">
          <BookOpen className="h-4 w-4 text-muted-foreground" />
          <h2 className="text-lg font-semibold">{block.title}</h2>
        </div>
      )}
      <ol className="list-decimal space-y-2 pl-6 text-base leading-relaxed">
        {block.body
          .split('\n')
          .filter((line) => line.trim())
          .map((step, i) => (
            <li key={i}>{step.replace(/^\d+[.)]\s*/, '')}</li>
          ))}
      </ol>
    </article>
  ),

  // Remediation blocks — warm, supportive styling
  remediation: (block) => (
    <article className="rounded-xl border-l-4 border-l-amber-400 bg-amber-50 p-6 shadow-sm">
      {block.title && (
        <div className="mb-3 flex items-center gap-2">
          <Lightbulb className="h-4 w-4 text-amber-600" />
          <h2 className="text-lg font-semibold text-amber-900">{block.title}</h2>
        </div>
      )}
      <div className="text-base leading-relaxed text-amber-900">{renderParagraphs(block.body)}</div>
    </article>
  ),

  // Conceptual explanation
  conceptual_explanation: (block) => (
    <article className="rounded-xl border bg-white p-6 shadow-sm">
      {block.title && <h2 className="mb-3 text-lg font-semibold">{block.title}</h2>}
      <div className="text-base leading-relaxed">{renderParagraphs(block.body)}</div>
    </article>
  ),

  exposition: (block) => blockRenderers['conceptual_explanation'](block),

  // Default / unknown kind — clean prose
  default: (block) => (
    <article className="rounded-xl border bg-white p-6 shadow-sm">
      {block.title && <h2 className="mb-3 text-lg font-semibold">{block.title}</h2>}
      <div className="prose prose-slate max-w-none text-base leading-relaxed">
        {renderParagraphs(block.body)}
      </div>
    </article>
  ),
}

function renderParagraphs(text: string) {
  return text
    .split('\n')
    .filter((p) => p.trim())
    .map((paragraph, i) => <p key={i} className="mb-2 last:mb-0">{paragraph}</p>)
}
