import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { AffectiveSupport } from './AffectiveSupport'

describe('AffectiveSupport', () => {
  it('shows break suggestion', () => {
    render(
      <AffectiveSupport
        message={{ kind: 'break_suggestion', title: "It's okay to take a break", detail: 'Take your time.' }}
      />,
    )
    expect(screen.getByText("It's okay to take a break")).toBeInTheDocument()
  })

  it('shows nudge', () => {
    render(
      <AffectiveSupport
        message={{ kind: 'nudge', title: 'Need a different approach?', detail: 'Try the hints.' }}
      />,
    )
    expect(screen.getByText('Need a different approach?')).toBeInTheDocument()
  })

  it('shows encouragement', () => {
    render(
      <AffectiveSupport
        message={{ kind: 'encouragement', title: "You're on a roll!", detail: 'Keep going.' }}
      />,
    )
    expect(screen.getByText("You're on a roll!")).toBeInTheDocument()
  })

  it('renders nothing when message is null', () => {
    const { container } = render(<AffectiveSupport message={null} />)
    expect(container.innerHTML).toBe('')
  })

  it('renders nothing when message is undefined', () => {
    const { container } = render(<AffectiveSupport />)
    expect(container.innerHTML).toBe('')
  })

  it('handles unknown kind gracefully', () => {
    render(
      <AffectiveSupport
        message={{ kind: 'new_kind', title: 'Something new', detail: 'From the backend.' }}
      />,
    )
    expect(screen.getByText('Something new')).toBeInTheDocument()
  })
})
