import { useCallback, useState } from 'react'
import { useNavigate, useOutletContext } from 'react-router'
import { ArrowRight, Check, ChevronLeft, Lightbulb, Loader2, Wrench } from 'lucide-react'
import type { LearnerContext } from '../../shells/LearnerShell'
import { PageContainer } from '../../components/shell/PageContainer'
import { ErrorBanner } from '@/components/ui/error-banner'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { useRemediationWorkspace } from '../../hooks/useRemediationWorkspace'
import { learnerRemediationPhase } from '../../lib/copy'
import { ContentBlock } from '../../components/content/ContentBlock'
import { AffectiveSupport } from '../../components/content/AffectiveSupport'
import type { DataSource } from '../../app/workspace'

export function RemediationSession() {
  const { config, workspace } = useOutletContext<LearnerContext>()
  const navigate = useNavigate()

  const [, setDataSource] = useState<DataSource>('demo')
  const handleDataSourceChange = useCallback((source: DataSource) => setDataSource(source), [])

  const remediation = useRemediationWorkspace({
    config,
    learnerId: workspace.student_id,
    workspace,
    onDataSourceChange: handleDataSourceChange,
  })

  const session = remediation.session
  const steps = session.steps
  const currentIndex = session.current_step_index ?? 0
  const currentStep = steps[currentIndex]
  const totalSteps = steps.length
  const contentBlocks = remediation.content?.response?.blocks ?? []

  function handleAdvance() {
    void remediation.handleAdvance()
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

      {/* Phase header */}
      <header className="animate-fade-in-up">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-amber-100 text-amber-600">
            <Wrench className="h-5 w-5" />
          </div>
          <div>
            <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Practice session
            </p>
            <h1 className="text-xl font-semibold">
              {currentStep?.title ?? 'Working through it'}
            </h1>
          </div>
        </div>

        {/* Step progress — enhanced with connected track and check marks */}
        <div className="mt-5">
          <div className="flex items-center gap-1">
            {steps.map((step, index) => (
              <StepIndicator
                key={index}
                index={index}
                currentIndex={currentIndex}
                totalSteps={totalSteps}
                label={learnerRemediationPhase(step.phase)}
              />
            ))}
          </div>
          <p className="mt-2 text-sm text-muted-foreground">
            Step {currentIndex + 1} of {totalSteps}
          </p>
        </div>
      </header>

      {/* Empty state — no steps yet */}
      {totalSteps === 0 && !remediation.loading && (
        <div className="rounded-xl border bg-white p-8 text-center text-muted-foreground animate-scale-in">
          <p>Your practice session is being prepared. Check back in a moment.</p>
        </div>
      )}

      {/* Phase label */}
      {currentStep && (
        <div className="rounded-lg bg-amber-50 border border-amber-200 px-4 py-3 animate-scale-in">
          <p className="text-sm font-medium text-amber-800">
            {learnerRemediationPhase(currentStep.phase)}
          </p>
          {currentStep.objective && (
            <p className="mt-1 text-sm text-amber-700">{currentStep.objective}</p>
          )}
        </div>
      )}

      {/* Affective state support */}
      <AffectiveSupport message={workspace.affective_support} />

      {/* Content from generated blocks */}
      {contentBlocks.length > 0 ? (
        <div className="flex flex-col gap-4">
          {contentBlocks.map((block, index) => (
            <div key={index} className="animate-fade-in-up" style={{ animationDelay: `${index * 80}ms` }}>
              <ContentBlock block={block} />
            </div>
          ))}
        </div>
      ) : remediation.loading ? (
        <div className="flex flex-col items-center justify-center gap-3 py-12 text-muted-foreground animate-fade-in">
          <Loader2 className="h-6 w-6 animate-spin text-amber-500" />
          <p className="font-medium">Preparing your next step...</p>
        </div>
      ) : null}

      {/* Learner input */}
      <div className="flex flex-col gap-3 animate-fade-in-up" style={{ animationDelay: '100ms' }}>
        <label className="text-sm font-medium">Your response</label>
        <Textarea
          value={remediation.advancePrompt}
          onChange={(e) => remediation.setAdvancePrompt(e.target.value)}
          placeholder="What do you think?"
          className="min-h-[100px] resize-none transition-shadow focus:shadow-sm"
        />
      </div>

      {/* Continue CTA */}
      <Button
        onClick={handleAdvance}
        disabled={remediation.loading || !remediation.advancePrompt.trim()}
        className="w-full transition-all"
        size="lg"
      >
        {remediation.loading ? 'Working...' : 'Continue'}
        <ArrowRight className="ml-2 h-4 w-4" />
      </Button>

      {remediation.error && (
        <div className="flex flex-col gap-2">
          <ErrorBanner message={remediation.error} />
          <Button
            variant="outline"
            size="sm"
            onClick={() => void remediation.handleReload()}
            className="self-start"
          >
            Try again
          </Button>
        </div>
      )}

      {/* "Why this lesson" disclosure */}
      {session.rationale && (
        <details className="rounded-xl border bg-slate-50 p-4">
          <summary className="flex cursor-pointer items-center gap-2 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors">
            <Lightbulb className="h-4 w-4" />
            Why am I working on this?
          </summary>
          <p className="mt-2 text-sm text-muted-foreground">{session.rationale}</p>
        </details>
      )}
    </PageContainer>
  )
}

function StepIndicator({
  index,
  currentIndex,
  totalSteps,
  label,
}: {
  index: number
  currentIndex: number
  totalSteps: number
  label: string
}) {
  const isComplete = index < currentIndex
  const isCurrent = index === currentIndex
  const isLast = index === totalSteps - 1

  return (
    <div className="flex items-center flex-1 group" aria-label={`Step ${index + 1}: ${label}`}>
      {/* Step circle */}
      <div className="relative">
        <div
          aria-current={isCurrent ? 'step' : undefined}
          className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-medium transition-all duration-300 ${
            isComplete
              ? 'bg-amber-500 text-white shadow-sm'
              : isCurrent
                ? 'bg-amber-100 text-amber-700 ring-2 ring-amber-300 shadow-sm'
                : 'bg-slate-100 text-slate-400'
          }`}
        >
          {isComplete ? (
            <Check className="h-3.5 w-3.5" />
          ) : (
            index + 1
          )}
        </div>
        {/* Tooltip */}
        <span className="pointer-events-none absolute -top-8 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-slate-800 px-2 py-1 text-xs text-white opacity-0 transition-opacity group-hover:opacity-100">
          {label}
        </span>
      </div>
      {/* Connector line */}
      {!isLast && (
        <div className="flex-1 mx-1">
          <div className="h-0.5 rounded-full bg-slate-200 overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-500 ${
                isComplete ? 'bg-amber-400 w-full' : 'w-0'
              }`}
            />
          </div>
        </div>
      )}
    </div>
  )
}
