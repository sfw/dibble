import katex from 'katex'
import 'katex/dist/katex.min.css'
import { splitMathSegments } from '../../lib/mathSegments'

/**
 * Renders backend-generated text that may contain LaTeX math delimited with
 * `$...$` (inline) or `$$...$$` (display). Splitting rules (including
 * streaming safety for unmatched delimiters) live in lib/mathSegments.
 */

function renderKatex(content: string, displayMode: boolean): string {
  return katex.renderToString(content, {
    displayMode,
    throwOnError: false,
    output: 'html',
  })
}

export function MathText({ text }: { text: string }) {
  const segments = splitMathSegments(text)
  if (segments.every((segment) => segment.type === 'text')) {
    return <>{text}</>
  }
  return (
    <>
      {segments.map((segment, index) => {
        if (segment.type === 'text') {
          return <span key={index}>{segment.content}</span>
        }
        if (segment.type === 'display') {
          return (
            <span
              key={index}
              className="block py-1 text-center"
              dangerouslySetInnerHTML={{ __html: renderKatex(segment.content, true) }}
            />
          )
        }
        return (
          <span
            key={index}
            dangerouslySetInnerHTML={{ __html: renderKatex(segment.content, false) }}
          />
        )
      })}
    </>
  )
}
