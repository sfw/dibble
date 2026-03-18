import { Loader2 } from 'lucide-react'
import { ContentBlock } from './ContentBlock'
import type { GeneratedBlock } from '../../types'

/**
 * Progressive content renderer that shows blocks as they stream in.
 * Displays a loading indicator while streaming is active.
 */
export function StreamingContent({
  blocks,
  streaming,
}: {
  blocks: GeneratedBlock[]
  streaming: boolean
}) {
  return (
    <div className="flex flex-col gap-4">
      {blocks.map((block, index) => (
        <ContentBlock key={index} block={block} />
      ))}
      {streaming && (
        <div className="flex items-center gap-2 rounded-xl border border-dashed bg-slate-50 px-4 py-6 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          <span>Generating your lesson...</span>
        </div>
      )}
    </div>
  )
}
