import { createBrowserRouter, Navigate } from 'react-router'
import { RoleSwitcher } from './shells/RoleSwitcher'
import { LearnerShell } from './shells/LearnerShell'
import { TeacherShell } from './shells/TeacherShell'
import { StaffShell } from './shells/StaffShell'

// Learner views
import { LearnerHome } from './views/learner/LearnerHome'
import { ContinueLearning } from './views/learner/ContinueLearning'
import { SocraticCheck } from './views/learner/SocraticCheck'
import { RemediationSession } from './views/learner/RemediationSession'
import { Progress } from './views/learner/Progress'
import { History } from './views/learner/History'

// Teacher views
import { Dashboard } from './views/teacher/Dashboard'
import { ClassroomDetail } from './views/teacher/ClassroomDetail'
import { LearnerDetail } from './views/teacher/LearnerDetail'
import { InterventionWorkspace } from './views/teacher/InterventionWorkspace'

function Placeholder({ label }: { label: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-24 text-center text-muted-foreground">
      <p className="text-lg font-medium">{label}</p>
      <p className="text-sm">Coming soon.</p>
    </div>
  )
}

export const router = createBrowserRouter([
  {
    path: '/',
    element: <RoleSwitcher />,
  },

  // Learner shell
  {
    path: '/learn',
    element: <LearnerShell />,
    children: [
      { index: true, element: <LearnerHome /> },
      { path: 'continue', element: <ContinueLearning /> },
      { path: 'socratic/:sessionId', element: <SocraticCheck /> },
      { path: 'remediation/:sessionId', element: <RemediationSession /> },
      { path: 'progress', element: <Progress /> },
      { path: 'history', element: <History /> },
    ],
  },

  // Teacher shell
  {
    path: '/teacher',
    element: <TeacherShell />,
    children: [
      { index: true, element: <Dashboard /> },
      { path: 'classrooms', element: <Dashboard /> },
      { path: 'classrooms/:classroomId', element: <ClassroomDetail /> },
      { path: 'learners/:studentId', element: <LearnerDetail /> },
      { path: 'learners/:studentId/intervention', element: <InterventionWorkspace /> },
      { path: 'reports', element: <Placeholder label="Reports" /> },
    ],
  },

  // Staff shell — wraps the existing tab-based workbench
  {
    path: '/staff',
    element: <StaffShell />,
  },

  // Catch-all redirect to role switcher
  {
    path: '*',
    element: <Navigate to="/" replace />,
  },
])
