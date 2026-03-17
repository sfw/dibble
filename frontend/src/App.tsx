import { useState } from 'react'
import './App.css'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { resolveContinueActionView, type DataSource, type ViewKey } from './app/workspace'
import { teacherContractGaps } from './sample-data'
import { WorkspaceHero } from './components/app/WorkspaceHero'
import { WorkspacePicker } from './components/app/WorkspacePicker'
import { useGenerationWorkspace } from './hooks/useGenerationWorkspace'
import { useLearnerContracts } from './hooks/useLearnerContracts'
import { useLearnerWorkspace } from './hooks/useLearnerWorkspace'
import { usePersistentConfig } from './hooks/usePersistentConfig'
import { useRemediationWorkspace } from './hooks/useRemediationWorkspace'
import { useSocraticWorkspace } from './hooks/useSocraticWorkspace'
import { useTeacherClassroom } from './hooks/useTeacherClassroom'
import { ClassroomView } from './views/ClassroomView'
import { GenerationView } from './views/GenerationView'
import { OverviewView } from './views/OverviewView'
import { RemediationView } from './views/RemediationView'
import { SocraticView } from './views/SocraticView'
import { TeacherView } from './views/TeacherView'

function App() {
  const [activeView, setActiveView] = useState<ViewKey>('overview')
  const [dataSource, setDataSource] = useState<DataSource>('demo')
  const [classroomHandoffStudentId, setClassroomHandoffStudentId] = useState<string | null>(null)
  const [teacherHandoffContext, setTeacherHandoffContext] = useState<{
    classroomId: string
    classroomTitle: string
    learnerId: string
  } | null>(null)
  const { config, setConfig } = usePersistentConfig()
  const learnerWorkspace = useLearnerWorkspace({
    config,
    onDataSourceChange: setDataSource,
  })
  const learnerContracts = useLearnerContracts({
    config,
    learnerId: learnerWorkspace.learnerId,
    onDataSourceChange: setDataSource,
  })
  const generationWorkspace = useGenerationWorkspace({
    config,
    learnerId: learnerWorkspace.learnerId,
    workspace: learnerWorkspace.workspace,
    onDataSourceChange: setDataSource,
  })
  const socraticWorkspace = useSocraticWorkspace({
    config,
    learnerId: learnerWorkspace.learnerId,
    workspace: learnerWorkspace.workspace,
    onDataSourceChange: setDataSource,
  })
  const remediationWorkspace = useRemediationWorkspace({
    config,
    learnerId: learnerWorkspace.learnerId,
    workspace: learnerWorkspace.workspace,
    onDataSourceChange: setDataSource,
  })
  const teacherClassroom = useTeacherClassroom({
    config,
    onDataSourceChange: setDataSource,
  })

  async function handoffClassroomLearner({
    studentId,
    targetView,
    includeTeacherContext = false,
  }: {
    studentId: string
    targetView: ViewKey
    includeTeacherContext?: boolean
  }) {
    setClassroomHandoffStudentId(studentId)

    if (includeTeacherContext) {
      setTeacherHandoffContext({
        classroomId: teacherClassroom.selectedClassroomId,
        classroomTitle: teacherClassroom.selectedOverview.title,
        learnerId: studentId,
      })
    } else {
      setTeacherHandoffContext(null)
    }

    try {
      await Promise.allSettled([
        learnerWorkspace.loadLearnerWorkspace(studentId),
        learnerContracts.loadContracts(studentId),
      ])
      setActiveView(targetView)
    } finally {
      setClassroomHandoffStudentId(null)
    }
  }

  return (
    <div className="app-shell">
      <WorkspaceHero
        dataSource={dataSource}
        learnerId={learnerWorkspace.learnerId}
        flowType={learnerWorkspace.flow.flow_type}
        config={config}
        setConfig={setConfig}
      />

      <Tabs
        value={activeView}
        onValueChange={(value) => setActiveView(value as ViewKey)}
        className="toolbar"
      >
        <WorkspacePicker
          learnerId={learnerWorkspace.learnerId}
          setLearnerId={learnerWorkspace.setLearnerId}
          learnerIds={learnerWorkspace.learnerIds}
          loading={learnerWorkspace.loading}
          error={learnerWorkspace.error}
          onRefresh={() => {
            void learnerWorkspace.refreshCurrentLearner()
            void learnerContracts.loadContracts()
            void teacherClassroom.loadClassrooms()
          }}
          onPickLearner={(learnerId) => {
            setTeacherHandoffContext(null)
            void learnerWorkspace.loadLearnerWorkspace(learnerId)
          }}
        />
        <TabsList className="tabbar" aria-label="Workspace views">
          <TabsTrigger value="overview">Learner Overview</TabsTrigger>
          <TabsTrigger value="generation">Generated Content</TabsTrigger>
          <TabsTrigger value="socratic">Socratic</TabsTrigger>
          <TabsTrigger value="remediation">Remediation</TabsTrigger>
          <TabsTrigger value="teacher">Teacher View</TabsTrigger>
          <TabsTrigger value="classroom">Classroom View</TabsTrigger>
        </TabsList>

        <main className="workspace">
          <TabsContent value="overview">
            <OverviewView
              summary={learnerWorkspace.summary}
              profile={learnerWorkspace.profile}
              flow={learnerWorkspace.flow}
              workspace={learnerWorkspace.workspace}
              progression={learnerWorkspace.summary.curriculum_progression}
              generationHistory={learnerContracts.generationHistory}
              socraticHistory={learnerContracts.socraticHistory}
              remediationHistory={learnerContracts.remediationHistory}
              contractsLoading={learnerContracts.loading}
              contractsError={learnerContracts.error}
              onSelectView={setActiveView}
              showDebugPanels={config.showDebugPanels}
            />
          </TabsContent>
          <TabsContent value="generation">
            <GenerationView
              form={generationWorkspace.form}
              onFormChange={generationWorkspace.setForm}
              loading={generationWorkspace.loading}
              error={generationWorkspace.error}
              result={generationWorkspace.result}
              streaming={generationWorkspace.streaming}
              streamEvents={generationWorkspace.streamEvents}
              streamedBlocks={generationWorkspace.streamedBlocks}
              showDebugPanels={config.showDebugPanels}
              onGenerate={() => void generationWorkspace.handleGenerate()}
              onStream={() => void generationWorkspace.handleStream()}
            />
          </TabsContent>
          <TabsContent value="socratic">
            <SocraticView
              form={socraticWorkspace.form}
              onFormChange={socraticWorkspace.setForm}
              loading={socraticWorkspace.loading}
              error={socraticWorkspace.error}
              response={socraticWorkspace.response}
              session={socraticWorkspace.session}
              showDebugPanels={config.showDebugPanels}
              onRun={() => void socraticWorkspace.handleRun()}
              onReload={() => void socraticWorkspace.handleReload()}
            />
          </TabsContent>
          <TabsContent value="remediation">
            <RemediationView
              form={remediationWorkspace.form}
              onFormChange={remediationWorkspace.setForm}
              loading={remediationWorkspace.loading}
              error={remediationWorkspace.error}
              content={remediationWorkspace.content}
              session={remediationWorkspace.session}
              advance={remediationWorkspace.advance}
              advancePrompt={remediationWorkspace.advancePrompt}
              showDebugPanels={config.showDebugPanels}
              onAdvancePromptChange={remediationWorkspace.setAdvancePrompt}
              onTrigger={() => void remediationWorkspace.handleTrigger()}
              onReload={() => void remediationWorkspace.handleReload()}
              onAdvance={() => void remediationWorkspace.handleAdvance()}
            />
          </TabsContent>
          <TabsContent value="teacher">
            <TeacherView
              summary={learnerWorkspace.summary}
              profile={learnerWorkspace.profile}
              flow={learnerWorkspace.flow}
              progression={learnerWorkspace.summary.curriculum_progression}
              intervention={learnerContracts.intervention}
              gaps={teacherContractGaps}
              dataSource={dataSource}
              loading={learnerContracts.loading || learnerWorkspace.loading}
              submissionError={learnerContracts.interventionError}
              submittingDecision={learnerContracts.submittingIntervention}
              onSubmitDecision={(payload) => void learnerContracts.submitTeacherDecision(payload)}
              handoffContext={teacherHandoffContext}
              onReturnToClassroom={() => setActiveView('classroom')}
              showDebugPanels={config.showDebugPanels}
            />
          </TabsContent>
          <TabsContent value="classroom">
            <ClassroomView
              classrooms={teacherClassroom.classrooms}
              selectedClassroomId={teacherClassroom.selectedClassroomId}
              classroom={teacherClassroom.classroom}
              loading={teacherClassroom.loading}
              error={teacherClassroom.error}
              handoffLoadingStudentId={classroomHandoffStudentId}
              onPickClassroom={(classroomId) => void teacherClassroom.loadClassroom(classroomId)}
              onOpenTeacher={(studentId) =>
                void handoffClassroomLearner({
                  studentId,
                  targetView: 'teacher',
                  includeTeacherContext: true,
                })}
              onContinueLearner={(studentId, continueActionKind) => {
                const targetView = resolveContinueActionView(continueActionKind)
                if (!targetView) {
                  return
                }

                void handoffClassroomLearner({
                  studentId,
                  targetView,
                })
              }}
              showDebugPanels={config.showDebugPanels}
            />
          </TabsContent>
        </main>
      </Tabs>
    </div>
  )
}

export default App
