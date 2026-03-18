import { useState } from 'react'
import { Button } from '../../components/ui/button'
import { postSetupConfigure } from '../../api'
import type { SetupConfigureRequest } from '../../types'

interface Props {
  baseUrl: string
  config: SetupConfigureRequest
  onSuccess: (configPath: string) => void
  onBack: () => void
}

export function SetupVerifyStep({ baseUrl, config, onSuccess, onBack }: Props) {
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  async function handleSave() {
    setSaving(true)
    setError('')
    try {
      const response = await postSetupConfigure(baseUrl, config)
      onSuccess(response.config_path)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save configuration')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="rounded-lg border bg-muted/50 p-4">
        <h3 className="mb-2 text-sm font-medium">Configuration summary</h3>
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
          {config.llm_api_base && (
            <>
              <dt className="text-muted-foreground">API base</dt>
              <dd className="font-mono text-xs">{config.llm_api_base}</dd>
            </>
          )}
          <dt className="text-muted-foreground">API key</dt>
          <dd className="font-mono text-xs">
            {config.llm_api_key ? `${config.llm_api_key.slice(0, 7)}...` : '(not set)'}
          </dd>
          {config.llm_model && (
            <>
              <dt className="text-muted-foreground">Model</dt>
              <dd className="font-mono text-xs">{config.llm_model}</dd>
            </>
          )}
          <dt className="text-muted-foreground">Embedding key</dt>
          <dd className="font-mono text-xs">
            {config.embedding_api_key ? `${config.embedding_api_key.slice(0, 7)}...` : '(same as LLM)'}
          </dd>
        </dl>
      </div>

      <p className="text-sm text-muted-foreground">
        This will write your configuration to <code className="rounded bg-muted px-1 py-0.5 text-xs">~/.dibble/config.toml</code>.
        The server will need to be restarted to pick up the changes.
      </p>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <div className="flex gap-2">
        <Button variant="outline" onClick={onBack}>
          Back
        </Button>
        <Button onClick={() => void handleSave()} disabled={saving}>
          {saving ? 'Saving...' : 'Save configuration'}
        </Button>
      </div>
    </div>
  )
}
