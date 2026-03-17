import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import './App.css'
import {
  advanceRemediationSession,
  generateContent,
  getLearnerFlow,
  getLearnerProfile,
  getLearnerSummary,
  getLearners,
  getRemediationSession,
  getSocraticSession,
  runSocraticAssessment,
  streamGeneration,
  triggerRemediation,
} from './api'
import { Pill } from './components/primitives'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { buildGenerationPayload, nullableNumber, nullableText, parseList, applyStreamChunk } from './lib/forms'
import { asMessage } from './lib/formatters'
import { loadStoredConfig, configStorageKey } from './lib/storage'
import {
  demoGeneration,
  demoLearnerFlow,
  demoProfile,
  demoProfileSummary,
  demoRemediationSession,
  demoSocraticResponse,
  demoSocraticSession,
  SAMPLE_STUDENT_ID,
  teacherContractGaps,
} from './sample-data'
import type {
  FrontendConfig,
  GeneratedContent,
  GeneratedBlock,
  GenerationStreamEvent,
  LearnerFlowSummary,
  LearnerProfileV2,
  ProfileSummary,
  RemediationWorkflowAdvanceResponse,
  RemediationWorkflowSession,
  SocraticAssessmentResponse,
  SocraticAssessmentSession,
} from './types'
import { GenerationView, type GenerationFormState } from './views/GenerationView'
import { OverviewView } from './views/OverviewView'
import { RemediationView, type RemediationFormState } from './views/RemediationView'
import { SocraticView, type SocraticFormState } from './views/SocraticView'
import { TeacherView } from './views/TeacherView'

type ViewKey = 'overview' | 'generation' | 'socratic' | 'remediation' | 'teacher'
type DataSource = 'live' | 'demo'

function App() {
  const [activeView, setActiveView] = useState<ViewKey>('overview')
  const hasBootstrapped = useRef(false)
  const [config, setConfig] = useState<FrontendConfig>(() => loadStoredConfig())
  const [learnerId, setLearnerId] = useState(SAMPLE_STUDENT_ID)
  const [learnerIds, setLearnerIds] = useState<string[]>([SAMPLE_STUDENT_ID])
  const [summary, setSummary] = useState<ProfileSummary>(demoProfileSummary)
  const [profile, setProfile] = useState<LearnerProfileV2>(demoProfile)
  const [flow, setFlow] = useState<LearnerFlowSummary>(demoLearnerFlow)
  const [dataSource, setDataSource] = useState<DataSource>('demo')
  const [overviewError, setOverviewError] = useState('')
  const [overviewLoading, setOverviewLoading] = useState(false)

  const [generationForm, setGenerationForm] = useState<GenerationFormState>({
    learning_session_id: 'session-fractions-bridge',
    target_kc_ids: 'KC-1',
    target_lo_ids: 'LO-1',
    intent: 'practice',
    requested_content_type: 'practice_problem',
    learner_prompt: 'Use a supportive tone and name the transfer move explicitly.',
    curriculum_context: 'Equivalent fractions',
  })
  const [generationResult, setGenerationResult] = useState<GeneratedContent>(demoGeneration)
  const [generationLoading, setGenerationLoading] = useState(false)
  const [generationError, setGenerationError] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [streamEvents, setStreamEvents] = useState<GenerationStreamEvent[]>([])
  const [streamedBlocks, setStreamedBlocks] = useState<GeneratedBlock[]>([])

  const [socraticForm, setSocraticForm] = useState<SocraticFormState>({
    session_id: demoSocraticResponse.session_id,
    learning_session_id: 'session-fractions-bridge',
    target_kc_ids: 'KC-1',
    target_lo_ids: 'LO-1',
    curriculum_context: 'Equivalent fractions',
    learner_response:
      'The amount stays the same because the whole does not change, only the number of equal parts changes.',
    learner_confidence: '0.76',
  })
  const [socraticResponse, setSocraticResponse] =
    useState<SocraticAssessmentResponse>(demoSocraticResponse)
  const [socraticSession, setSocraticSession] =
    useState<SocraticAssessmentSession>(demoSocraticSession)
  const [socraticLoading, setSocraticLoading] = useState(false)
  const [socraticError, setSocraticError] = useState('')

  const [remediationForm, setRemediationForm] = useState<RemediationFormState>({
    target_kc_id: 'KC-2',
    misconception_description:
      'The learner compares numerator and denominator separately instead of comparing the same whole amount.',
    learner_prompt: 'Step back to one whole model before returning to the target.',
    curriculum_context: 'Equivalent fractions',
  })
  const [remediationContent, setRemediationContent] = useState<GeneratedContent>(demoGeneration)
  const [remediationSession, setRemediationSession] =
    useState<RemediationWorkflowSession>(demoRemediationSession)
  const [remediationAdvance, setRemediationAdvance] =
    useState<RemediationWorkflowAdvanceResponse | null>(null)
  const [remediationLoading, setRemediationLoading] = useState(false)
  const [remediationError, setRemediationError] = useState('')
  const [remediationAdvancePrompt, setRemediationAdvancePrompt] = useState(
    'Advance only if the learner can explain the whole correctly without relying on numerator-only cues.',
  )

  const deferredTeacherGaps = useMemo(() => teacherContractGaps, [])

  const loadLearnerIds = useCallback(async () => {
    try {
      const ids = await getLearners(config)
      if (ids.length > 0) {
        setLearnerIds(ids)
      }
    } catch {
      setLearnerIds((current) => Array.from(new Set([SAMPLE_STUDENT_ID, ...current])))
    }
  }, [config])

  const loadLearnerWorkspace = useCallback(async (studentId: string) => {
    setOverviewLoading(true)
    setOverviewError('')

    try {
      const [nextSummary, nextProfile, nextFlow] = await Promise.all([
        getLearnerSummary(config, studentId),
        getLearnerProfile(config, studentId),
        getLearnerFlow(config, studentId),
      ])
      setSummary(nextSummary)
      setProfile(nextProfile)
      setFlow(nextFlow)
      setDataSource('live')
      setLearnerId(studentId)
    } catch (error) {
      if (!config.useDemoFallback) {
        setOverviewError(asMessage(error))
        return
      }
      setSummary(demoProfileSummary)
      setProfile(demoProfile)
      setFlow(demoLearnerFlow)
      setDataSource('demo')
      setOverviewError(`${asMessage(error)} Showing demo data instead.`)
      setLearnerId(studentId)
    } finally {
      setOverviewLoading(false)
    }
  }, [config])

  useEffect(() => {
    window.localStorage.setItem(configStorageKey, JSON.stringify(config))
  }, [config])

  useEffect(() => {
    if (hasBootstrapped.current) {
      return
    }
    hasBootstrapped.current = true
    void loadLearnerWorkspace(learnerId)
    void loadLearnerIds()
  }, [learnerId, loadLearnerIds, loadLearnerWorkspace])

  async function handleGenerate() {
    setGenerationLoading(true)
    setGenerationError('')

    try {
      const result = await generateContent(config, buildGenerationPayload(learnerId, generationForm))
      setGenerationResult(result)
      setDataSource('live')
    } catch (error) {
      if (!config.useDemoFallback) {
        setGenerationError(asMessage(error))
        return
      }
      setGenerationResult(demoGeneration)
      setGenerationError(`${asMessage(error)} Showing a demo generation instead.`)
      setDataSource('demo')
    } finally {
      setGenerationLoading(false)
    }
  }

  async function handleStream() {
    setStreaming(true)
    setGenerationError('')
    setStreamEvents([])
    setStreamedBlocks([])

    try {
      await streamGeneration(config, buildGenerationPayload(learnerId, generationForm), (event) => {
        setStreamEvents((current) => [...current, event])
        const chunk = event.chunk
        if (chunk) {
          setStreamedBlocks((current) => applyStreamChunk(current, chunk))
        }
        if (event.response) {
          setGenerationResult({
            generation_id: event.response.generation_id ?? 'stream-complete',
            student_id: learnerId,
            content_type:
              generationForm.requested_content_type || generationForm.intent || 'generated_content',
            request_context: {
              learning_session_id: generationForm.learning_session_id,
              source: 'stream',
            },
            workflow_summary: demoGeneration.workflow_summary,
            response: event.response,
            quality: event.response.generation_metadata ?? demoGeneration.quality,
            created_at: event.response.generated_at,
            expires_at: null,
          })
        }
      })
      setDataSource('live')
    } catch (error) {
      if (!config.useDemoFallback) {
        setGenerationError(asMessage(error))
      } else {
        setGenerationResult(demoGeneration)
        setStreamedBlocks(demoGeneration.response.blocks)
        setGenerationError(`${asMessage(error)} Showing a demo stream result instead.`)
        setDataSource('demo')
      }
    } finally {
      setStreaming(false)
    }
  }

  async function handleSocraticRun() {
    setSocraticLoading(true)
    setSocraticError('')

    try {
      const response = await runSocraticAssessment(config, {
        student_id: learnerId,
        session_id: nullableText(socraticForm.session_id),
        learning_session_id: nullableText(socraticForm.learning_session_id),
        target_kc_ids: parseList(socraticForm.target_kc_ids),
        target_lo_ids: parseList(socraticForm.target_lo_ids),
        curriculum_context: parseList(socraticForm.curriculum_context),
        learner_response: nullableText(socraticForm.learner_response),
        learner_confidence: nullableNumber(socraticForm.learner_confidence),
      })

      setSocraticResponse(response)
      setSocraticForm((current) => ({ ...current, session_id: response.session_id }))
      const session = await getSocraticSession(config, response.session_id)
      setSocraticSession(session)
      setDataSource('live')
    } catch (error) {
      if (!config.useDemoFallback) {
        setSocraticError(asMessage(error))
        return
      }
      setSocraticResponse(demoSocraticResponse)
      setSocraticSession(demoSocraticSession)
      setSocraticError(`${asMessage(error)} Showing a demo Socratic session instead.`)
      setDataSource('demo')
    } finally {
      setSocraticLoading(false)
    }
  }

  async function handleSocraticReload() {
    const sessionId = nullableText(socraticForm.session_id)
    if (!sessionId) {
      setSocraticError('Enter a Socratic session ID to load.')
      return
    }

    setSocraticLoading(true)
    setSocraticError('')
    try {
      const session = await getSocraticSession(config, sessionId)
      setSocraticSession(session)
      setDataSource('live')
    } catch (error) {
      if (!config.useDemoFallback) {
        setSocraticError(asMessage(error))
      } else {
        setSocraticSession(demoSocraticSession)
        setSocraticError(`${asMessage(error)} Showing a demo Socratic session instead.`)
        setDataSource('demo')
      }
    } finally {
      setSocraticLoading(false)
    }
  }

  async function handleRemediationTrigger() {
    setRemediationLoading(true)
    setRemediationError('')
    setRemediationAdvance(null)

    try {
      const content = await triggerRemediation(config, {
        student_id: learnerId,
        target_kc_id: remediationForm.target_kc_id,
        misconception_description: remediationForm.misconception_description,
        learner_prompt: nullableText(remediationForm.learner_prompt),
        curriculum_context: parseList(remediationForm.curriculum_context),
      })
      setRemediationContent(content)

      const rawSessionId = content.request_context.remediation_session_id
      const sessionId = typeof rawSessionId === 'string' ? rawSessionId : ''
      if (sessionId) {
        const session = await getRemediationSession(config, sessionId)
        setRemediationSession(session)
      }
      setDataSource('live')
    } catch (error) {
      if (!config.useDemoFallback) {
        setRemediationError(asMessage(error))
        return
      }
      setRemediationContent(demoGeneration)
      setRemediationSession(demoRemediationSession)
      setRemediationError(`${asMessage(error)} Showing a demo remediation session instead.`)
      setDataSource('demo')
    } finally {
      setRemediationLoading(false)
    }
  }

  async function handleRemediationReload() {
    setRemediationLoading(true)
    setRemediationError('')
    try {
      const session = await getRemediationSession(config, remediationSession.session_id)
      setRemediationSession(session)
      setDataSource('live')
    } catch (error) {
      if (!config.useDemoFallback) {
        setRemediationError(asMessage(error))
      } else {
        setRemediationSession(demoRemediationSession)
        setRemediationError(`${asMessage(error)} Showing a demo remediation session instead.`)
        setDataSource('demo')
      }
    } finally {
      setRemediationLoading(false)
    }
  }

  async function handleRemediationAdvance() {
    setRemediationLoading(true)
    setRemediationError('')
    try {
      const response = await advanceRemediationSession(config, remediationSession.session_id, {
        learner_prompt: nullableText(remediationAdvancePrompt),
        curriculum_context: remediationSession.curriculum_context,
      })
      setRemediationAdvance(response)
      setRemediationSession(response.session)
      setRemediationContent(response.content)
      setDataSource('live')
    } catch (error) {
      if (!config.useDemoFallback) {
        setRemediationError(asMessage(error))
      } else {
        setRemediationAdvance({
          session: demoRemediationSession,
          content: demoGeneration,
          executed_phase: 'repair',
        })
        setRemediationSession(demoRemediationSession)
        setRemediationContent(demoGeneration)
        setRemediationError(`${asMessage(error)} Showing a demo remediation advance instead.`)
        setDataSource('demo')
      }
    } finally {
      setRemediationLoading(false)
    }
  }

  return (
    <div className="app-shell">
      <header className="hero-shell">
        <div className="hero-copy">
          <p className="eyebrow">Adaptive Learning Frontend Workspace</p>
          <h1>Dibble Control Room</h1>
          <p className="hero-text">
            A React + Vite frontend for the revised generation-first learning platform. It is built
            around the backend’s stable read models: learner summary, learner flow, workflow
            summaries, Socratic session summaries, and remediation session summaries.
          </p>
          <div className="hero-pills">
            <Pill label={`Source: ${dataSource}`} tone={dataSource === 'live' ? 'success' : 'warning'} />
            <Pill label={`Learner: ${learnerId}`} tone="neutral" />
            <Pill label={`Flow: ${flow.flow_type}`} tone="accent" />
          </div>
        </div>
        <div className="hero-panel glass-panel">
          <h2>Workspace Settings</h2>
          <label>
            API base URL
            <Input
              value={config.baseUrl}
              onChange={(event) => setConfig({ ...config, baseUrl: event.target.value })}
              placeholder="http://127.0.0.1:8000"
            />
          </label>
          <label>
            API key
            <Input
              value={config.apiKey}
              onChange={(event) => setConfig({ ...config, apiKey: event.target.value })}
              placeholder="Optional X-API-Key"
            />
          </label>
          <label>
            Bearer token
            <Input
              value={config.bearerToken}
              onChange={(event) => setConfig({ ...config, bearerToken: event.target.value })}
              placeholder="Optional bearer token"
            />
          </label>
          <label className="toggle">
            <input
              type="checkbox"
              checked={config.useDemoFallback}
              onChange={(event) =>
                setConfig({ ...config, useDemoFallback: event.target.checked })
              }
            />
            Use demo fallback when the backend is unavailable
          </label>
        </div>
      </header>

      <Tabs
        value={activeView}
        onValueChange={(value) => setActiveView(value as ViewKey)}
        className="toolbar"
      >
        <div className="workspace-picker glass-panel">
          <div className="workspace-picker__row">
            <label>
              Learner ID
              <Input
                value={learnerId}
                onChange={(event) => setLearnerId(event.target.value)}
                placeholder="Learner UUID"
              />
            </label>
            <Button onClick={() => void loadLearnerWorkspace(learnerId)} disabled={overviewLoading}>
              {overviewLoading ? 'Refreshing...' : 'Refresh learner workspace'}
            </Button>
          </div>
          <div className="learner-chip-row">
            {learnerIds.slice(0, 8).map((id) => (
              <Button key={id} className="chip" variant="secondary" onClick={() => void loadLearnerWorkspace(id)}>
                {id}
              </Button>
            ))}
          </div>
          {overviewError ? <p className="inline-error">{overviewError}</p> : null}
        </div>
        <TabsList className="tabbar" aria-label="Workspace views">
          <TabsTrigger value="overview">Learner Overview</TabsTrigger>
          <TabsTrigger value="generation">Generated Content</TabsTrigger>
          <TabsTrigger value="socratic">Socratic</TabsTrigger>
          <TabsTrigger value="remediation">Remediation</TabsTrigger>
          <TabsTrigger value="teacher">Teacher View</TabsTrigger>
        </TabsList>

        <main className="workspace">
          <TabsContent value="overview">
            <OverviewView summary={summary} profile={profile} flow={flow} />
          </TabsContent>
          <TabsContent value="generation">
            <GenerationView
              form={generationForm}
              onFormChange={setGenerationForm}
              loading={generationLoading}
              error={generationError}
              result={generationResult}
              streaming={streaming}
              streamEvents={streamEvents}
              streamedBlocks={streamedBlocks}
              onGenerate={() => void handleGenerate()}
              onStream={() => void handleStream()}
            />
          </TabsContent>
          <TabsContent value="socratic">
            <SocraticView
              form={socraticForm}
              onFormChange={setSocraticForm}
              loading={socraticLoading}
              error={socraticError}
              response={socraticResponse}
              session={socraticSession}
              onRun={() => void handleSocraticRun()}
              onReload={() => void handleSocraticReload()}
            />
          </TabsContent>
          <TabsContent value="remediation">
            <RemediationView
              form={remediationForm}
              onFormChange={setRemediationForm}
              loading={remediationLoading}
              error={remediationError}
              content={remediationContent}
              session={remediationSession}
              advance={remediationAdvance}
              advancePrompt={remediationAdvancePrompt}
              onAdvancePromptChange={setRemediationAdvancePrompt}
              onTrigger={() => void handleRemediationTrigger()}
              onReload={() => void handleRemediationReload()}
              onAdvance={() => void handleRemediationAdvance()}
            />
          </TabsContent>
          <TabsContent value="teacher">
            <TeacherView
              summary={summary}
              profile={profile}
              flow={flow}
              gaps={deferredTeacherGaps}
              dataSource={dataSource}
            />
          </TabsContent>
        </main>
      </Tabs>
    </div>
  )
}

export default App
