import { useOutletContext } from 'react-router'
import { BookOpen, Clock, MessageCircle, Wrench } from 'lucide-react'
import type { LearnerContext } from '../../shells/LearnerShell'
import { PageContainer } from '../../components/shell/PageContainer'
import { formatTimestamp } from '../../lib/formatters'
import { learnerContentType, learnerStage } from '../../lib/copy'
import type {
  LearnerGenerationHistoryEntry,
  LearnerSocraticSessionHistoryEntry,
  LearnerRemediationSessionHistoryEntry,
} from '../../types'

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

const typeConfig = {
  lesson: { icon: BookOpen, bgClass: 'bg-blue-100 text-blue-600' },
  check: { icon: MessageCircle, bgClass: 'bg-violet-100 text-violet-600' },
  practice: { icon: Wrench, bgClass: 'bg-amber-100 text-amber-600' },
} as const

export function History() {
  const { generationHistory, socraticHistory, remediationHistory } = useOutletContext<LearnerContext>()

  const timeline = buildTimeline(generationHistory, socraticHistory, remediationHistory)

  return (
    <PageContainer size="narrow" className="flex flex-col gap-6 py-4">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">History</h1>
        <p className="mt-1 text-muted-foreground">Review your recent learning activities.</p>
      </header>

      {timeline.length === 0 ? (
        <div className="rounded-xl border bg-white p-8 text-center text-muted-foreground">
          <Clock className="mx-auto h-8 w-8 mb-2" />
          <p>No activities yet. Start a lesson to see your history here.</p>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {timeline.map((entry) => {
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
        </div>
      )}
    </PageContainer>
  )
}
