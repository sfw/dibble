import { Link, useNavigate, useOutletContext, useParams } from 'react-router'
import { ChevronLeft } from 'lucide-react'
import type { TeacherContext } from '../../shells/TeacherShell'
import { PageContainer } from '../../components/shell/PageContainer'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { buildTriageSections, describeLearnerRationale } from '../../lib/triage'
import { teacherFlowType, teacherStage } from '../../lib/copy'
import { formatPercent } from '../../lib/formatters'
import type { TeacherLearnerCard } from '../../types'

const badgeVariantForTone = {
  accent: 'secondary',
  success: 'default',
  warning: 'warning',
  danger: 'destructive',
  neutral: 'outline',
} as const

export function ClassroomDetail() {
  const { sectionId } = useParams<{ sectionId: string }>()
  const { classroom, loading, loadSection } = useOutletContext<TeacherContext>()
  const navigate = useNavigate()

  // If navigated to a different section, load it
  if (sectionId && sectionId !== classroom.section_id && !loading) {
    void loadSection(sectionId)
  }

  const triageSections = buildTriageSections(classroom.learners)

  return (
    <PageContainer className="flex flex-col gap-6 py-4">
      {/* Back nav */}
      <button
        onClick={() => navigate('/teacher')}
        className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ChevronLeft className="h-4 w-4" />
        Back to dashboard
      </button>

      {/* Header */}
      <header className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{classroom.title}</h1>
          <p className="mt-1 text-muted-foreground">
            {classroom.teacher_label ?? 'Unassigned'} &middot; {classroom.learner_count} learners
          </p>
        </div>
        <div className="flex gap-2 text-sm">
          <Badge variant="outline">{classroom.active_flow_count} active</Badge>
          <Badge variant="warning">{classroom.blocked_progression_count} blocked</Badge>
          <Badge variant="secondary">{classroom.intervention_available_count} interventions</Badge>
        </div>
      </header>

      {/* Triage sections */}
      {triageSections.map((section) => (
        <section key={section.key} className="flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="font-semibold">{section.title}</h2>
              <p className="text-sm text-muted-foreground">{section.description}</p>
            </div>
            <Badge variant={badgeVariantForTone[section.tone]}>{section.learners.length}</Badge>
          </div>

          {section.learners.length === 0 ? (
            <p className="rounded-lg bg-slate-50 px-4 py-6 text-center text-sm text-muted-foreground">
              No learners in this group.
            </p>
          ) : (
            <div className="flex flex-col gap-2">
              {section.learners.map((learner) => (
                <LearnerRow key={learner.student_id} learner={learner} />
              ))}
            </div>
          )}
        </section>
      ))}

      {loading && (
        <p className="py-4 text-center text-sm text-muted-foreground">Refreshing section...</p>
      )}
    </PageContainer>
  )
}

function LearnerRow({ learner }: { learner: TeacherLearnerCard }) {
  const hasIntervention = learner.intervention.proposal_status === 'available'

  return (
    <div className="flex items-center gap-4 rounded-xl border bg-white p-4 shadow-sm">
      {/* Identity + status */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <Link
            to={`/teacher/learners/${learner.student_id}`}
            className="font-medium hover:text-emerald-700 hover:underline"
          >
            {learner.student_id}
          </Link>
          <span className="text-xs text-muted-foreground">Grade {learner.grade_level}</span>
        </div>
        <p className="mt-0.5 text-sm text-muted-foreground truncate">
          {describeLearnerRationale(learner)}
        </p>
      </div>

      {/* Quick stats */}
      <div className="hidden sm:flex items-center gap-3 text-xs text-muted-foreground">
        <span>{teacherFlowType(learner.current_flow.flow_type)}</span>
        <span>&middot;</span>
        <span>{teacherStage(learner.curriculum_progression.current_stage)}</span>
        <span>&middot;</span>
        <span>{formatPercent(learner.curriculum_progression.mastered_outcome_ratio)}</span>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2">
        {hasIntervention && (
          <Link to={`/teacher/learners/${learner.student_id}/intervention`}>
            <Button size="sm" variant="default">Intervene</Button>
          </Link>
        )}
        <Link to={`/teacher/learners/${learner.student_id}`}>
          <Button size="sm" variant="outline">Review</Button>
        </Link>
      </div>
    </div>
  )
}
