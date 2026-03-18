import { Heart, HelpCircle, Pause, Sparkles } from 'lucide-react'
import type { ProfileSummary, SignalLevel } from '../../types'

/**
 * Shows contextual support messages based on the learner's affective state.
 *
 * Per the spec: learner surfaces should provide encouragement when engagement
 * is high, gentle nudges when frustration is detected, and offers to simplify
 * when confusion is high. Never shows raw signal names.
 */
export function AffectiveSupport({ summary }: { summary: ProfileSummary }) {
  const message = resolveAffectiveMessage(summary)
  if (!message) return null

  return (
    <div className={`flex items-start gap-3 rounded-xl px-4 py-3 ${message.bgClass}`}>
      <message.icon className={`mt-0.5 h-5 w-5 shrink-0 ${message.iconClass}`} />
      <div>
        <p className={`text-sm font-medium ${message.textClass}`}>{message.title}</p>
        <p className={`mt-0.5 text-sm ${message.detailClass}`}>{message.detail}</p>
      </div>
    </div>
  )
}

interface AffectiveMessage {
  icon: typeof Heart
  title: string
  detail: string
  bgClass: string
  iconClass: string
  textClass: string
  detailClass: string
}

function resolveAffectiveMessage(summary: ProfileSummary): AffectiveMessage | null {
  const frustration = summary.frustration
  const engagement = summary.engagement

  // High frustration takes priority — offer help
  if (isElevated(frustration)) {
    return {
      icon: Pause,
      title: "It's okay to take a break",
      detail: "If this feels tough, try re-reading the last step or ask for a hint. You've got this.",
      bgClass: 'bg-amber-50 border border-amber-200',
      iconClass: 'text-amber-600',
      textClass: 'text-amber-900',
      detailClass: 'text-amber-700',
    }
  }

  // Medium frustration — gentle nudge
  if (frustration === 'medium') {
    return {
      icon: HelpCircle,
      title: 'Need a different approach?',
      detail: "Sometimes seeing an idea from another angle helps. Check the hints if you're stuck.",
      bgClass: 'bg-slate-50 border border-slate-200',
      iconClass: 'text-slate-500',
      textClass: 'text-slate-800',
      detailClass: 'text-slate-600',
    }
  }

  // High engagement — encouragement
  if (isElevated(engagement)) {
    return {
      icon: Sparkles,
      title: "You're on a roll!",
      detail: 'Keep going — your focus is paying off.',
      bgClass: 'bg-blue-50 border border-blue-200',
      iconClass: 'text-blue-500',
      textClass: 'text-blue-900',
      detailClass: 'text-blue-700',
    }
  }

  return null
}

function isElevated(level: SignalLevel): boolean {
  return level === 'high'
}
