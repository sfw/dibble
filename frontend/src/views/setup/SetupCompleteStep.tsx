import { useNavigate } from 'react-router'
import { Button } from '../../components/ui/button'
import { useConfigContext } from '../../contexts/ConfigContext'
import { useSetupStatus } from '../../hooks/useSetupStatus'

interface Props {
  configPath: string
}

export function SetupCompleteStep({ configPath }: Props) {
  const navigate = useNavigate()
  const { baseUrl } = useConfigContext()
  const { status, loading, refetch } = useSetupStatus(baseUrl)
  const readyForSignIn = status?.configured === true

  return (
    <div className="flex flex-col gap-4">
      <div className="rounded-lg border border-green-200 bg-green-50 p-4 text-sm text-green-800">
        Configuration saved to <code className="rounded bg-green-100 px-1 py-0.5 text-xs">{configPath}</code>.
      </div>

      <p className="text-sm text-muted-foreground">
        Restart the Dibble server for the new configuration to take effect.
        Once restarted, you can sign in to start using the platform.
      </p>

      {!readyForSignIn && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
          The running backend still reports the setup as incomplete. Restart it, then check again.
        </div>
      )}

      <Button
        onClick={() => {
          if (readyForSignIn) {
            navigate('/login', { replace: true })
            return
          }
          refetch()
        }}
        disabled={loading}
      >
        {readyForSignIn
          ? 'Go to sign in'
          : loading
            ? 'Checking server...'
            : 'Check server again'}
      </Button>
    </div>
  )
}
