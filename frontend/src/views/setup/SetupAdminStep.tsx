import { useState } from 'react'
import { Copy, Check, ShieldAlert } from 'lucide-react'
import { Button } from '../../components/ui/button'
import { Input } from '../../components/ui/input'
import { Label } from '../../components/ui/label'
import { useConfigContext } from '../../contexts/ConfigContext'
import { postSetupAdmin } from '../../api'

interface Props {
  onNext: () => void
  onBack: () => void
}

export function SetupAdminStep({ onNext, onBack }: Props) {
  const { baseUrl } = useConfigContext()
  const [displayName, setDisplayName] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState(false)
  const [confirmed, setConfirmed] = useState(false)

  async function handleCreate() {
    setLoading(true)
    setError('')
    try {
      const result = await postSetupAdmin(baseUrl, {
        display_name: displayName.trim() || undefined,
      })
      setApiKey(result.api_key)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create admin')
    } finally {
      setLoading(false)
    }
  }

  async function handleCopy() {
    await navigator.clipboard.writeText(apiKey)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  if (apiKey) {
    return (
      <div className="flex flex-col gap-4">
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
          <div className="flex items-start gap-2">
            <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
            <div>
              <p className="font-medium">Save this API key now</p>
              <p className="mt-1">This key will not be shown again. You will need it to sign in as admin.</p>
            </div>
          </div>
        </div>

        <div className="flex flex-col gap-2">
          <Label>Admin API key</Label>
          <div className="flex gap-2">
            <code className="flex-1 rounded-md border bg-muted px-3 py-2 text-xs break-all">
              {apiKey}
            </code>
            <Button variant="outline" size="icon" onClick={() => void handleCopy()}>
              {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
            </Button>
          </div>
        </div>

        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={confirmed}
            onChange={(e) => setConfirmed(e.target.checked)}
            className="rounded"
          />
          I have saved this API key
        </label>

        <Button onClick={onNext} disabled={!confirmed}>
          Continue
        </Button>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">
        Create the first admin account. This user can manage all settings and other users.
      </p>

      <div className="flex flex-col gap-2">
        <Label htmlFor="admin-name">Display name (optional)</Label>
        <Input
          id="admin-name"
          placeholder="e.g. Admin"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
        />
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <div className="flex gap-2">
        <Button variant="outline" onClick={onBack}>
          Back
        </Button>
        <Button onClick={() => void handleCreate()} disabled={loading} className="flex-1">
          {loading ? 'Creating...' : 'Create admin account'}
        </Button>
      </div>
    </div>
  )
}
