import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  generateContent,
  getLearnerProgression,
  getLearnerSummary,
  getTeacherSection,
  getTeacherSections,
  getLearnerWorkspace,
  recordLearnerObservation,
  recordTeacherInterventionAction,
  streamGeneration,
} from './api'
import {
  defaultConfig,
  demoGeneration,
  demoCurriculumProgression,
  demoTeacherClassroom,
  demoTeacherClassrooms,
  demoLearnerWorkspace,
  demoProfileSummary,
  demoTeacherInterventionAction,
} from './sample-data'

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

  it('requests learner workspace and intervention decision contracts from the new learner endpoints', async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(demoLearnerWorkspace))
      .mockResolvedValueOnce(jsonResponse(demoTeacherInterventionAction))
    vi.stubGlobal('fetch', fetchMock)

    const config = {
      ...defaultConfig,
      baseUrl: 'https://api.example.com',
      apiKey: 'test-key',
    }

    const workspace = await getLearnerWorkspace(config, demoProfileSummary.student_id)
    const intervention = await recordTeacherInterventionAction(config, demoProfileSummary.student_id, {
      decision: 'approve',
      option_id: null,
      note: 'Looks right for this learner.',
    })

    expect(workspace.active_artifact.kind).toBe('generated_content')
    expect(intervention.action_key).toBe(demoTeacherInterventionAction.action_key)
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      `https://api.example.com/api/learners/${demoProfileSummary.student_id}/workspace`,
      expect.objectContaining({
        headers: {
          'X-API-Key': 'test-key',
        },
      }),
    )
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      `https://api.example.com/api/learners/${demoProfileSummary.student_id}/intervention-action`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          decision: 'approve',
          option_id: null,
          note: 'Looks right for this learner.',
        }),
      }),
    )
  })

  it('posts learner observations for generated interactions', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ status: 'ok' }))
    vi.stubGlobal('fetch', fetchMock)

    await recordLearnerObservation(defaultConfig, demoProfileSummary.student_id, {
      response_time_ms: 4200,
      task_type: 'practice',
      support_level: 'medium',
      learning_session_id: 'session-1',
      generation_id: demoGeneration.generation_id,
      observed_content_type: 'practice_problem',
      target_kc_ids: ['KC-1'],
      target_lo_ids: ['LO-1'],
      interaction_events: [
        {
          event_type: 'multiple_choice_selected',
          block_id: 'block-1',
          selected_option_id: 'B',
          correct: true,
        },
      ],
    })

    expect(fetchMock).toHaveBeenCalledWith(
      `${defaultConfig.baseUrl}/api/learners/${demoProfileSummary.student_id}/observations`,
      expect.objectContaining({
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          response_time_ms: 4200,
          task_type: 'practice',
          support_level: 'medium',
          learning_session_id: 'session-1',
          generation_id: demoGeneration.generation_id,
          observed_content_type: 'practice_problem',
          target_kc_ids: ['KC-1'],
          target_lo_ids: ['LO-1'],
          interaction_events: [
            {
              event_type: 'multiple_choice_selected',
              block_id: 'block-1',
              selected_option_id: 'B',
              correct: true,
            },
          ],
        }),
      }),
    )
  })

  it('loads learner progression and teacher classroom contracts', async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(demoCurriculumProgression))
      .mockResolvedValueOnce(jsonResponse(demoTeacherClassrooms))
      .mockResolvedValueOnce(jsonResponse(demoTeacherClassroom))
    vi.stubGlobal('fetch', fetchMock)

    const config = {
      ...defaultConfig,
      baseUrl: 'https://api.example.com',
      apiKey: 'test-key',
    }

    const progression = await getLearnerProgression(config, demoProfileSummary.student_id)
    const classrooms = await getTeacherSections(config)
    const classroom = await getTeacherSection(config, demoTeacherClassroom.section_id)

    expect(progression.status).toBe('active_curriculum_focus')
    expect(classrooms[0]?.section_id).toBe(demoTeacherClassroom.section_id)
    expect(classroom.learners).toHaveLength(2)
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      `https://api.example.com/api/learners/${demoProfileSummary.student_id}/progression`,
      expect.anything(),
    )
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      'https://api.example.com/api/teachers/sections',
      expect.anything(),
    )
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      `https://api.example.com/api/teachers/sections/${demoTeacherClassroom.section_id}`,
      expect.anything(),
    )
  })

  it('surfaces machine-readable backend error codes from the response body or header', async () => {
    fetchMock
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: 'Learner not found', code: 'learner_not_found' }), {
          status: 404,
          headers: {
            'Content-Type': 'application/json',
            'X-Dibble-Error-Code': 'ignored_header_code',
          },
        }),
      )
      .mockResolvedValueOnce(
        new Response('Unavailable', {
          status: 503,
          statusText: 'Service Unavailable',
          headers: {
            'X-Dibble-Error-Code': 'service_unavailable',
          },
        }),
      )
    vi.stubGlobal('fetch', fetchMock)

    await expect(getLearnerWorkspace(defaultConfig, demoProfileSummary.student_id)).rejects.toThrow(
      'Learner not found (learner_not_found)',
    )
    await expect(getLearnerWorkspace(defaultConfig, demoProfileSummary.student_id)).rejects.toThrow(
      '503 Service Unavailable (service_unavailable)',
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
