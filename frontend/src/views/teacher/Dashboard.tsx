import { Link, useOutletContext } from 'react-router'
import { AlertTriangle, ArrowRight, Ban, Zap } from 'lucide-react'
import type { TeacherContext } from '../../shells/TeacherShell'
import { PageContainer } from '../../components/shell/PageContainer'
import type { TeacherSectionOverview } from '../../types'

export function Dashboard() {
  const { classrooms, loading } = useOutletContext<TeacherContext>()

  const totalAttention = classrooms.reduce((sum, c) => sum + c.attention_needed_count, 0)
  const totalBlocked = classrooms.reduce((sum, c) => sum + c.blocked_progression_count, 0)
  const totalInterventions = classrooms.reduce((sum, c) => sum + c.intervention_available_count, 0)

  return (
    <PageContainer className="flex flex-col gap-8 py-4">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <p className="mt-1 text-muted-foreground">Your sections at a glance.</p>
      </header>

      {/* Summary stats */}
      <div className="grid gap-4 sm:grid-cols-3">
        <SummaryCard
          icon={AlertTriangle}
          label="Need attention"
          value={totalAttention}
          iconClass="text-amber-600 bg-amber-100"
        />
        <SummaryCard
          icon={Ban}
          label="Blocked"
          value={totalBlocked}
          iconClass="text-red-600 bg-red-100"
        />
        <SummaryCard
          icon={Zap}
          label="Interventions ready"
          value={totalInterventions}
          iconClass="text-emerald-600 bg-emerald-100"
        />
      </div>

      {/* Section cards */}
      {loading && classrooms.length === 0 && (
        <p className="py-12 text-center text-muted-foreground">Loading sections...</p>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {classrooms.map((classroom) => (
          <ClassroomCard key={classroom.section_id} classroom={classroom} />
        ))}
      </div>
    </PageContainer>
  )
}

function SummaryCard({
  icon: Icon,
  label,
  value,
  iconClass,
}: {
  icon: typeof AlertTriangle
  label: string
  value: number
  iconClass: string
}) {
  return (
    <div className="flex items-center gap-4 rounded-xl border bg-white p-5 shadow-sm">
      <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${iconClass}`}>
        <Icon className="h-5 w-5" />
      </div>
      <div>
        <p className="text-2xl font-semibold">{value}</p>
        <p className="text-sm text-muted-foreground">{label}</p>
      </div>
    </div>
  )
}

function ClassroomCard({ classroom }: { classroom: TeacherSectionOverview }) {
  return (
    <Link
      to={`/teacher/sections/${classroom.section_id}`}
      className="group flex flex-col gap-3 rounded-xl border bg-white p-5 shadow-sm transition-colors hover:border-emerald-300"
    >
      <div className="flex items-start justify-between">
        <div>
          <h2 className="font-semibold group-hover:text-emerald-700">{classroom.title}</h2>
          <p className="text-sm text-muted-foreground">
            {classroom.teacher_label ?? 'Unassigned'} &middot; {classroom.learner_count} learners
          </p>
        </div>
        <ArrowRight className="h-4 w-4 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
      </div>
      <div className="grid grid-cols-3 gap-2 text-center">
        <MiniStat
          label="Attention"
          value={classroom.attention_needed_count}
          warn={classroom.attention_needed_count > 0}
        />
        <MiniStat
          label="Blocked"
          value={classroom.blocked_progression_count}
          warn={classroom.blocked_progression_count > 0}
        />
        <MiniStat
          label="Interventions"
          value={classroom.intervention_available_count}
          highlight={classroom.intervention_available_count > 0}
        />
      </div>
    </Link>
  )
}

function MiniStat({
  label,
  value,
  warn = false,
  highlight = false,
}: {
  label: string
  value: number
  warn?: boolean
  highlight?: boolean
}) {
  return (
    <div className="rounded-lg bg-slate-50 px-2 py-1.5">
      <p className={`text-lg font-semibold ${warn ? 'text-amber-600' : highlight ? 'text-emerald-600' : ''}`}>
        {value}
      </p>
      <p className="text-xs text-muted-foreground">{label}</p>
    </div>
  )
}
