import { useCallback, useEffect, useState } from 'react'

import { generateContent, streamGeneration } from '../api'
import type { DataSource, GenerationFormState } from '../app/workspace'
import { initialGenerationForm } from '../app/workspace'
import { applyStreamChunk, buildGenerationFormFromWorkspace, buildGenerationPayload } from '../lib/forms'
import { asMessage } from '../lib/formatters'
import { demoGeneration } from '../sample-data'
import type {
  FrontendConfig,
  GeneratedBlock,
  GeneratedContent,
  GenerationStreamEvent,
  LearnerWorkspace,
} from '../types'

export function useGenerationWorkspace({
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
  const [form, setForm] = useState<GenerationFormState>(initialGenerationForm)
  const [result, setResult] = useState<GeneratedContent | null>(
    workspace.generated_content ?? null,
  )
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [streamEvents, setStreamEvents] = useState<GenerationStreamEvent[]>([])
  const [streamedBlocks, setStreamedBlocks] = useState<GeneratedBlock[]>([])

  useEffect(() => {
    setForm(buildGenerationFormFromWorkspace(workspace, initialGenerationForm))
    setResult(workspace.generated_content ?? null)
    setError('')
    setStreamEvents([])
    setStreamedBlocks([])
  }, [workspace])

  const handleGenerate = useCallback(async () => {
    setLoading(true)
    setError('')

    try {
      const payload = buildGenerationPayload(learnerId, form)
      const nextResult = await generateContent(config, payload)
      setResult(nextResult)
      onDataSourceChange('live')
    } catch (caughtError) {
      if (!config.useDemoFallback) {
        setError(asMessage(caughtError))
        return
      }

      setResult(demoGeneration)
      setError(`${asMessage(caughtError)} Showing a demo generation instead.`)
      onDataSourceChange('demo')
    } finally {
      setLoading(false)
    }
  }, [config, form, learnerId, onDataSourceChange])

  const handleStream = useCallback(async (overrides?: Partial<GenerationFormState>) => {
    setStreaming(true)
    setError('')
    setStreamEvents([])
    setStreamedBlocks([])

    try {
      const nextForm = { ...form, ...overrides }
      const payload = buildGenerationPayload(learnerId, nextForm)
      await streamGeneration(config, payload, (event) => {
        setStreamEvents((current) => [...current, event])

        const chunk = event.chunk
        if (chunk) {
          setStreamedBlocks((current) => applyStreamChunk(current, chunk))
        }

        if (event.response) {
          setResult({
            generation_id: event.response.generation_id ?? 'stream-complete',
            student_id: learnerId,
            content_type: nextForm.requested_content_type || nextForm.intent || 'generated_content',
            request_context: {
              learning_session_id: nextForm.learning_session_id,
              source: 'stream',
            },
            workflow_summary: null,
            response: event.response,
            quality: event.response.generation_metadata ?? null,
            created_at: event.response.generated_at,
            expires_at: null,
          })
        }
      })
      onDataSourceChange('live')
    } catch (caughtError) {
      if (!config.useDemoFallback) {
        setError(asMessage(caughtError))
      } else {
        setResult(demoGeneration)
        setStreamedBlocks(demoGeneration.response.blocks)
        setError(`${asMessage(caughtError)} Showing a demo stream result instead.`)
        onDataSourceChange('demo')
      }
    } finally {
      setStreaming(false)
    }
  }, [config, form, learnerId, onDataSourceChange])

  return {
    form,
    setForm,
    result,
    loading,
    error,
    streaming,
    streamEvents,
    streamedBlocks,
    handleGenerate,
    handleStream,
  }
}
