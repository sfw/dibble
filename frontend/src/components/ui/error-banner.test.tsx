import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ErrorBanner } from './error-banner'

describe('ErrorBanner', () => {
  it('renders nothing when message is empty', () => {
    const { container } = render(<ErrorBanner message="" />)
    expect(container.firstChild).toBeNull()
  })

  it('renders nothing when message is null', () => {
    const { container } = render(<ErrorBanner message={null} />)
    expect(container.firstChild).toBeNull()
  })

  it('renders error message when provided', () => {
    render(<ErrorBanner message="Something went wrong" />)
    expect(screen.getByText('Something went wrong')).toBeInTheDocument()
  })
})
