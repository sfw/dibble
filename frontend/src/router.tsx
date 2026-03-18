import { createBrowserRouter, Navigate } from 'react-router'
import { RoleSwitcher } from './shells/RoleSwitcher'
import { LearnerShell } from './shells/LearnerShell'
import { TeacherShell } from './shells/TeacherShell'
import { StaffShell } from './shells/StaffShell'
import { LearnerHome } from './views/learner/LearnerHome'

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
      { path: 'continue', element: <Placeholder label="Continue Learning" /> },
      { path: 'socratic/:sessionId', element: <Placeholder label="Socratic Check" /> },
      { path: 'remediation/:sessionId', element: <Placeholder label="Remediation Session" /> },
      { path: 'progress', element: <Placeholder label="Progress" /> },
      { path: 'history', element: <Placeholder label="History" /> },
    ],
  },

  // Teacher shell
  {
    path: '/teacher',
    element: <TeacherShell />,
    children: [
      { index: true, element: <Placeholder label="Teacher Dashboard" /> },
      { path: 'classrooms', element: <Placeholder label="Classrooms" /> },
      { path: 'classrooms/:classroomId', element: <Placeholder label="Classroom Detail" /> },
      { path: 'learners/:studentId', element: <Placeholder label="Learner Detail" /> },
      { path: 'learners/:studentId/intervention', element: <Placeholder label="Intervention Workspace" /> },
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
