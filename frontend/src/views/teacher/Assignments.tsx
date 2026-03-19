import { useCallback, useState } from 'react'
import { useOutletContext } from 'react-router'
import {
  BookOpen,
  CheckCircle2,
  ChevronUp,
  Clock,
  PlayCircle,
  Plus,
  XCircle,
} from 'lucide-react'
import type { TeacherContext } from '../../shells/TeacherShell'
import { PageContainer } from '../../components/shell/PageContainer'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { useTeacherAssignments } from '../../hooks/useAssignments'
import { formatTimestamp } from '../../lib/formatters'
import type { Assignment, AssignmentCreate, AssignmentStatus } from '../../types'

const statusConfig: Record<
  AssignmentStatus,
  { label: string; icon: typeof Clock; variant: 'default' | 'secondary' | 'outline' | 'destructive' | 'warning' }
> = {
  assigned: { label: 'Assigned', icon: Clock, variant: 'secondary' },
  in_progress: { label: 'In progress', icon: PlayCircle, variant: 'default' },
  completed: { label: 'Completed', icon: CheckCircle2, variant: 'outline' },
  canceled: { label: 'Canceled', icon: XCircle, variant: 'destructive' },
}

export function TeacherAssignments() {
  const { config, classroom } = useOutletContext<TeacherContext>()
  const { assignments, hasMore, loading, loadingMore, creating, error, loadMore, create, updateStatus } =
    useTeacherAssignments({ config })
  const [showForm, setShowForm] = useState(false)

  const handleCreate = useCallback(
    async (payload: AssignmentCreate) => {
      const result = await create(payload)
      if (result) setShowForm(false)
    },
    [create],
  )

  const activeCount = assignments.filter((a) => a.status === 'assigned' || a.status === 'in_progress').length
  const completedCount = assignments.filter((a) => a.status === 'completed').length

  return (
    <PageContainer className="flex flex-col gap-6 py-4">
      <header className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Assignments</h1>
          <p className="mt-1 text-muted-foreground">
            {activeCount} active &middot; {completedCount} completed
          </p>
        </div>
        <Button onClick={() => setShowForm(!showForm)}>
          {showForm ? (
            <>
              <ChevronUp className="mr-1.5 h-4 w-4" />
              Cancel
            </>
          ) : (
            <>
              <Plus className="mr-1.5 h-4 w-4" />
              New assignment
            </>
          )}
        </Button>
      </header>

      {error && (
        <p className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </p>
      )}

      {showForm && (
        <CreateAssignmentForm
          sectionId={classroom.section_id}
          learners={classroom.learners.map((l) => l.student_id)}
          creating={creating}
          onSubmit={handleCreate}
          onCancel={() => setShowForm(false)}
        />
      )}

      {loading && assignments.length === 0 && (
        <p className="text-center text-muted-foreground py-12">Loading assignments...</p>
      )}

      {!loading && assignments.length === 0 && !showForm && (
        <div className="flex flex-col items-center gap-2 py-16 text-center">
          <BookOpen className="h-10 w-10 text-muted-foreground/50" />
          <p className="text-muted-foreground">No assignments yet.</p>
          <p className="text-sm text-muted-foreground">
            Create one to assign work to your learners.
          </p>
        </div>
      )}

      {assignments.length > 0 && (
        <div className="flex flex-col gap-3">
          {assignments.map((assignment) => (
            <TeacherAssignmentRow
              key={assignment.assignment_id}
              assignment={assignment}
              onCancel={(id) => void updateStatus(id, 'canceled')}
            />
          ))}
        </div>
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

function TeacherAssignmentRow({
  assignment,
  onCancel,
}: {
  assignment: Assignment
  onCancel?: (assignmentId: string) => void
}) {
  const { label, icon: StatusIcon, variant } = statusConfig[assignment.status]
  const canCancel = (assignment.status === 'assigned' || assignment.status === 'in_progress') && onCancel

  return (
    <div className="flex items-start gap-4 rounded-xl border bg-white p-5 shadow-sm">
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-emerald-100 text-emerald-600">
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
        <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
          <span>Student: {assignment.student_id}</span>
          {assignment.due_at && <span>Due {formatTimestamp(assignment.due_at)}</span>}
          <span>Created {formatTimestamp(assignment.created_at)}</span>
          {assignment.status === 'in_progress' && assignment.started_at && (
            <span>Started {formatTimestamp(assignment.started_at)}</span>
          )}
          {assignment.status === 'completed' && assignment.completed_at && (
            <span>Completed {formatTimestamp(assignment.completed_at)}</span>
          )}
        </div>
      </div>
      {canCancel && (
        <Button
          variant="ghost"
          size="sm"
          className="shrink-0 text-muted-foreground hover:text-red-600"
          onClick={() => onCancel(assignment.assignment_id)}
        >
          <XCircle className="mr-1 h-4 w-4" />
          Cancel
        </Button>
      )}
    </div>
  )
}

function CreateAssignmentForm({
  sectionId,
  learners,
  creating,
  onSubmit,
  onCancel,
}: {
  sectionId: string
  learners: string[]
  creating: boolean
  onSubmit: (payload: AssignmentCreate) => Promise<void>
  onCancel: () => void
}) {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [studentId, setStudentId] = useState(learners[0] ?? '')
  const [dueAt, setDueAt] = useState('')

  const canSubmit = title.trim() && studentId.trim() && !creating

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!canSubmit) return
    void onSubmit({
      student_id: studentId.trim(),
      section_id: sectionId || undefined,
      title: title.trim(),
      description: description.trim() || undefined,
      due_at: dueAt ? new Date(dueAt).toISOString() : undefined,
    })
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex flex-col gap-4 rounded-xl border bg-white p-6 shadow-sm"
    >
      <h2 className="font-semibold">New assignment</h2>
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="flex flex-col gap-1.5">
          <label htmlFor="assignment-title" className="text-sm font-medium">
            Title
          </label>
          <input
            id="assignment-title"
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. Fractions practice"
            className="rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
            required
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <label htmlFor="assignment-student" className="text-sm font-medium">
            Student
          </label>
          {learners.length > 0 ? (
            <select
              id="assignment-student"
              value={studentId}
              onChange={(e) => setStudentId(e.target.value)}
              className="rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
            >
              {learners.map((id) => (
                <option key={id} value={id}>
                  {id}
                </option>
              ))}
            </select>
          ) : (
            <input
              id="assignment-student"
              type="text"
              value={studentId}
              onChange={(e) => setStudentId(e.target.value)}
              placeholder="Student ID"
              className="rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
              required
            />
          )}
        </div>
        <div className="flex flex-col gap-1.5 sm:col-span-2">
          <label htmlFor="assignment-description" className="text-sm font-medium">
            Description <span className="text-muted-foreground">(optional)</span>
          </label>
          <textarea
            id="assignment-description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Instructions or context for the student"
            rows={2}
            className="rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <label htmlFor="assignment-due" className="text-sm font-medium">
            Due date <span className="text-muted-foreground">(optional)</span>
          </label>
          <input
            id="assignment-due"
            type="datetime-local"
            value={dueAt}
            onChange={(e) => setDueAt(e.target.value)}
            className="rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
          />
        </div>
      </div>
      <div className="flex items-center gap-3">
        <Button type="submit" disabled={!canSubmit}>
          {creating ? 'Creating...' : 'Create assignment'}
        </Button>
        <Button type="button" variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </form>
  )
}
