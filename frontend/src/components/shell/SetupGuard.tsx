import { Navigate } from 'react-router'
import { useConfigContext } from '../../contexts/ConfigContext'
import { useSetupStatus } from '../../hooks/useSetupStatus'

interface SetupGuardProps {
  mode: 'configured' | 'unconfigured'
  children: React.ReactNode
}

export function SetupGuard({ mode, children }: SetupGuardProps) {
  const { baseUrl } = useConfigContext()
  const { status, reachable, loading } = useSetupStatus(baseUrl)

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center p-6 text-sm text-muted-foreground">
        Checking setup...
      </div>
    )
  }

  if (mode === 'configured') {
    if (!reachable || !status || !status.configured) {
      return <Navigate to="/setup" replace />
    }
  }

  if (reachable && status) {
    if (mode === 'unconfigured' && status.configured) {
      return <Navigate to="/login" replace />
    }
  }

  return <>{children}</>
}
