import { NavLink, Outlet } from 'react-router'
import { Blocks, BookOpen, Gauge, LayoutDashboard, LogOut, Settings, ShieldCheck, SlidersHorizontal, Users } from 'lucide-react'
import { useAuthContext } from '../contexts/AuthContext'
import { useConfigContext } from '../contexts/ConfigContext'

export function StaffShell() {
  const auth = useAuthContext()
  const { baseUrl } = useConfigContext()
  const isAdmin = auth.identity?.role === 'admin'
  const navItems = [
    { to: '/staff', icon: LayoutDashboard, label: 'Dashboard', end: true },
    ...(isAdmin
      ? [
          { to: '/staff/pilot', icon: Gauge, label: 'Pilot Metrics' },
          { to: '/staff/academics', icon: Blocks, label: 'Courses & Sections' },
          { to: '/staff/curriculum', icon: BookOpen, label: 'Curriculum' },
          { to: '/staff/rollout', icon: ShieldCheck, label: 'Rollout' },
          { to: '/staff/migrations', icon: ShieldCheck, label: 'Migrations' },
          { to: '/staff/config', icon: SlidersHorizontal, label: 'Configuration' },
          { to: '/staff/users', icon: Users, label: 'Users' },
        ]
      : []),
  ]

  return (
    <div className="flex min-h-screen flex-col bg-[linear-gradient(180deg,#fbfaf7_0%,#f7faf9_35%,#f8fafc_100%)]">
      <header className="border-b border-border/80 bg-white/90 px-6 py-4 shadow-sm backdrop-blur">
        <div className="mx-auto flex w-full max-w-7xl flex-col gap-4 lg:flex-row lg:items-center">
          <NavLink to="/staff" className="flex items-center gap-3 text-lg font-semibold tracking-tight text-slate-900">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-emerald-100 text-emerald-700">
              <Settings className="h-5 w-5" />
            </div>
            <div className="flex flex-col">
              <span>Dibble Admin</span>
              <span className="text-xs font-medium text-slate-500">{baseUrl}</span>
            </div>
          </NavLink>
          <nav className="flex flex-wrap items-center gap-2">
            {navItems.map(({ to, icon: Icon, label, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  `flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-emerald-600 text-white'
                      : 'border border-border bg-white text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                  }`
                }
              >
                <Icon className="h-4 w-4" />
                {label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-3">
            {auth.identity?.display_name && (
              <div className="text-right">
                <p className="text-sm font-medium text-slate-900">{auth.identity.display_name}</p>
                <p className="text-xs uppercase tracking-[0.2em] text-slate-500">{auth.identity.role}</p>
              </div>
            )}
            <button
              onClick={() => void auth.logout().then(() => window.location.assign('/login'))}
              className="flex items-center gap-1 rounded-full border border-border bg-white px-3 py-2 text-sm text-slate-600 transition-colors hover:bg-slate-50 hover:text-slate-900"
            >
              <LogOut className="h-4 w-4" />
              Sign out
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto flex w-full max-w-7xl flex-1 flex-col px-6 py-8">
        <Outlet />
      </main>
    </div>
  )
}
