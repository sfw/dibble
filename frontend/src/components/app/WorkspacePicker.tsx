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
    <div className="glass-panel flex flex-col gap-4">
      <div className="grid items-end gap-4 md:grid-cols-[minmax(0,1fr)_auto]">
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
      <div className="flex flex-wrap gap-3">
        {learnerIds.slice(0, 8).map((id) => (
          <Button key={id} variant="secondary" size="sm" onClick={() => onPickLearner(id)}>
            {id}
          </Button>
        ))}
      </div>
      {error ? <p className="inline-error">{error}</p> : null}
    </div>
  )
}
