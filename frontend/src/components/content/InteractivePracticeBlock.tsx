import { useRef, useState } from 'react'
import { CheckCircle2, Circle, ArrowRight } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import type { GeneratedBlock } from '../../types'

export interface PracticeInteractionSubmission {
  blockId: string
  selectedOptionId: string
  isCorrect: boolean
  responseText: string
  responseTimeMs: number
  hintsUsed: number
}

export function InteractivePracticeBlock({
  block,
  disabled = false,
  onSubmit,
}: {
  block: GeneratedBlock
  disabled?: boolean
  onSubmit: (submission: PracticeInteractionSubmission) => void
}) {
  const interaction = block.interaction
  const startedAt = useRef<number | null>(null)
  const [selectedOptionId, setSelectedOptionId] = useState<string | null>(null)
  const [responseText, setResponseText] = useState('')

  if (interaction?.type !== 'multiple_choice') {
    return null
  }

  const reveal = interaction.reveal
  const selectedOption = selectedOptionId
    ? interaction.options.find((option) => option.option_id === selectedOptionId) ?? null
    : null
  const canSubmit = selectedOptionId !== null && (reveal == null || responseText.trim().length > 0)

  return (
    <article className="rounded-xl border-l-4 border-l-emerald-400 bg-white p-6 shadow-sm">
      {block.title && <h2 className="mb-3 text-lg font-semibold">{block.title}</h2>}
      {block.body && <p className="mb-4 text-sm leading-6 text-slate-600">{block.body}</p>}

      <div className="space-y-3">
        <p className="text-base font-medium leading-7 text-slate-900">{interaction.prompt}</p>
        {interaction.options.map((option) => {
          const selected = option.option_id === selectedOptionId
          return (
            <button
              key={option.option_id}
              type="button"
              disabled={disabled}
              onClick={() => {
                if (startedAt.current === null) {
                  startedAt.current = Date.now()
                }
                setSelectedOptionId(option.option_id)
              }}
              className={[
                'w-full rounded-xl border px-4 py-4 text-left transition-colors',
                selected
                  ? 'border-emerald-500 bg-emerald-50 shadow-sm'
                  : 'border-slate-200 bg-slate-50 hover:border-slate-300 hover:bg-white',
                disabled ? 'cursor-not-allowed opacity-70' : '',
              ].join(' ')}
            >
              <div className="flex items-start gap-3">
                {selected ? (
                  <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" />
                ) : (
                  <Circle className="mt-0.5 h-5 w-5 shrink-0 text-slate-400" />
                )}
                <div className="space-y-1">
                  <p className="text-sm font-semibold text-slate-900">{option.label}</p>
                  <p className="whitespace-pre-line text-sm leading-6 text-slate-700">
                    {option.body}
                  </p>
                </div>
              </div>
            </button>
          )
        })}
      </div>

      {selectedOption && reveal && (
        <div className="mt-5 rounded-xl border bg-emerald-50/60 p-4">
          <p className="text-sm font-semibold text-emerald-900">Verify your reasoning</p>
          <p className="mt-2 text-sm leading-6 text-emerald-950">{reveal.prompt}</p>
          {reveal.support && (
            <p className="mt-3 text-xs leading-5 text-emerald-800">{reveal.support}</p>
          )}
          <Textarea
            value={responseText}
            onChange={(event) => setResponseText(event.target.value)}
            disabled={disabled}
            placeholder={reveal.placeholder ?? 'Explain your thinking.'}
            className="mt-4 min-h-[110px] resize-none bg-white"
          />
        </div>
      )}

      <Button
        type="button"
        onClick={() => {
          if (!selectedOptionId) {
            return
          }
          onSubmit({
            blockId: block.block_id ?? block.title,
            selectedOptionId,
            isCorrect: selectedOptionId === interaction.correct_option_id,
            responseText: responseText.trim(),
            responseTimeMs: Date.now() - (startedAt.current ?? Date.now()),
            hintsUsed: reveal?.support ? 1 : 0,
          })
        }}
        disabled={disabled || !canSubmit}
        className="mt-5 w-full"
        size="lg"
      >
        Submit and continue
        <ArrowRight className="ml-2 h-4 w-4" />
      </Button>
    </article>
  )
}
