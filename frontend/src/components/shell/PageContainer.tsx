import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

export function PageContainer({
  children,
  className,
  size = 'default',
}: {
  children: ReactNode
  className?: string
  size?: 'narrow' | 'default' | 'wide'
}) {
  return (
    <div
      className={cn(
        'mx-auto w-full',
        size === 'narrow' && 'max-w-2xl',
        size === 'default' && 'max-w-5xl',
        size === 'wide' && 'max-w-7xl',
        className,
      )}
    >
      {children}
    </div>
  )
}
