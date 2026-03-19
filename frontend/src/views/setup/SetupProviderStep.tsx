import { useCallback, useEffect, useRef, useState } from 'react'
import { postSetupModelCatalog } from '../../api'
import { Button } from '../../components/ui/button'
import { Input } from '../../components/ui/input'
import { Label } from '../../components/ui/label'
import type { SetupConfigureRequest } from '../../types'

interface Props {
  baseUrl: string
  config: SetupConfigureRequest
  onConfigChange: (config: SetupConfigureRequest) => void
  onNext: () => void
  onBack: () => void
}

export function SetupProviderStep({
  baseUrl,
  config,
  onConfigChange,
  onNext,
  onBack,
}: Props) {
  const [modelOptions, setModelOptions] = useState<string[]>([])
  const [loadingModels, setLoadingModels] = useState(false)
  const [modelError, setModelError] = useState('')
  const lastModelLookupRef = useRef<string | null>(null)

  const update = useCallback((fields: Partial<SetupConfigureRequest>) => {
    onConfigChange({ ...config, ...fields })
  }, [config, onConfigChange])

  const hasKey = Boolean(config.llm_api_key?.trim())
  const hasModel = Boolean(config.llm_model?.trim())

  useEffect(() => {
    const apiBase = config.llm_api_base?.trim()
    const apiKey = config.llm_api_key?.trim()

    if (!apiBase || !apiKey) {
      setModelOptions([])
      setModelError('')
      setLoadingModels(false)
      lastModelLookupRef.current = null
      return
    }

    const lookupKey = `${baseUrl}|${apiBase}|${apiKey}`
    if (lastModelLookupRef.current === lookupKey) {
      return
    }

    const timeoutId = window.setTimeout(() => {
      void (async () => {
        setLoadingModels(true)
        setModelError('')
        try {
          const response = await postSetupModelCatalog(baseUrl, {
            api_base: apiBase,
            api_key: apiKey,
          })
          lastModelLookupRef.current = lookupKey
          setModelOptions(response.models)
          if (!config.llm_model?.trim() && response.models.length > 0) {
            update({ llm_model: response.models[0] })
          }
        } catch (err) {
          setModelOptions([])
          setModelError(
            err instanceof Error ? err.message : 'Could not load models from the provider',
          )
        } finally {
          setLoadingModels(false)
        }
      })()
    }, 400)

    return () => window.clearTimeout(timeoutId)
  }, [baseUrl, config.llm_api_base, config.llm_api_key, config.llm_model, update])

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-2">
        <Label htmlFor="setup-llm-base">LLM API base URL</Label>
        <Input
          id="setup-llm-base"
          type="url"
          placeholder="https://api.openai.com/v1"
          value={config.llm_api_base ?? ''}
          onChange={(e) => update({ llm_api_base: e.target.value || undefined })}
        />
      </div>

      <div className="flex flex-col gap-2">
        <Label htmlFor="setup-llm-key">API key</Label>
        <Input
          id="setup-llm-key"
          type="password"
          placeholder="sk-..."
          value={config.llm_api_key ?? ''}
          onChange={(e) => update({ llm_api_key: e.target.value || undefined })}
          autoComplete="off"
        />
      </div>

      <div className="flex flex-col gap-2">
        <Label htmlFor="setup-llm-model">Model name</Label>
        <Input
          id="setup-llm-model"
          placeholder="gpt-4o"
          value={config.llm_model ?? ''}
          list={modelOptions.length > 0 ? 'setup-llm-model-options' : undefined}
          onChange={(e) => update({ llm_model: e.target.value || undefined })}
        />
        {modelOptions.length > 0 && (
          <datalist id="setup-llm-model-options">
            {modelOptions.map((model) => (
              <option key={model} value={model} />
            ))}
          </datalist>
        )}
        {loadingModels && (
          <p className="text-xs text-muted-foreground">Loading available models from the provider...</p>
        )}
        {!loadingModels && modelOptions.length > 0 && (
          <p className="text-xs text-muted-foreground">
            Loaded {modelOptions.length} model option{modelOptions.length === 1 ? '' : 's'} from the provider.
          </p>
        )}
        {modelError && <p className="text-xs text-destructive">{modelError}</p>}
      </div>

      <div className="flex flex-col gap-2">
        <Label htmlFor="setup-embed-base">Embedding API base URL (optional)</Label>
        <Input
          id="setup-embed-base"
          type="url"
          placeholder="Defaults to the LLM API base URL"
          value={config.embedding_api_base ?? ''}
          onChange={(e) => update({ embedding_api_base: e.target.value || undefined })}
        />
      </div>

      <div className="flex flex-col gap-2">
        <Label htmlFor="setup-embed-key">Embedding API key (optional)</Label>
        <Input
          id="setup-embed-key"
          type="password"
          placeholder="Optional override for a separate embedding provider"
          value={config.embedding_api_key ?? ''}
          onChange={(e) => update({ embedding_api_key: e.target.value || undefined })}
          autoComplete="off"
        />
        <p className="text-xs text-muted-foreground">
          Leave blank to inherit the LLM key only if you want embeddings from the same provider.
        </p>
      </div>

      <div className="flex flex-col gap-2">
        <Label htmlFor="setup-embed-model">Embedding model (optional)</Label>
        <Input
          id="setup-embed-model"
          placeholder="text-embedding-3-small"
          value={config.embedding_model ?? ''}
          onChange={(e) => update({ embedding_model: e.target.value || undefined })}
        />
        <p className="text-xs text-muted-foreground">
          Leave blank to keep the local embedding fallback. If you set an embedding model but no
          embedding base URL, Dibble reuses the LLM API base URL.
        </p>
      </div>

      <div className="flex gap-2">
        <Button variant="outline" onClick={onBack}>
          Back
        </Button>
        <Button onClick={onNext} disabled={!hasKey || !hasModel}>
          Next
        </Button>
      </div>
    </div>
  )
}
