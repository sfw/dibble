import { useCallback, useState } from 'react'
import { NavLink, Outlet } from 'react-router'
import { BookOpen, Clock, Home, TrendingUp } from 'lucide-react'
import { useLearnerWorkspace } from '../hooks/useLearnerWorkspace'
import { useLearnerContracts } from '../hooks/useLearnerContracts'
import { usePersistentConfig } from '../hooks/usePersistentConfig'
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
  loading: boolean
  error: string
}

const navItems = [
  { to: '/learn', icon: Home, label: 'Home', end: true },
  { to: '/learn/progress', icon: TrendingUp, label: 'Progress' },
  { to: '/learn/history', icon: Clock, label: 'History' },
]

export function LearnerShell() {
  const { config } = usePersistentConfig()

  // Learner shell always uses demo fallback and hides debug panels
  const learnerConfig: FrontendConfig = { ...config, useDemoFallback: true, showDebugPanels: false }

  const [, setDataSource] = useState<DataSource>('demo')
  const handleDataSourceChange = useCallback((source: DataSource) => setDataSource(source), [])

  const learner = useLearnerWorkspace({
    config: learnerConfig,
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
      </header>
      <main className="flex-1 p-6">
        <Outlet context={context} />
      </main>
    </div>
  )
}
