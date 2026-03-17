import type { Dispatch, SetStateAction } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

export function WorkspacePicker({
  learnerId,
  setLearnerId,
  learnerIds,
  loading,
  error,
  onRefresh,
  onPickLearner,
}: {
  learnerId: string
  setLearnerId: Dispatch<SetStateAction<string>>
  learnerIds: string[]
  loading: boolean
  error: string
  onRefresh: () => void
  onPickLearner: (learnerId: string) => void
}) {
  return (
    <div className="workspace-picker glass-panel">
      <div className="workspace-picker__row">
        <label>
          Learner ID
          <Input
            value={learnerId}
            onChange={(event) => setLearnerId(event.target.value)}
            placeholder="Learner UUID"
          />
        </label>
        <Button onClick={onRefresh} disabled={loading}>
          {loading ? 'Refreshing...' : 'Refresh learner workspace'}
        </Button>
      </div>
      <div className="learner-chip-row">
        {learnerIds.slice(0, 8).map((id) => (
          <Button key={id} className="chip" variant="secondary" onClick={() => onPickLearner(id)}>
            {id}
          </Button>
        ))}
      </div>
      {error ? <p className="inline-error">{error}</p> : null}
    </div>
  )
}
