import { useNavigate } from 'react-router'
import { Button } from '../../components/ui/button'

interface Props {
  configPath: string
}

export function SetupCompleteStep({ configPath }: Props) {
  const navigate = useNavigate()

  return (
    <div className="flex flex-col gap-4">
      <div className="rounded-lg border border-green-200 bg-green-50 p-4 text-sm text-green-800">
        Configuration saved to <code className="rounded bg-green-100 px-1 py-0.5 text-xs">{configPath}</code>.
      </div>

      <p className="text-sm text-muted-foreground">
        Restart the Dibble server for the new configuration to take effect.
        Once restarted, you can sign in to start using the platform.
      </p>

      <Button onClick={() => navigate('/', { replace: true })}>
        Go to sign in
      </Button>
    </div>
  )
}
