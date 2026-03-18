import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ContentBlock } from './ContentBlock'
import type { GeneratedBlock } from '../../types'

function makeBlock(overrides: Partial<GeneratedBlock> = {}): GeneratedBlock {
  return {
    kind: 'exposition',
    title: 'Test Block',
    body: 'Test body content.',
    ...overrides,
  }
}

describe('ContentBlock', () => {
  it('renders exposition blocks with title and body', () => {
    render(<ContentBlock block={makeBlock()} />)
    expect(screen.getByText('Test Block')).toBeInTheDocument()
    expect(screen.getByText('Test body content.')).toBeInTheDocument()
  })

  it('renders code_example blocks with pre/code elements', () => {
    render(
      <ContentBlock
        block={makeBlock({ kind: 'code_example', title: 'Code', body: 'const x = 1' })}
      />,
    )
    expect(screen.getByText('const x = 1')).toBeInTheDocument()
    expect(screen.getByText('const x = 1').closest('code')).toBeInTheDocument()
  })

  it('renders worked_example blocks with blue border styling', () => {
    const { container } = render(
      <ContentBlock block={makeBlock({ kind: 'worked_example', title: 'Example' })} />,
    )
    const article = container.querySelector('article')
    expect(article?.className).toContain('border-l-blue-400')
  })

  it('renders practice_problem blocks with green border styling', () => {
    const { container } = render(
      <ContentBlock block={makeBlock({ kind: 'practice_problem', title: 'Practice' })} />,
    )
    const article = container.querySelector('article')
    expect(article?.className).toContain('border-l-emerald-400')
  })

  it('renders remediation blocks with amber styling', () => {
    const { container } = render(
      <ContentBlock block={makeBlock({ kind: 'remediation', title: 'Remediation' })} />,
    )
    const article = container.querySelector('article')
    expect(article?.className).toContain('bg-amber-50')
  })

  it('renders scaffolded_steps as an ordered list', () => {
    render(
      <ContentBlock
        block={makeBlock({
          kind: 'scaffolded_steps',
          title: 'Steps',
          body: '1. First step\n2. Second step\n3. Third step',
        })}
      />,
    )
    const items = screen.getAllByRole('listitem')
    expect(items).toHaveLength(3)
    expect(items[0]).toHaveTextContent('First step')
  })

  it('falls back to default rendering for unknown kinds', () => {
    render(<ContentBlock block={makeBlock({ kind: 'unknown_kind' })} />)
    expect(screen.getByText('Test Block')).toBeInTheDocument()
    expect(screen.getByText('Test body content.')).toBeInTheDocument()
  })

  it('renders blocks without a title', () => {
    render(<ContentBlock block={makeBlock({ title: '' })} />)
    expect(screen.getByText('Test body content.')).toBeInTheDocument()
    expect(screen.queryByRole('heading')).not.toBeInTheDocument()
  })
})
