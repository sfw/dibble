import { useCallback, useEffect, useState } from 'react'
import { Copy, Check, KeyRound, Plus, RefreshCw, Trash2, Edit2, X, Upload } from 'lucide-react'
import { Button } from '../../components/ui/button'
import { Input } from '../../components/ui/input'
import { Label } from '../../components/ui/label'
import { Badge } from '../../components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select'
import {
  listUsers,
  createUser,
  updateUser,
  deleteUser,
  rotateUserKey,
  bulkCreateUsers,
} from '../../api'
import type { FrontendConfig, UserSummary, UserCreateRequest, UserCreateResponse } from '../../types'
import { useStaffApiConfig } from './useStaffApiConfig'

const ROLE_STYLES: Record<string, string> = {
  admin: 'bg-amber-100 text-amber-800',
  editor: 'bg-purple-100 text-purple-800',
  teacher: 'bg-emerald-100 text-emerald-800',
  viewer: 'bg-slate-100 text-slate-700',
  learner: 'bg-blue-100 text-blue-800',
}

function RoleBadge({ role }: { role: string }) {
  return (
    <Badge variant="secondary" className={ROLE_STYLES[role] ?? ''}>
      {role}
    </Badge>
  )
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  const handleCopy = async () => {
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  return (
    <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => void handleCopy()}>
      {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
    </Button>
  )
}

function useConfig(): FrontendConfig {
  return useStaffApiConfig()
}

function formatSectionIds(classroomIds: string[]): string {
  return classroomIds.join(', ')
}

// ---------------------------------------------------------------------------
// Create User Form
// ---------------------------------------------------------------------------

function CreateUserForm({
  config,
  onCreated,
  onCancel,
}: {
  config: FrontendConfig
  onCreated: (result: UserCreateResponse) => void
  onCancel: () => void
}) {
  const [form, setForm] = useState<UserCreateRequest>({ role: 'learner' })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const result = await createUser(config, {
        display_name: form.display_name,
        role: form.role,
      })
      onCreated(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create user')
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3">
      <div className="grid grid-cols-2 gap-3">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="create-name">Display name</Label>
          <Input
            id="create-name"
            placeholder="Name"
            value={form.display_name ?? ''}
            onChange={(e) => setForm({ ...form, display_name: e.target.value })}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="create-role">Role</Label>
          <Select
            value={form.role}
            onValueChange={(v) => setForm((current) => ({ ...current, role: v }))}
          >
            <SelectTrigger id="create-role">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="learner">Learner</SelectItem>
              <SelectItem value="viewer">Viewer</SelectItem>
              <SelectItem value="teacher">Teacher</SelectItem>
              <SelectItem value="editor">Editor</SelectItem>
              <SelectItem value="admin">Admin</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>
      <p className="text-xs text-muted-foreground">
        Create the user here, then assign teachers and learners to sections from Courses &amp; Sections.
      </p>
      {error && <p className="text-sm text-destructive">{error}</p>}
      <div className="flex gap-2">
        <Button variant="outline" type="button" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" disabled={loading}>
          {loading ? 'Creating...' : 'Create user'}
        </Button>
      </div>
    </form>
  )
}

// ---------------------------------------------------------------------------
// Credential reveal banner
// ---------------------------------------------------------------------------

function CredentialBanner({
  result,
  onDismiss,
}: {
  result: UserCreateResponse
  onDismiss: () => void
}) {
  const isPassphrase = result.credential.includes(' ')
  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1">
          <p className="text-sm font-medium text-amber-800">
            {isPassphrase ? 'Passphrase' : 'API key'} for {result.display_name ?? result.user_id}
          </p>
          <div className="mt-1 flex items-center gap-2">
            <code className="rounded bg-amber-100 px-2 py-1 text-xs break-all">{result.credential}</code>
            <CopyButton text={result.credential} />
          </div>
          <p className="mt-1 text-xs text-amber-700">This will not be shown again.</p>
        </div>
        <Button variant="ghost" size="icon" className="h-7 w-7 shrink-0" onClick={onDismiss}>
          <X className="h-4 w-4" />
        </Button>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Bulk import dialog
// ---------------------------------------------------------------------------

function BulkImportPanel({
  config,
  onDone,
  onCancel,
}: {
  config: FrontendConfig
  onDone: (results: UserCreateResponse[]) => void
  onCancel: () => void
}) {
  const [csv, setCsv] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  function parseCsv(): UserCreateRequest[] {
    const lines = csv.trim().split('\n').filter((l) => l.trim())
    if (lines.length === 0) return []

    return lines.map((line) => {
      const [display_name, role] = line.split(',').map((s) => s.trim())
      const req: UserCreateRequest = { role: role || 'learner' }
      if (display_name) req.display_name = display_name
      return req
    })
  }

  async function handleImport() {
    const users = parseCsv()
    if (users.length === 0) {
      setError('No users to import')
      return
    }
    setLoading(true)
    setError('')
    try {
      const result = await bulkCreateUsers(config, { users })
      onDone(result.created)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Bulk import failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-muted-foreground">
        Paste CSV rows: <code className="text-xs">display_name, role</code>
      </p>
      <textarea
        value={csv}
        onChange={(e) => setCsv(e.target.value)}
        placeholder={'Alice, learner\nMs Rivera, teacher'}
        rows={6}
        className="w-full rounded-md border bg-white px-3 py-2 text-sm font-mono placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
      />
      <p className="text-xs text-muted-foreground">
        Section assignments and enrollments are managed from Courses &amp; Sections after import.
      </p>
      {error && <p className="text-sm text-destructive">{error}</p>}
      <div className="flex gap-2">
        <Button variant="outline" onClick={onCancel}>Cancel</Button>
        <Button onClick={() => void handleImport()} disabled={loading || !csv.trim()}>
          {loading ? 'Importing...' : `Import ${parseCsv().length} users`}
        </Button>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// User row
// ---------------------------------------------------------------------------

function UserRow({
  user,
  config,
  onUpdated,
  onDeleted,
  onCredential,
}: {
  user: UserSummary
  config: FrontendConfig
  onUpdated: (u: UserSummary) => void
  onDeleted: (id: string) => void
  onCredential: (r: UserCreateResponse) => void
}) {
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState({
    display_name: user.display_name ?? '',
    role: user.role,
  })
  const [loading, setLoading] = useState(false)

  async function handleSave() {
    setLoading(true)
    try {
      const updated = await updateUser(config, user.user_id, {
        display_name: form.display_name || undefined,
        role: form.role,
      })
      onUpdated(updated)
      setEditing(false)
    } catch {
      // silent
    } finally {
      setLoading(false)
    }
  }

  async function handleRotate() {
    setLoading(true)
    try {
      const result = await rotateUserKey(config, user.user_id)
      onCredential(result)
    } catch {
      // silent
    } finally {
      setLoading(false)
    }
  }

  async function handleDelete() {
    if (!window.confirm(`Delete user ${user.display_name ?? user.user_id}?`)) return
    setLoading(true)
    try {
      await deleteUser(config, user.user_id)
      onDeleted(user.user_id)
    } catch {
      // silent
    } finally {
      setLoading(false)
    }
  }

  if (editing) {
    return (
      <tr className="border-b">
        <td className="px-4 py-2">
          <Input
            aria-label="Edit display name"
            value={form.display_name}
            onChange={(e) => setForm({ ...form, display_name: e.target.value })}
            className="h-8 text-sm"
          />
        </td>
        <td className="px-4 py-2">
          <Select
            value={form.role}
            onValueChange={(v) => setForm((current) => ({ ...current, role: v }))}
          >
            <SelectTrigger className="h-8 text-sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="learner">Learner</SelectItem>
              <SelectItem value="viewer">Viewer</SelectItem>
              <SelectItem value="teacher">Teacher</SelectItem>
              <SelectItem value="editor">Editor</SelectItem>
              <SelectItem value="admin">Admin</SelectItem>
            </SelectContent>
          </Select>
        </td>
        <td className="px-4 py-2 text-sm text-muted-foreground">
          {user.learner_id ?? '-'}
        </td>
        <td className="px-4 py-2">
          <span className="text-sm text-muted-foreground">
            Manage in Courses &amp; Sections
          </span>
        </td>
        <td className="px-4 py-2">
          <div className="flex gap-1">
            <Button variant="outline" size="sm" onClick={() => setEditing(false)} disabled={loading}>
              Cancel
            </Button>
            <Button size="sm" onClick={() => void handleSave()} disabled={loading}>
              Save
            </Button>
          </div>
        </td>
      </tr>
    )
  }

  return (
    <tr className="border-b hover:bg-muted/50">
      <td className="px-4 py-2 text-sm">{user.display_name ?? <span className="text-muted-foreground">-</span>}</td>
      <td className="px-4 py-2"><RoleBadge role={user.role} /></td>
      <td className="px-4 py-2 text-sm text-muted-foreground">{user.learner_id ?? '-'}</td>
      <td className="px-4 py-2 text-sm text-muted-foreground">
        {user.section_ids.length > 0 ? formatSectionIds(user.section_ids) : '-'}
      </td>
      <td className="px-4 py-2">
        <div className="flex gap-1">
          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setEditing(true)} title="Edit">
            <Edit2 className="h-3.5 w-3.5" />
          </Button>
          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => void handleRotate()} disabled={loading} title="Rotate credential">
            <KeyRound className="h-3.5 w-3.5" />
          </Button>
          <Button variant="ghost" size="icon" className="h-7 w-7 text-destructive hover:text-destructive" onClick={() => void handleDelete()} disabled={loading} title="Delete">
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      </td>
    </tr>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function UserManagement() {
  const config = useConfig()
  const [users, setUsers] = useState<UserSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [showBulk, setShowBulk] = useState(false)
  const [credential, setCredential] = useState<UserCreateResponse | null>(null)
  const [bulkCredentials, setBulkCredentials] = useState<UserCreateResponse[]>([])

  const fetchUsers = useCallback(async () => {
    setLoading(true)
    try {
      const result = await listUsers(config)
      setUsers(result)
    } catch {
      // silent
    } finally {
      setLoading(false)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [config.baseUrl, config.bearerToken])

  useEffect(() => {
    void fetchUsers()
  }, [fetchUsers])

  function handleCreated(result: UserCreateResponse) {
    setCredential(result)
    setShowCreate(false)
    void fetchUsers()
  }

  function handleBulkDone(results: UserCreateResponse[]) {
    setBulkCredentials(results)
    setShowBulk(false)
    void fetchUsers()
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Users</h1>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => { setShowBulk(true); setShowCreate(false) }}>
            <Upload className="h-4 w-4" />
            Bulk import
          </Button>
          <Button onClick={() => { setShowCreate(true); setShowBulk(false) }}>
            <Plus className="h-4 w-4" />
            Create user
          </Button>
        </div>
      </div>

      {credential && (
        <CredentialBanner result={credential} onDismiss={() => setCredential(null)} />
      )}

      {bulkCredentials.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">Imported {bulkCredentials.length} users</CardTitle>
              <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setBulkCredentials([])}>
                <X className="h-4 w-4" />
              </Button>
            </div>
            <p className="text-xs text-amber-700">Save these credentials now. They will not be shown again.</p>
          </CardHeader>
          <CardContent>
            <div className="max-h-60 overflow-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-xs text-muted-foreground">
                    <th className="px-2 py-1">Name</th>
                    <th className="px-2 py-1">Role</th>
                    <th className="px-2 py-1">Credential</th>
                  </tr>
                </thead>
                <tbody>
                  {bulkCredentials.map((r) => (
                    <tr key={r.user_id} className="border-b">
                      <td className="px-2 py-1">{r.display_name ?? r.user_id}</td>
                      <td className="px-2 py-1"><RoleBadge role={r.role} /></td>
                      <td className="px-2 py-1">
                        <div className="flex items-center gap-1">
                          <code className="text-xs break-all">{r.credential}</code>
                          <CopyButton text={r.credential} />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {showCreate && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Create user</CardTitle>
          </CardHeader>
          <CardContent>
            <CreateUserForm config={config} onCreated={handleCreated} onCancel={() => setShowCreate(false)} />
          </CardContent>
        </Card>
      )}

      {showBulk && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Bulk import</CardTitle>
          </CardHeader>
          <CardContent>
            <BulkImportPanel config={config} onDone={handleBulkDone} onCancel={() => setShowBulk(false)} />
          </CardContent>
        </Card>
      )}

      <div className="rounded-2xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-900">
        User management handles identities and credentials. Teacher assignments and learner enrollments belong to sections in Courses &amp; Sections.
      </div>

      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <RefreshCw className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : users.length === 0 ? (
            <div className="py-12 text-center text-sm text-muted-foreground">
              No users yet. Create one to get started.
            </div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b text-left text-xs text-muted-foreground">
                  <th className="px-4 py-2 font-medium">Name</th>
                  <th className="px-4 py-2 font-medium">Role</th>
                  <th className="px-4 py-2 font-medium">Learner ID</th>
                  <th className="px-4 py-2 font-medium">Sections</th>
                  <th className="px-4 py-2 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <UserRow
                    key={user.user_id}
                    user={user}
                    config={config}
                    onUpdated={(u) => setUsers((prev) => prev.map((p) => (p.user_id === u.user_id ? u : p)))}
                    onDeleted={(id) => setUsers((prev) => prev.filter((p) => p.user_id !== id))}
                    onCredential={setCredential}
                  />
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
