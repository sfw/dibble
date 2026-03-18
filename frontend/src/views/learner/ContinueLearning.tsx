import { useNavigate, useOutletContext } from 'react-router'
import { ArrowRight, BookOpen, ChevronLeft } from 'lucide-react'
import type { LearnerContext } from '../../shells/LearnerShell'
import { PageContainer } from '../../components/shell/PageContainer'
import { Button } from '@/components/ui/button'
import { learnerContentType, learnerContinueAction, learnerStage } from '../../lib/copy'
import type { GeneratedBlock } from '../../types'

export function ContinueLearning() {
  const { workspace, flow, progression, loading } = useOutletContext<LearnerContext>()
  const navigate = useNavigate()

  const artifact = workspace.active_artifact
  const continueAction = workspace.continue_action
  const generated = workspace.generated_content

  // Redirect to the appropriate flow-specific route
  if (continueAction.kind === 'continue_socratic' && flow.socratic_session_id) {
    navigate(`/learn/socratic/${flow.socratic_session_id}`, { replace: true })
    return null
  }
  if (continueAction.kind === 'advance_remediation' && flow.remediation_session_id) {
    navigate(`/learn/remediation/${flow.remediation_session_id}`, { replace: true })
    return null
  }

  const blocks = generated?.response?.blocks ?? []
  const hasContent = blocks.length > 0

  return (
    <PageContainer size="narrow" className="flex flex-col gap-6 py-4">
      {/* Back nav */}
      <button
        onClick={() => navigate('/learn')}
        className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ChevronLeft className="h-4 w-4" />
        Back to home
      </button>

      {/* Lesson header */}
      <header className="flex items-start gap-4">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-blue-100 text-blue-600">
          <BookOpen className="h-5 w-5" />
        </div>
        <div>
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            {learnerContentType(artifact.content_type)}
          </p>
          <h1 className="text-xl font-semibold">
            {progression.current_resource?.title ?? learnerStage(progression.current_stage)}
          </h1>
        </div>
      </header>

      {/* Content canvas */}
      {loading && !hasContent && (
        <div className="flex items-center justify-center py-16 text-muted-foreground">
          Loading your lesson...
        </div>
      )}

      {hasContent && (
        <div className="flex flex-col gap-6">
          {blocks.map((block, index) => (
            <ContentBlock key={index} block={block} />
          ))}
        </div>
      )}

      {!loading && !hasContent && (
        <div className="rounded-xl border bg-white p-8 text-center text-muted-foreground">
          <p>No content available yet. Your next lesson is being prepared.</p>
        </div>
      )}

      {/* Progress rail */}
      <div className="flex items-center gap-3 rounded-lg bg-slate-100 px-4 py-3 text-sm">
        <span className="font-medium">{learnerStage(progression.current_stage)}</span>
        <span className="text-muted-foreground">
          {progression.mastered_resource_count} of {progression.resource_count} complete
        </span>
      </div>

      {/* Next step CTA */}
      {continueAction.kind !== 'idle' && (
        <Button size="lg" className="w-full" disabled={loading}>
          {learnerContinueAction(continueAction.kind)}
          <ArrowRight className="ml-2 h-4 w-4" />
        </Button>
      )}
    </PageContainer>
  )
}

function ContentBlock({ block }: { block: GeneratedBlock }) {
  return (
    <article className="rounded-xl border bg-white p-6 shadow-sm">
      {block.title && (
        <h2 className="mb-3 text-lg font-semibold">{block.title}</h2>
      )}
      <div className="prose prose-slate max-w-none text-base leading-relaxed">
        {block.body.split('\n').map((paragraph, i) => (
          paragraph.trim() ? <p key={i}>{paragraph}</p> : null
        ))}
      </div>
    </article>
  )
}
