export function formatPercent(value: number | null | undefined): string {
  if (value == null) {
    return 'n/a'
  }
  return `${Math.round(value * 100)}%`
}

export function signedPercent(value: number): string {
  const prefix = value > 0 ? '+' : ''
  return `${prefix}${Math.round(value * 100)}%`
}

export function asMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Unknown error'
}

export function formatTimestamp(value: string | null | undefined): string {
  if (!value) {
    return 'n/a'
  }

  try {
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: 'medium',
      timeStyle: 'short',
    }).format(new Date(value))
  } catch {
    return value
  }
}

export function titleCase(value: string | null | undefined): string {
  if (!value) {
    return 'n/a'
  }

  return value
    .split(/[_-]/g)
    .filter(Boolean)
    .map((token) => token.charAt(0).toUpperCase() + token.slice(1))
    .join(' ')
}

export function formatContractLabel(value: string | null | undefined, fallback = 'n/a'): string {
  if (!value) {
    return fallback
  }

  return titleCase(value)
}

export function formatContentType(value: string | null | undefined): string {
  if (!value) {
    return 'Monitor'
  }

  return formatContractLabel(value)
}

export function formatArtifactKind(value: string | null | undefined): string {
  if (!value) {
    return 'Unknown artifact'
  }

  if (value === 'generated_content') {
    return 'Generated content'
  }
  if (value === 'socratic_session') {
    return 'Socratic session'
  }
  if (value === 'remediation_session') {
    return 'Remediation session'
  }

  return formatContractLabel(value)
}

export function formatContinueAction(value: string | null | undefined): string {
  if (!value || value === 'idle') {
    return 'No immediate action'
  }

  if (value === 'generate_follow_up') {
    return 'Continue generated content'
  }
  if (value === 'advance_remediation') {
    return 'Continue remediation'
  }
  if (value === 'continue_socratic') {
    return 'Continue Socratic'
  }

  return formatContractLabel(value)
}

export function formatAttentionReason(value: string): string {
  if (value === 'blocked_on_prerequisites') {
    return 'Blocked on prerequisites'
  }
  if (value === 'teacher_intervention_available') {
    return 'Teacher intervention ready'
  }

  return formatContractLabel(value)
}
