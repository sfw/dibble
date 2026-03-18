import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Button } from '@/components/ui/button'
import { LayoutGrid, List } from 'lucide-react'

export type AttentionFilter = 'all' | 'high' | 'medium' | 'low'
export type InterventionFilter = 'all' | 'has_intervention'
export type LayoutMode = 'card' | 'compact'

export function ClassroomFilterBar({
  searchQuery,
  onSearchChange,
  attentionFilter,
  onAttentionFilterChange,
  interventionFilter,
  onInterventionFilterChange,
  layoutMode,
  onLayoutModeChange,
  filteredCount,
  totalCount,
}: {
  searchQuery: string
  onSearchChange: (value: string) => void
  attentionFilter: AttentionFilter
  onAttentionFilterChange: (value: AttentionFilter) => void
  interventionFilter: InterventionFilter
  onInterventionFilterChange: (value: InterventionFilter) => void
  layoutMode: LayoutMode
  onLayoutModeChange: (value: LayoutMode) => void
  filteredCount: number
  totalCount: number
}) {
  const isFiltered = searchQuery !== '' || attentionFilter !== 'all' || interventionFilter !== 'all'

  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:flex-wrap">
      <Input
        type="text"
        placeholder="Search by student ID..."
        value={searchQuery}
        onChange={(e) => onSearchChange(e.target.value)}
        className="sm:max-w-[220px]"
        aria-label="Search by student ID"
      />
      <Select value={attentionFilter} onValueChange={(v) => onAttentionFilterChange(v as AttentionFilter)}>
        <SelectTrigger className="sm:max-w-[180px]" aria-label="Attention level filter">
          <SelectValue placeholder="Attention level" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All attention levels</SelectItem>
          <SelectItem value="high">High attention</SelectItem>
          <SelectItem value="medium">Medium attention</SelectItem>
          <SelectItem value="low">Low attention</SelectItem>
        </SelectContent>
      </Select>
      <Button
        type="button"
        variant={interventionFilter === 'has_intervention' ? 'default' : 'outline'}
        size="sm"
        onClick={() =>
          onInterventionFilterChange(interventionFilter === 'all' ? 'has_intervention' : 'all')
        }
        aria-label="Filter by intervention"
        aria-pressed={interventionFilter === 'has_intervention'}
      >
        {interventionFilter === 'has_intervention' ? 'Has intervention' : 'All interventions'}
      </Button>

      <div className="flex items-center gap-2 sm:ml-auto">
        {isFiltered ? (
          <span className="text-sm text-muted-foreground" data-testid="filter-count">
            {filteredCount} of {totalCount} learners
          </span>
        ) : null}
        <div className="flex rounded-xl border border-input overflow-hidden">
          <button
            type="button"
            className={`p-2 transition-colors ${layoutMode === 'card' ? 'bg-accent text-accent-foreground' : 'bg-white text-muted-foreground hover:bg-accent/50'}`}
            onClick={() => onLayoutModeChange('card')}
            aria-label="Card layout"
            aria-pressed={layoutMode === 'card'}
          >
            <LayoutGrid className="h-4 w-4" />
          </button>
          <button
            type="button"
            className={`p-2 transition-colors ${layoutMode === 'compact' ? 'bg-accent text-accent-foreground' : 'bg-white text-muted-foreground hover:bg-accent/50'}`}
            onClick={() => onLayoutModeChange('compact')}
            aria-label="Compact layout"
            aria-pressed={layoutMode === 'compact'}
          >
            <List className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  )
}
