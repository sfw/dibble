import { CheckCircle2, CircleDashed, Compass } from 'lucide-react'
import type { LearnerCurriculumProgressionSummary } from '../../types'

/**
 * Learner-legible progress strip: mastered / working on / up next, derived
 * entirely from the backend-owned curriculum progression read model.
 */
export function ProgressStrip({
  progression,
}: {
  progression: LearnerCurriculumProgressionSummary
}) {
  const workingOn = progression.current_outcome?.title ?? null
  const upNext =
    progression.next_outcome?.title ?? progression.ready_outcomes[0]?.title ?? null

  return (
    <section
      aria-label="Progress strip"
      className="grid gap-3 rounded-xl border bg-white p-4 shadow-sm sm:grid-cols-3"
    >
      <div className="flex items-center gap-3">
        <CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-600" />
        <div>
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Mastered
          </p>
          <p className="text-sm font-semibold">
            {progression.mastered_outcome_count} of {progression.outcome_count} topics
          </p>
        </div>
      </div>
      <div className="flex items-center gap-3">
        <Compass className="h-5 w-5 shrink-0 text-blue-600" />
        <div>
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Working on
          </p>
          <p className="text-sm font-semibold">{workingOn ?? 'Finding your next topic'}</p>
        </div>
      </div>
      <div className="flex items-center gap-3">
        <CircleDashed className="h-5 w-5 shrink-0 text-slate-400" />
        <div>
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Up next
          </p>
          <p className="text-sm font-semibold">{upNext ?? 'We will pick this together'}</p>
        </div>
      </div>
    </section>
  )
}
