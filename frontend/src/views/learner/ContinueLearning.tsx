import { useCallback, useState } from 'react'
import { useNavigate, useOutletContext } from 'react-router'
import { ArrowRight, BookOpen, ChevronLeft, Loader2 } from 'lucide-react'
import type { LearnerContext } from '../../shells/LearnerShell'
import { PageContainer } from '../../components/shell/PageContainer'
import { ErrorBanner } from '@/components/ui/error-banner'
import { AffectiveSupport } from '../../components/content/AffectiveSupport'
import { StreamingContent } from '../../components/content/StreamingContent'
import { Button } from '@/components/ui/button'
import { learnerContentType, learnerContinueAction, learnerStage } from '../../lib/copy'
import { useGenerationWorkspace } from '../../hooks/useGenerationWorkspace'
import type { DataSource } from '../../app/workspace'

export function ContinueLearning() {
  const { config, workspace, flow, progression, loading } = useOutletContext<LearnerContext>()
  const navigate = useNavigate()

  const [, setDataSource] = useState<DataSource>('demo')
  const handleDataSourceChange = useCallback((source: DataSource) => setDataSource(source), [])

  const generation = useGenerationWorkspace({
    config,
    learnerId: workspace.student_id,
    workspace,
    onDataSourceChange: handleDataSourceChange,
  })

  const artifact = workspace.active_artifact
  const continueAction = workspace.continue_action

  // Redirect to the appropriate flow-specific route
  if (continueAction.kind === 'continue_socratic' && flow.socratic_session_id) {
    navigate(`/learn/socratic/${flow.socratic_session_id}`, { replace: true })
    return null
  }
  if (continueAction.kind === 'advance_remediation' && flow.remediation_session_id) {
    navigate(`/learn/remediation/${flow.remediation_session_id}`, { replace: true })
    return null
  }

  // Use streaming blocks if available, otherwise static blocks
  const staticBlocks = generation.result?.response?.blocks ?? []
  const isStreaming = generation.streaming
  const displayBlocks = isStreaming ? generation.streamedBlocks : staticBlocks
  const hasContent = displayBlocks.length > 0

  function handleContinue() {
    void generation.handleStream()
  }

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
            {progression.current_resource?.title ?? learnerStage(progression.current_stage, progression.stage_display_label)}
          </h1>
        </div>
      </header>

      {/* Affective state support */}
      <AffectiveSupport message={workspace.affective_support} />

      {/* Content canvas — streaming-aware with block type rendering */}
      {loading && !hasContent && !isStreaming && (
        <div className="flex flex-col items-center justify-center gap-3 py-16 text-muted-foreground">
          <Loader2 className="h-6 w-6 animate-spin" />
          <p>Loading your lesson...</p>
        </div>
      )}

      {(hasContent || isStreaming) && (
        <StreamingContent blocks={displayBlocks} streaming={isStreaming} />
      )}

      <ErrorBanner message={generation.error} />

      {!loading && !hasContent && !isStreaming && !generation.error && (
        <div className="rounded-xl border bg-white p-8 text-center text-muted-foreground">
          <p>No content available yet. Your next lesson is being prepared.</p>
        </div>
      )}

      {/* Progress rail */}
      <div className="flex items-center gap-3 rounded-lg bg-slate-100 px-4 py-3 text-sm">
        <span className="font-medium">{learnerStage(progression.current_stage, progression.stage_display_label)}</span>
        <span className="text-muted-foreground">
          {progression.mastered_resource_count} of {progression.resource_count} complete
        </span>
      </div>

      {/* Next step CTA */}
      {continueAction.kind !== 'idle' && (
        <Button
          size="lg"
          className="w-full"
          disabled={loading || isStreaming}
          onClick={handleContinue}
        >
          {isStreaming ? 'Generating...' : learnerContinueAction(continueAction.kind, continueAction.display_label)}
          <ArrowRight className="ml-2 h-4 w-4" />
        </Button>
      )}
    </PageContainer>
  )
}
