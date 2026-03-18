import { Button } from '../../components/ui/button'
import { Input } from '../../components/ui/input'
import { Label } from '../../components/ui/label'
import type { SetupConfigureRequest } from '../../types'

interface Props {
  config: SetupConfigureRequest
  onConfigChange: (config: SetupConfigureRequest) => void
  onNext: () => void
  onBack: () => void
}

export function SetupProviderStep({ config, onConfigChange, onNext, onBack }: Props) {
  function update(fields: Partial<SetupConfigureRequest>) {
    onConfigChange({ ...config, ...fields })
  }

  const hasKey = Boolean(config.llm_api_key?.trim())

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
        <Label htmlFor="setup-llm-model">Model name (optional)</Label>
        <Input
          id="setup-llm-model"
          placeholder="gpt-4o"
          value={config.llm_model ?? ''}
          onChange={(e) => update({ llm_model: e.target.value || undefined })}
        />
      </div>

      <div className="flex flex-col gap-2">
        <Label htmlFor="setup-embed-key">Embedding API key (optional)</Label>
        <Input
          id="setup-embed-key"
          type="password"
          placeholder="Defaults to LLM API key"
          value={config.embedding_api_key ?? ''}
          onChange={(e) => update({ embedding_api_key: e.target.value || undefined })}
          autoComplete="off"
        />
        <p className="text-xs text-muted-foreground">
          Leave blank to use the same key as the LLM provider.
        </p>
      </div>

      <div className="flex gap-2">
        <Button variant="outline" onClick={onBack}>
          Back
        </Button>
        <Button onClick={onNext} disabled={!hasKey}>
          Next
        </Button>
      </div>
    </div>
  )
}
