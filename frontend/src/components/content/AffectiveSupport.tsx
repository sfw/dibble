import { Heart, HelpCircle, Pause, Sparkles } from 'lucide-react'
import type { AffectiveSupportMessage } from '../../types'

/**
 * Renders an affective support message for the learner.
 *
 * The backend owns the decision about when to show encouragement, nudges,
 * or break suggestions. It provides an `affective_support` field on the
 * learner workspace with { kind, title, detail } or null.
 *
 * When null, the component renders nothing.
 */
export function AffectiveSupport({ message }: { message?: AffectiveSupportMessage | null }) {
  if (!message) return null

  const style = styleForKind(message.kind)

  return (
    <div className={`flex items-start gap-3 rounded-xl px-4 py-3 ${style.bgClass}`}>
      <style.icon className={`mt-0.5 h-5 w-5 shrink-0 ${style.iconClass}`} />
      <div>
        <p className={`text-sm font-medium ${style.textClass}`}>{message.title}</p>
        <p className={`mt-0.5 text-sm ${style.detailClass}`}>{message.detail}</p>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Visual styling per message kind — presentation only, no pedagogical logic
// ---------------------------------------------------------------------------

interface AffectiveStyle {
  icon: typeof Heart
  bgClass: string
  iconClass: string
  textClass: string
  detailClass: string
}

function styleForKind(kind: string): AffectiveStyle {
  switch (kind) {
    case 'break_suggestion':
      return {
        icon: Pause,
        bgClass: 'bg-amber-50 border border-amber-200',
        iconClass: 'text-amber-600',
        textClass: 'text-amber-900',
        detailClass: 'text-amber-700',
      }
    case 'nudge':
      return {
        icon: HelpCircle,
        bgClass: 'bg-slate-50 border border-slate-200',
        iconClass: 'text-slate-500',
        textClass: 'text-slate-800',
        detailClass: 'text-slate-600',
      }
    case 'encouragement':
      return {
        icon: Sparkles,
        bgClass: 'bg-blue-50 border border-blue-200',
        iconClass: 'text-blue-500',
        textClass: 'text-blue-900',
        detailClass: 'text-blue-700',
      }
    default:
      return {
        icon: Heart,
        bgClass: 'bg-gray-50 border border-gray-200',
        iconClass: 'text-gray-500',
        textClass: 'text-gray-800',
        detailClass: 'text-gray-600',
      }
  }
}
