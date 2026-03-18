import { useCallback, useState } from 'react'
import { Link, useNavigate, useOutletContext, useParams } from 'react-router'
import {
  BookOpen,
  ChevronLeft,
  Clock,
  MessageCircle,
  Target,
  TrendingUp,
  Wrench,
  Zap,
} from 'lucide-react'
import type { TeacherContext } from '../../shells/TeacherShell'
import { PageContainer } from '../../components/shell/PageContainer'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { useLearnerWorkspace } from '../../hooks/useLearnerWorkspace'
import { useLearnerContracts } from '../../hooks/useLearnerContracts'
import {
  teacherFlowType,
  teacherStage,
  teacherContinueAction,
  teacherArtifact,
  teacherProgressionAction,
} from '../../lib/copy'
import { formatPercent, formatTimestamp } from '../../lib/formatters'
import type { DataSource } from '../../app/workspace'

export function LearnerDetail() {
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

  // Load requested student if different from default
  if (studentId && studentId !== learner.learnerId && !learner.loading) {
    void learner.loadLearnerWorkspace(studentId)
  }

  const { summary, flow, workspace } = learner
  const progression = summary.curriculum_progression
  const hasIntervention = contracts.intervention?.proposal_status === 'available'

  return (
    <PageContainer className="flex flex-col gap-6 py-4">
      {/* Back nav */}
      <button
        onClick={() => navigate(-1)}
        className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ChevronLeft className="h-4 w-4" />
        Back
      </button>

      {/* Header */}
      <header className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{studentId}</h1>
          <p className="mt-1 text-muted-foreground">
            Grade {summary.grade_level} &middot; {teacherFlowType(flow.flow_type)} &middot; {teacherStage(progression.current_stage)}
          </p>
        </div>
        {hasIntervention && (
          <Link to={`/teacher/learners/${studentId}/intervention`}>
            <Button>
              <Zap className="mr-2 h-4 w-4" />
              Open intervention
            </Button>
          </Link>
        )}
      </header>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Learner overview */}
        <section className="rounded-xl border bg-white p-6 shadow-sm">
          <div className="flex items-center gap-3 mb-4">
            <TrendingUp className="h-5 w-5 text-muted-foreground" />
            <h2 className="font-semibold">Overview</h2>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <StatItem label="Engagement" value={summary.engagement} />
            <StatItem label="Frustration" value={summary.frustration} />
            <StatItem
              label="Progress"
              value={formatPercent(progression.mastered_resource_ratio)}
            />
            <StatItem label="Stage" value={teacherStage(progression.current_stage)} />
            <StatItem label="Progression" value={teacherProgressionAction(progression.progression_action)} />
            <StatItem label="Next action" value={teacherContinueAction(workspace.continue_action.kind)} />
          </div>
        </section>

        {/* Current activity */}
        <section className="rounded-xl border bg-white p-6 shadow-sm">
          <div className="flex items-center gap-3 mb-4">
            <BookOpen className="h-5 w-5 text-muted-foreground" />
            <h2 className="font-semibold">Current activity</h2>
          </div>
          <div className="space-y-3">
            <div className="rounded-lg bg-slate-50 px-4 py-3">
              <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                {teacherArtifact(workspace.active_artifact.kind)}
              </p>
              <p className="mt-1 font-medium">
                {progression.current_resource?.title ?? 'No active resource'}
              </p>
              <p className="mt-0.5 text-sm text-muted-foreground">
                Phase: {flow.current_phase} &middot; {flow.session_phase}
              </p>
            </div>
            {flow.rationale && (
              <p className="text-sm text-muted-foreground">{flow.rationale}</p>
            )}
          </div>
        </section>

        {/* Backend recommendation */}
        {contracts.intervention && (
          <section className="rounded-xl border bg-white p-6 shadow-sm">
            <div className="flex items-center gap-3 mb-4">
              <Target className="h-5 w-5 text-muted-foreground" />
              <h2 className="font-semibold">Backend recommendation</h2>
            </div>
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Badge variant={hasIntervention ? 'default' : 'outline'}>
                  {hasIntervention ? 'Intervention available' : 'No intervention'}
                </Badge>
              </div>
              {hasIntervention && (
                <>
                  <p className="text-sm">
                    {contracts.intervention.available_options.length} option{contracts.intervention.available_options.length === 1 ? '' : 's'} proposed
                  </p>
                  {contracts.intervention.latest_decision && (
                    <p className="text-sm text-muted-foreground">
                      Latest decision: {contracts.intervention.latest_decision.status} at{' '}
                      {formatTimestamp(contracts.intervention.latest_decision.decided_at)}
                    </p>
                  )}
                </>
              )}
            </div>
          </section>
        )}

        {/* Recent evidence (history timeline) */}
        <section className="rounded-xl border bg-white p-6 shadow-sm">
          <div className="flex items-center gap-3 mb-4">
            <Clock className="h-5 w-5 text-muted-foreground" />
            <h2 className="font-semibold">Recent work</h2>
          </div>
          <div className="space-y-2">
            {contracts.generationHistory.slice(0, 3).map((g) => (
              <TimelineItem
                key={g.generation_id}
                icon={BookOpen}
                label={g.content_type}
                detail={g.rationale ?? g.progression_action}
                timestamp={g.created_at}
              />
            ))}
            {contracts.socraticHistory.slice(0, 2).map((s) => (
              <TimelineItem
                key={s.session_id}
                icon={MessageCircle}
                label="Socratic check"
                detail={`${s.turn_count} turns &middot; ${s.latest_evidence_strength}`}
                timestamp={s.created_at}
              />
            ))}
            {contracts.remediationHistory.slice(0, 2).map((r) => (
              <TimelineItem
                key={r.session_id}
                icon={Wrench}
                label="Remediation"
                detail={`${r.completed_step_count}/${r.step_count} steps &middot; ${r.progression_decision}`}
                timestamp={r.created_at}
              />
            ))}
            {contracts.generationHistory.length === 0 &&
              contracts.socraticHistory.length === 0 &&
              contracts.remediationHistory.length === 0 && (
                <p className="text-sm text-muted-foreground">No recent activity recorded.</p>
              )}
          </div>
        </section>
      </div>

      {learner.loading && (
        <p className="text-center text-sm text-muted-foreground">Loading learner data...</p>
      )}
    </PageContainer>
  )
}

function StatItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-slate-50 px-3 py-2">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="font-medium">{value}</p>
    </div>
  )
}

function TimelineItem({
  icon: Icon,
  label,
  detail,
  timestamp,
}: {
  icon: typeof BookOpen
  label: string
  detail: string
  timestamp: string
}) {
  return (
    <div className="flex items-start gap-3 text-sm">
      <Icon className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
      <div className="flex-1 min-w-0">
        <p className="font-medium">{label}</p>
        <p className="text-muted-foreground truncate">{detail}</p>
      </div>
      <time className="shrink-0 text-xs text-muted-foreground">{formatTimestamp(timestamp)}</time>
    </div>
  )
}
