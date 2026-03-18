import { useMemo, useState } from 'react'
import { useOutletContext } from 'react-router'
import { BookOpen, Clock, Loader2, MessageCircle, Wrench } from 'lucide-react'
import type { LearnerContext } from '../../shells/LearnerShell'
import { PageContainer } from '../../components/shell/PageContainer'
import { CardSkeleton } from '@/components/ui/skeleton'
import { ErrorBanner } from '@/components/ui/error-banner'
import { Button } from '../../components/ui/button'
import { formatTimestamp } from '../../lib/formatters'
import { learnerContentType, learnerStage } from '../../lib/copy'
import type {
  LearnerGenerationHistoryEntry,
  LearnerSocraticSessionHistoryEntry,
  LearnerRemediationSessionHistoryEntry,
} from '../../types'

// ---------------------------------------------------------------------------
// Timeline construction
// ---------------------------------------------------------------------------

interface TimelineEntry {
  id: string
  type: 'lesson' | 'check' | 'practice'
  title: string
  detail: string
  stage: string
  timestamp: string
}

function buildTimeline(
  generations: LearnerGenerationHistoryEntry[],
  socratic: LearnerSocraticSessionHistoryEntry[],
  remediation: LearnerRemediationSessionHistoryEntry[],
): TimelineEntry[] {
  const entries: TimelineEntry[] = []

  for (const g of generations) {
    entries.push({
      id: g.generation_id,
      type: 'lesson',
      title: learnerContentType(g.content_type),
      detail: g.rationale ?? 'Lesson completed',
      stage: g.target_stage,
      timestamp: g.created_at,
    })
  }

  for (const s of socratic) {
    entries.push({
      id: s.session_id,
      type: 'check',
      title: 'Understanding check',
      detail: s.rationale ?? `${s.turn_count} turn${s.turn_count === 1 ? '' : 's'}`,
      stage: s.next_step?.target_stage ?? '',
      timestamp: s.created_at,
    })
  }

  for (const r of remediation) {
    entries.push({
      id: r.session_id,
      type: 'practice',
      title: 'Practice session',
      detail: r.progression_rationale ?? `${r.completed_step_count} of ${r.step_count} steps`,
      stage: r.next_step?.target_stage ?? '',
      timestamp: r.created_at,
    })
  }

  entries.sort((a, b) => (b.timestamp > a.timestamp ? 1 : -1))
  return entries
}

// ---------------------------------------------------------------------------
// Type filter config
// ---------------------------------------------------------------------------

type FilterType = 'all' | 'lesson' | 'check' | 'practice'

const filterTabs: { key: FilterType; label: string; activeClass: string; dotClass: string }[] = [
  { key: 'all', label: 'All', activeClass: 'bg-slate-700 text-white', dotClass: '' },
  { key: 'lesson', label: 'Lessons', activeClass: 'bg-blue-100 text-blue-700', dotClass: 'bg-blue-500' },
  { key: 'check', label: 'Checks', activeClass: 'bg-violet-100 text-violet-700', dotClass: 'bg-violet-500' },
  { key: 'practice', label: 'Practice', activeClass: 'bg-amber-100 text-amber-700', dotClass: 'bg-amber-500' },
]

const typeConfig = {
  lesson: { icon: BookOpen, bgClass: 'bg-blue-100 text-blue-600' },
  check: { icon: MessageCircle, bgClass: 'bg-violet-100 text-violet-600' },
  practice: { icon: Wrench, bgClass: 'bg-amber-100 text-amber-600' },
} as const

export function History() {
  const {
    generationHistory,
    socraticHistory,
    remediationHistory,
    hasMoreHistory,
    loadingMore,
    loadMoreHistory,
    loading,
    error,
  } = useOutletContext<LearnerContext>()

  const [filter, setFilter] = useState<FilterType>('all')

  const timeline = useMemo(
    () => buildTimeline(generationHistory, socraticHistory, remediationHistory),
    [generationHistory, socraticHistory, remediationHistory],
  )

  const typeCounts = useMemo(() => {
    const counts: Record<string, number> = { lesson: 0, check: 0, practice: 0 }
    for (const entry of timeline) {
      counts[entry.type] = (counts[entry.type] ?? 0) + 1
    }
    return counts
  }, [timeline])

  const filtered = useMemo(
    () => (filter === 'all' ? timeline : timeline.filter((e) => e.type === filter)),
    [timeline, filter],
  )

  return (
    <PageContainer size="narrow" className="flex flex-col gap-6 py-4">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">History</h1>
        <p className="mt-1 text-muted-foreground">Review your recent learning activities.</p>
      </header>

      <ErrorBanner message={error} />

      {/* Type filter tabs */}
      {timeline.length > 0 && (
        <div className="flex gap-2" role="tablist" aria-label="Filter by type">
          {filterTabs.map((tab) => {
            const isActive = filter === tab.key
            const count = tab.key === 'all' ? timeline.length : typeCounts[tab.key] ?? 0
            return (
              <button
                key={tab.key}
                role="tab"
                aria-selected={isActive}
                onClick={() => setFilter(tab.key)}
                className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                  isActive ? tab.activeClass : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
                }`}
              >
                {tab.dotClass && (
                  <span className={`h-2 w-2 rounded-full ${tab.dotClass}`} />
                )}
                {tab.label}
                <span className={`ml-0.5 text-xs ${isActive ? 'opacity-80' : 'opacity-60'}`}>
                  {count}
                </span>
              </button>
            )
          })}
        </div>
      )}

      {loading && timeline.length === 0 ? (
        <div className="flex flex-col gap-3">
          <CardSkeleton lines={2} />
          <CardSkeleton lines={2} />
          <CardSkeleton lines={2} />
        </div>
      ) : timeline.length === 0 ? (
        <div className="rounded-xl border bg-white p-8 text-center text-muted-foreground">
          <Clock className="mx-auto h-8 w-8 mb-2" />
          <p>No activities yet. Start a lesson to see your history here.</p>
        </div>
      ) : filtered.length === 0 ? (
        <div className="rounded-xl border bg-white p-8 text-center text-muted-foreground">
          <Clock className="mx-auto h-8 w-8 mb-2" />
          <p>No {filter === 'lesson' ? 'lessons' : filter === 'check' ? 'checks' : 'practice sessions'} yet.</p>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {filtered.map((entry) => {
            const cfg = typeConfig[entry.type]
            const Icon = cfg.icon
            return (
              <article key={entry.id} className="flex items-start gap-4 rounded-xl border bg-white p-4 shadow-sm">
                <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${cfg.bgClass}`}>
                  <Icon className="h-4 w-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-baseline justify-between gap-2">
                    <p className="font-medium">{entry.title}</p>
                    <time className="shrink-0 text-xs text-muted-foreground">
                      {formatTimestamp(entry.timestamp)}
                    </time>
                  </div>
                  <p className="mt-0.5 text-sm text-muted-foreground truncate">{entry.detail}</p>
                  {entry.stage && (
                    <p className="mt-1 text-xs text-muted-foreground">{learnerStage(entry.stage)}</p>
                  )}
                </div>
              </article>
            )
          })}

          {hasMoreHistory && (
            <div className="flex justify-center pt-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => void loadMoreHistory()}
                disabled={loadingMore}
              >
                {loadingMore ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Loading...
                  </>
                ) : (
                  'Load more'
                )}
              </Button>
            </div>
          )}
        </div>
      )}
    </PageContainer>
  )
}
