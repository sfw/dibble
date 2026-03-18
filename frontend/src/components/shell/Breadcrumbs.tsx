import { Link, useLocation, useParams } from 'react-router'
import { ChevronRight } from 'lucide-react'

interface Crumb {
  label: string
  to: string
}

export function TeacherBreadcrumbs() {
  const { pathname } = useLocation()
  const { classroomId, studentId } = useParams()

  const crumbs: Crumb[] = [{ label: 'Dashboard', to: '/teacher' }]

  if (pathname.startsWith('/teacher/classrooms') && classroomId) {
    crumbs.push({ label: 'Classrooms', to: '/teacher/classrooms' })
    crumbs.push({ label: classroomId, to: `/teacher/classrooms/${classroomId}` })
  } else if (pathname.startsWith('/teacher/classrooms')) {
    crumbs.push({ label: 'Classrooms', to: '/teacher/classrooms' })
  }

  if (studentId) {
    crumbs.push({ label: studentId, to: `/teacher/learners/${studentId}` })
    if (pathname.endsWith('/intervention')) {
      crumbs.push({ label: 'Intervention', to: `/teacher/learners/${studentId}/intervention` })
    }
  }

  if (crumbs.length <= 1) return null

  return (
    <nav className="flex items-center gap-1 text-sm text-muted-foreground mb-4">
      {crumbs.map((crumb, index) => {
        const isLast = index === crumbs.length - 1
        return (
          <span key={crumb.to} className="flex items-center gap-1">
            {index > 0 && <ChevronRight className="h-3 w-3" />}
            {isLast ? (
              <span className="font-medium text-foreground">{crumb.label}</span>
            ) : (
              <Link to={crumb.to} className="hover:text-foreground hover:underline">
                {crumb.label}
              </Link>
            )}
          </span>
        )
      })}
    </nav>
  )
}
