import { useOutletContext } from 'react-router'
import { BookOpen, CheckCircle2, Clock, PlayCircle, XCircle } from 'lucide-react'
import type { LearnerContext } from '../../shells/LearnerShell'
import { PageContainer } from '../../components/shell/PageContainer'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { useLearnerAssignments } from '../../hooks/useAssignments'
import { formatTimestamp } from '../../lib/formatters'
import type { Assignment, AssignmentStatus } from '../../types'

const statusConfig: Record<AssignmentStatus, { label: string; icon: typeof Clock; variant: 'default' | 'secondary' | 'outline' | 'destructive' | 'warning' }> = {
  assigned: { label: 'Assigned', icon: Clock, variant: 'secondary' },
  in_progress: { label: 'In progress', icon: PlayCircle, variant: 'default' },
  completed: { label: 'Completed', icon: CheckCircle2, variant: 'outline' },
  canceled: { label: 'Canceled', icon: XCircle, variant: 'destructive' },
}

export function Assignments() {
  const { config, summary } = useOutletContext<LearnerContext>()
  const learnerId = summary.student_id

  const { assignments, hasMore, loading, loadingMore, error, loadMore, updateStatus } =
    useLearnerAssignments({ config, learnerId })

  const activeAssignments = assignments.filter((a) => a.status === 'assigned' || a.status === 'in_progress')
  const pastAssignments = assignments.filter((a) => a.status === 'completed' || a.status === 'canceled')

  return (
    <PageContainer size="narrow" className="flex flex-col gap-8 py-4">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Assignments</h1>
        <p className="mt-1 text-muted-foreground">Work assigned by your teacher.</p>
      </header>

      {error && (
        <p className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </p>
      )}

      {loading && assignments.length === 0 && (
        <p className="text-center text-muted-foreground py-12">Loading assignments...</p>
      )}

      {!loading && assignments.length === 0 && (
        <div className="flex flex-col items-center gap-2 py-16 text-center">
          <BookOpen className="h-10 w-10 text-muted-foreground/50" />
          <p className="text-muted-foreground">No assignments yet.</p>
          <p className="text-sm text-muted-foreground">Your teacher will assign work here.</p>
        </div>
      )}

      {/* Active assignments */}
      {activeAssignments.length > 0 && (
        <section className="flex flex-col gap-3">
          <h2 className="font-semibold">To do</h2>
          <div className="flex flex-col gap-3">
            {activeAssignments.map((assignment) => (
              <AssignmentCard
                key={assignment.assignment_id}
                assignment={assignment}
                onStart={(id) => void updateStatus(id, 'in_progress')}
              />
            ))}
          </div>
        </section>
      )}

      {/* Past assignments */}
      {pastAssignments.length > 0 && (
        <section className="flex flex-col gap-3">
          <h2 className="font-semibold text-muted-foreground">Past</h2>
          <div className="flex flex-col gap-3">
            {pastAssignments.map((assignment) => (
              <AssignmentCard key={assignment.assignment_id} assignment={assignment} />
            ))}
          </div>
        </section>
      )}

      {hasMore && (
        <div className="flex justify-center">
          <Button variant="outline" size="sm" onClick={() => void loadMore()} disabled={loadingMore}>
            {loadingMore ? 'Loading...' : 'Load more'}
          </Button>
        </div>
      )}
    </PageContainer>
  )
}

function AssignmentCard({
  assignment,
  onStart,
}: {
  assignment: Assignment
  onStart?: (assignmentId: string) => void
}) {
  const { label, icon: StatusIcon, variant } = statusConfig[assignment.status]
  const isActionable = assignment.status === 'assigned' && onStart

  return (
    <div className="flex items-start gap-4 rounded-xl border bg-white p-5 shadow-sm">
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-blue-100 text-blue-600">
        <BookOpen className="h-5 w-5" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 className="font-semibold">{assignment.title}</h3>
            {assignment.description && (
              <p className="mt-0.5 text-sm text-muted-foreground">{assignment.description}</p>
            )}
          </div>
          <Badge variant={variant} className="shrink-0">
            <StatusIcon className="mr-1 h-3 w-3" />
            {label}
          </Badge>
        </div>
        <div className="mt-2 flex items-center gap-4 text-xs text-muted-foreground">
          {assignment.due_at && (
            <span>Due {formatTimestamp(assignment.due_at)}</span>
          )}
          <span>Assigned {formatTimestamp(assignment.created_at)}</span>
        </div>
        {isActionable && (
          <Button
            size="sm"
            className="mt-3"
            onClick={() => onStart(assignment.assignment_id)}
          >
            <PlayCircle className="mr-1.5 h-4 w-4" />
            Start
          </Button>
        )}
      </div>
    </div>
  )
}
