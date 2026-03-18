import { useCallback, useEffect, useRef, useState } from 'react'

import {
  getGenerationHistory,
  getRemediationHistory,
  getSocraticHistory,
  getTeacherInterventionAction,
  recordTeacherInterventionAction,
} from '../api'
import type { DataSource } from '../app/workspace'
import { asMessage } from '../lib/formatters'
import {
  demoGenerationHistory,
  demoRemediationHistory,
  demoSocraticHistory,
  demoTeacherInterventionAction,
} from '../sample-data'
import type {
  FrontendConfig,
  LearnerGenerationHistoryEntry,
  LearnerRemediationSessionHistoryEntry,
  LearnerSocraticSessionHistoryEntry,
  TeacherInterventionActionContract,
  TeacherInterventionDecisionRequest,
} from '../types'

export function useLearnerContracts({
  config,
  learnerId,
  onDataSourceChange,
}: {
  config: FrontendConfig
  learnerId: string
  onDataSourceChange: (source: DataSource) => void
}) {
  const hasBootstrapped = useRef(false)
  const [generationHistory, setGenerationHistory] =
    useState<LearnerGenerationHistoryEntry[]>(demoGenerationHistory)
  const [socraticHistory, setSocraticHistory] =
    useState<LearnerSocraticSessionHistoryEntry[]>(demoSocraticHistory)
  const [remediationHistory, setRemediationHistory] =
    useState<LearnerRemediationSessionHistoryEntry[]>(demoRemediationHistory)
  const [hasMoreGenerations, setHasMoreGenerations] = useState(false)
  const [hasMoreSocratic, setHasMoreSocratic] = useState(false)
  const [hasMoreRemediation, setHasMoreRemediation] = useState(false)
  const [intervention, setIntervention] =
    useState<TeacherInterventionActionContract>(demoTeacherInterventionAction)
  const [loading, setLoading] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState('')
  const [submittingIntervention, setSubmittingIntervention] = useState(false)
  const [interventionError, setInterventionError] = useState('')

  const applyDemoFallback = useCallback(
    (message: string) => {
      setGenerationHistory(demoGenerationHistory)
      setSocraticHistory(demoSocraticHistory)
      setRemediationHistory(demoRemediationHistory)
      setIntervention(demoTeacherInterventionAction)
      setError(message)
      onDataSourceChange('demo')
    },
    [onDataSourceChange],
  )

  const loadContracts = useCallback(async (nextLearnerId?: string) => {
    const targetLearnerId = nextLearnerId ?? learnerId
    setLoading(true)
    setError('')

    try {
      const [generationPage, socraticPage, remediationPage, nextIntervention] =
        await Promise.all([
          getGenerationHistory(config, targetLearnerId),
          getSocraticHistory(config, targetLearnerId),
          getRemediationHistory(config, targetLearnerId),
          getTeacherInterventionAction(config, targetLearnerId),
        ])

      setGenerationHistory(generationPage.items)
      setHasMoreGenerations(generationPage.has_more)
      setSocraticHistory(socraticPage.items)
      setHasMoreSocratic(socraticPage.has_more)
      setRemediationHistory(remediationPage.items)
      setHasMoreRemediation(remediationPage.has_more)
      setIntervention(nextIntervention)
      onDataSourceChange('live')
    } catch (caughtError) {
      if (!config.useDemoFallback) {
        setError(asMessage(caughtError))
        return
      }

      applyDemoFallback(`${asMessage(caughtError)} Showing demo contract data instead.`)
    } finally {
      setLoading(false)
    }
  }, [applyDemoFallback, config, learnerId, onDataSourceChange])

  const loadMoreHistory = useCallback(async () => {
    setLoadingMore(true)
    try {
      const fetches: Promise<void>[] = []

      if (hasMoreGenerations) {
        fetches.push(
          getGenerationHistory(config, learnerId, 20, generationHistory.length).then((page) => {
            setGenerationHistory((prev) => [...prev, ...page.items])
            setHasMoreGenerations(page.has_more)
          }),
        )
      }
      if (hasMoreSocratic) {
        fetches.push(
          getSocraticHistory(config, learnerId, 20, socraticHistory.length).then((page) => {
            setSocraticHistory((prev) => [...prev, ...page.items])
            setHasMoreSocratic(page.has_more)
          }),
        )
      }
      if (hasMoreRemediation) {
        fetches.push(
          getRemediationHistory(config, learnerId, 20, remediationHistory.length).then((page) => {
            setRemediationHistory((prev) => [...prev, ...page.items])
            setHasMoreRemediation(page.has_more)
          }),
        )
      }

      await Promise.all(fetches)
    } catch (caughtError) {
      setError(asMessage(caughtError))
    } finally {
      setLoadingMore(false)
    }
  }, [config, learnerId, generationHistory.length, socraticHistory.length, remediationHistory.length, hasMoreGenerations, hasMoreSocratic, hasMoreRemediation])

  const hasMoreHistory = hasMoreGenerations || hasMoreSocratic || hasMoreRemediation

  const submitTeacherDecision = useCallback(
    async (payload: TeacherInterventionDecisionRequest) => {
      setSubmittingIntervention(true)
      setInterventionError('')

      try {
        const nextIntervention = await recordTeacherInterventionAction(config, learnerId, payload)
        setIntervention(nextIntervention)
        onDataSourceChange('live')
      } catch (caughtError) {
        if (!config.useDemoFallback) {
          setInterventionError(asMessage(caughtError))
          return
        }

        const recommendedOption =
          demoTeacherInterventionAction.available_options.find((option) => option.is_recommended) ?? null
        const selectedOption =
          payload.decision === 'select_option'
            ? demoTeacherInterventionAction.available_options.find((option) => option.option_id === payload.option_id) ??
              recommendedOption
            : payload.decision === 'approve'
              ? recommendedOption
              : null

        setIntervention({
          ...demoTeacherInterventionAction,
          latest_decision: {
            action_key: demoTeacherInterventionAction.action_key,
            decision_id: 'teacher-decision-demo-local',
            decision: payload.decision,
            status:
              payload.decision === 'approve'
                ? 'approved'
                : payload.decision === 'select_option'
                  ? 'option_selected'
                  : payload.decision === 'escalate_human'
                    ? 'escalated_human'
                    : 'deferred',
            selected_option_id:
              payload.decision === 'approve' || payload.decision === 'select_option'
                ? selectedOption?.option_id ?? null
                : null,
            note: payload.note ?? null,
            decided_by: 'Demo teacher',
            decided_role: 'teacher',
            decided_at: '2026-03-17T12:00:00Z',
            execution_action: selectedOption?.continue_action ?? demoTeacherInterventionAction.proposed_action,
          },
        })
        setInterventionError(`${asMessage(caughtError)} Recorded a demo decision instead.`)
        onDataSourceChange('demo')
      } finally {
        setSubmittingIntervention(false)
      }
    },
    [config, learnerId, onDataSourceChange],
  )

  useEffect(() => {
    if (hasBootstrapped.current && !learnerId) {
      return
    }

    hasBootstrapped.current = true
    void loadContracts()
  }, [learnerId, loadContracts])

  return {
    generationHistory,
    socraticHistory,
    remediationHistory,
    intervention,
    loading,
    error,
    hasMoreHistory,
    loadingMore,
    loadMoreHistory,
    submittingIntervention,
    interventionError,
    loadContracts,
    submitTeacherDecision,
  }
}
