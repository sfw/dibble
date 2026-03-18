import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { StreamingContent } from './StreamingContent'
import type { GeneratedBlock } from '../../types'

const blocks: GeneratedBlock[] = [
  { kind: 'exposition', title: 'First', body: 'First block body.' },
  { kind: 'code_example', title: 'Code', body: 'console.log("hi")' },
]

describe('StreamingContent', () => {
  it('renders all blocks', () => {
    render(<StreamingContent blocks={blocks} streaming={false} />)
    expect(screen.getByText('First')).toBeInTheDocument()
    expect(screen.getByText('console.log("hi")')).toBeInTheDocument()
  })

  it('shows loading indicator while streaming', () => {
    render(<StreamingContent blocks={[blocks[0]]} streaming={true} />)
    expect(screen.getByText('Generating your lesson...')).toBeInTheDocument()
  })

  it('hides loading indicator when not streaming', () => {
    render(<StreamingContent blocks={blocks} streaming={false} />)
    expect(screen.queryByText('Generating your lesson...')).not.toBeInTheDocument()
  })

  it('renders empty state when no blocks and not streaming', () => {
    const { container } = render(<StreamingContent blocks={[]} streaming={false} />)
    expect(container.querySelectorAll('article')).toHaveLength(0)
  })
})
