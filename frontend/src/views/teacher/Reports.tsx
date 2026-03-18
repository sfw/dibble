import { useEffect } from 'react'
import { Link, useOutletContext } from 'react-router'
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BarChart3,
  BookOpen,
  Layers,
  MessageCircle,
  Users,
  Wrench,
} from 'lucide-react'
import type { TeacherContext } from '../../shells/TeacherShell'
import { PageContainer } from '../../components/shell/PageContainer'
import { Badge } from '@/components/ui/badge'
import { teacherStage, teacherAttention } from '../../lib/copy'
import { formatPercent } from '../../lib/formatters'
import type { TeacherClassroomOverview, TeacherLearnerCard } from '../../types'

// ---------------------------------------------------------------------------
// Aggregation helpers
// ---------------------------------------------------------------------------

function countByKey<T>(items: T[], keyFn: (item: T) => string): Record<string, number> {
  const counts: Record<string, number> = {}
  for (const item of items) {
    const key = keyFn(item)
    counts[key] = (counts[key] ?? 0) + 1
  }
  return counts
}

function sumBy<T>(items: T[], valueFn: (item: T) => number): number {
  return items.reduce((sum, item) => sum + valueFn(item), 0)
}

// ---------------------------------------------------------------------------
// Reports view
// ---------------------------------------------------------------------------

export function Reports() {
  const { classrooms, classroom, loading, loadClassroom } = useOutletContext<TeacherContext>()
  const learners = classroom.learners ?? []

  // Auto-load the first classroom if none is selected yet
  useEffect(() => {
    if (!classroom.classroom_id && classrooms.length > 0 && !loading) {
      void loadClassroom(classrooms[0].classroom_id)
    }
  }, [classroom.classroom_id, classrooms, loading, loadClassroom])

  const totalLearners = classrooms.reduce((sum, c) => sum + c.learner_count, 0)
  const totalActive = classrooms.reduce((sum, c) => sum + c.active_flow_count, 0)
  const totalBlocked = classrooms.reduce((sum, c) => sum + c.blocked_progression_count, 0)
  const totalAttention = classrooms.reduce((sum, c) => sum + c.attention_needed_count, 0)
  const totalInterventions = classrooms.reduce((sum, c) => sum + c.intervention_available_count, 0)

  return (
    <PageContainer size="wide" className="flex flex-col gap-8 py-4">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Reports</h1>
        <p className="mt-1 text-muted-foreground">
          Class progress, learner distribution, and activity across your classrooms.
        </p>
      </header>

      {loading && classrooms.length === 0 && (
        <p className="text-center text-muted-foreground py-12">Loading report data...</p>
      )}

      {/* Top-line summary */}
      <div className="grid gap-4 sm:grid-cols-3 lg:grid-cols-5">
        <SummaryCard icon={Users} label="Total learners" value={totalLearners} iconClass="text-slate-600 bg-slate-100" />
        <SummaryCard icon={Activity} label="Active now" value={totalActive} iconClass="text-emerald-600 bg-emerald-100" />
        <SummaryCard icon={AlertTriangle} label="Need attention" value={totalAttention} iconClass="text-amber-600 bg-amber-100" />
        <SummaryCard icon={Layers} label="Blocked" value={totalBlocked} iconClass="text-red-600 bg-red-100" />
        <SummaryCard icon={BarChart3} label="Interventions" value={totalInterventions} iconClass="text-blue-600 bg-blue-100" />
      </div>

      {/* Per-classroom progress */}
      {classrooms.length > 0 && (
        <section className="flex flex-col gap-4">
          <h2 className="font-semibold">Classroom progress</h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {classrooms.map((c) => (
              <ClassroomProgressCard key={c.classroom_id} classroom={c} />
            ))}
          </div>
        </section>
      )}

      {/* Selected classroom deep-dive */}
      {learners.length > 0 && (
        <>
          <div className="flex items-center gap-3">
            <h2 className="font-semibold">{classroom.title} — learner breakdown</h2>
            <Badge variant="outline">{learners.length} learners</Badge>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <StageDistribution learners={learners} />
            <EngagementOverview learners={learners} />
            <ActivitySummary learners={learners} />
            <AttentionSummary learners={learners} />
          </div>
        </>
      )}
    </PageContainer>
  )
}

// ---------------------------------------------------------------------------
// Summary card (matches Dashboard pattern)
// ---------------------------------------------------------------------------

function SummaryCard({
  icon: Icon,
  label,
  value,
  iconClass,
}: {
  icon: typeof Users
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

// ---------------------------------------------------------------------------
// Per-classroom progress card
// ---------------------------------------------------------------------------

function ClassroomProgressCard({ classroom }: { classroom: TeacherClassroomOverview }) {
  const total = classroom.learner_count || 1
  const activeRate = classroom.active_flow_count / total
  const blockedRate = classroom.blocked_progression_count / total
  const attentionRate = classroom.attention_needed_count / total

  return (
    <Link
      to={`/teacher/classrooms/${classroom.classroom_id}`}
      className="group flex flex-col gap-3 rounded-xl border bg-white p-5 shadow-sm transition-colors hover:border-emerald-300"
    >
      <div className="flex items-start justify-between">
        <div>
          <h3 className="font-semibold group-hover:text-emerald-700">{classroom.title}</h3>
          <p className="text-sm text-muted-foreground">
            {classroom.learner_count} learners
            {classroom.grade_level ? ` · Grade ${classroom.grade_level}` : ''}
          </p>
        </div>
        <ArrowRight className="h-4 w-4 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
      </div>

      {/* Stacked bar */}
      <div className="flex h-2 overflow-hidden rounded-full bg-slate-100">
        <div
          className="bg-emerald-500 transition-all"
          style={{ width: `${activeRate * 100}%` }}
        />
        <div
          className="bg-amber-400 transition-all"
          style={{ width: `${attentionRate * 100}%` }}
        />
        <div
          className="bg-red-400 transition-all"
          style={{ width: `${blockedRate * 100}%` }}
        />
      </div>

      <div className="grid grid-cols-3 gap-2 text-center text-xs">
        <div>
          <p className="font-semibold text-emerald-600">{formatPercent(activeRate)}</p>
          <p className="text-muted-foreground">Active</p>
        </div>
        <div>
          <p className={`font-semibold ${attentionRate > 0 ? 'text-amber-600' : ''}`}>{formatPercent(attentionRate)}</p>
          <p className="text-muted-foreground">Attention</p>
        </div>
        <div>
          <p className={`font-semibold ${blockedRate > 0 ? 'text-red-600' : ''}`}>{formatPercent(blockedRate)}</p>
          <p className="text-muted-foreground">Blocked</p>
        </div>
      </div>
    </Link>
  )
}

// ---------------------------------------------------------------------------
// Stage distribution
// ---------------------------------------------------------------------------

const stageOrder = ['repair', 'bridge', 'target', 'transfer', 'mastered']
const stageColors: Record<string, string> = {
  repair: 'bg-red-100 text-red-700',
  bridge: 'bg-amber-100 text-amber-700',
  target: 'bg-blue-100 text-blue-700',
  transfer: 'bg-emerald-100 text-emerald-700',
  mastered: 'bg-slate-100 text-slate-600',
}
const stageBarColors: Record<string, string> = {
  repair: 'bg-red-400',
  bridge: 'bg-amber-400',
  target: 'bg-blue-400',
  transfer: 'bg-emerald-400',
  mastered: 'bg-slate-300',
}

function StageDistribution({ learners }: { learners: TeacherLearnerCard[] }) {
  const counts = countByKey(learners, (l) => l.curriculum_progression.current_stage)
  const total = learners.length || 1

  return (
    <section className="rounded-xl border bg-white p-6 shadow-sm">
      <div className="flex items-center gap-3 mb-4">
        <Layers className="h-5 w-5 text-muted-foreground" />
        <h3 className="font-semibold">Stage distribution</h3>
      </div>
      <div className="space-y-3">
        {stageOrder.map((stage) => {
          const count = counts[stage] ?? 0
          const pct = count / total
          return (
            <div key={stage} className="flex items-center gap-3">
              <span className={`rounded-md px-2 py-0.5 text-xs font-medium ${stageColors[stage] ?? 'bg-slate-100 text-slate-600'}`}>
                {teacherStage(stage)}
              </span>
              <div className="flex-1">
                <div className="flex h-2 overflow-hidden rounded-full bg-slate-100">
                  <div
                    className={`${stageBarColors[stage] ?? 'bg-slate-300'} transition-all`}
                    style={{ width: `${pct * 100}%` }}
                  />
                </div>
              </div>
              <span className="w-12 text-right text-sm font-medium">{count}</span>
              <span className="w-10 text-right text-xs text-muted-foreground">{formatPercent(pct)}</span>
            </div>
          )
        })}
      </div>
    </section>
  )
}

// ---------------------------------------------------------------------------
// Engagement & frustration overview
// ---------------------------------------------------------------------------

const signalLevels = ['none', 'low', 'medium', 'high'] as const
const engagementColors: Record<string, string> = {
  none: 'bg-slate-200',
  low: 'bg-amber-300',
  medium: 'bg-emerald-300',
  high: 'bg-emerald-500',
}
const frustrationColors: Record<string, string> = {
  none: 'bg-slate-200',
  low: 'bg-emerald-300',
  medium: 'bg-amber-300',
  high: 'bg-red-400',
}

function EngagementOverview({ learners }: { learners: TeacherLearnerCard[] }) {
  const engagementCounts = countByKey(learners, (l) => l.engagement)
  const frustrationCounts = countByKey(learners, (l) => l.frustration)
  const total = learners.length || 1

  return (
    <section className="rounded-xl border bg-white p-6 shadow-sm">
      <div className="flex items-center gap-3 mb-4">
        <Activity className="h-5 w-5 text-muted-foreground" />
        <h3 className="font-semibold">Engagement & frustration</h3>
      </div>
      <div className="space-y-5">
        {/* Engagement row */}
        <div>
          <p className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">Engagement</p>
          <div className="flex h-3 overflow-hidden rounded-full bg-slate-100">
            {signalLevels.map((level) => {
              const count = engagementCounts[level] ?? 0
              return (
                <div
                  key={level}
                  className={`${engagementColors[level]} transition-all`}
                  style={{ width: `${(count / total) * 100}%` }}
                  title={`${level}: ${count}`}
                />
              )
            })}
          </div>
          <div className="mt-1.5 flex gap-4 text-xs text-muted-foreground">
            {signalLevels.map((level) => (
              <span key={level}>
                {level}: <strong className="text-foreground">{engagementCounts[level] ?? 0}</strong>
              </span>
            ))}
          </div>
        </div>

        {/* Frustration row */}
        <div>
          <p className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">Frustration</p>
          <div className="flex h-3 overflow-hidden rounded-full bg-slate-100">
            {signalLevels.map((level) => {
              const count = frustrationCounts[level] ?? 0
              return (
                <div
                  key={level}
                  className={`${frustrationColors[level]} transition-all`}
                  style={{ width: `${(count / total) * 100}%` }}
                  title={`${level}: ${count}`}
                />
              )
            })}
          </div>
          <div className="mt-1.5 flex gap-4 text-xs text-muted-foreground">
            {signalLevels.map((level) => (
              <span key={level}>
                {level}: <strong className="text-foreground">{frustrationCounts[level] ?? 0}</strong>
              </span>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}

// ---------------------------------------------------------------------------
// Activity summary
// ---------------------------------------------------------------------------

function ActivitySummary({ learners }: { learners: TeacherLearnerCard[] }) {
  const totalGenerations = sumBy(learners, (l) => l.recent_activity.generation_count)
  const totalObservations = sumBy(learners, (l) => l.recent_activity.observation_count)
  const totalSocratic = sumBy(learners, (l) => l.recent_activity.socratic_assessment_count)

  return (
    <section className="rounded-xl border bg-white p-6 shadow-sm">
      <div className="flex items-center gap-3 mb-4">
        <BarChart3 className="h-5 w-5 text-muted-foreground" />
        <h3 className="font-semibold">Recent activity</h3>
      </div>
      <div className="grid grid-cols-3 gap-4">
        <ActivityStat icon={BookOpen} label="Lessons generated" value={totalGenerations} color="text-blue-600 bg-blue-100" />
        <ActivityStat icon={Wrench} label="Observations" value={totalObservations} color="text-slate-600 bg-slate-100" />
        <ActivityStat icon={MessageCircle} label="Socratic checks" value={totalSocratic} color="text-emerald-600 bg-emerald-100" />
      </div>
    </section>
  )
}

function ActivityStat({
  icon: Icon,
  label,
  value,
  color,
}: {
  icon: typeof BookOpen
  label: string
  value: number
  color: string
}) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-lg bg-slate-50 px-3 py-4 text-center">
      <div className={`flex h-8 w-8 items-center justify-center rounded-lg ${color}`}>
        <Icon className="h-4 w-4" />
      </div>
      <p className="text-xl font-semibold">{value}</p>
      <p className="text-xs text-muted-foreground">{label}</p>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Attention summary
// ---------------------------------------------------------------------------

const attentionOrder = ['high', 'medium', 'low', 'none']
const attentionBadgeVariants: Record<string, 'destructive' | 'warning' | 'outline' | 'default'> = {
  high: 'destructive',
  medium: 'warning',
  low: 'outline',
  none: 'default',
}

function AttentionSummary({ learners }: { learners: TeacherLearnerCard[] }) {
  const counts = countByKey(learners, (l) => l.attention_level)

  return (
    <section className="rounded-xl border bg-white p-6 shadow-sm">
      <div className="flex items-center gap-3 mb-4">
        <AlertTriangle className="h-5 w-5 text-muted-foreground" />
        <h3 className="font-semibold">Attention levels</h3>
      </div>
      <div className="space-y-2">
        {attentionOrder.map((level) => {
          const count = counts[level] ?? 0
          return (
            <div key={level} className="flex items-center justify-between rounded-lg bg-slate-50 px-4 py-2.5">
              <div className="flex items-center gap-3">
                <Badge variant={attentionBadgeVariants[level] ?? 'outline'}>
                  {teacherAttention(level)}
                </Badge>
              </div>
              <span className="text-sm font-semibold">{count}</span>
            </div>
          )
        })}
      </div>
    </section>
  )
}
