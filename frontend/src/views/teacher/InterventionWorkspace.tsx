import { useCallback, useState } from 'react'
import { useNavigate, useOutletContext, useParams } from 'react-router'
import { Check, ChevronLeft, Clock, Zap } from 'lucide-react'
import type { TeacherContext } from '../../shells/TeacherShell'
import { PageContainer } from '../../components/shell/PageContainer'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Textarea } from '@/components/ui/textarea'
import { useLearnerWorkspace } from '../../hooks/useLearnerWorkspace'
import { useLearnerContracts } from '../../hooks/useLearnerContracts'
import { teacherContinueAction, teacherStage, teacherFlowType } from '../../lib/copy'
import type { DataSource } from '../../app/workspace'
import type { TeacherInterventionOption, TeacherInterventionDecisionRequest } from '../../types'

export function InterventionWorkspace() {
  const { studentId } = useParams<{ studentId: string }>()
  const { config } = useOutletContext<TeacherContext>()
  const navigate = useNavigate()

  const [, setDataSource] = useState<DataSource>('demo')
  const handleDataSourceChange = useCallback((source: DataSource) => setDataSource(source), [])

  const learner = useLearnerWorkspace({
    config,
    onDataSourceChange: handleDataSourceChange,
  })

  const contracts = useLearnerContracts({
    config,
    learnerId: studentId ?? learner.learnerId,
    onDataSourceChange: handleDataSourceChange,
  })

  // Load the requested student
  if (studentId && studentId !== learner.learnerId && !learner.loading) {
    void learner.loadLearnerWorkspace(studentId)
  }

  const intervention = contracts.intervention
  const [selectedOptionId, setSelectedOptionId] = useState<string | null>(null)
  const [note, setNote] = useState('')

  function handleDecision(decision: TeacherInterventionDecisionRequest['decision']) {
    const payload: TeacherInterventionDecisionRequest = {
      decision,
      option_id: decision === 'select_option' ? selectedOptionId : undefined,
      note: note.trim() || undefined,
    }
    void contracts.submitTeacherDecision(payload)
  }

  const hasDecision = !!intervention.latest_decision

  return (
    <PageContainer size="default" className="flex flex-col gap-6 py-4">
      {/* Back nav */}
      <button
        onClick={() => navigate(`/teacher/learners/${studentId}`)}
        className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ChevronLeft className="h-4 w-4" />
        Back to learner detail
      </button>

      {/* Header */}
      <header className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Intervention: {studentId}</h1>
          <p className="mt-1 text-muted-foreground">
            {teacherFlowType(intervention.flow_type)} &middot; {teacherStage(intervention.target_stage)}
          </p>
        </div>
        <Badge variant={intervention.proposal_status === 'available' ? 'default' : 'outline'}>
          {intervention.proposal_status === 'available' ? 'Proposal ready' : 'No proposal'}
        </Badge>
      </header>

      {/* Proposed action summary */}
      <section className="rounded-xl border bg-white p-6 shadow-sm">
        <div className="flex items-center gap-3 mb-4">
          <Zap className="h-5 w-5 text-emerald-600" />
          <h2 className="font-semibold">Proposed action</h2>
        </div>
        <div className="rounded-lg bg-emerald-50 px-4 py-3">
          <p className="font-medium text-emerald-800">
            {teacherContinueAction(intervention.proposed_action.kind)}
          </p>
          {intervention.proposed_action.rationale && (
            <p className="mt-1 text-sm text-emerald-700">{intervention.proposed_action.rationale}</p>
          )}
        </div>
      </section>

      {/* Alternative options */}
      {intervention.available_options.length > 0 && (
        <section className="rounded-xl border bg-white p-6 shadow-sm">
          <h2 className="mb-4 font-semibold">Options</h2>
          <div className="flex flex-col gap-3">
            {intervention.available_options.map((option) => (
              <OptionCard
                key={option.option_id}
                option={option}
                selected={selectedOptionId === option.option_id}
                onSelect={() => setSelectedOptionId(option.option_id)}
              />
            ))}
          </div>
        </section>
      )}

      {/* Teacher note */}
      <section className="rounded-xl border bg-white p-6 shadow-sm">
        <h2 className="mb-3 font-semibold">Note (optional)</h2>
        <Textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Add a note about this decision..."
          className="resize-none"
        />
      </section>

      {/* Decision controls */}
      <div className="flex flex-wrap items-center gap-3">
        <Button
          onClick={() => handleDecision('approve')}
          disabled={contracts.submittingIntervention}
        >
          <Check className="mr-2 h-4 w-4" />
          Approve recommendation
        </Button>
        {selectedOptionId && (
          <Button
            variant="secondary"
            onClick={() => handleDecision('select_option')}
            disabled={contracts.submittingIntervention}
          >
            Use selected option
          </Button>
        )}
        <Button
          variant="outline"
          onClick={() => handleDecision('defer')}
          disabled={contracts.submittingIntervention}
        >
          <Clock className="mr-2 h-4 w-4" />
          Defer
        </Button>
        <Button
          variant="outline"
          onClick={() => handleDecision('escalate_human')}
          disabled={contracts.submittingIntervention}
        >
          Escalate
        </Button>
      </div>

      {/* Latest decision status */}
      {hasDecision && (
        <div className="rounded-lg bg-slate-50 px-4 py-3 text-sm">
          <p className="font-medium">
            Decision recorded: {intervention.latest_decision!.status}
          </p>
          <p className="text-muted-foreground">
            By {intervention.latest_decision!.decided_by} &middot;{' '}
            {intervention.latest_decision!.decided_role}
          </p>
        </div>
      )}

      {contracts.interventionError && (
        <p className="text-sm text-red-600">{contracts.interventionError}</p>
      )}
    </PageContainer>
  )
}

function OptionCard({
  option,
  selected,
  onSelect,
}: {
  option: TeacherInterventionOption
  selected: boolean
  onSelect: () => void
}) {
  return (
    <button
      onClick={onSelect}
      className={`flex flex-col gap-1 rounded-lg border p-4 text-left transition-colors ${
        selected
          ? 'border-emerald-300 bg-emerald-50'
          : 'border-slate-200 hover:border-slate-300'
      }`}
    >
      <div className="flex items-center gap-2">
        <p className="font-medium">{option.label}</p>
        {option.is_recommended && (
          <Badge variant="secondary" className="text-xs">Recommended</Badge>
        )}
      </div>
      {option.rationale && (
        <p className="text-sm text-muted-foreground">{option.rationale}</p>
      )}
    </button>
  )
}
