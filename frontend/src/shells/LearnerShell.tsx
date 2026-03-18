import { NavLink, Outlet } from 'react-router'
import { BookOpen, Clock, Home, TrendingUp } from 'lucide-react'

const navItems = [
  { to: '/learn', icon: Home, label: 'Home', end: true },
  { to: '/learn/progress', icon: TrendingUp, label: 'Progress' },
  { to: '/learn/history', icon: Clock, label: 'History' },
]

export function LearnerShell() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="flex items-center gap-6 border-b bg-white px-6 py-3">
        <NavLink to="/learn" className="flex items-center gap-2 text-lg font-semibold tracking-tight">
          <BookOpen className="h-5 w-5" />
          Dibble
        </NavLink>
        <nav className="flex items-center gap-1">
          {navItems.map(({ to, icon: Icon, label, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-blue-50 text-blue-700'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                }`
              }
            >
              <Icon className="h-4 w-4" />
              {label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="flex-1 p-6">
        <Outlet />
      </main>
    </div>
  )
}
