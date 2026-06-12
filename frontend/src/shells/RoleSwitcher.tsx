import { Link, Navigate } from 'react-router'
import { BookOpen, GraduationCap, LogIn, Users, Wrench } from 'lucide-react'
import { useAuthContext } from '../contexts/AuthContext'

const roles = [
  {
    to: '/learn',
    icon: BookOpen,
    title: 'Learner',
    description: 'Resume your learning, complete activities, and track your progress.',
    tone: 'learner' as const,
  },
  {
    to: '/parent',
    icon: Users,
    title: 'Parent',
    description: 'Manage a household, review weekly progress, and respond to gentle escalation signals.',
    tone: 'parent' as const,
  },
  {
    to: '/teacher',
    icon: GraduationCap,
    title: 'Teacher',
    description: 'Monitor sections, review learner progress, and manage interventions.',
    tone: 'teacher' as const,
  },
  {
    to: '/staff',
    icon: Wrench,
    title: 'Staff',
    description: 'Inspect contracts, debug workflows, and validate backend integration.',
    tone: 'staff' as const,
  },
] as const

const toneClasses: Record<string, string> = {
  learner: 'hover:border-blue-400 hover:bg-blue-50',
  parent: 'hover:border-amber-400 hover:bg-amber-50',
  teacher: 'hover:border-emerald-400 hover:bg-emerald-50',
  staff: 'hover:border-amber-400 hover:bg-amber-50',
}

export function RoleSwitcher() {
  const auth = useAuthContext()

  // If already authenticated, redirect to the appropriate shell
  if (auth.authenticated && auth.identity) {
    if (auth.identity.role === 'learner') return <Navigate to="/learn" replace />
    if (auth.identity.role === 'household_admin' || auth.identity.role === 'parent') return <Navigate to="/parent" replace />
    if (auth.identity.role === 'teacher' || auth.identity.role === 'guardian') return <Navigate to="/teacher" replace />
    return <Navigate to="/staff" replace />
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-8 p-6">
      <header className="text-center">
        <h1 className="text-3xl font-semibold tracking-tight">Dibble</h1>
        <p className="mt-2 text-muted-foreground">Choose how you want to use the platform.</p>
      </header>

      <div className="grid w-full max-w-4xl gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {roles.map(({ to, icon: Icon, title, description, tone }) => (
          <Link
            key={to}
            to={to}
            className={`flex flex-col items-center gap-3 rounded-xl border bg-card p-6 text-center transition-colors ${toneClasses[tone]}`}
          >
            <Icon className="h-8 w-8 text-muted-foreground" />
            <h2 className="text-lg font-medium">{title}</h2>
            <p className="text-sm text-muted-foreground">{description}</p>
          </Link>
        ))}
      </div>

      <Link
        to="/login"
        className="flex items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <LogIn className="h-4 w-4" />
        Sign in with an API key
      </Link>
    </div>
  )
}
