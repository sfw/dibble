import { useCallback, useState } from 'react'
import { NavLink, Outlet } from 'react-router'
import { BarChart3, ClipboardList, GraduationCap, LayoutDashboard, LogOut, School } from 'lucide-react'
import { useTeacherClassroom } from '../hooks/useTeacherClassroom'
import { useAuthContext } from '../contexts/AuthContext'
import { useConfigContext } from '../contexts/ConfigContext'
import type { DataSource } from '../app/workspace'
import { TeacherBreadcrumbs } from '../components/shell/Breadcrumbs'
import type {
  FrontendConfig,
  TeacherClassroomOverview,
  TeacherClassroomReadModel,
} from '../types'

export interface TeacherContext {
  config: FrontendConfig
  classrooms: TeacherClassroomOverview[]
  selectedClassroomId: string
  classroom: TeacherClassroomReadModel
  loading: boolean
  error: string
  loadClassroom: (classroomId: string) => Promise<void>
}

const navItems = [
  { to: '/teacher', icon: LayoutDashboard, label: 'Dashboard', end: true },
  { to: '/teacher/classrooms', icon: School, label: 'Classrooms' },
  { to: '/teacher/assignments', icon: ClipboardList, label: 'Assignments' },
  { to: '/teacher/reports', icon: BarChart3, label: 'Reports' },
]

export function TeacherShell() {
  const auth = useAuthContext()
  const { baseUrl } = useConfigContext()
  const teacherConfig: FrontendConfig = {
    baseUrl,
    apiKey: '',
    bearerToken: auth.getToken(),
    useDemoFallback: !auth.authenticated,
    showDebugPanels: false,
  }

  const [, setDataSource] = useState<DataSource>('demo')
  const handleDataSourceChange = useCallback((source: DataSource) => setDataSource(source), [])

  const tc = useTeacherClassroom({
    config: teacherConfig,
    onDataSourceChange: handleDataSourceChange,
  })

  const context: TeacherContext = {
    config: teacherConfig,
    classrooms: tc.classrooms,
    selectedClassroomId: tc.selectedClassroomId,
    classroom: tc.classroom,
    loading: tc.loading,
    error: tc.error,
    loadClassroom: tc.loadClassroom,
  }

  return (
    <div className="flex min-h-screen flex-col bg-slate-50">
      <header className="flex items-center gap-6 border-b bg-white px-6 py-3 shadow-sm">
        <NavLink to="/teacher" className="flex items-center gap-2 text-lg font-semibold tracking-tight text-emerald-700">
          <GraduationCap className="h-5 w-5" />
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
                    ? 'bg-emerald-50 text-emerald-700'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground'
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
            <span className="text-sm text-muted-foreground">{auth.identity.display_name}</span>
          )}
          <button
            onClick={() => void auth.logout().then(() => window.location.assign('/login'))}
            className="flex items-center gap-1 rounded-md px-2 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </header>
      <main className="flex-1 p-6">
        <TeacherBreadcrumbs />
        <Outlet context={context} />
      </main>
    </div>
  )
}
