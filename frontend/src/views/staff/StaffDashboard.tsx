import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { ArrowRight, Gauge, KeyRound, Server, ShieldCheck, Users } from 'lucide-react'
import { Badge } from '../../components/ui/badge'
import { Button } from '../../components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card'
import { ErrorBanner } from '../../components/ui/error-banner'
import { useAuthContext } from '../../contexts/AuthContext'
import { useConfigContext } from '../../contexts/ConfigContext'
import { useSetupStatus } from '../../hooks/useSetupStatus'
import { getSystemConfig } from '../../api'
import type { SystemConfigResponse } from '../../types'
import { useStaffApiConfig } from './useStaffApiConfig'

function StatusBadge({ ok, label }: { ok: boolean; label: string }) {
  return (
    <Badge className={ok ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-900'} variant="secondary">
      {label}
    </Badge>
  )
}

export function StaffDashboard() {
  const auth = useAuthContext()
  const { baseUrl } = useConfigContext()
  const apiConfig = useStaffApiConfig()
  const { apiKey, bearerToken } = apiConfig
  const { status, loading: statusLoading, error: statusError } = useSetupStatus(baseUrl)
  const [systemConfig, setSystemConfig] = useState<SystemConfigResponse | null>(null)
  const [configError, setConfigError] = useState('')

  useEffect(() => {
    if (auth.identity?.role !== 'admin') {
      return
    }

    void (async () => {
      try {
        const result = await getSystemConfig({
          baseUrl,
          apiKey,
          bearerToken,
          useDemoFallback: false,
          showDebugPanels: false,
        })
        setSystemConfig(result)
        setConfigError('')
      } catch (err) {
        setConfigError(err instanceof Error ? err.message : 'Could not load configuration')
      }
    })()
  }, [apiKey, baseUrl, bearerToken, auth.identity?.role])

  const configValues = systemConfig?.values

  return (
    <div className="flex flex-col gap-6">
      <section className="rounded-[2rem] border border-border bg-[radial-gradient(circle_at_top_left,_rgba(23,141,109,0.12),_transparent_45%),linear-gradient(135deg,#fff9ef_0%,#ffffff_70%)] p-8 shadow-[0_24px_80px_rgba(56,46,24,0.08)]">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl space-y-3">
            <Badge variant="secondary" className="w-fit bg-amber-100 text-amber-900">
              System administration
            </Badge>
            <div className="space-y-2">
              <h1 className="text-3xl font-semibold tracking-tight text-slate-900">Operate Dibble as a service, not a demo.</h1>
              <p className="max-w-2xl text-sm leading-6 text-slate-600">
                This dashboard is the control room for backend status, provider wiring, authentication posture, and operator actions.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3 text-sm text-slate-600">
              <StatusBadge ok={status?.configured === true} label={status?.configured ? 'Configured' : 'Setup incomplete'} />
              <span>Backend: <code className="rounded bg-white/80 px-2 py-1 text-xs">{baseUrl}</code></span>
              <span>Signed in as {auth.identity?.display_name ?? auth.identity?.role ?? 'staff'}</span>
            </div>
          </div>
          <div className="flex flex-wrap gap-3">
            {auth.identity?.role === 'admin' && (
              <Button asChild>
                <Link to="/staff/config">
                  Open configuration
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
            )}
            <Button asChild variant="outline">
              <Link to="/staff/users">
                Manage users
                <Users className="h-4 w-4" />
              </Link>
            </Button>
          </div>
        </div>
      </section>

      {statusError && <ErrorBanner message={statusError} />}
      {configError && auth.identity?.role === 'admin' && <ErrorBanner message={configError} />}

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Card>
          <CardHeader>
            <CardDescription>Runtime</CardDescription>
            <CardTitle className="flex items-center gap-2">
              <Server className="h-5 w-5 text-emerald-700" />
              Setup state
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-slate-600">
            <p>{statusLoading ? 'Loading backend status...' : status?.configured ? 'Ready for sign-in and API traffic.' : 'Still in first-run setup mode.'}</p>
            <p>Config file: {status?.config_file_exists ? 'present' : 'missing'}</p>
            <p>Database: {status?.has_database ? 'ready' : 'missing'}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardDescription>Providers</CardDescription>
            <CardTitle className="flex items-center gap-2">
              <Gauge className="h-5 w-5 text-emerald-700" />
              Model wiring
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-slate-600">
            <p>LLM base: {status?.llm_api_base ?? 'Unknown'}</p>
            <p>LLM model: {status?.llm_model ?? 'Not configured'}</p>
            <p>Embedding model: {configValues?.embedding_model ?? 'Local fallback'}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardDescription>Authentication</CardDescription>
            <CardTitle className="flex items-center gap-2">
              <ShieldCheck className="h-5 w-5 text-emerald-700" />
              Access control
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-slate-600">
            <p>Auth mode: {status?.auth_enabled ? 'Enabled' : 'Disabled'}</p>
            <p>Current session: {auth.identity?.auth_scheme ?? 'Unknown'}</p>
            <p>Bearer tokens: {configValues?.auth_token_secret ? 'Configured' : 'Unavailable'}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardDescription>Operators</CardDescription>
            <CardTitle className="flex items-center gap-2">
              <KeyRound className="h-5 w-5 text-emerald-700" />
              Admin access
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-slate-600">
            <p>Admin user present: {status?.has_admin_user ? 'Yes' : 'No'}</p>
            <p>Current role: {auth.identity?.role ?? 'Unknown'}</p>
            <p>{auth.identity?.role === 'admin' ? 'You can change system configuration.' : 'You have read-only staff access.'}</p>
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
        <Card>
          <CardHeader>
            <CardDescription>What changed</CardDescription>
            <CardTitle>Admin-first staff area</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm leading-6 text-slate-600">
            <p>
              The old staff route embedded the entire workbench app. This surface is now deliberately scoped for system administration: setup state, service posture, configuration, and account operations.
            </p>
            <p>
              Configuration changes are written into <code className="rounded bg-muted px-1 py-0.5 text-xs">~/.dibble/config.toml</code> and still require a backend restart before the running process picks them up.
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardDescription>Quick actions</CardDescription>
            <CardTitle>Operator shortcuts</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {auth.identity?.role === 'admin' && (
              <Button asChild variant="outline" className="justify-between">
                <Link to="/staff/config">
                  Review all configuration
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
            )}
            <Button asChild variant="outline" className="justify-between">
              <Link to="/staff/users">
                Manage staff and learner accounts
                <ArrowRight className="h-4 w-4" />
              </Link>
            </Button>
          </CardContent>
        </Card>
      </section>
    </div>
  )
}
