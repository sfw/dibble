import { Navigate } from 'react-router'
import { useAuthContext } from '../../contexts/AuthContext'

interface AuthGuardProps {
  allowedRoles: string[]
  children: React.ReactNode
}

export function AuthGuard({ allowedRoles, children }: AuthGuardProps) {
  const { authenticated, identity } = useAuthContext()

  if (!authenticated || !identity) {
    return <Navigate to="/login" replace />
  }

  if (!allowedRoles.includes(identity.role)) {
    // Redirect to the correct shell based on their role
    if (identity.role === 'learner') return <Navigate to="/learn" replace />
    if (identity.role === 'teacher') return <Navigate to="/teacher" replace />
    return <Navigate to="/staff" replace />
  }

  return <>{children}</>
}
