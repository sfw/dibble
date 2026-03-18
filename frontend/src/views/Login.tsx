import { useState } from 'react'
import { useNavigate } from 'react-router'
import { BookOpen, LogIn } from 'lucide-react'
import { Button } from '../components/ui/button'
import { Input } from '../components/ui/input'
import { Label } from '../components/ui/label'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card'
import { useAuthContext } from '../contexts/AuthContext'
import { useConfigContext } from '../contexts/ConfigContext'

type LoginMode = 'student' | 'staff'

export function Login() {
  const navigate = useNavigate()
  const auth = useAuthContext()
  const { baseUrl, setBaseUrl } = useConfigContext()
  const [mode, setMode] = useState<LoginMode>('student')
  const [credential, setCredential] = useState('')
  const [showAdvanced, setShowAdvanced] = useState(false)

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (!credential.trim()) return

    try {
      const identity = await auth.login(credential.trim(), baseUrl.trim())
      if (identity.role === 'learner') {
        navigate('/learn', { replace: true })
      } else if (identity.role === 'teacher') {
        navigate('/teacher', { replace: true })
      } else {
        navigate('/staff', { replace: true })
      }
    } catch {
      // error is set on auth state
    }
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-8 bg-slate-50 p-6">
      <header className="flex flex-col items-center gap-2 text-center">
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10">
          <BookOpen className="h-6 w-6 text-primary" />
        </div>
        <h1 className="text-3xl font-semibold tracking-tight">Dibble</h1>
        <p className="text-muted-foreground">Sign in to continue learning.</p>
      </header>

      <Card className="w-full max-w-sm">
        <CardHeader className="pb-3">
          <div className="flex rounded-lg border bg-muted p-1">
            <button
              type="button"
              onClick={() => { setMode('student'); setCredential('') }}
              className={`flex-1 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                mode === 'student'
                  ? 'bg-white text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              Student
            </button>
            <button
              type="button"
              onClick={() => { setMode('staff'); setCredential('') }}
              className={`flex-1 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                mode === 'staff'
                  ? 'bg-white text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              Staff
            </button>
          </div>
          <CardTitle className="text-lg">Sign in</CardTitle>
          <CardDescription>
            {mode === 'student'
              ? 'Enter the passphrase your teacher gave you.'
              : 'Enter your API key to get started.'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div className="flex flex-col gap-2">
              {mode === 'student' ? (
                <>
                  <Label htmlFor="passphrase">Passphrase</Label>
                  <Input
                    id="passphrase"
                    type="text"
                    placeholder="e.g. blue tiger runs fast"
                    value={credential}
                    onChange={(e) => setCredential(e.target.value)}
                    autoFocus
                    autoComplete="off"
                    className="text-lg tracking-wide"
                  />
                </>
              ) : (
                <>
                  <Label htmlFor="api-key">API key</Label>
                  <Input
                    id="api-key"
                    type="password"
                    placeholder="Enter your API key"
                    value={credential}
                    onChange={(e) => setCredential(e.target.value)}
                    autoFocus
                    autoComplete="current-password"
                  />
                </>
              )}
            </div>

            {mode === 'staff' && showAdvanced && (
              <div className="flex flex-col gap-2">
                <Label htmlFor="base-url">Server URL</Label>
                <Input
                  id="base-url"
                  type="url"
                  placeholder="http://127.0.0.1:8000"
                  value={baseUrl}
                  onChange={(e) => setBaseUrl(e.target.value)}
                />
              </div>
            )}

            {auth.error && (
              <p className="text-sm text-destructive">{auth.error}</p>
            )}

            <Button type="submit" disabled={auth.loading || !credential.trim()}>
              {auth.loading ? (
                'Signing in...'
              ) : (
                <>
                  <LogIn className="h-4 w-4" />
                  Sign in
                </>
              )}
            </Button>

            {mode === 'staff' && (
              <button
                type="button"
                onClick={() => setShowAdvanced(!showAdvanced)}
                className="text-xs text-muted-foreground hover:text-foreground transition-colors"
              >
                {showAdvanced ? 'Hide advanced settings' : 'Advanced settings'}
              </button>
            )}
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
