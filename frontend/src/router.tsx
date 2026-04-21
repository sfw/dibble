import { createBrowserRouter, Navigate } from 'react-router'
import { RoleSwitcher } from './shells/RoleSwitcher'
import { LearnerShell } from './shells/LearnerShell'
import { ParentShell } from './shells/ParentShell'
import { TeacherShell } from './shells/TeacherShell'
import { StaffShell } from './shells/StaffShell'
import { AuthGuard } from './components/shell/AuthGuard'
import { SetupGuard } from './components/shell/SetupGuard'
import { Login } from './views/Login'
import { Setup } from './views/Setup'

// Learner views
import { LearnerHome } from './views/learner/LearnerHome'
import { ContinueLearning } from './views/learner/ContinueLearning'
import { SocraticCheck } from './views/learner/SocraticCheck'
import { RemediationSession } from './views/learner/RemediationSession'
import { Progress } from './views/learner/Progress'
import { History } from './views/learner/History'
import { Assignments as LearnerAssignments } from './views/learner/Assignments'

// Teacher views
import { Dashboard as ParentDashboard } from './views/parent/Dashboard'
import { Dashboard } from './views/teacher/Dashboard'
import { ClassroomDetail } from './views/teacher/ClassroomDetail'
import { LearnerDetail } from './views/teacher/LearnerDetail'
import { InterventionWorkspace } from './views/teacher/InterventionWorkspace'
import { TeacherAssignments } from './views/teacher/Assignments'
import { Reports } from './views/teacher/Reports'

// Staff views
import { StaffDashboard } from './views/staff/StaffDashboard'
import { AcademicCatalog } from './views/staff/AcademicCatalog'
import { CurriculumManager } from './views/staff/CurriculumManager'
import { SystemConfig } from './views/staff/SystemConfig'
import { UserManagement } from './views/staff/UserManagement'

export const router = createBrowserRouter([
  {
    path: '/',
    element: (
      <SetupGuard mode="configured">
        <RoleSwitcher />
      </SetupGuard>
    ),
  },

  {
    path: '/login',
    element: (
      <SetupGuard mode="configured">
        <Login />
      </SetupGuard>
    ),
  },

  {
    path: '/setup',
    element: (
      <SetupGuard mode="unconfigured">
        <Setup />
      </SetupGuard>
    ),
  },

  // Learner shell — requires learner or higher role
  {
    path: '/learn',
    element: (
      <SetupGuard mode="configured">
        <AuthGuard allowedRoles={['learner', 'editor', 'admin']}>
          <LearnerShell />
        </AuthGuard>
      </SetupGuard>
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
    path: '/parent',
    element: (
      <SetupGuard mode="configured">
        <AuthGuard allowedRoles={['parent', 'household_admin', 'admin']}>
          <ParentShell />
        </AuthGuard>
      </SetupGuard>
    ),
    children: [{ index: true, element: <ParentDashboard /> }],
  },

  // Teacher shell — requires teacher or higher role
  {
    path: '/teacher',
    element: (
      <SetupGuard mode="configured">
        <AuthGuard allowedRoles={['teacher', 'editor', 'admin']}>
          <TeacherShell />
        </AuthGuard>
      </SetupGuard>
    ),
    children: [
      { index: true, element: <Dashboard /> },
      { path: 'sections', element: <Dashboard /> },
      { path: 'sections/:sectionId', element: <ClassroomDetail /> },
      { path: 'learners/:studentId', element: <LearnerDetail /> },
      { path: 'learners/:studentId/intervention', element: <InterventionWorkspace /> },
      { path: 'assignments', element: <TeacherAssignments /> },
      { path: 'reports', element: <Reports /> },
    ],
  },

  // Staff shell — requires admin/editor/viewer
  {
    path: '/staff',
    element: (
      <SetupGuard mode="configured">
        <AuthGuard allowedRoles={['admin', 'editor', 'viewer']}>
          <StaffShell />
        </AuthGuard>
      </SetupGuard>
    ),
    children: [
      { index: true, element: <StaffDashboard /> },
      {
        path: 'academics',
        element: (
          <AuthGuard allowedRoles={['admin']}>
            <AcademicCatalog />
          </AuthGuard>
        ),
      },
      {
        path: 'curriculum',
        element: (
          <AuthGuard allowedRoles={['admin']}>
            <CurriculumManager />
          </AuthGuard>
        ),
      },
      {
        path: 'config',
        element: (
          <AuthGuard allowedRoles={['admin']}>
            <SystemConfig />
          </AuthGuard>
        ),
      },
      {
        path: 'users',
        element: (
          <AuthGuard allowedRoles={['admin']}>
            <UserManagement />
          </AuthGuard>
        ),
      },
    ],
  },

  // Catch-all redirect to role switcher
  {
    path: '*',
    element: <Navigate to="/" replace />,
  },
])
