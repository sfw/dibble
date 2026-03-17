import { useCallback, useEffect, useState } from 'react'

import { getSocraticSession, runSocraticAssessment } from '../api'
import type { DataSource, SocraticFormState } from '../app/workspace'
import { initialSocraticForm } from '../app/workspace'
import { buildSocraticFormFromWorkspace, nullableNumber, nullableText, parseList } from '../lib/forms'
import { asMessage } from '../lib/formatters'
import { demoSocraticResponse, demoSocraticSession } from '../sample-data'
import type {
  FrontendConfig,
  LearnerWorkspace,
  SocraticAssessmentResponse,
  SocraticAssessmentSession,
} from '../types'

export function useSocraticWorkspace({
  config,
  learnerId,
  workspace,
  onDataSourceChange,
}: {
  config: FrontendConfig
  learnerId: string
  workspace: LearnerWorkspace
  onDataSourceChange: (source: DataSource) => void
}) {
  const [form, setForm] = useState<SocraticFormState>({
    ...initialSocraticForm,
    session_id: demoSocraticResponse.session_id,
  })
  const [response, setResponse] = useState<SocraticAssessmentResponse>(demoSocraticResponse)
  const [session, setSession] = useState<SocraticAssessmentSession>(demoSocraticSession)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    setForm(buildSocraticFormFromWorkspace(workspace, initialSocraticForm))
    setSession(workspace.socratic_session ?? demoSocraticSession)
    setError('')
  }, [workspace])

  const handleRun = useCallback(async () => {
    setLoading(true)
    setError('')

    try {
      const nextResponse = await runSocraticAssessment(config, {
        student_id: learnerId,
        session_id: nullableText(form.session_id),
        learning_session_id: nullableText(form.learning_session_id),
        target_kc_ids: parseList(form.target_kc_ids),
        target_lo_ids: parseList(form.target_lo_ids),
        curriculum_context: parseList(form.curriculum_context),
        learner_response: nullableText(form.learner_response),
        learner_confidence: nullableNumber(form.learner_confidence),
      })

      setResponse(nextResponse)
      setForm((current) => ({ ...current, session_id: nextResponse.session_id }))

      const nextSession = await getSocraticSession(config, nextResponse.session_id)
      setSession(nextSession)
      onDataSourceChange('live')
    } catch (caughtError) {
      if (!config.useDemoFallback) {
        setError(asMessage(caughtError))
        return
      }

      setResponse(demoSocraticResponse)
      setSession(demoSocraticSession)
      setError(`${asMessage(caughtError)} Showing a demo Socratic session instead.`)
      onDataSourceChange('demo')
    } finally {
      setLoading(false)
    }
  }, [config, form, learnerId, onDataSourceChange])

  const handleReload = useCallback(async () => {
    const sessionId = nullableText(form.session_id)
    if (!sessionId) {
      setError('Enter a Socratic session ID to load.')
      return
    }

    setLoading(true)
    setError('')

    try {
      const nextSession = await getSocraticSession(config, sessionId)
      setSession(nextSession)
      onDataSourceChange('live')
    } catch (caughtError) {
      if (!config.useDemoFallback) {
        setError(asMessage(caughtError))
      } else {
        setSession(demoSocraticSession)
        setError(`${asMessage(caughtError)} Showing a demo Socratic session instead.`)
        onDataSourceChange('demo')
      }
    } finally {
      setLoading(false)
    }
  }, [config, form.session_id, onDataSourceChange])

  return {
    form,
    setForm,
    response,
    session,
    loading,
    error,
    handleRun,
    handleReload,
  }
}
