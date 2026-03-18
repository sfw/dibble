import { renderHook, act } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { useLearnerAssignments, useTeacherAssignments } from './useAssignments'
import type { FrontendConfig } from '../types'

vi.mock('../api', () => ({
  getLearnerAssignments: vi.fn().mockResolvedValue({
    items: [
      {
        assignment_id: 'asgn-1',
        student_id: 'student-123',
        teacher_id: 'teacher-1',
        classroom_id: 'class-1',
        title: 'Fractions practice',
        description: 'Practice equivalent fractions',
        status: 'assigned',
        target_resource_id: null,
        target_kc_ids: ['kc-fractions'],
        target_lo_ids: [],
        due_at: '2026-03-20T00:00:00Z',
        created_at: '2026-03-17T12:00:00Z',
        started_at: null,
        completed_at: null,
        updated_at: '2026-03-17T12:00:00Z',
      },
    ],
    offset: 0,
    limit: 20,
    has_more: false,
  }),
  getTeacherAssignments: vi.fn().mockResolvedValue({
    items: [
      {
        assignment_id: 'asgn-1',
        student_id: 'student-123',
        teacher_id: 'teacher-1',
        classroom_id: 'class-1',
        title: 'Fractions practice',
        description: 'Practice equivalent fractions',
        status: 'assigned',
        target_resource_id: null,
        target_kc_ids: ['kc-fractions'],
        target_lo_ids: [],
        due_at: '2026-03-20T00:00:00Z',
        created_at: '2026-03-17T12:00:00Z',
        started_at: null,
        completed_at: null,
        updated_at: '2026-03-17T12:00:00Z',
      },
    ],
    offset: 0,
    limit: 50,
    has_more: false,
  }),
  createAssignment: vi.fn().mockResolvedValue({
    assignment_id: 'asgn-2',
    student_id: 'student-123',
    teacher_id: 'teacher-1',
    classroom_id: 'class-1',
    title: 'Decimals intro',
    description: '',
    status: 'assigned',
    target_resource_id: null,
    target_kc_ids: [],
    target_lo_ids: [],
    due_at: null,
    created_at: '2026-03-17T14:00:00Z',
    started_at: null,
    completed_at: null,
    updated_at: '2026-03-17T14:00:00Z',
  }),
  updateAssignmentStatus: vi.fn().mockResolvedValue({
    assignment_id: 'asgn-1',
    student_id: 'student-123',
    teacher_id: 'teacher-1',
    classroom_id: 'class-1',
    title: 'Fractions practice',
    description: 'Practice equivalent fractions',
    status: 'in_progress',
    target_resource_id: null,
    target_kc_ids: ['kc-fractions'],
    target_lo_ids: [],
    due_at: '2026-03-20T00:00:00Z',
    created_at: '2026-03-17T12:00:00Z',
    started_at: '2026-03-17T13:00:00Z',
    completed_at: null,
    updated_at: '2026-03-17T13:00:00Z',
  }),
}))

const config: FrontendConfig = {
  baseUrl: 'http://localhost:8000',
  apiKey: '',
  bearerToken: 'test-token',
  useDemoFallback: false,
  showDebugPanels: false,
}

describe('useLearnerAssignments', () => {
  it('loads assignments on mount', async () => {
    const { result } = renderHook(() =>
      useLearnerAssignments({ config, learnerId: 'student-123' }),
    )

    // Wait for the async load
    await act(async () => {})

    expect(result.current.assignments).toHaveLength(1)
    expect(result.current.assignments[0].title).toBe('Fractions practice')
    expect(result.current.hasMore).toBe(false)
  })

  it('updates assignment status', async () => {
    const { result } = renderHook(() =>
      useLearnerAssignments({ config, learnerId: 'student-123' }),
    )

    await act(async () => {})

    await act(async () => {
      await result.current.updateStatus('asgn-1', 'in_progress')
    })

    expect(result.current.assignments[0].status).toBe('in_progress')
  })
})

describe('useTeacherAssignments', () => {
  it('loads assignments on mount', async () => {
    const { result } = renderHook(() =>
      useTeacherAssignments({ config }),
    )

    await act(async () => {})

    expect(result.current.assignments).toHaveLength(1)
    expect(result.current.assignments[0].title).toBe('Fractions practice')
  })

  it('creates a new assignment', async () => {
    const { result } = renderHook(() =>
      useTeacherAssignments({ config }),
    )

    await act(async () => {})

    await act(async () => {
      await result.current.create({
        student_id: 'student-123',
        classroom_id: 'class-1',
        title: 'Decimals intro',
      })
    })

    expect(result.current.assignments).toHaveLength(2)
    expect(result.current.assignments[0].title).toBe('Decimals intro')
  })

  it('updates assignment status', async () => {
    const { result } = renderHook(() =>
      useTeacherAssignments({ config }),
    )

    await act(async () => {})

    await act(async () => {
      await result.current.updateStatus('asgn-1', 'in_progress')
    })

    expect(result.current.assignments[0].status).toBe('in_progress')
  })
})
