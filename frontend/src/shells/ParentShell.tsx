import { useCallback, useEffect, useMemo, useState } from 'react'
import { NavLink, Outlet } from 'react-router'
import { Home, LogOut, Users } from 'lucide-react'
import {
  acceptHouseholdSessionSuggestion,
  approveHouseholdParentApproval,
  deferHouseholdSessionSuggestion,
  dismissHouseholdNotification,
  getHouseholdOverview,
  markHouseholdNotificationRead,
  rejectHouseholdParentApproval,
  setupHousehold,
  snoozeHouseholdNotification,
  snoozeHouseholdSessionSuggestion,
  updateHouseholdPreferences,
} from '../api'
import { useAuthContext } from '../contexts/AuthContext'
import { useConfigContext } from '../contexts/ConfigContext'
import type {
  FrontendConfig,
  HouseholdNotificationSnoozeRequest,
  HouseholdOverview,
  HouseholdPreferenceUpdateRequest,
  HouseholdSessionSuggestionSnoozeRequest,
  HouseholdSetupRequest,
} from '../types'

export interface ParentContext {
  config: FrontendConfig
  overview: HouseholdOverview
  loading: boolean
  error: string
  saveSetup: (payload: HouseholdSetupRequest) => Promise<void>
  savePreferences: (payload: HouseholdPreferenceUpdateRequest) => Promise<void>
  refresh: () => Promise<void>
  markRead: (notificationId: string) => Promise<void>
  dismissNotification: (notificationId: string) => Promise<void>
  snoozeNotification: (notificationId: string, payload: HouseholdNotificationSnoozeRequest) => Promise<void>
  acceptSuggestion: (learnerId: string) => Promise<void>
  deferSuggestion: (learnerId: string) => Promise<void>
  snoozeSuggestion: (learnerId: string, payload: HouseholdSessionSuggestionSnoozeRequest) => Promise<void>
  approveParentApproval: (learnerId: string, approvalId: string) => Promise<void>
  rejectParentApproval: (learnerId: string, approvalId: string) => Promise<void>
}

const emptyOverview: HouseholdOverview = {
  household: null,
  learners: [],
  session_suggestions: [],
  weekly_summaries: [],
  pending_approvals: [],
  notifications: [],
  available_learners: [],
}

export function ParentShell() {
  const auth = useAuthContext()
  const { baseUrl } = useConfigContext()
  const [overview, setOverview] = useState<HouseholdOverview>(emptyOverview)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const apiKey = auth.getApiKey()
  const bearerToken = auth.getToken()
  const useDemoFallback = !auth.authenticated
  const config: FrontendConfig = useMemo(
    () => ({ baseUrl, apiKey, bearerToken, useDemoFallback, showDebugPanels: false }),
    [baseUrl, apiKey, bearerToken, useDemoFallback],
  )

  const loadOverview = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      setOverview(await getHouseholdOverview(config))
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : 'Unable to load household overview.')
    } finally {
      setLoading(false)
    }
  }, [config])

  const saveSetup = useCallback(async (payload: HouseholdSetupRequest) => {
    setLoading(true)
    setError('')
    try {
      await setupHousehold(config, payload)
      setOverview(await getHouseholdOverview(config))
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : 'Unable to save household setup.')
    } finally {
      setLoading(false)
    }
  }, [config])

  const markRead = useCallback(async (notificationId: string) => {
    try {
      setOverview(await markHouseholdNotificationRead(config, notificationId))
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : 'Unable to update the notification.')
    }
  }, [config])

  const dismissNotification = useCallback(async (notificationId: string) => {
    try {
      setOverview(await dismissHouseholdNotification(config, notificationId))
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : 'Unable to dismiss the notification.')
    }
  }, [config])

  const snoozeNotification = useCallback(async (notificationId: string, payload: HouseholdNotificationSnoozeRequest) => {
    try {
      setOverview(await snoozeHouseholdNotification(config, notificationId, payload))
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : 'Unable to snooze the notification.')
    }
  }, [config])

  const savePreferences = useCallback(async (payload: HouseholdPreferenceUpdateRequest) => {
    setLoading(true)
    setError('')
    try {
      setOverview(await updateHouseholdPreferences(config, payload))
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : 'Unable to save household preferences.')
    } finally {
      setLoading(false)
    }
  }, [config])

  const acceptSuggestion = useCallback(async (learnerId: string) => {
    try {
      setOverview(await acceptHouseholdSessionSuggestion(config, learnerId))
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : 'Unable to accept the session suggestion.')
    }
  }, [config])

  const deferSuggestion = useCallback(async (learnerId: string) => {
    try {
      setOverview(await deferHouseholdSessionSuggestion(config, learnerId))
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : 'Unable to defer the session suggestion.')
    }
  }, [config])

  const snoozeSuggestion = useCallback(async (learnerId: string, payload: HouseholdSessionSuggestionSnoozeRequest) => {
    try {
      setOverview(await snoozeHouseholdSessionSuggestion(config, learnerId, payload))
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : 'Unable to snooze the session suggestion.')
    }
  }, [config])

  const approveParentApproval = useCallback(async (learnerId: string, approvalId: string) => {
    try {
      setOverview(await approveHouseholdParentApproval(config, learnerId, approvalId))
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : 'Unable to approve the teaching change.')
    }
  }, [config])

  const rejectParentApproval = useCallback(async (learnerId: string, approvalId: string) => {
    try {
      setOverview(await rejectHouseholdParentApproval(config, learnerId, approvalId))
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : 'Unable to hold the teaching change.')
    }
  }, [config])

  useEffect(() => {
    void loadOverview()
  }, [loadOverview])

  const context: ParentContext = {
    config,
    overview,
    loading,
    error,
    saveSetup,
    savePreferences,
    refresh: loadOverview,
    markRead,
    dismissNotification,
    snoozeNotification,
    acceptSuggestion,
    deferSuggestion,
    snoozeSuggestion,
    approveParentApproval,
    rejectParentApproval,
  }

  return (
    <div className="flex min-h-screen flex-col bg-[radial-gradient(circle_at_top_left,_rgba(251,191,36,0.18),_transparent_30%),linear-gradient(180deg,#fffdf7_0%,#f8fafc_100%)]">
      <header className="flex items-center gap-6 border-b bg-white/90 px-6 py-3 shadow-sm backdrop-blur">
        <NavLink to="/parent" className="flex items-center gap-2 text-lg font-semibold tracking-tight text-amber-700">
          <Users className="h-5 w-5" />
          Dibble Household
        </NavLink>
        <nav className="flex items-center gap-1">
          <NavLink
            to="/parent"
            end
            className={({ isActive }) =>
              `flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-amber-50 text-amber-800'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground'
              }`
            }
          >
            <Home className="h-4 w-4" />
            Dashboard
          </NavLink>
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
