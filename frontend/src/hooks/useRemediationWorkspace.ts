import { useCallback, useEffect, useState } from 'react'

import { advanceRemediationSession, getRemediationSession, triggerRemediation } from '../api'
import type { DataSource, RemediationFormState } from '../app/workspace'
import { initialRemediationAdvancePrompt, initialRemediationForm } from '../app/workspace'
import {
  buildRemediationAdvancePromptFromWorkspace,
  buildRemediationFormFromWorkspace,
  nullableText,
  parseList,
} from '../lib/forms'
import { asMessage } from '../lib/formatters'
import { demoGeneration, demoRemediationSession } from '../sample-data'
import type {
  FrontendConfig,
  GeneratedContent,
  LearnerWorkspace,
  RemediationWorkflowAdvanceResponse,
  RemediationWorkflowSession,
} from '../types'

export function useRemediationWorkspace({
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
  const [form, setForm] = useState<RemediationFormState>(initialRemediationForm)
  const [content, setContent] = useState<GeneratedContent>(demoGeneration)
  const [session, setSession] = useState<RemediationWorkflowSession>(demoRemediationSession)
  const [advance, setAdvance] = useState<RemediationWorkflowAdvanceResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [advancePrompt, setAdvancePrompt] = useState(initialRemediationAdvancePrompt)

  useEffect(() => {
    setForm(buildRemediationFormFromWorkspace(workspace, initialRemediationForm))
    setSession(workspace.remediation_session ?? demoRemediationSession)
    setContent(workspace.generated_content ?? demoGeneration)
    setAdvance(null)
    setAdvancePrompt(buildRemediationAdvancePromptFromWorkspace(workspace, initialRemediationAdvancePrompt))
    setError('')
  }, [workspace])

  const handleTrigger = useCallback(async () => {
    setLoading(true)
    setError('')
    setAdvance(null)

    try {
      const nextContent = await triggerRemediation(config, {
        student_id: learnerId,
        target_kc_id: form.target_kc_id,
        misconception_description: form.misconception_description,
        learner_prompt: nullableText(form.learner_prompt),
        curriculum_context: parseList(form.curriculum_context),
      })
      setContent(nextContent)

      const rawSessionId = nextContent.request_context.remediation_session_id
      const sessionId = typeof rawSessionId === 'string' ? rawSessionId : ''

      if (sessionId) {
        const nextSession = await getRemediationSession(config, sessionId)
        setSession(nextSession)
      }

      onDataSourceChange('live')
    } catch (caughtError) {
      if (!config.useDemoFallback) {
        setError(asMessage(caughtError))
        return
      }

      setContent(demoGeneration)
      setSession(demoRemediationSession)
      setError(`${asMessage(caughtError)} Showing a demo remediation session instead.`)
      onDataSourceChange('demo')
    } finally {
      setLoading(false)
    }
  }, [config, form, learnerId, onDataSourceChange])

  const handleReload = useCallback(async () => {
    setLoading(true)
    setError('')

    try {
      const nextSession = await getRemediationSession(config, session.session_id)
      setSession(nextSession)
      onDataSourceChange('live')
    } catch (caughtError) {
      if (!config.useDemoFallback) {
        setError(asMessage(caughtError))
      } else {
        setSession(demoRemediationSession)
        setError(`${asMessage(caughtError)} Showing a demo remediation session instead.`)
        onDataSourceChange('demo')
      }
    } finally {
      setLoading(false)
    }
  }, [config, onDataSourceChange, session.session_id])

  const handleAdvance = useCallback(async () => {
    setLoading(true)
    setError('')

    try {
      const nextAdvance = await advanceRemediationSession(config, session.session_id, {
        learner_prompt: nullableText(advancePrompt),
        curriculum_context: session.curriculum_context,
      })
      setAdvance(nextAdvance)
      setSession(nextAdvance.session)
      setContent(nextAdvance.content)
      onDataSourceChange('live')
    } catch (caughtError) {
      if (!config.useDemoFallback) {
        setError(asMessage(caughtError))
      } else {
        setAdvance({
          session: demoRemediationSession,
          content: demoGeneration,
          executed_phase: 'repair',
        })
        setSession(demoRemediationSession)
        setContent(demoGeneration)
        setError(`${asMessage(caughtError)} Showing a demo remediation advance instead.`)
        onDataSourceChange('demo')
      }
    } finally {
      setLoading(false)
    }
  }, [advancePrompt, config, onDataSourceChange, session.curriculum_context, session.session_id])

  return {
    form,
    setForm,
    content,
    session,
    advance,
    loading,
    error,
    advancePrompt,
    setAdvancePrompt,
    handleTrigger,
    handleReload,
    handleAdvance,
  }
}
