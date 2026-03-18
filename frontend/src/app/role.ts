import { useLocation } from 'react-router'

export type AppRole = 'learner' | 'teacher' | 'staff'

export function useAppRole(): AppRole {
  const { pathname } = useLocation()
  if (pathname.startsWith('/learn')) return 'learner'
  if (pathname.startsWith('/teacher')) return 'teacher'
  return 'staff'
}
