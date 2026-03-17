import type { Dispatch, SetStateAction } from 'react'

import { Pill } from '../primitives'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import type { FrontendConfig } from '../../types'
import type { DataSource } from '../../app/workspace'
import { formatContractLabel } from '../../lib/formatters'

export function WorkspaceHero({
  dataSource,
  learnerId,
  flowType,
  config,
  setConfig,
}: {
  dataSource: DataSource
  learnerId: string
  flowType: string
  config: FrontendConfig
  setConfig: Dispatch<SetStateAction<FrontendConfig>>
}) {
  return (
    <header className="hero-shell">
      <div className="hero-copy">
        <p className="eyebrow">Adaptive Learning Frontend Workspace</p>
        <h1>Dibble Control Room</h1>
        <p className="hero-text">
          A React + Vite frontend for the revised generation-first learning platform. It is built
          around the backend’s stable read models: learner summary, learner flow, workflow
          summaries, Socratic session summaries, and remediation session summaries.
        </p>
        <div className="hero-pills">
          <Pill label={`Source: ${dataSource}`} tone={dataSource === 'live' ? 'success' : 'warning'} />
          <Pill label={`Learner: ${learnerId}`} tone="neutral" />
          <Pill label={`Flow: ${formatContractLabel(flowType)}`} tone="accent" />
        </div>
      </div>
      <div className="hero-panel glass-panel">
        <h2>Workspace Settings</h2>
        <label>
          API base URL
          <Input
            value={config.baseUrl}
            onChange={(event) => setConfig((current) => ({ ...current, baseUrl: event.target.value }))}
            placeholder="http://127.0.0.1:8000"
          />
        </label>
        <label>
          API key
          <Input
            value={config.apiKey}
            onChange={(event) => setConfig((current) => ({ ...current, apiKey: event.target.value }))}
            placeholder="Optional X-API-Key"
          />
        </label>
        <label>
          Bearer token
          <Input
            value={config.bearerToken}
            onChange={(event) =>
              setConfig((current) => ({ ...current, bearerToken: event.target.value }))
            }
            placeholder="Optional bearer token"
          />
        </label>
        <div className="toggle">
          <div className="toggle__copy">
            <Label htmlFor="workspace-demo-fallback">Use demo fallback</Label>
            <p className="muted">Show seeded learner workflows when the backend is unavailable.</p>
          </div>
          <Switch
            id="workspace-demo-fallback"
            checked={config.useDemoFallback}
            onCheckedChange={(checked) =>
              setConfig((current) => ({ ...current, useDemoFallback: checked }))
            }
          />
        </div>
        <div className="toggle">
          <div className="toggle__copy">
            <Label htmlFor="workspace-debug-panels">Show debug payload panels</Label>
            <p className="muted">Reveal raw contract payloads for integration debugging.</p>
          </div>
          <Switch
            id="workspace-debug-panels"
            checked={config.showDebugPanels}
            onCheckedChange={(checked) =>
              setConfig((current) => ({ ...current, showDebugPanels: checked }))
            }
          />
        </div>
      </div>
    </header>
  )
}
