import { useCallback, useState } from 'react'
import { useNavigate, useOutletContext } from 'react-router'
import { ArrowRight, ChevronLeft, Lightbulb, Wrench } from 'lucide-react'
import type { LearnerContext } from '../../shells/LearnerShell'
import { PageContainer } from '../../components/shell/PageContainer'
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
        className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ChevronLeft className="h-4 w-4" />
        Back to home
      </button>

      {/* Phase header */}
      <header>
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

        {/* Step progress */}
        <div className="mt-4 flex items-center gap-2">
          {steps.map((step, index) => (
            <StepDot
              key={index}
              index={index}
              currentIndex={currentIndex}
              label={learnerRemediationPhase(step.phase)}
            />
          ))}
          <span className="ml-2 text-sm text-muted-foreground">
            Step {currentIndex + 1} of {totalSteps}
          </span>
        </div>
      </header>

      {/* Phase label */}
      {currentStep && (
        <div className="rounded-lg bg-amber-50 px-4 py-3">
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
      {contentBlocks.length > 0 && (
        <div className="flex flex-col gap-4">
          {contentBlocks.map((block, index) => (
            <ContentBlock key={index} block={block} />
          ))}
        </div>
      )}

      {/* Learner input */}
      <div className="flex flex-col gap-3">
        <label className="text-sm font-medium">Your response</label>
        <Textarea
          value={remediation.advancePrompt}
          onChange={(e) => remediation.setAdvancePrompt(e.target.value)}
          placeholder="What do you think?"
          className="min-h-[100px] resize-none"
        />
      </div>

      {/* Continue CTA */}
      <Button
        onClick={handleAdvance}
        disabled={remediation.loading}
        className="w-full"
        size="lg"
      >
        {remediation.loading ? 'Working...' : 'Continue'}
        <ArrowRight className="ml-2 h-4 w-4" />
      </Button>

      {remediation.error && (
        <p className="text-sm text-red-600">{remediation.error}</p>
      )}

      {/* "Why this lesson" disclosure */}
      {session.rationale && (
        <details className="rounded-xl border bg-slate-50 p-4">
          <summary className="flex cursor-pointer items-center gap-2 text-sm font-medium text-muted-foreground">
            <Lightbulb className="h-4 w-4" />
            Why am I working on this?
          </summary>
          <p className="mt-2 text-sm text-muted-foreground">{session.rationale}</p>
        </details>
      )}
    </PageContainer>
  )
}

function StepDot({ index, currentIndex, label }: { index: number; currentIndex: number; label: string }) {
  const isComplete = index < currentIndex
  const isCurrent = index === currentIndex
  return (
    <div className="group relative">
      <div
        className={`h-2.5 w-2.5 rounded-full transition-colors ${
          isComplete
            ? 'bg-amber-500'
            : isCurrent
              ? 'bg-amber-400 ring-2 ring-amber-200'
              : 'bg-slate-200'
        }`}
      />
      <span className="pointer-events-none absolute -top-8 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-slate-800 px-2 py-1 text-xs text-white opacity-0 transition-opacity group-hover:opacity-100">
        {label}
      </span>
    </div>
  )
}
