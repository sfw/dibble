import type { PropsWithChildren } from 'react'

import { Label } from '@/components/ui/label'
import { cn } from '@/lib/utils'

export function FormGrid({ className, children }: PropsWithChildren<{ className?: string }>) {
  return <div className={cn('grid gap-4 md:grid-cols-2', className)}>{children}</div>
}

export function FormField({
  label,
  htmlFor,
  className,
  children,
}: PropsWithChildren<{
  label: string
  htmlFor: string
  className?: string
}>) {
  return (
    <div className={cn('flex flex-col gap-2', className)}>
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
    </div>
  )
}

export function FormActions({ className, children }: PropsWithChildren<{ className?: string }>) {
  return <div className={cn('flex flex-wrap gap-3', className)}>{children}</div>
}

export function InlineError({ message }: { message: string }) {
  return <p className="font-semibold text-destructive">{message}</p>
}
