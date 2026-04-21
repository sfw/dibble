import { useMemo, useState } from 'react'
import { useOutletContext } from 'react-router'
import { BellRing, CalendarClock, CheckCircle2, Sparkles } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import type { ParentContext } from '../../shells/ParentShell'

export function Dashboard() {
  const {
    overview,
    loading,
    error,
    saveSetup,
    savePreferences,
    markRead,
    dismissNotification,
    snoozeNotification,
    acceptSuggestion,
    deferSuggestion,
    snoozeSuggestion,
  } = useOutletContext<ParentContext>()
  const [householdNameDraft, setHouseholdNameDraft] = useState<string | null>(null)
  const [relationshipLabelDraft, setRelationshipLabelDraft] = useState<string | null>(null)
  const [learnerIds, setLearnerIds] = useState<string[]>([])
  const [sessionCadenceDraft, setSessionCadenceDraft] = useState<string | null>(null)
  const [autoSuggestionsDraft, setAutoSuggestionsDraft] = useState<boolean | null>(null)
  const [softEscalationDraft, setSoftEscalationDraft] = useState<boolean | null>(null)
  const [weeklySummaryDayDraft, setWeeklySummaryDayDraft] = useState<string | null>(null)

  const parentProfile = overview.household?.parent_profiles[0]
  const householdName = householdNameDraft ?? overview.household?.household_name ?? 'Our household'
  const relationshipLabel = relationshipLabelDraft ?? parentProfile?.relationship_label ?? 'parent'
  const sessionCadence = sessionCadenceDraft ?? parentProfile?.preferences.session_cadence ?? 'daily'
  const autoSuggestions = autoSuggestionsDraft ?? parentProfile?.preferences.auto_session_suggestions ?? true
  const softEscalation = softEscalationDraft ?? parentProfile?.preferences.soft_escalation_enabled ?? true
  const weeklySummaryDay = weeklySummaryDayDraft ?? parentProfile?.preferences.weekly_summary_day ?? 'sunday'

  const learnerOptions = useMemo(
    () =>
      overview.available_learners.filter((item): item is { learner_id: string; display_name?: string | null } =>
        Boolean(item.learner_id),
      ),
    [overview.available_learners],
  )

  if (!overview.household) {
    return (
      <section className="mx-auto flex max-w-5xl flex-col gap-6">
        <header className="rounded-[2rem] border border-amber-200 bg-white/95 p-8 shadow-[0_24px_70px_rgba(120,53,15,0.08)]">
          <p className="text-sm font-medium uppercase tracking-[0.24em] text-amber-700">Parent-managed POC</p>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight text-slate-900">Set up your household teaching loop</h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">
            Dibble keeps learner-private state local, suggests the next teaching cadence, and only shares curriculum-shaped
            artifacts with the cloud library. Start by naming the household and selecting the learners this parent account manages.
          </p>
          {error && <p className="mt-4 text-sm text-rose-600">{error}</p>}
        </header>

        <Card className="border-amber-100 bg-white/95">
          <CardHeader>
            <CardTitle>Household setup</CardTitle>
            <CardDescription>One household, one parent role, and a conservative approval model for the POC.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-6 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="household-name">Household name</Label>
              <Input id="household-name" value={householdName} onChange={(event) => setHouseholdNameDraft(event.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="relationship-label">Relationship</Label>
              <Select value={relationshipLabel} onValueChange={setRelationshipLabelDraft}>
                <SelectTrigger id="relationship-label">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="parent">Parent</SelectItem>
                  <SelectItem value="guardian">Guardian</SelectItem>
                  <SelectItem value="mentor">Mentor</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-3 md:col-span-2">
              <Label>Learners</Label>
              <div className="flex flex-wrap gap-3">
                {learnerOptions.map((learner) => {
                  const selected = learnerIds.includes(learner.learner_id)
                  return (
                    <button
                      key={learner.learner_id}
                      type="button"
                      onClick={() =>
                        setLearnerIds((current) =>
                          selected
                            ? current.filter((id) => id !== learner.learner_id)
                            : [...current, learner.learner_id],
                        )
                      }
                      className={`rounded-full border px-4 py-2 text-sm transition-colors ${
                        selected
                          ? 'border-amber-300 bg-amber-50 text-amber-900'
                          : 'border-slate-200 bg-white text-slate-700 hover:border-amber-200 hover:bg-amber-50/50'
                      }`}
                    >
                      {learner.display_name ?? learner.learner_id}
                    </button>
                  )
                })}
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="session-cadence">Suggested cadence</Label>
              <Select value={sessionCadence} onValueChange={setSessionCadenceDraft}>
                <SelectTrigger id="session-cadence">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="daily">Daily</SelectItem>
                  <SelectItem value="weekdays">Weekdays</SelectItem>
                  <SelectItem value="flexible">Flexible</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-4 rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-sm font-medium text-slate-900">Automatic session suggestions</p>
                  <p className="text-xs text-slate-600">Let the autonomous teacher propose the next lesson timing.</p>
                </div>
                <Switch checked={autoSuggestions} onCheckedChange={setAutoSuggestionsDraft} />
              </div>
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-sm font-medium text-slate-900">Soft escalation alerts</p>
                  <p className="text-xs text-slate-600">Show “I need your help” when a learner is stalling repeatedly.</p>
                </div>
                <Switch checked={softEscalation} onCheckedChange={setSoftEscalationDraft} />
              </div>
            </div>
            <div className="md:col-span-2">
              <Button
                onClick={() =>
                  void saveSetup({
                    household_name: householdName,
                    learner_ids: learnerIds,
                    relationship_label: relationshipLabel,
                    preferences: {
                      session_cadence: sessionCadence,
                      auto_session_suggestions: autoSuggestions,
                      weekly_summary_day: 'sunday',
                      soft_escalation_enabled: softEscalation,
                      approval_mode: 'guided',
                    },
                  })
                }
                disabled={loading || !householdName.trim() || learnerIds.length === 0}
              >
                {loading ? 'Saving...' : 'Create household'}
              </Button>
            </div>
          </CardContent>
        </Card>
      </section>
    )
  }

  return (
    <section className="mx-auto flex max-w-6xl flex-col gap-6">
      <header className="rounded-[2rem] border border-amber-200 bg-white/95 p-8 shadow-[0_24px_70px_rgba(120,53,15,0.08)]">
        <div className="flex flex-wrap items-start justify-between gap-6">
          <div>
            <p className="text-sm font-medium uppercase tracking-[0.24em] text-amber-700">Household dashboard</p>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight text-slate-900">{overview.household.household_name}</h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">
              The autonomous teacher is owning cadence, next-session focus, weekly summaries, and soft escalation while the
              cloud library stays curriculum-only.
            </p>
          </div>
          <div className="grid min-w-[260px] gap-3 rounded-2xl border border-amber-100 bg-amber-50/70 p-4">
            <div className="flex items-center gap-2 text-sm font-medium text-amber-900">
              <Sparkles className="h-4 w-4" />
              {overview.session_suggestions.length} active session suggestions
            </div>
            <div className="flex items-center gap-2 text-sm font-medium text-amber-900">
              <BellRing className="h-4 w-4" />
              {overview.notifications.filter((item) => item.status !== 'read').length} unread parent notifications
            </div>
          </div>
        </div>
      </header>

      {error && <p className="text-sm text-rose-600">{error}</p>}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.4fr)_360px]">
        <div className="grid gap-6">
          <Card className="border-emerald-100 bg-white/95">
            <CardHeader>
              <CardTitle>Learner overview</CardTitle>
              <CardDescription>Goal progress, next focus, cadence, and modality suggestions.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4">
              {overview.learners.map((learner) => (
                <article key={learner.learner_id} className="rounded-2xl border border-slate-200 bg-slate-50/70 p-5">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h2 className="text-lg font-semibold text-slate-900">{learner.learner_label}</h2>
                      <p className="text-sm text-slate-600">Grade {learner.grade_level} • {learner.goal_title ?? 'Current curriculum journey'}</p>
                    </div>
                    <div className="rounded-full bg-white px-3 py-1 text-xs font-medium text-slate-700 shadow-sm">
                      {Math.round(learner.mastery_ratio * 100)}% mastered
                    </div>
                  </div>
                  <div className="mt-4 grid gap-3 md:grid-cols-3">
                    <InfoStat label="Cadence" value={learner.cadence_decision} />
                    <InfoStat label="Suggested modality" value={learner.suggested_modality} />
                    <InfoStat label="Current stage" value={learner.current_stage} />
                  </div>
                  <p className="mt-4 text-sm text-slate-700">{learner.summary_headline ?? learner.next_session_focus ?? 'No summary yet.'}</p>
                </article>
              ))}
            </CardContent>
          </Card>

          <Card className="border-sky-100 bg-white/95">
            <CardHeader>
              <CardTitle>Weekly summaries</CardTitle>
              <CardDescription>Compact long-horizon updates generated by the autonomous teacher harness.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4">
              {overview.weekly_summaries.map((summary) => (
                <article key={`${summary.learner_id}-${summary.generated_at}`} className="rounded-2xl border border-sky-100 bg-sky-50/60 p-5">
                  <h3 className="text-base font-semibold text-slate-900">{summary.headline}</h3>
                  <p className="mt-2 text-sm text-slate-700">{summary.celebration}</p>
                  {summary.support_need && <p className="mt-2 text-sm text-amber-800">{summary.support_need}</p>}
                  {summary.next_focus && <p className="mt-2 text-sm text-slate-600">Next focus: {summary.next_focus}</p>}
                </article>
              ))}
            </CardContent>
          </Card>

          <Card className="border-amber-100 bg-white/95">
            <CardHeader>
              <CardTitle>Parent preferences</CardTitle>
              <CardDescription>These settings shape cadence suggestions, summaries, and escalation visibility.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-6 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="active-relationship-label">Relationship</Label>
                <Select value={relationshipLabel} onValueChange={setRelationshipLabelDraft}>
                  <SelectTrigger id="active-relationship-label">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="parent">Parent</SelectItem>
                    <SelectItem value="guardian">Guardian</SelectItem>
                    <SelectItem value="mentor">Mentor</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="active-session-cadence">Suggested cadence</Label>
                <Select value={sessionCadence} onValueChange={setSessionCadenceDraft}>
                  <SelectTrigger id="active-session-cadence">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="daily">Daily</SelectItem>
                    <SelectItem value="weekdays">Weekdays</SelectItem>
                    <SelectItem value="flexible">Flexible</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="weekly-summary-day">Weekly summary day</Label>
                <Select value={weeklySummaryDay} onValueChange={setWeeklySummaryDayDraft}>
                  <SelectTrigger id="weekly-summary-day">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="sunday">Sunday</SelectItem>
                    <SelectItem value="monday">Monday</SelectItem>
                    <SelectItem value="friday">Friday</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-4 rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-sm font-medium text-slate-900">Automatic session suggestions</p>
                    <p className="text-xs text-slate-600">Hide or surface proactive next-session nudges.</p>
                  </div>
                  <Switch checked={autoSuggestions} onCheckedChange={setAutoSuggestionsDraft} />
                </div>
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-sm font-medium text-slate-900">Soft escalation alerts</p>
                    <p className="text-xs text-slate-600">Control whether the parent sees “I need your help” prompts.</p>
                  </div>
                  <Switch checked={softEscalation} onCheckedChange={setSoftEscalationDraft} />
                </div>
              </div>
              <div className="md:col-span-2">
                <Button
                  onClick={() =>
                    void savePreferences({
                      relationship_label: relationshipLabel,
                      preferences: {
                        session_cadence: sessionCadence,
                        auto_session_suggestions: autoSuggestions,
                        weekly_summary_day: weeklySummaryDay,
                        soft_escalation_enabled: softEscalation,
                        approval_mode: 'guided',
                      },
                    })
                  }
                  disabled={loading}
                >
                  {loading ? 'Saving...' : 'Save preferences'}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="grid gap-6">
          <Card className="border-slate-200 bg-white/95">
            <CardHeader>
              <CardTitle>Session initiation suggestions</CardTitle>
              <CardDescription>Teacher-like cadence decisions translated into concrete next steps.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3">
              {overview.session_suggestions.map((suggestion) => (
                <article key={`${suggestion.learner_id}-${suggestion.learning_session_id ?? suggestion.modality}`} className="rounded-2xl border border-slate-200 p-4">
                  <div className="flex items-center gap-2 text-sm font-medium text-slate-900">
                    <CalendarClock className="h-4 w-4 text-amber-700" />
                    {suggestion.cadence_decision}
                  </div>
                  <p className="mt-2 text-sm text-slate-700">{suggestion.focus_label ?? 'Continue the current trajectory.'}</p>
                  <p className="mt-2 text-xs text-slate-500">Modality: {suggestion.modality} • Status: {suggestion.status}</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button variant="outline" size="sm" onClick={() => void acceptSuggestion(suggestion.learner_id)}>
                      Accept
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => void deferSuggestion(suggestion.learner_id)}>
                      Defer
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => void snoozeSuggestion(suggestion.learner_id, { hours: 24 })}>
                      Snooze 1 day
                    </Button>
                  </div>
                </article>
              ))}
            </CardContent>
          </Card>

          <Card className="border-rose-100 bg-white/95">
            <CardHeader>
              <CardTitle>Notifications</CardTitle>
              <CardDescription>“I need your help” and weekly-summary signals from the orchestration layer.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3">
              {overview.notifications.map((notification) => (
                <article key={notification.notification_id} className="rounded-2xl border border-slate-200 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h3 className="text-sm font-semibold text-slate-900">{notification.title}</h3>
                      <p className="mt-1 text-sm text-slate-700">{notification.message}</p>
                    </div>
                    {notification.status === 'read' ? (
                      <div className="flex items-center gap-2">
                        <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                        <Button variant="ghost" size="sm" onClick={() => void dismissNotification(notification.notification_id)}>
                          Dismiss
                        </Button>
                      </div>
                    ) : (
                      <div className="flex items-center gap-2">
                        <Button variant="outline" size="sm" onClick={() => void markRead(notification.notification_id)}>
                          Mark read
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => void snoozeNotification(notification.notification_id, { hours: 24 })}>
                          Snooze 1 day
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => void dismissNotification(notification.notification_id)}>
                          Dismiss
                        </Button>
                      </div>
                    )}
                  </div>
                </article>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>
    </section>
  )
}

function InfoStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-white bg-white px-4 py-3 shadow-sm">
      <p className="text-xs font-medium uppercase tracking-[0.18em] text-slate-500">{label}</p>
      <p className="mt-2 text-sm font-semibold text-slate-900">{value}</p>
    </div>
  )
}
