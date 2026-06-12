import { useCallback, useEffect, useState } from 'react'
import { Flag, Play } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { startLearnerSession, endLearnerSession } from '../../api'
import type { FrontendConfig, SessionRecap, SessionStartResponse } from '../../types'

const storageKey = (studentId: string) => `dibble-session-${studentId}`

interface StoredSession {
  learning_session_id: string
  goal_display: string
}

function readStoredSession(studentId: string): StoredSession | null {
  try {
    const raw = sessionStorage.getItem(storageKey(studentId))
    return raw ? (JSON.parse(raw) as StoredSession) : null
  } catch {
    return null
  }
}

/**
 * Explicit session start/end for the daily-use rhythm: a per-session goal at
 * the start, a recap at the end. The active session id survives a page
 * refresh via sessionStorage.
 */
export function SessionBookends({
  config,
  studentId,
}: {
  config: FrontendConfig
  studentId: string
}) {
  const [active, setActive] = useState<StoredSession | null>(null)
  const [recap, setRecap] = useState<SessionRecap | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    setActive(readStoredSession(studentId))
  }, [studentId])

  const handleStart = useCallback(async () => {
    setBusy(true)
    setError('')
    setRecap(null)
    try {
      const started: SessionStartResponse = await startLearnerSession(config, studentId)
      const stored: StoredSession = {
        learning_session_id: started.learning_session_id,
        goal_display: started.goal_display,
      }
      sessionStorage.setItem(storageKey(studentId), JSON.stringify(stored))
      setActive(stored)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not start the session')
    } finally {
      setBusy(false)
    }
  }, [config, studentId])

  const handleEnd = useCallback(async () => {
    if (!active) return
    setBusy(true)
    setError('')
    try {
      const ended = await endLearnerSession(config, studentId, active.learning_session_id)
      sessionStorage.removeItem(storageKey(studentId))
      setActive(null)
      setRecap(ended)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not finish the session')
    } finally {
      setBusy(false)
    }
  }, [active, config, studentId])

  return (
    <section className="rounded-xl border bg-white p-6 shadow-sm">
      {active ? (
        <div className="flex flex-col gap-3">
          <p className="text-sm font-semibold text-emerald-700">Session in progress</p>
          <p className="text-base">{active.goal_display}</p>
          <Button variant="outline" onClick={() => void handleEnd()} disabled={busy}>
            <Flag className="mr-2 h-4 w-4" />
            Finish today's session
          </Button>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {recap ? (
            <>
              <p className="text-sm font-semibold text-emerald-700">Session complete</p>
              <p className="text-base">{recap.display_recap}</p>
            </>
          ) : (
            <p className="text-sm text-muted-foreground">
              Ready to learn? Start a session to get today's goal.
            </p>
          )}
          <Button onClick={() => void handleStart()} disabled={busy}>
            <Play className="mr-2 h-4 w-4" />
            Start today's session
          </Button>
        </div>
      )}
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
    </section>
  )
}
