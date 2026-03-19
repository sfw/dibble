import { useCallback, useMemo, useState } from 'react'
import { Link, useNavigate, useOutletContext, useParams } from 'react-router'
import {
  AlertTriangle,
  BookOpen,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Clock,
  Loader2,
  MessageCircle,
  Shield,
  Target,
  TrendingUp,
  Wrench,
  X,
  Zap,
} from 'lucide-react'
import type { TeacherContext } from '../../shells/TeacherShell'
import { PageContainer } from '../../components/shell/PageContainer'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { ContentBlock } from '../../components/content/ContentBlock'
import { useLearnerWorkspace } from '../../hooks/useLearnerWorkspace'
import { useLearnerContracts } from '../../hooks/useLearnerContracts'
import { getGeneratedContent } from '../../api'
import {
  teacherFlowType,
  teacherStage,
  teacherContinueAction,
  teacherArtifact,
  teacherProgressionAction,
  teacherRemediationPhase,
} from '../../lib/copy'
import { formatPercent, formatTimestamp, titleCase } from '../../lib/formatters'
import { asMessage } from '../../lib/formatters'
import type { DataSource } from '../../app/workspace'
import type {
  GeneratedContent,
  LearnerGenerationHistoryEntry,
  LearnerRemediationSessionHistoryEntry,
  LearnerSocraticSessionHistoryEntry,
} from '../../types'

// ---------------------------------------------------------------------------
// Unified timeline item
// ---------------------------------------------------------------------------

type TimelineEntryKind = 'generation' | 'socratic' | 'remediation'

interface TimelineEntry {
  kind: TimelineEntryKind
  id: string
  generationId: string | null
  timestamp: string
  generation?: LearnerGenerationHistoryEntry
  socratic?: LearnerSocraticSessionHistoryEntry
  remediation?: LearnerRemediationSessionHistoryEntry
}

function buildTimeline(
  generations: LearnerGenerationHistoryEntry[],
  socratic: LearnerSocraticSessionHistoryEntry[],
  remediation: LearnerRemediationSessionHistoryEntry[],
): TimelineEntry[] {
  const entries: TimelineEntry[] = []

  for (const g of generations) {
    entries.push({
      kind: 'generation',
      id: g.generation_id,
      generationId: g.generation_id,
      timestamp: g.created_at,
      generation: g,
    })
  }

  for (const s of socratic) {
    entries.push({
      kind: 'socratic',
      id: s.session_id,
      generationId: null,
      timestamp: s.created_at,
      socratic: s,
    })
  }

  for (const r of remediation) {
    entries.push({
      kind: 'remediation',
      id: r.session_id,
      generationId: r.latest_generation_id ?? null,
      timestamp: r.created_at,
      remediation: r,
    })
  }

  entries.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
  return entries
}

// ---------------------------------------------------------------------------
// Main view
// ---------------------------------------------------------------------------

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

  // Unified timeline
  const timeline = useMemo(
    () =>
      buildTimeline(
        contracts.generationHistory,
        contracts.socraticHistory,
        contracts.remediationHistory,
      ),
    [contracts.generationHistory, contracts.socraticHistory, contracts.remediationHistory],
  )

  // Artifact review state
  const [reviewContent, setReviewContent] = useState<GeneratedContent | null>(null)
  const [reviewLoading, setReviewLoading] = useState(false)
  const [reviewError, setReviewError] = useState('')

  const openArtifactReview = useCallback(
    async (generationId: string) => {
      setReviewLoading(true)
      setReviewError('')
      try {
        const content = await getGeneratedContent(config, generationId)
        setReviewContent(content)
      } catch (err) {
        setReviewError(asMessage(err))
      } finally {
        setReviewLoading(false)
      }
    },
    [config],
  )

  const closeArtifactReview = useCallback(() => {
    setReviewContent(null)
    setReviewError('')
  }, [])

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
              value={formatPercent(progression.mastered_outcome_ratio)}
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
                {progression.current_outcome?.title ?? 'No active outcome'}
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

        {/* Model reliability */}
        {summary.state_prediction_reliability && summary.state_prediction_reliability.evaluated_count > 0 && (
          <section className="rounded-xl border bg-white p-6 shadow-sm">
            <div className="flex items-center gap-3 mb-4">
              <Target className="h-5 w-5 text-muted-foreground" />
              <h2 className="font-semibold">Model reliability</h2>
            </div>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Overall accuracy</span>
                <span className={`text-sm font-medium ${
                  summary.state_prediction_reliability.overall_accuracy >= 0.7
                    ? 'text-green-700'
                    : summary.state_prediction_reliability.overall_accuracy >= 0.5
                      ? 'text-amber-700'
                      : 'text-red-700'
                }`}>
                  {formatPercent(summary.state_prediction_reliability.overall_accuracy)}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Evaluated predictions</span>
                <span className="text-sm">{summary.state_prediction_reliability.evaluated_count}</span>
              </div>
              {summary.state_prediction_reliability.per_classification.length > 0 && (
                <div className="space-y-1.5 pt-1">
                  {summary.state_prediction_reliability.per_classification.map((c) => (
                    <div key={c.classification} className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">{titleCase(c.classification.replace(/_/g, ' '))}</span>
                      <span className={
                        c.accuracy_rate >= 0.7 ? 'text-green-700' :
                        c.accuracy_rate >= 0.5 ? 'text-amber-700' : 'text-red-700'
                      }>
                        {formatPercent(c.accuracy_rate)} ({c.evaluated_count})
                      </span>
                    </div>
                  ))}
                </div>
              )}
              {summary.state_prediction_reliability.weakest_classification && (
                <p className="text-xs text-muted-foreground pt-1">
                  {summary.state_prediction_reliability.rationale}
                </p>
              )}
            </div>
          </section>
        )}

        {/* Signal consistency */}
        {summary.signal_consistency && summary.signal_consistency.divergence_count > 0 && (
          <section className="rounded-xl border bg-white p-6 shadow-sm">
            <div className="flex items-center gap-3 mb-4">
              <Shield className="h-5 w-5 text-muted-foreground" />
              <h2 className="font-semibold">Signal consistency</h2>
              <Badge
                variant="outline"
                className={`ml-auto ${
                  summary.signal_consistency.high_count > 0
                    ? 'border-red-200 text-red-700'
                    : summary.signal_consistency.medium_count > 0
                      ? 'border-amber-200 text-amber-700'
                      : 'border-slate-200'
                }`}
              >
                {formatPercent(summary.signal_consistency.coherence_score)} coherent
              </Badge>
            </div>
            <div className="space-y-3">
              {summary.signal_consistency.divergences.map((d, i) => (
                <div key={i} className="rounded-lg bg-slate-50 px-4 py-3">
                  <div className="flex items-center gap-2 mb-1">
                    <AlertTriangle className={`h-3.5 w-3.5 ${
                      d.severity === 'high'
                        ? 'text-red-500'
                        : d.severity === 'medium'
                          ? 'text-amber-500'
                          : 'text-slate-400'
                    }`} />
                    <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                      {d.signal_a} vs {d.signal_b}
                    </span>
                    <Badge
                      variant="outline"
                      className={`text-[10px] px-1.5 py-0 ${
                        d.severity === 'high'
                          ? 'border-red-200 text-red-700'
                          : d.severity === 'medium'
                            ? 'border-amber-200 text-amber-700'
                            : 'border-slate-200'
                      }`}
                    >
                      {d.severity}
                    </Badge>
                  </div>
                  <p className="text-sm text-muted-foreground">{d.description}</p>
                </div>
              ))}
              <p className="text-xs text-muted-foreground pt-1">
                {summary.signal_consistency.rationale}
              </p>
            </div>
          </section>
        )}

        {/* Evidence timeline */}
        <section className="rounded-xl border bg-white p-6 shadow-sm lg:col-span-2">
          <div className="flex items-center gap-3 mb-4">
            <Clock className="h-5 w-5 text-muted-foreground" />
            <h2 className="font-semibold">Evidence timeline</h2>
            <Badge variant="outline" className="ml-auto">
              {timeline.length} event{timeline.length !== 1 ? 's' : ''}
            </Badge>
          </div>

          {timeline.length === 0 && (
            <p className="text-sm text-muted-foreground">No recent activity recorded.</p>
          )}

          <div className="space-y-1">
            {timeline.map((entry) => (
              <TimelineRow
                key={`${entry.kind}-${entry.id}`}
                entry={entry}
                onViewArtifact={entry.generationId ? () => openArtifactReview(entry.generationId!) : undefined}
                reviewLoading={reviewLoading}
              />
            ))}
          </div>

          {contracts.hasMoreHistory && (
            <div className="mt-4 flex justify-center">
              <Button
                variant="outline"
                size="sm"
                onClick={() => void contracts.loadMoreHistory()}
                disabled={contracts.loadingMore}
              >
                {contracts.loadingMore ? (
                  <>
                    <Loader2 className="mr-2 h-3 w-3 animate-spin" />
                    Loading...
                  </>
                ) : (
                  'Load more'
                )}
              </Button>
            </div>
          )}
        </section>
      </div>

      {/* Artifact review panel */}
      {(reviewContent || reviewLoading || reviewError) && (
        <ArtifactReviewPanel
          content={reviewContent}
          loading={reviewLoading}
          error={reviewError}
          onClose={closeArtifactReview}
        />
      )}

      {learner.loading && (
        <p className="text-center text-sm text-muted-foreground">Loading learner data...</p>
      )}
    </PageContainer>
  )
}

// ---------------------------------------------------------------------------
// Timeline row
// ---------------------------------------------------------------------------

const kindIcons = {
  generation: BookOpen,
  socratic: MessageCircle,
  remediation: Wrench,
} as const

const kindColors = {
  generation: 'text-blue-500 bg-blue-50',
  socratic: 'text-emerald-500 bg-emerald-50',
  remediation: 'text-amber-500 bg-amber-50',
} as const

function TimelineRow({
  entry,
  onViewArtifact,
  reviewLoading,
}: {
  entry: TimelineEntry
  onViewArtifact?: () => void
  reviewLoading: boolean
}) {
  const [expanded, setExpanded] = useState(false)
  const Icon = kindIcons[entry.kind]

  return (
    <div className="rounded-lg border border-transparent transition-colors hover:border-slate-200 hover:bg-slate-50">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-3 px-3 py-2.5 text-left text-sm"
      >
        <div className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg ${kindColors[entry.kind]}`}>
          <Icon className="h-3.5 w-3.5" />
        </div>
        <div className="flex-1 min-w-0">
          <TimelineLabel entry={entry} />
        </div>
        <time className="shrink-0 text-xs text-muted-foreground">{formatTimestamp(entry.timestamp)}</time>
        <ChevronDown className={`h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform ${expanded ? 'rotate-180' : ''}`} />
      </button>

      {expanded && (
        <div className="px-3 pb-3">
          <TimelineDetail entry={entry} />
          {onViewArtifact && (
            <button
              onClick={onViewArtifact}
              disabled={reviewLoading}
              className="mt-2 flex items-center gap-1 text-xs font-medium text-emerald-600 hover:text-emerald-700 disabled:opacity-50"
            >
              {reviewLoading ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <ChevronRight className="h-3 w-3" />
              )}
              View generated content
            </button>
          )}
        </div>
      )}
    </div>
  )
}

function TimelineLabel({ entry }: { entry: TimelineEntry }) {
  switch (entry.kind) {
    case 'generation': {
      const g = entry.generation!
      return (
        <div className="flex items-center gap-2">
          <span className="font-medium">{titleCase(g.content_type)}</span>
          <Badge variant="outline" className="text-[10px] px-1.5 py-0">
            {teacherStage(g.target_stage)}
          </Badge>
          {g.rationale && (
            <span className="truncate text-muted-foreground">{g.rationale}</span>
          )}
        </div>
      )
    }
    case 'socratic': {
      const s = entry.socratic!
      return (
        <div className="flex items-center gap-2">
          <span className="font-medium">Socratic check</span>
          <Badge variant="outline" className="text-[10px] px-1.5 py-0">
            {s.turn_count} turn{s.turn_count !== 1 ? 's' : ''}
          </Badge>
          <span className="text-muted-foreground">{titleCase(s.latest_evidence_strength)}</span>
        </div>
      )
    }
    case 'remediation': {
      const r = entry.remediation!
      return (
        <div className="flex items-center gap-2">
          <span className="font-medium">Remediation</span>
          <Badge variant="outline" className="text-[10px] px-1.5 py-0">
            {r.completed_step_count}/{r.step_count} steps
          </Badge>
          {r.current_phase && (
            <span className="text-muted-foreground">{teacherRemediationPhase(r.current_phase)}</span>
          )}
        </div>
      )
    }
  }
}

function TimelineDetail({ entry }: { entry: TimelineEntry }) {
  switch (entry.kind) {
    case 'generation': {
      const g = entry.generation!
      return (
        <div className="ml-10 space-y-1 text-xs text-muted-foreground">
          <div className="flex flex-wrap gap-x-4 gap-y-1">
            <span>Flow: {teacherFlowType(g.flow_type)}</span>
            <span>Status: {titleCase(g.status)}</span>
            <span>Phase: {titleCase(g.delivered_phase)}</span>
            <span>Progression: {teacherProgressionAction(g.progression_action)}</span>
          </div>
          {g.rationale && <p className="italic">{g.rationale}</p>}
        </div>
      )
    }
    case 'socratic': {
      const s = entry.socratic!
      return (
        <div className="ml-10 space-y-1 text-xs text-muted-foreground">
          <div className="flex flex-wrap gap-x-4 gap-y-1">
            <span>Status: {titleCase(s.status)}</span>
            <span>Steering: {titleCase(s.latest_steering_action)}</span>
            <span>Next: {titleCase(s.latest_next_action)}</span>
            <span>Evidence: {titleCase(s.latest_evidence_strength)}</span>
          </div>
          {s.rationale && <p className="italic">{s.rationale}</p>}
        </div>
      )
    }
    case 'remediation': {
      const r = entry.remediation!
      return (
        <div className="ml-10 space-y-1 text-xs text-muted-foreground">
          <div className="flex flex-wrap gap-x-4 gap-y-1">
            <span>Status: {titleCase(r.status)}</span>
            <span>Decision: {titleCase(r.progression_decision)}</span>
            {r.current_phase && <span>Phase: {teacherRemediationPhase(r.current_phase)}</span>}
          </div>
          {r.progression_rationale && <p className="italic">{r.progression_rationale}</p>}
        </div>
      )
    }
  }
}

// ---------------------------------------------------------------------------
// Artifact review panel
// ---------------------------------------------------------------------------

function ArtifactReviewPanel({
  content,
  loading,
  error,
  onClose,
}: {
  content: GeneratedContent | null
  loading: boolean
  error: string
  onClose: () => void
}) {
  return (
    <section className="rounded-xl border bg-white shadow-sm">
      <div className="flex items-center justify-between border-b px-6 py-4">
        <div className="flex items-center gap-3">
          <BookOpen className="h-5 w-5 text-muted-foreground" />
          <h2 className="font-semibold">Artifact review</h2>
          {content && (
            <Badge variant="outline">{titleCase(content.content_type)}</Badge>
          )}
        </div>
        <button
          onClick={onClose}
          className="rounded-lg p-1.5 text-muted-foreground transition-colors hover:bg-slate-100 hover:text-foreground"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="p-6">
        {loading && (
          <div className="flex items-center justify-center gap-2 py-8 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading generated content...
          </div>
        )}

        {error && (
          <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
        )}

        {content && !loading && (
          <>
            {/* Metadata bar */}
            <div className="mb-4 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
              <span>Type: {titleCase(content.content_type)}</span>
              <span>Quality: {Math.round(content.quality.quality_score * 100)}%</span>
              <span>Validation: {content.quality.validation_passed ? 'Passed' : 'Issues found'}</span>
              <span>Grounding: {content.quality.grounding_count} ref{content.quality.grounding_count !== 1 ? 's' : ''}</span>
              <span>Created: {formatTimestamp(content.created_at)}</span>
            </div>

            {content.response.safety_notes.length > 0 && (
              <div className="mb-4 rounded-lg bg-amber-50 px-4 py-2 text-xs text-amber-700">
                Safety notes: {content.response.safety_notes.join('; ')}
              </div>
            )}

            {/* Content blocks */}
            <div className="space-y-4">
              {content.response.blocks.map((block, i) => (
                <ContentBlock key={i} block={block} />
              ))}
            </div>

            {content.response.blocks.length === 0 && (
              <p className="text-sm text-muted-foreground">No content blocks in this generation.</p>
            )}
          </>
        )}
      </div>
    </section>
  )
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function StatItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-slate-50 px-3 py-2">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="font-medium">{value}</p>
    </div>
  )
}
