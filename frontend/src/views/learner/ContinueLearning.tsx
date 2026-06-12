import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useOutletContext } from 'react-router'
import { ArrowRight, BookOpen, ChevronLeft, Loader2, Send } from 'lucide-react'
import type { LearnerContext } from '../../shells/LearnerShell'
import { PageContainer } from '../../components/shell/PageContainer'
import { ErrorBanner } from '@/components/ui/error-banner'
import { AffectiveSupport } from '../../components/content/AffectiveSupport'
import { StreamingContent } from '../../components/content/StreamingContent'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { learnerContentType, learnerContinueAction, learnerStage } from '../../lib/copy'
import { useGenerationWorkspace } from '../../hooks/useGenerationWorkspace'
import type { DataSource } from '../../app/workspace'
import { recordLearnerObservation } from '../../api'
import { DefectReportButton } from '../../components/app/DefectReportButton'
import { parseList } from '../../lib/forms'
import type { PracticeInteractionSubmission } from '../../components/content/InteractivePracticeBlock'

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

  const [learnerResponse, setLearnerResponse] = useState('')
  const [interactionError, setInteractionError] = useState('')
  const [submittingInteraction, setSubmittingInteraction] = useState(false)

  // Auto-trigger content generation when arriving with no existing content
  const autoTriggered = useRef(false)
  const { result, streaming, error: genError, handleStream } = generation
  useEffect(() => {
    if (!autoTriggered.current && !result && !streaming && !genError && !loading) {
      autoTriggered.current = true
      void handleStream()
    }
  }, [result, streaming, genError, loading, handleStream])

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
  const interactivePracticeBlock = !isStreaming
    ? (displayBlocks.find(
        (block) => block.kind === 'practice_problem' && block.interaction?.type === 'multiple_choice',
      ) ?? null)
    : null
  const hasPracticePrompt = !isStreaming && hasContent && displayBlocks.some(
    (b) => b.kind === 'practice_problem' && b.interaction?.type !== 'multiple_choice',
  )

  const masteryPercent = Math.round(
    (progression.mastered_outcome_count / Math.max(progression.outcome_count, 1)) * 100,
  )
  const defectGenerationId =
    generation.result?.generation_id ?? workspace.generated_content?.generation_id ?? null

  function handleContinue() {
    if (hasPracticePrompt && learnerResponse.trim()) {
      const nextPrompt = learnerResponse.trim()
      void generation.handleStream({ learner_prompt: nextPrompt })
      setLearnerResponse('')
      return
    }
    void generation.handleStream()
  }

  async function handlePracticeSubmit(submission: PracticeInteractionSubmission) {
    const generationId = generation.result?.generation_id ?? workspace.generated_content?.generation_id ?? null
    const requestContextSession =
      typeof generation.result?.request_context?.learning_session_id === 'string'
        ? generation.result.request_context.learning_session_id
        : null
    const learningSessionId =
      requestContextSession ??
      generation.form.learning_session_id ??
      workspace.active_artifact.learning_session_id ??
      flow.learning_session_id

    setSubmittingInteraction(true)
    setInteractionError('')
    try {
      await recordLearnerObservation(config, workspace.student_id, {
        response_time_ms: submission.responseTimeMs,
        hints_used: submission.hintsUsed,
        error_count: submission.isCorrect ? 0 : 1,
        completed: true,
        confidence: submission.isCorrect ? 0.8 : 0.4,
        task_type: 'practice',
        support_level: 'medium',
        learning_session_id: learningSessionId ?? null,
        generation_id: generationId,
        observed_content_type: generation.result?.content_type ?? workspace.active_artifact.content_type ?? 'practice_problem',
        target_kc_ids: parseList(generation.form.target_kc_ids),
        target_lo_ids: parseList(generation.form.target_lo_ids),
        response_text: submission.responseText || null,
        interaction_events: [
          {
            event_type: 'multiple_choice_selected',
            block_id: submission.blockId,
            selected_option_id: submission.selectedOptionId,
            correct: submission.isCorrect,
          },
          {
            event_type: 'reasoning_submitted',
            block_id: submission.blockId,
            selected_option_id: submission.selectedOptionId,
            correct: submission.isCorrect,
            response_text: submission.responseText || null,
          },
        ],
      })

      const learnerPrompt = [
        `The learner selected option ${submission.selectedOptionId}.`,
        submission.responseText ? `Reasoning: ${submission.responseText}` : null,
      ]
        .filter(Boolean)
        .join(' ')

      await generation.handleStream({ learner_prompt: learnerPrompt })
    } catch (caughtError) {
      setInteractionError(caughtError instanceof Error ? caughtError.message : 'Unable to record learner interaction.')
    } finally {
      setSubmittingInteraction(false)
    }
  }

  return (
    <PageContainer size="narrow" className="flex flex-col gap-6 py-4">
      {/* Back nav */}
      <button
        onClick={() => navigate('/learn')}
        className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        <ChevronLeft className="h-4 w-4" />
        Back to home
      </button>

      {/* Lesson header */}
      <header className="flex items-start gap-4 animate-fade-in-up">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-blue-100 text-blue-600">
          <BookOpen className="h-5 w-5" />
        </div>
        <div>
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            {learnerContentType(artifact.content_type)}
          </p>
          <h1 className="text-xl font-semibold">
            {progression.current_outcome?.title ?? learnerStage(progression.current_stage, progression.stage_display_label)}
          </h1>
        </div>
      </header>

      {/* Affective state support */}
      <AffectiveSupport message={workspace.affective_support} />

      {/* Content canvas — streaming-aware with block type rendering */}
      {loading && !hasContent && !isStreaming && (
        <div className="flex flex-col items-center justify-center gap-3 py-16 text-muted-foreground animate-fade-in">
          <Loader2 className="h-6 w-6 animate-spin text-blue-500" />
          <p className="font-medium">Loading your lesson...</p>
        </div>
      )}

      {(hasContent || isStreaming) && (
        <>
          <StreamingContent
            blocks={displayBlocks}
            streaming={isStreaming}
            onPracticeSubmit={interactivePracticeBlock ? handlePracticeSubmit : undefined}
          />
          {!isStreaming && defectGenerationId && (
            <DefectReportButton
              config={config}
              studentId={workspace.student_id}
              generationId={defectGenerationId}
              learningSessionId={flow.learning_session_id}
            />
          )}
        </>
      )}

      {(generation.error || interactionError) && (
        <div className="flex flex-col gap-2">
          <ErrorBanner message={generation.error || interactionError} />
          <Button
            variant="outline"
            size="sm"
            onClick={handleContinue}
            disabled={loading || isStreaming || submittingInteraction}
            className="self-start"
          >
            Try again
          </Button>
        </div>
      )}

      {!loading && !hasContent && !isStreaming && !generation.error && (
        <div className="rounded-xl border bg-white p-8 text-center text-muted-foreground animate-scale-in">
          <p>No content available yet. Your next lesson is being prepared.</p>
        </div>
      )}

      {/* Interactive response area for practice problems */}
      {hasPracticePrompt && (
        <div className="rounded-xl border-l-4 border-l-emerald-400 bg-white p-6 shadow-sm animate-fade-in-up flex flex-col gap-3">
          <p className="text-sm font-medium text-emerald-700">Write your answer</p>
          <Textarea
            value={learnerResponse}
            onChange={(e) => setLearnerResponse(e.target.value)}
            placeholder="Type your response here..."
            className="min-h-[100px] resize-none transition-shadow focus:shadow-sm"
          />
          <Button
            onClick={handleContinue}
            disabled={loading || isStreaming || submittingInteraction || !learnerResponse.trim()}
            className="w-full transition-all"
            size="lg"
          >
            <Send className="mr-2 h-4 w-4" />
            Submit your answer
          </Button>
        </div>
      )}

      {/* Progress rail — animated bar */}
      <div className="rounded-lg bg-slate-100 px-4 py-3 animate-fade-in-up" style={{ animationDelay: '100ms' }}>
        <div className="flex items-baseline justify-between text-sm mb-2">
          <span className="font-medium">{learnerStage(progression.current_stage, progression.stage_display_label)}</span>
          <span className="text-muted-foreground">
            {progression.mastered_outcome_count} of {progression.outcome_count} complete
          </span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-slate-200">
          <div
            className="h-full rounded-full bg-blue-500 animate-progress-fill transition-all"
            style={{ width: `${masteryPercent}%` }}
          />
        </div>
      </div>

      {/* Next step CTA — hidden when practice response area is shown */}
      {continueAction.kind !== 'idle' && !hasPracticePrompt && !interactivePracticeBlock && (
        <Button
          size="lg"
          className="w-full transition-all"
          disabled={loading || isStreaming || submittingInteraction}
          onClick={handleContinue}
        >
          {isStreaming ? 'Generating...' : learnerContinueAction(continueAction.kind, continueAction.display_label)}
          <ArrowRight className="ml-2 h-4 w-4" />
        </Button>
      )}
    </PageContainer>
  )
}
