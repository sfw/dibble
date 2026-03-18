import { Loader2 } from 'lucide-react'
import { ContentBlock } from './ContentBlock'
import type { GeneratedBlock } from '../../types'

/**
 * Progressive content renderer that shows blocks as they stream in.
 * Each block fades in with a staggered delay for a polished feel.
 * Displays a pulsing indicator while streaming is active.
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
        <div
          key={index}
          className="animate-fade-in-up"
          style={{ animationDelay: `${index * 80}ms` }}
        >
          <ContentBlock block={block} />
        </div>
      ))}
      {streaming && (
        <div className="flex items-center gap-3 rounded-xl border border-dashed bg-slate-50 px-5 py-8 text-sm text-muted-foreground animate-fade-in">
          <Loader2 className="h-5 w-5 animate-spin text-primary" />
          <div>
            <p className="font-medium text-foreground">Generating your lesson...</p>
            <p className="text-xs mt-0.5">This usually takes a few seconds</p>
          </div>
        </div>
      )}
    </div>
  )
}
