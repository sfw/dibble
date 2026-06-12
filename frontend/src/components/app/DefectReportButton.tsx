import { useState } from 'react'
import { Flag } from 'lucide-react'
import { reportContentDefect } from '../../api'
import type { FrontendConfig } from '../../types'

/**
 * "Something's wrong with this question" — writes a content.defect.report
 * audit event keyed by generation_id so defects are enumerable during the
 * pilot. Deliberately low-friction: one tap, no required text.
 */
export function DefectReportButton({
  config,
  studentId,
  generationId,
  learningSessionId,
}: {
  config: FrontendConfig
  studentId: string
  generationId: string
  learningSessionId?: string | null
}) {
  const [state, setState] = useState<'idle' | 'sending' | 'sent'>('idle')
  const [message, setMessage] = useState('')

  if (state === 'sent') {
    return <p className="text-xs text-muted-foreground">{message}</p>
  }

  return (
    <button
      type="button"
      disabled={state === 'sending'}
      onClick={() => {
        setState('sending')
        void reportContentDefect(config, studentId, {
          generation_id: generationId,
          learning_session_id: learningSessionId ?? null,
        })
          .then((response) => {
            setMessage(response.display_message)
            setState('sent')
          })
          .catch(() => {
            setMessage("Thanks — we couldn't send that right now, but keep going.")
            setState('sent')
          })
      }}
      className="flex items-center gap-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground disabled:opacity-50"
    >
      <Flag className="h-3.5 w-3.5" />
      Something wrong with this question?
    </button>
  )
}
