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
