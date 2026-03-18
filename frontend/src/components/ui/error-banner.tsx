import { AlertTriangle } from 'lucide-react'
import { cn } from '@/lib/utils'

export function ErrorBanner({
  message,
  className,
}: {
  message: string | undefined | null
  className?: string
}) {
  if (!message) return null
  return (
    <div className={cn('flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3', className)}>
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-red-500" />
      <p className="text-sm text-red-700">{message}</p>
    </div>
  )
}
