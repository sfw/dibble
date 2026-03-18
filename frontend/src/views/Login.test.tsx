import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router'
import { Login } from './Login'
import { AuthContext } from '../contexts/AuthContext'
import type { AuthState } from '../hooks/useAuth'

function renderWithAuth(authOverrides: Partial<AuthState> = {}) {
  const defaultAuth: AuthState = {
    identity: null,
    authenticated: false,
    loading: false,
    error: '',
    login: vi.fn().mockResolvedValue({
      principal_id: 'learner-1',
      role: 'learner',
      auth_scheme: 'bearer',
      learner_id: 'student-123',
      teacher_id: null,
      display_name: 'Alice',
      classroom_ids: [],
    }),
    logout: vi.fn().mockResolvedValue(undefined),
    getToken: vi.fn().mockReturnValue(''),
    ...authOverrides,
  }

  return render(
    <AuthContext.Provider value={defaultAuth}>
      <MemoryRouter>
        <Login />
      </MemoryRouter>
    </AuthContext.Provider>,
  )
}

describe('Login', () => {
  it('renders the login form', () => {
    renderWithAuth()
    expect(screen.getByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(screen.getByLabelText('API key')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument()
  })

  it('disables submit when API key is empty', () => {
    renderWithAuth()
    const button = screen.getByRole('button', { name: /sign in/i })
    expect(button).toBeDisabled()
  })

  it('shows loading state', () => {
    renderWithAuth({ loading: true })
    expect(screen.getByText('Signing in...')).toBeInTheDocument()
  })

  it('displays error message', () => {
    renderWithAuth({ error: 'Invalid API key' })
    expect(screen.getByText('Invalid API key')).toBeInTheDocument()
  })

  it('shows advanced settings toggle', () => {
    renderWithAuth()
    expect(screen.getByText('Advanced settings')).toBeInTheDocument()
  })
})
