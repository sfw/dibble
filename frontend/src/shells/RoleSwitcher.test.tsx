import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router'
import { RoleSwitcher } from './RoleSwitcher'
import { AuthContext } from '../contexts/AuthContext'
import type { AuthState } from '../hooks/useAuth'

const unauthenticated: AuthState = {
  identity: null,
  authenticated: false,
  loading: false,
  error: '',
  login: vi.fn(),
  logout: vi.fn(),
  getToken: vi.fn().mockReturnValue(''),
}

function renderSwitcher(auth: AuthState = unauthenticated) {
  return render(
    <AuthContext.Provider value={auth}>
      <MemoryRouter>
        <RoleSwitcher />
      </MemoryRouter>
    </AuthContext.Provider>,
  )
}

describe('RoleSwitcher', () => {
  it('renders all three role cards', () => {
    renderSwitcher()
    expect(screen.getByText('Learner')).toBeInTheDocument()
    expect(screen.getByText('Teacher')).toBeInTheDocument()
    expect(screen.getByText('Staff')).toBeInTheDocument()
  })

  it('links learner card to /learn', () => {
    renderSwitcher()
    const learnerLink = screen.getByText('Learner').closest('a')
    expect(learnerLink).toHaveAttribute('href', '/learn')
  })

  it('links teacher card to /teacher', () => {
    renderSwitcher()
    const teacherLink = screen.getByText('Teacher').closest('a')
    expect(teacherLink).toHaveAttribute('href', '/teacher')
  })

  it('links staff card to /staff', () => {
    renderSwitcher()
    const staffLink = screen.getByText('Staff').closest('a')
    expect(staffLink).toHaveAttribute('href', '/staff')
  })

  it('shows sign in link', () => {
    renderSwitcher()
    expect(screen.getByText('Sign in with an API key')).toBeInTheDocument()
  })
})
