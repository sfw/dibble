import { useEffect, useMemo, useState } from 'react'
import { RefreshCw, Save } from 'lucide-react'
import { getSystemConfig, updateSystemConfig } from '../../api'
import { Badge } from '../../components/ui/badge'
import { Button } from '../../components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card'
import { ErrorBanner } from '../../components/ui/error-banner'
import { Input } from '../../components/ui/input'
import { Label } from '../../components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select'
import { Switch } from '../../components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs'
import type { SystemConfigValues } from '../../types'
import { systemConfigSections, type SystemConfigFieldKey, type SystemConfigFieldDefinition } from './systemConfigSchema'
import { useStaffApiConfig } from './useStaffApiConfig'

function normalizeNullableString(value: string) {
  return value.trim() ? value : null
}

function buildConfigPatch(
  draft: SystemConfigValues,
  savedConfig: SystemConfigValues,
): Partial<SystemConfigValues> {
  const entries = Object.entries(draft).filter(([key, value]) => (
    JSON.stringify(value) !== JSON.stringify(savedConfig[key as SystemConfigFieldKey])
  ))

  return Object.fromEntries(entries) as Partial<SystemConfigValues>
}

function ConfigField({
  field,
  value,
  onChange,
}: {
  field: SystemConfigFieldDefinition
  value: SystemConfigValues[SystemConfigFieldKey]
  onChange: (key: SystemConfigFieldKey, value: SystemConfigValues[SystemConfigFieldKey]) => void
}) {
  const id = `config-${field.key}`

  if (field.input === 'boolean') {
    return (
      <div className="rounded-2xl border border-border bg-white/80 p-4">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-1">
            <Label htmlFor={id} className="text-sm font-medium text-slate-900">{field.label}</Label>
            <p className="text-sm leading-6 text-slate-500">{field.description}</p>
          </div>
          <Switch
            id={id}
            checked={Boolean(value)}
            onCheckedChange={(checked) => onChange(field.key, checked)}
          />
        </div>
      </div>
    )
  }

  if (field.input === 'select') {
    return (
      <div className="flex flex-col gap-2 rounded-2xl border border-border bg-white/80 p-4">
        <Label htmlFor={id} className="text-sm font-medium text-slate-900">{field.label}</Label>
        <Select
          value={typeof value === 'string' ? value : ''}
          onValueChange={(selected) => onChange(field.key, selected)}
        >
          <SelectTrigger id={id}>
            <SelectValue placeholder={field.placeholder ?? 'Select a value'} />
          </SelectTrigger>
          <SelectContent>
            {field.options?.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <p className="text-sm leading-6 text-slate-500">{field.description}</p>
      </div>
    )
  }

  const inputMode = field.input === 'number' ? 'decimal' : undefined
  const inputType = field.input === 'password' ? 'password' : field.input === 'number' ? 'number' : field.input
  const inputValue = typeof value === 'boolean' ? '' : value ?? ''

  return (
    <div className="flex flex-col gap-2 rounded-2xl border border-border bg-white/80 p-4">
      <Label htmlFor={id} className="text-sm font-medium text-slate-900">{field.label}</Label>
      <Input
        id={id}
        type={inputType}
        inputMode={inputMode}
        step={field.step}
        placeholder={field.placeholder}
        value={inputValue}
        onChange={(event) => {
          const raw = event.target.value
          if (field.input === 'number') {
            if (field.key === 'llm_secondary_timeout_seconds') {
              onChange(field.key, raw === '' ? null : Number(raw))
              return
            }
            onChange(field.key, raw === '' ? 0 : Number(raw))
            return
          }

          if (field.key === 'llm_api_key'
            || field.key === 'llm_model'
            || field.key === 'llm_secondary_api_base'
            || field.key === 'llm_secondary_api_key'
            || field.key === 'llm_secondary_model'
            || field.key === 'prompt_variant_override'
            || field.key === 'embedding_api_key'
            || field.key === 'embedding_model'
            || field.key === 'auth_token_secret') {
            onChange(field.key, normalizeNullableString(raw))
            return
          }

          onChange(field.key, raw)
        }}
      />
      <p className="text-sm leading-6 text-slate-500">{field.description}</p>
    </div>
  )
}

export function SystemConfig() {
  const apiConfig = useStaffApiConfig()
  const { apiKey, baseUrl, bearerToken } = apiConfig
  const [savedConfig, setSavedConfig] = useState<SystemConfigValues | null>(null)
  const [draft, setDraft] = useState<SystemConfigValues | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [successMessage, setSuccessMessage] = useState('')
  const [configPath, setConfigPath] = useState('~/.dibble/config.toml')

  useEffect(() => {
    void (async () => {
      setLoading(true)
      setError('')
      try {
        const response = await getSystemConfig({
          baseUrl,
          apiKey,
          bearerToken,
          useDemoFallback: false,
          showDebugPanels: false,
        })
        setSavedConfig(response.values)
        setDraft(response.values)
        setConfigPath(response.config_path)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load system configuration')
      } finally {
        setLoading(false)
      }
    })()
  }, [apiKey, baseUrl, bearerToken])

  const dirty = useMemo(() => {
    if (!draft || !savedConfig) {
      return false
    }
    return JSON.stringify(draft) !== JSON.stringify(savedConfig)
  }, [draft, savedConfig])

  async function handleSave() {
    if (!draft || !savedConfig) {
      return
    }

    setSaving(true)
    setError('')
    setSuccessMessage('')
    try {
      const response = await updateSystemConfig(apiConfig, buildConfigPatch(draft, savedConfig))
      setSavedConfig(draft)
      setConfigPath(response.config_path)
      setSuccessMessage('Configuration saved. Restart the backend to apply runtime changes.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save configuration')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Loading configuration</CardTitle>
          <CardDescription>Reading the current Dibble system configuration from the backend.</CardDescription>
        </CardHeader>
      </Card>
    )
  }

  if (!draft) {
    return <ErrorBanner message={error || 'No configuration was returned by the backend.'} />
  }

  return (
    <div className="flex flex-col gap-6">
      <section className="flex flex-col gap-4 rounded-[2rem] border border-border bg-[linear-gradient(135deg,#ffffff_0%,#f4fbf7_55%,#fff7eb_100%)] p-8 shadow-[0_24px_80px_rgba(56,46,24,0.08)] lg:flex-row lg:items-end lg:justify-between">
        <div className="space-y-3">
          <Badge variant="secondary" className="w-fit bg-emerald-100 text-emerald-800">
            System configuration
          </Badge>
          <div className="space-y-2">
            <h1 className="text-3xl font-semibold tracking-tight text-slate-900">Configure the backend without hand-editing TOML.</h1>
            <p className="max-w-3xl text-sm leading-6 text-slate-600">
              Every setting in the current `Settings` contract is editable here. Saving writes to{' '}
              <code className="rounded bg-white/80 px-2 py-1 text-xs">{configPath}</code>.
            </p>
          </div>
        </div>
        <div className="flex flex-wrap gap-3">
          <Button
            variant="outline"
            onClick={() => setDraft(savedConfig)}
            disabled={!dirty || saving}
          >
            <RefreshCw className="h-4 w-4" />
            Reset changes
          </Button>
          <Button
            onClick={() => void handleSave()}
            disabled={!dirty || saving}
          >
            <Save className="h-4 w-4" />
            {saving ? 'Saving...' : 'Save config'}
          </Button>
        </div>
      </section>

      <ErrorBanner message={error} />
      {successMessage && (
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          {successMessage}
        </div>
      )}

      <Card>
        <CardHeader className="gap-3">
          <CardTitle>Configuration sections</CardTitle>
          <CardDescription>
            Changes update the on-disk config only. Restart the backend process after saving to load the new runtime settings.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Tabs defaultValue={systemConfigSections[0].key} className="flex flex-col gap-6">
            <TabsList className="overflow-x-auto pb-2">
              {systemConfigSections.map((section) => (
                <TabsTrigger key={section.key} value={section.key}>
                  {section.label}
                </TabsTrigger>
              ))}
            </TabsList>

            {systemConfigSections.map((section) => (
              <TabsContent key={section.key} value={section.key} className="space-y-4">
                <div className="space-y-1">
                  <h2 className="text-lg font-semibold text-slate-900">{section.label}</h2>
                  <p className="text-sm leading-6 text-slate-500">{section.description}</p>
                </div>
                <div className="grid gap-4 lg:grid-cols-2">
                  {section.fields.map((field) => (
                    <ConfigField
                      key={field.key}
                      field={field}
                      value={draft[field.key]}
                      onChange={(key, value) => {
                        setDraft((current) => (
                          current
                            ? {
                                ...current,
                                [key]: value,
                              }
                            : current
                        ))
                      }}
                    />
                  ))}
                </div>
              </TabsContent>
            ))}
          </Tabs>
        </CardContent>
      </Card>
    </div>
  )
}
