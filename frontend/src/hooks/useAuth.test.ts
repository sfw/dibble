import { renderHook, act } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { useAuth } from './useAuth'

vi.mock('../api', () => ({
  issueAuthToken: vi.fn().mockResolvedValue({
    access_token: 'test-access-token',
    refresh_token: 'test-refresh-token',
    token_type: 'Bearer',
    expires_in: 3600,
    identity: {
      principal_id: 'learner-1',
      role: 'learner',
      auth_scheme: 'bearer',
      learner_id: 'student-123',
      teacher_id: null,
      display_name: 'Alice Student',
      classroom_ids: [],
    },
  }),
  getAuthIdentity: vi.fn().mockResolvedValue({
    principal_id: 'admin-1',
    role: 'admin',
    auth_scheme: 'api_key',
    learner_id: null,
    teacher_id: null,
    display_name: 'Admin User',
    classroom_ids: [],
  }),
  refreshAuthToken: vi.fn().mockResolvedValue({
    access_token: 'refreshed-token',
    refresh_token: 'refreshed-refresh',
    token_type: 'Bearer',
    expires_in: 3600,
    identity: {
      principal_id: 'learner-1',
      role: 'learner',
      auth_scheme: 'bearer',
      learner_id: 'student-123',
      teacher_id: null,
      display_name: 'Alice Student',
      classroom_ids: [],
    },
  }),
  revokeAuthToken: vi.fn().mockResolvedValue({ status: 'revoked' }),
}))

describe('useAuth', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it('starts unauthenticated with no stored session', () => {
    const { result } = renderHook(() => useAuth('http://localhost:8000'))
    expect(result.current.authenticated).toBe(false)
    expect(result.current.identity).toBeNull()
  })

  it('logs in and stores session', async () => {
    const { result } = renderHook(() => useAuth('http://localhost:8000'))

    let identity: { role: string; learner_id?: string | null } | undefined
    await act(async () => {
      identity = await result.current.login('test-key', 'http://localhost:8000')
    })

    expect(identity?.role).toBe('learner')
    expect(identity?.learner_id).toBe('student-123')
    expect(result.current.authenticated).toBe(true)
    expect(result.current.identity?.display_name).toBe('Alice Student')
    expect(window.localStorage.getItem('dibble-auth')).toBeTruthy()
  })

  it('logs out and clears session', async () => {
    const { result } = renderHook(() => useAuth('http://localhost:8000'))

    await act(async () => {
      await result.current.login('test-key', 'http://localhost:8000')
    })
    expect(result.current.authenticated).toBe(true)

    await act(async () => {
      await result.current.logout()
    })
    expect(result.current.authenticated).toBe(false)
    expect(result.current.identity).toBeNull()
    expect(window.localStorage.getItem('dibble-auth')).toBeNull()
  })

  it('restores session from localStorage', () => {
    const stored = {
      apiKey: '',
      accessToken: 'stored-token',
      authMode: 'bearer',
      refreshToken: 'stored-refresh',
      identity: {
        principal_id: 'learner-1',
        role: 'learner',
        auth_scheme: 'bearer',
        learner_id: 'student-123',
        teacher_id: null,
        display_name: 'Alice Student',
        classroom_ids: [],
      },
      expiresAt: Date.now() + 3600_000,
    }
    window.localStorage.setItem('dibble-auth', JSON.stringify(stored))

    const { result } = renderHook(() => useAuth('http://localhost:8000'))
    expect(result.current.authenticated).toBe(true)
    expect(result.current.identity?.role).toBe('learner')
  })

  it('getToken returns the access token', async () => {
    const { result } = renderHook(() => useAuth('http://localhost:8000'))

    await act(async () => {
      await result.current.login('test-key', 'http://localhost:8000')
    })

    expect(result.current.getToken()).toBe('test-access-token')
  })

  it('falls back to an API key session when bearer tokens are unavailable', async () => {
    const { issueAuthToken } = await import('../api')
    vi.mocked(issueAuthToken).mockRejectedValueOnce(
      new Error('Bearer token issuance requires DIBBLE_AUTH_TOKEN_SECRET. (auth_token_unavailable)'),
    )

    const { result } = renderHook(() => useAuth('http://localhost:8000'))

    await act(async () => {
      await result.current.login('staff-key', 'http://localhost:8000')
    })

    expect(result.current.authenticated).toBe(true)
    expect(result.current.identity?.role).toBe('admin')
    expect(result.current.getToken()).toBe('')
    expect(result.current.getApiKey()).toBe('staff-key')
  })
})
