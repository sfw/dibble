import { useEffect, useMemo, useState } from 'react'
import { Link, useOutletContext } from 'react-router'
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  ArrowUpDown,
  BarChart3,
  BookOpen,
  ChevronDown,
  GraduationCap,
  Layers,
  MessageCircle,
  TrendingUp,
  Users,
  Wrench,
} from 'lucide-react'
import type { TeacherContext } from '../../shells/TeacherShell'
import { PageContainer } from '../../components/shell/PageContainer'
import { PageSkeleton } from '@/components/ui/skeleton'
import { ErrorBanner } from '@/components/ui/error-banner'
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

function groupByKey<T>(items: T[], keyFn: (item: T) => string): Record<string, T[]> {
  const groups: Record<string, T[]> = {}
  for (const item of items) {
    const key = keyFn(item)
    ;(groups[key] ??= []).push(item)
  }
  return groups
}

function sumBy<T>(items: T[], valueFn: (item: T) => number): number {
  return items.reduce((sum, item) => sum + valueFn(item), 0)
}

// ---------------------------------------------------------------------------
// Sorting
// ---------------------------------------------------------------------------

type SortField = 'student_id' | 'stage' | 'mastery' | 'engagement' | 'frustration' | 'attention'
type SortDir = 'asc' | 'desc'

const signalWeight: Record<string, number> = { none: 0, low: 1, medium: 2, high: 3 }

function sortLearners(learners: TeacherLearnerCard[], field: SortField, dir: SortDir): TeacherLearnerCard[] {
  const sorted = [...learners].sort((a, b) => {
    let cmp = 0
    switch (field) {
      case 'student_id':
        cmp = a.student_id.localeCompare(b.student_id)
        break
      case 'stage':
        cmp = stageOrder.indexOf(a.curriculum_progression.current_stage) - stageOrder.indexOf(b.curriculum_progression.current_stage)
        break
      case 'mastery':
        cmp = a.curriculum_progression.mastered_resource_ratio - b.curriculum_progression.mastered_resource_ratio
        break
      case 'engagement':
        cmp = (signalWeight[a.engagement] ?? 0) - (signalWeight[b.engagement] ?? 0)
        break
      case 'frustration':
        cmp = (signalWeight[a.frustration] ?? 0) - (signalWeight[b.frustration] ?? 0)
        break
      case 'attention':
        cmp = (signalWeight[a.attention_level] ?? 0) - (signalWeight[b.attention_level] ?? 0)
        break
    }
    return cmp
  })
  return dir === 'desc' ? sorted.reverse() : sorted
}

// ---------------------------------------------------------------------------
// Attention reason labels
// ---------------------------------------------------------------------------

const attentionReasonLabels: Record<string, string> = {
  teacher_intervention_available: 'Intervention ready',
  blocked_by_prerequisites: 'Blocked by prerequisites',
  high_frustration: 'High frustration',
  low_engagement_risk: 'Low engagement',
  repeated_struggle: 'Repeated struggle',
  support_dependent: 'Support dependent',
}

function attentionReasonLabel(reason: string): string {
  return attentionReasonLabels[reason] ?? reason.replace(/_/g, ' ')
}

// ---------------------------------------------------------------------------
// Reports view
// ---------------------------------------------------------------------------

export function Reports() {
  const { classrooms, classroom, loading, error, loadClassroom } = useOutletContext<TeacherContext>()
  const learners = useMemo(() => classroom.learners ?? [], [classroom.learners])

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

  // Class average mastery
  const classAverageMastery = learners.length > 0
    ? learners.reduce((sum, l) => sum + l.curriculum_progression.mastered_resource_ratio, 0) / learners.length
    : 0

  // Sorting state for learner table
  const [sortField, setSortField] = useState<SortField>('attention')
  const [sortDir, setSortDir] = useState<SortDir>('desc')

  function toggleSort(field: SortField) {
    if (sortField === field) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortField(field)
      setSortDir('desc')
    }
  }

  const sortedLearners = useMemo(
    () => sortLearners(learners, sortField, sortDir),
    [learners, sortField, sortDir],
  )

  if (loading && classrooms.length === 0) {
    return (
      <PageContainer size="wide" className="py-4">
        <PageSkeleton cards={4} />
      </PageContainer>
    )
  }

  return (
    <PageContainer size="wide" className="flex flex-col gap-8 py-4">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Reports</h1>
        <p className="mt-1 text-muted-foreground">
          Class progress, learner distribution, and activity across your classrooms.
        </p>
      </header>

      <ErrorBanner message={error} />

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

      {/* Classroom selector for deep-dive */}
      {classrooms.length > 1 && (
        <ClassroomSelector
          classrooms={classrooms}
          selectedId={classroom.classroom_id}
          onSelect={(id) => void loadClassroom(id)}
          loading={loading}
        />
      )}

      {/* Selected classroom deep-dive */}
      {learners.length > 0 && (
        <>
          <div className="flex items-center gap-3">
            <h2 className="font-semibold">{classroom.title} — learner breakdown</h2>
            <Badge variant="outline">{learners.length} learners</Badge>
          </div>

          {/* Class average mastery banner */}
          <ClassMasteryBanner average={classAverageMastery} learners={learners} />

          <div className="grid gap-6 lg:grid-cols-2">
            <StageDistribution learners={learners} />
            <MasteryDistribution learners={learners} />
            <EngagementOverview learners={learners} />
            <ActivitySummary learners={learners} />
            <ResourceMastery learners={learners} />
            <AttentionSummary learners={learners} />
          </div>

          {/* Per-learner drill-down table */}
          <section className="flex flex-col gap-4">
            <h2 className="font-semibold">All learners</h2>
            <div className="overflow-x-auto rounded-xl border bg-white shadow-sm">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-slate-50 text-left">
                    <SortableHeader field="student_id" label="Learner" current={sortField} dir={sortDir} onSort={toggleSort} />
                    <SortableHeader field="stage" label="Stage" current={sortField} dir={sortDir} onSort={toggleSort} />
                    <SortableHeader field="mastery" label="Mastery" current={sortField} dir={sortDir} onSort={toggleSort} />
                    <SortableHeader field="engagement" label="Engagement" current={sortField} dir={sortDir} onSort={toggleSort} />
                    <SortableHeader field="frustration" label="Frustration" current={sortField} dir={sortDir} onSort={toggleSort} />
                    <SortableHeader field="attention" label="Attention" current={sortField} dir={sortDir} onSort={toggleSort} />
                    <th className="px-4 py-3 font-medium text-muted-foreground">Reasons</th>
                    <th className="px-4 py-3 font-medium text-muted-foreground" />
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {sortedLearners.map((learner) => (
                    <LearnerRow key={learner.student_id} learner={learner} />
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </PageContainer>
  )
}

// ---------------------------------------------------------------------------
// Class mastery banner
// ---------------------------------------------------------------------------

function ClassMasteryBanner({ average, learners }: { average: number; learners: TeacherLearnerCard[] }) {
  const avgPercent = Math.round(average * 100)
  const atRisk = learners.filter((l) => l.curriculum_progression.mastered_resource_ratio < 0.25).length
  const onTrack = learners.filter((l) => l.curriculum_progression.mastered_resource_ratio >= 0.5).length

  return (
    <div className="flex items-center gap-6 rounded-xl border bg-white p-5 shadow-sm">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-blue-100 text-blue-600">
          <GraduationCap className="h-5 w-5" />
        </div>
        <div>
          <p className="text-2xl font-semibold">{avgPercent}%</p>
          <p className="text-sm text-muted-foreground">Class average mastery</p>
        </div>
      </div>
      <div className="hidden sm:flex items-center gap-6 ml-auto text-sm">
        <div className="text-center">
          <p className="font-semibold text-emerald-600">{onTrack}</p>
          <p className="text-muted-foreground">On track (≥50%)</p>
        </div>
        <div className="text-center">
          <p className={`font-semibold ${atRisk > 0 ? 'text-red-600' : ''}`}>{atRisk}</p>
          <p className="text-muted-foreground">At risk (&lt;25%)</p>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Mastery distribution histogram
// ---------------------------------------------------------------------------

const masteryBuckets = [
  { label: '0–25%', min: 0, max: 0.25, color: 'bg-red-400' },
  { label: '25–50%', min: 0.25, max: 0.5, color: 'bg-amber-400' },
  { label: '50–75%', min: 0.5, max: 0.75, color: 'bg-blue-400' },
  { label: '75–100%', min: 0.75, max: 1.01, color: 'bg-emerald-400' },
]

function MasteryDistribution({ learners }: { learners: TeacherLearnerCard[] }) {
  const bucketCounts = masteryBuckets.map((bucket) => ({
    ...bucket,
    count: learners.filter((l) => {
      const r = l.curriculum_progression.mastered_resource_ratio
      return r >= bucket.min && r < bucket.max
    }).length,
  }))

  const maxCount = Math.max(...bucketCounts.map((b) => b.count), 1)

  return (
    <section className="rounded-xl border bg-white p-6 shadow-sm">
      <div className="flex items-center gap-3 mb-4">
        <TrendingUp className="h-5 w-5 text-muted-foreground" />
        <h3 className="font-semibold">Mastery distribution</h3>
      </div>
      <div className="flex items-end gap-3 h-32">
        {bucketCounts.map((bucket) => {
          const heightPct = (bucket.count / maxCount) * 100
          return (
            <div key={bucket.label} className="flex-1 flex flex-col items-center gap-1">
              <span className="text-sm font-semibold">{bucket.count}</span>
              <div className="w-full flex items-end" style={{ height: '80px' }}>
                <div
                  className={`w-full rounded-t-md transition-all ${bucket.color}`}
                  style={{ height: `${Math.max(heightPct, 4)}%` }}
                />
              </div>
              <span className="text-xs text-muted-foreground">{bucket.label}</span>
            </div>
          )
        })}
      </div>
    </section>
  )
}

// ---------------------------------------------------------------------------
// Resource mastery breakdown
// ---------------------------------------------------------------------------

interface ResourceMasteryRow {
  title: string
  resourceId: string
  avgMastery: number
  learnerCount: number
  masteredCount: number
}

function ResourceMastery({ learners }: { learners: TeacherLearnerCard[] }) {
  const resources = useMemo(() => {
    // Collect all resources across learners and aggregate mastery
    const resourceMap = new Map<string, { title: string; masterySum: number; count: number; masteredCount: number }>()

    for (const learner of learners) {
      const prog = learner.curriculum_progression
      const allResources = [
        prog.current_resource,
        prog.next_resource,
        ...prog.blocked_resources,
        ...prog.ready_resources,
      ].filter(Boolean)

      for (const resource of allResources) {
        if (!resource) continue
        const existing = resourceMap.get(resource.resource_id)
        if (existing) {
          existing.masterySum += resource.mastery_ratio
          existing.count += 1
          if (resource.mastery_ratio >= 0.8) existing.masteredCount += 1
        } else {
          resourceMap.set(resource.resource_id, {
            title: resource.title,
            masterySum: resource.mastery_ratio,
            count: 1,
            masteredCount: resource.mastery_ratio >= 0.8 ? 1 : 0,
          })
        }
      }
    }

    const rows: ResourceMasteryRow[] = []
    for (const [resourceId, data] of resourceMap) {
      rows.push({
        resourceId,
        title: data.title,
        avgMastery: data.masterySum / data.count,
        learnerCount: data.count,
        masteredCount: data.masteredCount,
      })
    }

    // Sort by average mastery ascending (weakest first)
    return rows.sort((a, b) => a.avgMastery - b.avgMastery)
  }, [learners])

  if (resources.length === 0) return null

  return (
    <section className="rounded-xl border bg-white p-6 shadow-sm lg:col-span-2">
      <div className="flex items-center gap-3 mb-4">
        <BookOpen className="h-5 w-5 text-muted-foreground" />
        <h3 className="font-semibold">Resource mastery</h3>
        <span className="text-xs text-muted-foreground ml-auto">Weakest first</span>
      </div>
      <div className="space-y-2">
        {resources.slice(0, 8).map((resource) => {
          const pct = Math.round(resource.avgMastery * 100)
          const barColor = pct < 25 ? 'bg-red-400' : pct < 50 ? 'bg-amber-400' : pct < 75 ? 'bg-blue-400' : 'bg-emerald-400'
          return (
            <div key={resource.resourceId} className="flex items-center gap-3">
              <span className="w-48 truncate text-sm font-medium" title={resource.title}>
                {resource.title}
              </span>
              <div className="flex-1">
                <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                  <div
                    className={`h-full rounded-full transition-all ${barColor}`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>
              <span className="w-12 text-right text-sm font-medium">{pct}%</span>
              <span className="w-20 text-right text-xs text-muted-foreground">
                {resource.masteredCount}/{resource.learnerCount} mastered
              </span>
            </div>
          )
        })}
      </div>
    </section>
  )
}

// ---------------------------------------------------------------------------
// Classroom selector
// ---------------------------------------------------------------------------

function ClassroomSelector({
  classrooms,
  selectedId,
  onSelect,
  loading,
}: {
  classrooms: TeacherClassroomOverview[]
  selectedId: string
  onSelect: (id: string) => void
  loading: boolean
}) {
  return (
    <div className="flex items-center gap-3">
      <label className="text-sm font-medium text-muted-foreground">Deep-dive into:</label>
      <div className="relative">
        <select
          value={selectedId}
          onChange={(e) => onSelect(e.target.value)}
          disabled={loading}
          className="appearance-none rounded-lg border bg-white py-2 pl-3 pr-8 text-sm font-medium shadow-sm transition-colors hover:border-emerald-300 focus:border-emerald-400 focus:outline-none focus:ring-1 focus:ring-emerald-400 disabled:opacity-50"
        >
          {classrooms.map((c) => (
            <option key={c.classroom_id} value={c.classroom_id}>
              {c.title}
            </option>
          ))}
        </select>
        <ChevronDown className="pointer-events-none absolute right-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Sortable table header
// ---------------------------------------------------------------------------

function SortableHeader({
  field,
  label,
  current,
  dir,
  onSort,
}: {
  field: SortField
  label: string
  current: SortField
  dir: SortDir
  onSort: (field: SortField) => void
}) {
  const isActive = current === field
  return (
    <th className="px-4 py-3">
      <button
        onClick={() => onSort(field)}
        className={`flex items-center gap-1 font-medium transition-colors ${
          isActive ? 'text-emerald-700' : 'text-muted-foreground hover:text-foreground'
        }`}
      >
        {label}
        <ArrowUpDown className="h-3 w-3" />
        {isActive && <span className="text-xs">{dir === 'asc' ? '↑' : '↓'}</span>}
      </button>
    </th>
  )
}

// ---------------------------------------------------------------------------
// Learner table row
// ---------------------------------------------------------------------------

const signalBadgeColors: Record<string, string> = {
  none: 'bg-slate-100 text-slate-600',
  low: 'bg-emerald-100 text-emerald-700',
  medium: 'bg-amber-100 text-amber-700',
  high: 'bg-red-100 text-red-700',
}

function LearnerRow({ learner }: { learner: TeacherLearnerCard }) {
  const prog = learner.curriculum_progression
  return (
    <tr className="transition-colors hover:bg-slate-50">
      <td className="px-4 py-3 font-medium">{learner.student_id}</td>
      <td className="px-4 py-3">
        <span className={`inline-block rounded-md px-2 py-0.5 text-xs font-medium ${stageColors[prog.current_stage] ?? 'bg-slate-100 text-slate-600'}`}>
          {teacherStage(prog.current_stage)}
        </span>
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-2">
          <div className="h-1.5 w-16 overflow-hidden rounded-full bg-slate-100">
            <div
              className="h-full rounded-full bg-blue-400 transition-all"
              style={{ width: `${Math.round(prog.mastered_resource_ratio * 100)}%` }}
            />
          </div>
          <span className="text-xs text-muted-foreground">{formatPercent(prog.mastered_resource_ratio)}</span>
        </div>
      </td>
      <td className="px-4 py-3">
        <span className={`inline-block rounded-md px-2 py-0.5 text-xs font-medium ${signalBadgeColors[learner.engagement] ?? ''}`}>
          {learner.engagement}
        </span>
      </td>
      <td className="px-4 py-3">
        <span className={`inline-block rounded-md px-2 py-0.5 text-xs font-medium ${signalBadgeColors[learner.frustration] ?? ''}`}>
          {learner.frustration}
        </span>
      </td>
      <td className="px-4 py-3">
        <Badge variant={attentionBadgeVariants[learner.attention_level] ?? 'outline'}>
          {teacherAttention(learner.attention_level)}
        </Badge>
      </td>
      <td className="px-4 py-3">
        {learner.attention_reasons.length > 0 ? (
          <div className="flex flex-wrap gap-1">
            {learner.attention_reasons.map((reason) => (
              <span key={reason} className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-muted-foreground">
                {attentionReasonLabel(reason)}
              </span>
            ))}
          </div>
        ) : (
          <span className="text-xs text-muted-foreground">—</span>
        )}
      </td>
      <td className="px-4 py-3">
        <Link
          to={`/teacher/learners/${learner.student_id}`}
          className="text-xs font-medium text-emerald-600 hover:text-emerald-700"
        >
          View
        </Link>
      </td>
    </tr>
  )
}

// ---------------------------------------------------------------------------
// Summary card
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
  const groups = groupByKey(learners, (l) => l.attention_level)

  const [expanded, setExpanded] = useState<string | null>(null)

  return (
    <section className="rounded-xl border bg-white p-6 shadow-sm">
      <div className="flex items-center gap-3 mb-4">
        <AlertTriangle className="h-5 w-5 text-muted-foreground" />
        <h3 className="font-semibold">Attention levels</h3>
      </div>
      <div className="space-y-2">
        {attentionOrder.map((level) => {
          const count = counts[level] ?? 0
          const levelLearners = groups[level] ?? []
          const isExpanded = expanded === level && count > 0
          return (
            <div key={level}>
              <button
                onClick={() => count > 0 && setExpanded(isExpanded ? null : level)}
                disabled={count === 0}
                className="flex w-full items-center justify-between rounded-lg bg-slate-50 px-4 py-2.5 transition-colors hover:bg-slate-100 disabled:cursor-default disabled:hover:bg-slate-50"
              >
                <div className="flex items-center gap-3">
                  <Badge variant={attentionBadgeVariants[level] ?? 'outline'}>
                    {teacherAttention(level)}
                  </Badge>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold">{count}</span>
                  {count > 0 && (
                    <ChevronDown className={`h-4 w-4 text-muted-foreground transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
                  )}
                </div>
              </button>
              {isExpanded && (
                <div className="ml-4 mt-1 space-y-1 pb-1">
                  {levelLearners.map((l) => (
                    <div key={l.student_id} className="flex items-center justify-between rounded-md px-3 py-1.5 text-sm">
                      <Link
                        to={`/teacher/learners/${l.student_id}`}
                        className="font-medium text-emerald-600 hover:text-emerald-700"
                      >
                        {l.student_id}
                      </Link>
                      {l.attention_reasons.length > 0 && (
                        <div className="flex gap-1">
                          {l.attention_reasons.map((r) => (
                            <span key={r} className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-muted-foreground">
                              {attentionReasonLabel(r)}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </section>
  )
}
