import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { MathText } from './MathText'
import { splitMathSegments } from '../../lib/mathSegments'

describe('splitMathSegments', () => {
  it('splits inline math out of surrounding text', () => {
    const segments = splitMathSegments('Add $\\frac{3}{4} + \\frac{1}{8}$ to find the sum.')

    expect(segments).toEqual([
      { type: 'text', content: 'Add ' },
      { type: 'inline', content: '\\frac{3}{4} + \\frac{1}{8}' },
      { type: 'text', content: ' to find the sum.' },
    ])
  })

  it('splits display math', () => {
    const segments = splitMathSegments('Solve: $$\\frac{1}{2} \\times 6 = 3$$ Done.')

    expect(segments.map((segment) => segment.type)).toEqual(['text', 'display', 'text'])
  })

  it('leaves unmatched trailing delimiters as text for streaming safety', () => {
    const segments = splitMathSegments('The sum is $\\frac{7}')

    expect(segments).toEqual([{ type: 'text', content: 'The sum is $\\frac{7}' }])
  })

  it('does not treat currency amounts as math', () => {
    const segments = splitMathSegments('It costs $5 and $3 at the store.')

    expect(segments.every((segment) => segment.type === 'text')).toBe(true)
  })

  it('returns plain text untouched', () => {
    expect(splitMathSegments('No math here.')).toEqual([
      { type: 'text', content: 'No math here.' },
    ])
  })
})

describe('MathText', () => {
  it('renders KaTeX markup for inline math', () => {
    const { container } = render(<MathText text="Add $\frac{3}{4}$ now." />)

    expect(container.querySelector('.katex')).not.toBeNull()
    expect(container.textContent).toContain('Add')
  })

  it('renders display math as a block', () => {
    const { container } = render(<MathText text="$$\frac{1}{2} + \frac{1}{4}$$" />)

    expect(container.querySelector('.katex-display, .katex')).not.toBeNull()
  })

  it('renders plain text without KaTeX wrappers', () => {
    const { container } = render(<MathText text="Three quarters plus one eighth." />)

    expect(container.querySelector('.katex')).toBeNull()
    expect(container.textContent).toBe('Three quarters plus one eighth.')
  })

  it('does not crash on malformed latex', () => {
    const { container } = render(<MathText text={'Broken $\\frac{3}{$ math'} />)

    expect(container.textContent).toContain('Broken')
  })
})
