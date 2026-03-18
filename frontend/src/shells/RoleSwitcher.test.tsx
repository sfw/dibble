import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { MemoryRouter } from 'react-router'
import { RoleSwitcher } from './RoleSwitcher'

describe('RoleSwitcher', () => {
  it('renders all three role cards', () => {
    render(
      <MemoryRouter>
        <RoleSwitcher />
      </MemoryRouter>,
    )
    expect(screen.getByText('Learner')).toBeInTheDocument()
    expect(screen.getByText('Teacher')).toBeInTheDocument()
    expect(screen.getByText('Staff')).toBeInTheDocument()
  })

  it('links learner card to /learn', () => {
    render(
      <MemoryRouter>
        <RoleSwitcher />
      </MemoryRouter>,
    )
    const learnerLink = screen.getByText('Learner').closest('a')
    expect(learnerLink).toHaveAttribute('href', '/learn')
  })

  it('links teacher card to /teacher', () => {
    render(
      <MemoryRouter>
        <RoleSwitcher />
      </MemoryRouter>,
    )
    const teacherLink = screen.getByText('Teacher').closest('a')
    expect(teacherLink).toHaveAttribute('href', '/teacher')
  })

  it('links staff card to /staff', () => {
    render(
      <MemoryRouter>
        <RoleSwitcher />
      </MemoryRouter>,
    )
    const staffLink = screen.getByText('Staff').closest('a')
    expect(staffLink).toHaveAttribute('href', '/staff')
  })
})
