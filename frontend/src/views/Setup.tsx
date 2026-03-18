import { useState } from 'react'
import { BookOpen } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card'
import { useConfigContext } from '../contexts/ConfigContext'
import { useSetupStatus } from '../hooks/useSetupStatus'
import { SetupConnectStep } from './setup/SetupConnectStep'
import { SetupProviderStep } from './setup/SetupProviderStep'
import { SetupVerifyStep } from './setup/SetupVerifyStep'
import { SetupAdminStep } from './setup/SetupAdminStep'
import { SetupCompleteStep } from './setup/SetupCompleteStep'
import type { SetupConfigureRequest } from '../types'

type Step = 'connect' | 'provider' | 'verify' | 'admin' | 'complete'

const stepLabels: Record<Step, string> = {
  connect: 'Connect to server',
  provider: 'Configure LLM provider',
  verify: 'Review & save',
  admin: 'Create admin account',
  complete: 'Done',
}

export function Setup() {
  const { baseUrl, setBaseUrl } = useConfigContext()
  const { status } = useSetupStatus(baseUrl)
  const [step, setStep] = useState<Step>('connect')
  const [providerConfig, setProviderConfig] = useState<SetupConfigureRequest>({})
  const [configPath, setConfigPath] = useState('')

  const allSteps = Object.keys(stepLabels) as Step[]
  const stepIndex = allSteps.indexOf(step) + 1

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-8 bg-slate-50 p-6">
      <header className="flex flex-col items-center gap-2 text-center">
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10">
          <BookOpen className="h-6 w-6 text-primary" />
        </div>
        <h1 className="text-3xl font-semibold tracking-tight">Dibble Setup</h1>
        <p className="text-muted-foreground">Configure your Dibble instance.</p>
      </header>

      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle className="text-lg">{stepLabels[step]}</CardTitle>
          <CardDescription>
            Step {stepIndex} of {allSteps.length}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {step === 'connect' && (
            <SetupConnectStep
              baseUrl={baseUrl}
              onBaseUrlChange={setBaseUrl}
              onNext={() => setStep('provider')}
            />
          )}
          {step === 'provider' && (
            <SetupProviderStep
              config={providerConfig}
              onConfigChange={setProviderConfig}
              onNext={() => setStep('verify')}
              onBack={() => setStep('connect')}
            />
          )}
          {step === 'verify' && (
            <SetupVerifyStep
              baseUrl={baseUrl}
              config={providerConfig}
              onSuccess={(path) => {
                setConfigPath(path)
                // Skip admin step if admin already exists
                if (status?.has_admin_user) {
                  setStep('complete')
                } else {
                  setStep('admin')
                }
              }}
              onBack={() => setStep('provider')}
            />
          )}
          {step === 'admin' && (
            <SetupAdminStep
              onNext={() => setStep('complete')}
              onBack={() => setStep('verify')}
            />
          )}
          {step === 'complete' && (
            <SetupCompleteStep configPath={configPath} />
          )}
        </CardContent>
      </Card>
    </div>
  )
}
