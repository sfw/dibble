import { useState } from 'react'
import { Button } from '../../components/ui/button'
import { Input } from '../../components/ui/input'
import { Label } from '../../components/ui/label'

interface Props {
  baseUrl: string
  onBaseUrlChange: (url: string) => void
  onNext: () => void
}

export function SetupConnectStep({ baseUrl, onBaseUrlChange, onNext }: Props) {
  const [checking, setChecking] = useState(false)
  const [error, setError] = useState('')
  const [connected, setConnected] = useState(false)

  async function handleCheck() {
    setChecking(true)
    setError('')
    setConnected(false)
    try {
      const response = await fetch(`${baseUrl.trim()}/health`)
      if (!response.ok) {
        throw new Error(`Server returned ${response.status}`)
      }
      const data = (await response.json()) as { status: string }
      if (data.status !== 'ok') {
        throw new Error('Unexpected health response')
      }
      setConnected(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not reach server')
    } finally {
      setChecking(false)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-2">
        <Label htmlFor="setup-base-url">Server URL</Label>
        <Input
          id="setup-base-url"
          type="url"
          placeholder="http://127.0.0.1:8000"
          value={baseUrl}
          onChange={(e) => {
            onBaseUrlChange(e.target.value)
            setConnected(false)
          }}
        />
        <p className="text-xs text-muted-foreground">
          The URL where your Dibble backend is running.
        </p>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}
      {connected && (
        <p className="text-sm text-green-600">Connected successfully.</p>
      )}

      <div className="flex gap-2">
        <Button
          variant="outline"
          onClick={() => void handleCheck()}
          disabled={checking || !baseUrl.trim()}
        >
          {checking ? 'Checking...' : 'Test connection'}
        </Button>
        <Button onClick={onNext} disabled={!connected}>
          Next
        </Button>
      </div>
    </div>
  )
}
