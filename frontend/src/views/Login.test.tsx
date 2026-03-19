import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router'
import { Login } from './Login'
import { AuthContext } from '../contexts/AuthContext'
import { ConfigContext } from '../contexts/ConfigContext'
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
      display_name: 'Alice',
    }),
    logout: vi.fn().mockResolvedValue(undefined),
    getToken: vi.fn().mockReturnValue(''),
    getApiKey: vi.fn().mockReturnValue(''),
    ...authOverrides,
  }

  return render(
    <ConfigContext.Provider value={{ baseUrl: 'http://localhost:8000', setBaseUrl: vi.fn() }}>
      <AuthContext.Provider value={defaultAuth}>
        <MemoryRouter>
          <Login />
        </MemoryRouter>
      </AuthContext.Provider>
    </ConfigContext.Provider>,
  )
}

describe('Login', () => {
  it('renders the login form with student mode by default', () => {
    renderWithAuth()
    expect(screen.getByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(screen.getByLabelText('Passphrase')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument()
  })

  it('shows student and staff toggle buttons', () => {
    renderWithAuth()
    expect(screen.getByRole('button', { name: 'Student' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Staff' })).toBeInTheDocument()
  })

  it('switches to staff mode with API key input', async () => {
    renderWithAuth()
    await userEvent.click(screen.getByRole('button', { name: 'Staff' }))
    expect(screen.getByLabelText('API key')).toBeInTheDocument()
  })

  it('shows passphrase placeholder in student mode', () => {
    renderWithAuth()
    expect(screen.getByPlaceholderText('e.g. blue tiger runs fast')).toBeInTheDocument()
  })

  it('disables submit when credential is empty', () => {
    renderWithAuth()
    const button = screen.getByRole('button', { name: /sign in/i })
    expect(button).toBeDisabled()
  })

  it('shows loading state', () => {
    renderWithAuth({ loading: true })
    expect(screen.getByText('Signing in...')).toBeInTheDocument()
  })

  it('displays error message', () => {
    renderWithAuth({ error: 'Invalid credentials' })
    expect(screen.getByText('Invalid credentials')).toBeInTheDocument()
  })

  it('shows advanced settings only in staff mode', async () => {
    renderWithAuth()
    // Student mode — no advanced settings link
    expect(screen.queryByText('Advanced settings')).not.toBeInTheDocument()

    // Switch to staff mode
    await userEvent.click(screen.getByRole('button', { name: 'Staff' }))
    expect(screen.getByText('Advanced settings')).toBeInTheDocument()
  })
})
