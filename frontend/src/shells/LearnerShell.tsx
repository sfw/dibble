import { useCallback, useState } from 'react'
import { NavLink, Outlet } from 'react-router'
import { BookOpen, ClipboardList, Clock, Home, LogOut, TrendingUp } from 'lucide-react'
import { useLearnerWorkspace } from '../hooks/useLearnerWorkspace'
import { useLearnerContracts } from '../hooks/useLearnerContracts'
import { useAuthContext } from '../contexts/AuthContext'
import { useConfigContext } from '../contexts/ConfigContext'
import type { DataSource } from '../app/workspace'
import type {
  FrontendConfig,
  LearnerFlowSummary,
  LearnerWorkspace,
  LearnerCurriculumProgressionSummary,
  ProfileSummary,
  LearnerGenerationHistoryEntry,
  LearnerSocraticSessionHistoryEntry,
  LearnerRemediationSessionHistoryEntry,
} from '../types'

export interface LearnerContext {
  config: FrontendConfig
  summary: ProfileSummary
  flow: LearnerFlowSummary
  workspace: LearnerWorkspace
  progression: LearnerCurriculumProgressionSummary
  generationHistory: LearnerGenerationHistoryEntry[]
  socraticHistory: LearnerSocraticSessionHistoryEntry[]
  remediationHistory: LearnerRemediationSessionHistoryEntry[]
  hasMoreHistory: boolean
  loadingMore: boolean
  loadMoreHistory: () => Promise<void>
  loading: boolean
  error: string
}

const navItems = [
  { to: '/learn', icon: Home, label: 'Home', end: true },
  { to: '/learn/assignments', icon: ClipboardList, label: 'Assignments' },
  { to: '/learn/progress', icon: TrendingUp, label: 'Progress' },
  { to: '/learn/history', icon: Clock, label: 'History' },
]

export function LearnerShell() {
  const auth = useAuthContext()
  const { baseUrl } = useConfigContext()

  // Build config from auth state — bearer token from auth, no demo fallback in authenticated mode
  const learnerConfig: FrontendConfig = {
    baseUrl,
    apiKey: '',
    bearerToken: auth.getToken(),
    useDemoFallback: !auth.authenticated,
    showDebugPanels: false,
  }

  const [, setDataSource] = useState<DataSource>('demo')
  const handleDataSourceChange = useCallback((source: DataSource) => setDataSource(source), [])

  const learner = useLearnerWorkspace({
    config: learnerConfig,
    initialLearnerId: auth.identity?.learner_id ?? undefined,
    onDataSourceChange: handleDataSourceChange,
  })

  const contracts = useLearnerContracts({
    config: learnerConfig,
    learnerId: learner.learnerId,
    onDataSourceChange: handleDataSourceChange,
  })

  const context: LearnerContext = {
    config: learnerConfig,
    summary: learner.summary,
    flow: learner.flow,
    workspace: learner.workspace,
    progression: learner.summary.curriculum_progression,
    generationHistory: contracts.generationHistory,
    socraticHistory: contracts.socraticHistory,
    remediationHistory: contracts.remediationHistory,
    hasMoreHistory: contracts.hasMoreHistory,
    loadingMore: contracts.loadingMore,
    loadMoreHistory: contracts.loadMoreHistory,
    loading: learner.loading || contracts.loading,
    error: learner.error || contracts.error,
  }

  return (
    <div className="flex min-h-screen flex-col bg-slate-50">
      <header className="flex items-center gap-6 border-b bg-white px-6 py-3 shadow-sm">
        <NavLink to="/learn" className="flex items-center gap-2 text-lg font-semibold tracking-tight text-blue-700">
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
        <Outlet context={context} />
      </main>
    </div>
  )
}
