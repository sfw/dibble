import { createBrowserRouter, Navigate } from 'react-router'
import { RoleSwitcher } from './shells/RoleSwitcher'
import { LearnerShell } from './shells/LearnerShell'
import { TeacherShell } from './shells/TeacherShell'
import { StaffShell } from './shells/StaffShell'
import { AuthGuard } from './components/shell/AuthGuard'
import { Login } from './views/Login'

// Learner views
import { LearnerHome } from './views/learner/LearnerHome'
import { ContinueLearning } from './views/learner/ContinueLearning'
import { SocraticCheck } from './views/learner/SocraticCheck'
import { RemediationSession } from './views/learner/RemediationSession'
import { Progress } from './views/learner/Progress'
import { History } from './views/learner/History'
import { Assignments as LearnerAssignments } from './views/learner/Assignments'

// Teacher views
import { Dashboard } from './views/teacher/Dashboard'
import { ClassroomDetail } from './views/teacher/ClassroomDetail'
import { LearnerDetail } from './views/teacher/LearnerDetail'
import { InterventionWorkspace } from './views/teacher/InterventionWorkspace'
import { TeacherAssignments } from './views/teacher/Assignments'
import { Reports } from './views/teacher/Reports'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <RoleSwitcher />,
  },

  {
    path: '/login',
    element: <Login />,
  },

  // Learner shell — requires learner or higher role
  {
    path: '/learn',
    element: (
      <AuthGuard allowedRoles={['learner', 'editor', 'admin']}>
        <LearnerShell />
      </AuthGuard>
    ),
    children: [
      { index: true, element: <LearnerHome /> },
      { path: 'continue', element: <ContinueLearning /> },
      { path: 'socratic/:sessionId', element: <SocraticCheck /> },
      { path: 'remediation/:sessionId', element: <RemediationSession /> },
      { path: 'assignments', element: <LearnerAssignments /> },
      { path: 'progress', element: <Progress /> },
      { path: 'history', element: <History /> },
    ],
  },

  // Teacher shell — requires teacher or higher role
  {
    path: '/teacher',
    element: (
      <AuthGuard allowedRoles={['teacher', 'editor', 'admin']}>
        <TeacherShell />
      </AuthGuard>
    ),
    children: [
      { index: true, element: <Dashboard /> },
      { path: 'classrooms', element: <Dashboard /> },
      { path: 'classrooms/:classroomId', element: <ClassroomDetail /> },
      { path: 'learners/:studentId', element: <LearnerDetail /> },
      { path: 'learners/:studentId/intervention', element: <InterventionWorkspace /> },
      { path: 'assignments', element: <TeacherAssignments /> },
      { path: 'reports', element: <Reports /> },
    ],
  },

  // Staff shell — wraps the existing tab-based workbench, requires admin
  {
    path: '/staff',
    element: (
      <AuthGuard allowedRoles={['admin', 'editor', 'viewer']}>
        <StaffShell />
      </AuthGuard>
    ),
  },

  // Catch-all redirect to role switcher
  {
    path: '*',
    element: <Navigate to="/" replace />,
  },
])
