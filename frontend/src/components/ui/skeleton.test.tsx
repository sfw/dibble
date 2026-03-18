import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Skeleton, CardSkeleton, PageSkeleton } from './skeleton'

describe('Skeleton', () => {
  it('renders a pulsing placeholder', () => {
    const { container } = render(<Skeleton className="h-4 w-32" />)
    const el = container.firstElementChild!
    expect(el.className).toContain('animate-pulse')
  })
})

describe('CardSkeleton', () => {
  it('renders a card-shaped skeleton with default 3 lines', () => {
    const { container } = render(<CardSkeleton />)
    // 1 heading line + 3 body lines = 4 skeleton bars total
    const bars = container.querySelectorAll('.animate-pulse')
    expect(bars.length).toBe(4)
  })
})

describe('PageSkeleton', () => {
  it('renders a header skeleton and multiple card skeletons', () => {
    const { container } = render(<PageSkeleton cards={2} />)
    // 2 header bars + 2 cards × 4 bars = 10
    const bars = container.querySelectorAll('.animate-pulse')
    expect(bars.length).toBe(10)
  })
})
