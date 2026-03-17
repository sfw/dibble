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
