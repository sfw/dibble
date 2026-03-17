import { useCallback, useState } from 'react'

import { generateContent, streamGeneration } from '../api'
import type { DataSource, GenerationFormState } from '../app/workspace'
import { buildGenerationPayload, applyStreamChunk } from '../lib/forms'
import { asMessage } from '../lib/formatters'
import { demoGeneration } from '../sample-data'
import type { FrontendConfig, GeneratedBlock, GeneratedContent, GenerationStreamEvent } from '../types'
import { initialGenerationForm } from '../app/workspace'

export function useGenerationWorkspace({
  config,
  learnerId,
  onDataSourceChange,
}: {
  config: FrontendConfig
  learnerId: string
  onDataSourceChange: (source: DataSource) => void
}) {
  const [form, setForm] = useState<GenerationFormState>(initialGenerationForm)
  const [result, setResult] = useState<GeneratedContent>(demoGeneration)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [streamEvents, setStreamEvents] = useState<GenerationStreamEvent[]>([])
  const [streamedBlocks, setStreamedBlocks] = useState<GeneratedBlock[]>([])

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

  const handleStream = useCallback(async () => {
    setStreaming(true)
    setError('')
    setStreamEvents([])
    setStreamedBlocks([])

    try {
      const payload = buildGenerationPayload(learnerId, form)
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
            content_type: form.requested_content_type || form.intent || 'generated_content',
            request_context: {
              learning_session_id: form.learning_session_id,
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
