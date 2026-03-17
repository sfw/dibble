import { afterEach, describe, expect, it, vi } from 'vitest'

import { generateContent, getLearnerSummary, streamGeneration } from './api'
import { defaultConfig, demoGeneration, demoProfileSummary } from './sample-data'

const fetchMock = vi.fn<typeof fetch>()

function jsonResponse(body: unknown, init?: ResponseInit) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: {
      'Content-Type': 'application/json',
    },
    ...init,
  })
}

describe('api contract helpers', () => {
  afterEach(() => {
    fetchMock.mockReset()
    vi.unstubAllGlobals()
  })

  it('adds API key auth for learner summary requests', async () => {
    fetchMock.mockResolvedValue(jsonResponse(demoProfileSummary))
    vi.stubGlobal('fetch', fetchMock)

    const config = {
      ...defaultConfig,
      baseUrl: 'https://api.example.com',
      apiKey: 'test-key',
      bearerToken: '',
    }

    const result = await getLearnerSummary(config, demoProfileSummary.student_id)

    expect(result.student_id).toBe(demoProfileSummary.student_id)
    expect(fetchMock).toHaveBeenCalledWith(
      `https://api.example.com/api/learners/${demoProfileSummary.student_id}/summary`,
      expect.objectContaining({
        headers: {
          'X-API-Key': 'test-key',
        },
      }),
    )
  })

  it('prefers bearer auth and posts generation payloads as JSON', async () => {
    fetchMock.mockResolvedValue(jsonResponse(demoGeneration))
    vi.stubGlobal('fetch', fetchMock)

    const config = {
      ...defaultConfig,
      baseUrl: 'https://api.example.com',
      apiKey: 'ignored-key',
      bearerToken: 'bearer-token',
    }
    const payload = {
      student_id: demoGeneration.student_id,
      target_kc_ids: ['KC-1'],
      target_lo_ids: ['LO-1'],
      intent: 'practice',
      curriculum_context: ['Equivalent fractions'],
    }

    const result = await generateContent(config, payload)

    expect(result.generation_id).toBe(demoGeneration.generation_id)
    expect(fetchMock).toHaveBeenCalledWith(
      'https://api.example.com/api/content/generate',
      expect.objectContaining({
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: 'Bearer bearer-token',
        },
        body: JSON.stringify(payload),
      }),
    )
  })

  it('parses server-sent generation stream events in order', async () => {
    const encoder = new TextEncoder()
    const body = new ReadableStream({
      start(controller) {
        controller.enqueue(
          encoder.encode(
            [
              'event: chunk',
              'data: {"chunk":{"block_index":0,"kind":"hint","title":"Bridge","body_delta":"Start from the whole.","done":false}}',
              '',
              'event: complete',
              `data: ${JSON.stringify({ response: demoGeneration.response })}`,
              '',
            ].join('\n'),
          ),
        )
        controller.close()
      },
    })

    fetchMock.mockResolvedValue(
      new Response(body, {
        status: 200,
        headers: {
          'Content-Type': 'text/event-stream',
        },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const events: Array<{ event: string; hasChunk: boolean; hasResponse: boolean }> = []

    await streamGeneration(
      {
        ...defaultConfig,
        baseUrl: 'https://api.example.com',
      },
      {
        student_id: demoGeneration.student_id,
        target_kc_ids: ['KC-1'],
        target_lo_ids: ['LO-1'],
        intent: 'practice',
        curriculum_context: ['Equivalent fractions'],
      },
      (event) => {
        events.push({
          event: event.event,
          hasChunk: Boolean(event.chunk),
          hasResponse: Boolean(event.response),
        })
      },
    )

    expect(events).toEqual([
      { event: 'chunk', hasChunk: true, hasResponse: false },
      { event: 'complete', hasChunk: false, hasResponse: true },
    ])
  })
})
