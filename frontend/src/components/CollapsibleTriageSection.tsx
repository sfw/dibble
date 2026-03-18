import { useState } from 'react'
import { ChevronRight } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import type { BadgeProps } from '@/components/ui/badge'

export function CollapsibleTriageSection({
  title,
  description,
  tone,
  count,
  defaultExpanded = true,
  children,
}: {
  title: string
  description: string
  tone: 'accent' | 'success' | 'warning' | 'danger' | 'neutral'
  count: number
  defaultExpanded?: boolean
  children: React.ReactNode
}) {
  const [expanded, setExpanded] = useState(defaultExpanded)

  const variant: BadgeProps['variant'] =
    tone === 'success'
      ? 'default'
      : tone === 'warning'
        ? 'warning'
        : tone === 'danger'
          ? 'destructive'
          : tone === 'neutral'
            ? 'outline'
            : 'secondary'

  return (
    <section className="flex flex-col gap-4">
      <button
        type="button"
        className="flex items-start gap-3 text-left w-full group cursor-pointer"
        onClick={() => setExpanded(!expanded)}
        aria-expanded={expanded}
      >
        <ChevronRight
          className={`h-5 w-5 mt-0.5 shrink-0 text-muted-foreground transition-transform duration-200 ${expanded ? 'rotate-90' : ''}`}
        />
        <div className="flex flex-col gap-1 flex-1 md:flex-row md:items-start md:justify-between">
          <div>
            <h3 className="flex items-center gap-2">
              {title}
              <Badge variant={variant}>{count} {count === 1 ? 'learner' : 'learners'}</Badge>
            </h3>
            <p className="muted">{description}</p>
          </div>
        </div>
      </button>
      <div
        className={`grid transition-[grid-template-rows] duration-200 ease-out ${expanded ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]'}`}
      >
        <div className="overflow-hidden">
          <div className="flex flex-col gap-4">
            {children}
          </div>
        </div>
      </div>
    </section>
  )
}
