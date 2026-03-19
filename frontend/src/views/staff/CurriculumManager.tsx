import { useEffect, useMemo, useState } from 'react'
import {
  BookOpen,
  ChevronDown,
  ChevronRight,
  GitBranch,
  Layers,
  Network,
  RefreshCw,
  Search,
  Target,
} from 'lucide-react'
import {
  listAdminCourses,
  listKnowledgeComponents,
  listOutcomes,
  listStrands,
} from '../../api'
import { Badge } from '../../components/ui/badge'
import { Button } from '../../components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card'
import { Combobox } from '../../components/ui/combobox'
import type { ComboboxOption } from '../../components/ui/combobox'
import { ErrorBanner } from '../../components/ui/error-banner'
import { Input } from '../../components/ui/input'
import type {
  AdminCourseSummary,
  KnowledgeComponent,
  Outcome,
  Strand,
} from '../../types'
import { useStaffApiConfig } from './useStaffApiConfig'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function difficultyLabel(d: number): string {
  if (d <= 0.3) return 'Easy'
  if (d <= 0.6) return 'Medium'
  return 'Hard'
}

function difficultyColor(d: number): string {
  if (d <= 0.3) return 'bg-emerald-100 text-emerald-800'
  if (d <= 0.6) return 'bg-amber-100 text-amber-800'
  return 'bg-rose-100 text-rose-800'
}

// ---------------------------------------------------------------------------
// KC Card
// ---------------------------------------------------------------------------

function KcCard({
  kc,
  allKcs,
}: {
  kc: KnowledgeComponent
  allKcs: Map<string, KnowledgeComponent>
}) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="rounded-xl border border-slate-200 bg-white">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-start gap-3 px-4 py-3 text-left transition-colors hover:bg-slate-50"
      >
        <div className="mt-0.5 shrink-0 text-slate-400">
          {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        </div>
        <div className="flex-1 space-y-1">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-slate-900">{kc.name}</span>
            <Badge variant="secondary" className={`text-[10px] ${difficultyColor(kc.difficulty)}`}>
              {difficultyLabel(kc.difficulty)}
            </Badge>
          </div>
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
            <span>{kc.estimated_time_minutes} min</span>
            {kc.prerequisite_kc_ids.length > 0 && (
              <span className="flex items-center gap-1">
                <GitBranch className="h-3 w-3" />
                {kc.prerequisite_kc_ids.length} prereq{kc.prerequisite_kc_ids.length !== 1 ? 's' : ''}
              </span>
            )}
            {kc.common_misconceptions.length > 0 && (
              <span>{kc.common_misconceptions.length} misconception{kc.common_misconceptions.length !== 1 ? 's' : ''}</span>
            )}
          </div>
        </div>
      </button>

      {expanded && (
        <div className="space-y-3 border-t border-slate-100 px-4 py-3">
          <div className="grid gap-3 text-xs md:grid-cols-2">
            <div>
              <span className="font-medium text-slate-600">KC ID</span>
              <p className="mt-0.5 font-mono text-slate-500">{kc.kc_id}</p>
            </div>
            <div>
              <span className="font-medium text-slate-600">Outcome</span>
              <p className="mt-0.5 font-mono text-slate-500">{kc.outcome_id}</p>
            </div>
            {kc.taxonomy_cluster_id && (
              <div>
                <span className="font-medium text-slate-600">Taxonomy cluster</span>
                <p className="mt-0.5 text-slate-500">{kc.taxonomy_cluster_id}</p>
              </div>
            )}
            {kc.concept_family && (
              <div>
                <span className="font-medium text-slate-600">Concept family</span>
                <p className="mt-0.5 text-slate-500">{kc.concept_family}</p>
              </div>
            )}
          </div>

          {kc.prerequisite_kc_ids.length > 0 && (
            <div>
              <span className="text-xs font-medium text-slate-600">Prerequisites</span>
              <div className="mt-1 flex flex-wrap gap-1">
                {kc.prerequisite_kc_ids.map((pid) => {
                  const prereq = allKcs.get(pid)
                  return (
                    <Badge key={pid} variant="secondary" className="bg-violet-50 text-violet-800 text-[10px]">
                      {prereq?.name ?? pid}
                    </Badge>
                  )
                })}
              </div>
            </div>
          )}

          {kc.common_misconceptions.length > 0 && (
            <div>
              <span className="text-xs font-medium text-slate-600">Common misconceptions</span>
              <ul className="mt-1 list-inside list-disc space-y-0.5 text-xs text-slate-600">
                {kc.common_misconceptions.map((m, i) => (
                  <li key={i}>{m}</li>
                ))}
              </ul>
            </div>
          )}

          {kc.tags.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {kc.tags.map((tag) => (
                <Badge key={tag} variant="outline" className="text-[10px]">
                  {tag}
                </Badge>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Outcome Card
// ---------------------------------------------------------------------------

function OutcomeCard({
  outcome,
  kcs,
  allKcs,
}: {
  outcome: Outcome
  kcs: KnowledgeComponent[]
  allKcs: Map<string, KnowledgeComponent>
}) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50/50">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-start gap-3 px-5 py-4 text-left transition-colors hover:bg-slate-100/50"
      >
        <div className="mt-0.5 shrink-0 text-sky-500">
          {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        </div>
        <div className="flex-1 space-y-1">
          <div className="flex items-center gap-2">
            <Target className="h-4 w-4 shrink-0 text-sky-600" />
            <span className="text-sm font-semibold text-slate-900">{outcome.title}</span>
          </div>
          <p className="text-xs leading-5 text-slate-600">{outcome.description}</p>
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
            <span>{kcs.length} knowledge component{kcs.length !== 1 ? 's' : ''}</span>
            <span className="font-mono">{outcome.outcome_id}</span>
          </div>
        </div>
      </button>

      {expanded && kcs.length > 0 && (
        <div className="space-y-2 border-t border-slate-200 px-5 py-4">
          {kcs.map((kc) => (
            <KcCard key={kc.kc_id} kc={kc} allKcs={allKcs} />
          ))}
        </div>
      )}

      {expanded && kcs.length === 0 && (
        <div className="border-t border-slate-200 px-5 py-6 text-center text-xs text-slate-400">
          No knowledge components linked to this outcome.
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Strand Card
// ---------------------------------------------------------------------------

function StrandCard({
  strand,
  outcomes,
  kcsByOutcome,
  allKcs,
}: {
  strand: Strand
  outcomes: Outcome[]
  kcsByOutcome: Map<string, KnowledgeComponent[]>
  allKcs: Map<string, KnowledgeComponent>
}) {
  const [expanded, setExpanded] = useState(false)
  const totalKcs = outcomes.reduce((acc, o) => acc + (kcsByOutcome.get(o.outcome_id)?.length ?? 0), 0)

  return (
    <Card className="overflow-hidden">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-start gap-3 px-6 py-5 text-left transition-colors hover:bg-slate-50"
      >
        <div className="mt-1 shrink-0 text-emerald-500">
          {expanded ? <ChevronDown className="h-5 w-5" /> : <ChevronRight className="h-5 w-5" />}
        </div>
        <div className="flex-1 space-y-1">
          <div className="flex items-center gap-2">
            <Layers className="h-5 w-5 shrink-0 text-emerald-600" />
            <span className="text-base font-semibold text-slate-900">{strand.title}</span>
          </div>
          {strand.description && (
            <p className="text-sm text-slate-600">{strand.description}</p>
          )}
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
            <span>{outcomes.length} outcome{outcomes.length !== 1 ? 's' : ''}</span>
            <span>{totalKcs} KC{totalKcs !== 1 ? 's' : ''}</span>
            <span className="font-mono">{strand.strand_id}</span>
          </div>
        </div>
        {strand.tags.length > 0 && (
          <div className="hidden flex-wrap gap-1 lg:flex">
            {strand.tags.map((tag) => (
              <Badge key={tag} variant="outline" className="text-[10px]">
                {tag}
              </Badge>
            ))}
          </div>
        )}
      </button>

      {expanded && (
        <div className="space-y-3 border-t border-border px-6 py-5">
          {outcomes.length > 0 ? (
            outcomes.map((outcome) => (
              <OutcomeCard
                key={outcome.outcome_id}
                outcome={outcome}
                kcs={kcsByOutcome.get(outcome.outcome_id) ?? []}
                allKcs={allKcs}
              />
            ))
          ) : (
            <p className="py-4 text-center text-sm text-slate-400">No outcomes in this strand.</p>
          )}
        </div>
      )}
    </Card>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function CurriculumManager() {
  const apiConfig = useStaffApiConfig()
  const [courses, setCourses] = useState<AdminCourseSummary[]>([])
  const [allStrands, setAllStrands] = useState<Strand[]>([])
  const [allOutcomes, setAllOutcomes] = useState<Outcome[]>([])
  const [allKcsList, setAllKcsList] = useState<KnowledgeComponent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selectedCourseId, setSelectedCourseId] = useState('')
  const [searchTerm, setSearchTerm] = useState('')

  async function loadAll() {
    setLoading(true)
    setError('')
    try {
      const [coursesRes, strandsRes, outcomesRes, kcsRes] = await Promise.all([
        listAdminCourses(apiConfig),
        listStrands(apiConfig),
        listOutcomes(apiConfig),
        listKnowledgeComponents(apiConfig),
      ])
      setCourses(coursesRes)
      setAllStrands(strandsRes)
      setAllOutcomes(outcomesRes)
      setAllKcsList(kcsRes)

      // Auto-select first course that has strands
      if (!selectedCourseId) {
        const courseIdsWithStrands = new Set(strandsRes.map((s) => s.course_id))
        const first = coursesRes.find((c) => courseIdsWithStrands.has(c.course_id))
        if (first) setSelectedCourseId(first.course_id)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load curriculum data')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadAll()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiConfig.baseUrl, apiConfig.apiKey, apiConfig.bearerToken])

  // Build lookup maps
  const allKcs = useMemo(
    () => new Map(allKcsList.map((kc) => [kc.kc_id, kc])),
    [allKcsList],
  )

  // Course filter options
  const courseOptions: ComboboxOption[] = useMemo(() => {
    const courseIdsWithStrands = new Set(allStrands.map((s) => s.course_id))
    return courses
      .filter((c) => courseIdsWithStrands.has(c.course_id))
      .map((c) => ({
        value: c.course_id,
        label: c.title,
        detail: [c.subject, c.grade_band].filter(Boolean).join(' / ') || c.course_id,
      }))
  }, [courses, allStrands])

  // Filtered strands for selected course
  const strands = useMemo(
    () =>
      allStrands
        .filter((s) => !selectedCourseId || s.course_id === selectedCourseId)
        .sort((a, b) => a.sort_order - b.sort_order),
    [allStrands, selectedCourseId],
  )

  // Outcomes by strand
  const outcomesByStrand = useMemo(() => {
    const map = new Map<string, Outcome[]>()
    for (const outcome of allOutcomes) {
      const list = map.get(outcome.strand_id) ?? []
      list.push(outcome)
      map.set(outcome.strand_id, list)
    }
    // Sort each list
    for (const [, list] of map) {
      list.sort((a, b) => a.sort_order - b.sort_order)
    }
    return map
  }, [allOutcomes])

  // KCs by outcome
  const kcsByOutcome = useMemo(() => {
    const map = new Map<string, KnowledgeComponent[]>()
    for (const kc of allKcsList) {
      const list = map.get(kc.outcome_id) ?? []
      list.push(kc)
      map.set(kc.outcome_id, list)
    }
    return map
  }, [allKcsList])

  // Search filter
  const filteredStrands = useMemo(() => {
    if (!searchTerm.trim()) return strands
    const term = searchTerm.toLowerCase()
    return strands.filter((strand) => {
      if (strand.title.toLowerCase().includes(term)) return true
      if (strand.description.toLowerCase().includes(term)) return true
      const outcomes = outcomesByStrand.get(strand.strand_id) ?? []
      return outcomes.some(
        (o) =>
          o.title.toLowerCase().includes(term) ||
          o.description.toLowerCase().includes(term) ||
          (kcsByOutcome.get(o.outcome_id) ?? []).some(
            (kc) => kc.name.toLowerCase().includes(term) || kc.kc_id.toLowerCase().includes(term),
          ),
      )
    })
  }, [strands, searchTerm, outcomesByStrand, kcsByOutcome])

  // Stats
  const totalOutcomes = strands.reduce(
    (acc, s) => acc + (outcomesByStrand.get(s.strand_id)?.length ?? 0),
    0,
  )
  const totalKcs = strands.reduce((acc, s) => {
    const outcomes = outcomesByStrand.get(s.strand_id) ?? []
    return acc + outcomes.reduce((a, o) => a + (kcsByOutcome.get(o.outcome_id)?.length ?? 0), 0)
  }, 0)
  const totalPrereqs = allKcsList.reduce((acc, kc) => acc + kc.prerequisite_kc_ids.length, 0)

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <section className="flex flex-col gap-4 rounded-[2rem] border border-border bg-[linear-gradient(135deg,#ffffff_0%,#eef7ff_55%,#f4f0ff_100%)] p-8 shadow-[0_24px_80px_rgba(56,46,24,0.08)] lg:flex-row lg:items-end lg:justify-between">
        <div className="space-y-3">
          <Badge variant="secondary" className="w-fit bg-violet-100 text-violet-900">
            Curriculum browser
          </Badge>
          <div className="space-y-2">
            <h1 className="text-3xl font-semibold tracking-tight text-slate-900">
              Explore loaded curriculum packages.
            </h1>
            <p className="max-w-3xl text-sm leading-6 text-slate-600">
              View the full hierarchy of strands, outcomes, and knowledge components that drive adaptive content generation.
            </p>
          </div>
        </div>
        <div className="flex gap-3">
          <Button variant="outline" onClick={() => void loadAll()} disabled={loading}>
            <RefreshCw className="h-4 w-4" />
            Refresh
          </Button>
        </div>
      </section>

      <ErrorBanner message={error} />

      {/* Stats */}
      {!loading && strands.length > 0 && (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <div className="rounded-2xl border border-border bg-white px-5 py-4">
            <p className="text-2xl font-bold text-emerald-700">{filteredStrands.length}</p>
            <p className="text-xs text-slate-500">Strands</p>
          </div>
          <div className="rounded-2xl border border-border bg-white px-5 py-4">
            <p className="text-2xl font-bold text-sky-700">{totalOutcomes}</p>
            <p className="text-xs text-slate-500">Outcomes</p>
          </div>
          <div className="rounded-2xl border border-border bg-white px-5 py-4">
            <p className="text-2xl font-bold text-violet-700">{totalKcs}</p>
            <p className="text-xs text-slate-500">Knowledge Components</p>
          </div>
          <div className="rounded-2xl border border-border bg-white px-5 py-4">
            <p className="text-2xl font-bold text-amber-700">{totalPrereqs}</p>
            <p className="text-xs text-slate-500">Prerequisite Edges</p>
          </div>
        </div>
      )}

      {/* Filters */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <Network className="h-4 w-4 text-violet-600" />
            Filter curriculum
          </CardTitle>
          <CardDescription>Select a course to browse its curriculum hierarchy.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 md:grid-cols-2">
            <div className="flex flex-col gap-2">
              <Combobox
                options={courseOptions}
                value={selectedCourseId}
                onValueChange={setSelectedCourseId}
                placeholder="All courses"
                searchPlaceholder="Search courses..."
                emptyMessage="No courses with curriculum loaded."
              />
            </div>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Search strands, outcomes, or KCs..."
                className="pl-9"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Strand list */}
      {loading && (
        <div className="flex items-center justify-center py-16">
          <div className="flex flex-col items-center gap-3 text-slate-400">
            <RefreshCw className="h-6 w-6 animate-spin" />
            <p className="text-sm">Loading curriculum...</p>
          </div>
        </div>
      )}

      {!loading && filteredStrands.length === 0 && (
        <div className="flex flex-col items-center gap-4 py-16">
          <BookOpen className="h-12 w-12 text-slate-300" />
          <div className="text-center">
            <p className="text-lg font-medium text-slate-600">No curriculum data found</p>
            <p className="mt-1 text-sm text-slate-400">
              {searchTerm
                ? 'Try a different search term.'
                : 'Load a curriculum package using the seed script or API.'}
            </p>
          </div>
        </div>
      )}

      <div className="space-y-4">
        {filteredStrands.map((strand) => (
          <StrandCard
            key={strand.strand_id}
            strand={strand}
            outcomes={outcomesByStrand.get(strand.strand_id) ?? []}
            kcsByOutcome={kcsByOutcome}
            allKcs={allKcs}
          />
        ))}
      </div>
    </div>
  )
}
