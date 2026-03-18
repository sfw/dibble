import { useCallback, useState } from 'react'
import { NavLink, Outlet } from 'react-router'
import { GraduationCap, LayoutDashboard, School } from 'lucide-react'
import { useTeacherClassroom } from '../hooks/useTeacherClassroom'
import { usePersistentConfig } from '../hooks/usePersistentConfig'
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
]

export function TeacherShell() {
  const { config } = usePersistentConfig()
  const teacherConfig: FrontendConfig = { ...config, useDemoFallback: true, showDebugPanels: false }

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
      </header>
      <main className="flex-1 p-6">
        <TeacherBreadcrumbs />
        <Outlet context={context} />
      </main>
    </div>
  )
}
