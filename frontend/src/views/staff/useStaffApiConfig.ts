import { useAuthContext } from '../../contexts/AuthContext'
import { useConfigContext } from '../../contexts/ConfigContext'
import type { FrontendConfig } from '../../types'


export function useStaffApiConfig(): FrontendConfig {
  const auth = useAuthContext()
  const { baseUrl } = useConfigContext()

  return {
    baseUrl,
    apiKey: auth.getApiKey(),
    bearerToken: auth.getToken(),
    useDemoFallback: false,
    showDebugPanels: false,
  }
}
