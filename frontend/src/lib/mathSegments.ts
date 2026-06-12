/**
 * Splits backend-generated text into plain-text and LaTeX math segments.
 *
 * Streaming-safe: an unmatched trailing delimiter (a math expression still
 * arriving over SSE) is left as plain text until its closing delimiter
 * arrives, so partial deltas never produce KaTeX errors.
 */

export interface MathSegment {
  type: 'text' | 'inline' | 'display'
  content: string
}

const DISPLAY_MATH = /\$\$([\s\S]+?)\$\$/g
const INLINE_MATH = /\$([^$\n]+?)\$/g

function looksLikeMath(content: string): boolean {
  // Guard against currency false positives like "costs $5 and $3": real math
  // content does not start or end with whitespace.
  return content.trim().length > 0 && content === content.trim()
}

export function splitMathSegments(text: string): MathSegment[] {
  const segments: MathSegment[] = []
  let lastIndex = 0
  DISPLAY_MATH.lastIndex = 0
  for (let match = DISPLAY_MATH.exec(text); match !== null; match = DISPLAY_MATH.exec(text)) {
    if (match.index > lastIndex) {
      segments.push(...splitInline(text.slice(lastIndex, match.index)))
    }
    segments.push({ type: 'display', content: match[1].trim() })
    lastIndex = match.index + match[0].length
  }
  if (lastIndex < text.length) {
    segments.push(...splitInline(text.slice(lastIndex)))
  }
  return segments
}

function splitInline(text: string): MathSegment[] {
  const segments: MathSegment[] = []
  let lastIndex = 0
  INLINE_MATH.lastIndex = 0
  for (let match = INLINE_MATH.exec(text); match !== null; match = INLINE_MATH.exec(text)) {
    if (!looksLikeMath(match[1])) {
      continue
    }
    if (match.index > lastIndex) {
      segments.push({ type: 'text', content: text.slice(lastIndex, match.index) })
    }
    segments.push({ type: 'inline', content: match[1] })
    lastIndex = match.index + match[0].length
  }
  if (lastIndex < text.length) {
    segments.push({ type: 'text', content: text.slice(lastIndex) })
  }
  return segments
}
