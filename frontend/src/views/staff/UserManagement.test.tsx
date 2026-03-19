import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { MemoryRouter } from 'react-router'
import { UserManagement } from './UserManagement'
import { AuthContext } from '../../contexts/AuthContext'
import { ConfigContext } from '../../contexts/ConfigContext'
import type { AuthState } from '../../hooks/useAuth'
import {
  bulkCreateUsers,
  createUser,
  deleteUser,
  listUsers,
  rotateUserKey,
  updateUser,
} from '../../api'
import type { UserSummary } from '../../types'

vi.mock('../../api', () => ({
  listUsers: vi.fn(),
  createUser: vi.fn(),
  updateUser: vi.fn(),
  deleteUser: vi.fn(),
  rotateUserKey: vi.fn(),
  bulkCreateUsers: vi.fn(),
}))

const mockedListUsers = vi.mocked(listUsers)
const mockedCreateUser = vi.mocked(createUser)
const mockedUpdateUser = vi.mocked(updateUser)
const mockedDeleteUser = vi.mocked(deleteUser)
const mockedRotateUserKey = vi.mocked(rotateUserKey)
const mockedBulkCreateUsers = vi.mocked(bulkCreateUsers)

function makeAuthState(): AuthState {
  return {
    identity: {
      principal_id: 'admin-1',
      role: 'admin',
      auth_scheme: 'api_key',
      display_name: 'Admin Operator',
      learner_id: null,
    },
    authenticated: true,
    loading: false,
    error: '',
    login: vi.fn(),
    logout: vi.fn().mockResolvedValue(undefined),
    getToken: vi.fn().mockReturnValue(''),
    getApiKey: vi.fn().mockReturnValue('admin-key'),
  }
}

function buildUser(overrides: Partial<UserSummary> = {}): UserSummary {
  return {
    user_id: 'user-1',
    display_name: 'Ava Rivera',
    role: 'learner',
    learner_id: 'student-1',
    classroom_ids: ['room-a'],
    created_at: '2026-03-19T00:00:00Z',
    updated_at: '2026-03-19T00:00:00Z',
    ...overrides,
  }
}

function renderUserManagement() {
  return render(
    <ConfigContext.Provider value={{ baseUrl: 'http://localhost:8000', setBaseUrl: vi.fn() }}>
      <AuthContext.Provider value={makeAuthState()}>
        <MemoryRouter>
          <UserManagement />
        </MemoryRouter>
      </AuthContext.Provider>
    </ConfigContext.Provider>,
  )
}

describe('UserManagement', () => {
  beforeEach(() => {
    mockedListUsers.mockReset()
    mockedCreateUser.mockReset()
    mockedUpdateUser.mockReset()
    mockedDeleteUser.mockReset()
    mockedRotateUserKey.mockReset()
    mockedBulkCreateUsers.mockReset()
  })

  it('shows section memberships as read-only roster context in the table', async () => {
    mockedListUsers.mockResolvedValue([
      buildUser({
        role: 'teacher',
        learner_id: null,
        classroom_ids: ['algebra-1', 'advisory-7'],
      }),
    ])

    renderUserManagement()

    expect(await screen.findByText('algebra-1, advisory-7')).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Sections' })).toBeInTheDocument()
    expect(screen.queryByRole('columnheader', { name: 'Teacher ID' })).not.toBeInTheDocument()
    expect(screen.queryByText('teacher-legacy')).not.toBeInTheDocument()
  })

  it('creates learners without editing section memberships in the user form', async () => {
    mockedListUsers.mockResolvedValue([])
    mockedCreateUser.mockResolvedValue({
      user_id: 'user-2',
      credential: 'key-123',
      display_name: 'Jordan Kim',
      role: 'learner',
    })

    renderUserManagement()

    await screen.findByText('No users yet. Create one to get started.')
    await userEvent.click(screen.getByRole('button', { name: /create user/i }))

    expect(screen.queryByLabelText('Teacher ID')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Classrooms')).not.toBeInTheDocument()

    await userEvent.type(screen.getByLabelText('Display name'), 'Jordan Kim')
    await userEvent.type(screen.getByLabelText('Learner ID'), 'student-44')
    await userEvent.click(screen.getAllByRole('button', { name: /^create user$/i })[1])

    await waitFor(() => {
      expect(mockedCreateUser).toHaveBeenCalledWith(
        expect.objectContaining({ baseUrl: 'http://localhost:8000' }),
        expect.objectContaining({
          display_name: 'Jordan Kim',
          role: 'learner',
          learner_id: 'student-44',
        }),
      )
    })

    expect(mockedCreateUser.mock.calls[0]?.[1]).not.toHaveProperty('teacher_id')
    expect(mockedCreateUser.mock.calls[0]?.[1]).not.toHaveProperty('classroom_ids')
  })

  it('keeps section assignments out of the edit row', async () => {
    mockedListUsers.mockResolvedValue([
      buildUser({
        user_id: 'teacher-1',
        role: 'teacher',
        learner_id: null,
        classroom_ids: ['algebra-1'],
      }),
    ])
    mockedUpdateUser.mockResolvedValue(
      buildUser({
        user_id: 'teacher-1',
        role: 'teacher',
        learner_id: null,
        classroom_ids: ['geometry-2', 'advisory-7'],
      }),
    )

    renderUserManagement()

    await screen.findByText('algebra-1')
    await userEvent.click(screen.getByTitle('Edit'))

    expect(screen.queryByLabelText('Edit classrooms')).not.toBeInTheDocument()
    expect(screen.getByText('Manage in Courses & Sections')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() => {
      expect(mockedUpdateUser).toHaveBeenCalledWith(
        expect.objectContaining({ baseUrl: 'http://localhost:8000' }),
        'teacher-1',
        expect.objectContaining({
          role: 'teacher',
        }),
      )
    })

    expect(mockedUpdateUser.mock.calls[0]?.[2]).not.toHaveProperty('teacher_id')
    expect(mockedUpdateUser.mock.calls[0]?.[2]).not.toHaveProperty('classroom_ids')
  })
})
