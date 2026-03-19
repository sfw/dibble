import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { MemoryRouter } from 'react-router'
import { AcademicCatalog } from './AcademicCatalog'
import { AuthContext } from '../../contexts/AuthContext'
import { ConfigContext } from '../../contexts/ConfigContext'
import type { AuthState } from '../../hooks/useAuth'
import {
  listAdminCourses,
  listAdminSections,
  upsertAdminCourse,
  upsertAdminSection,
} from '../../api'

vi.mock('../../api', () => ({
  listAdminCourses: vi.fn(),
  listAdminSections: vi.fn(),
  upsertAdminCourse: vi.fn(),
  upsertAdminSection: vi.fn(),
}))

const mockedListAdminCourses = vi.mocked(listAdminCourses)
const mockedListAdminSections = vi.mocked(listAdminSections)
const mockedUpsertAdminCourse = vi.mocked(upsertAdminCourse)
const mockedUpsertAdminSection = vi.mocked(upsertAdminSection)

function makeAuthState(): AuthState {
  return {
    identity: {
      principal_id: 'admin-1',
      role: 'admin',
      auth_scheme: 'api_key',
      display_name: 'Admin Operator',
      learner_id: null,
    },
    authenticated: true,
    loading: false,
    error: '',
    login: vi.fn(),
    logout: vi.fn().mockResolvedValue(undefined),
    getToken: vi.fn().mockReturnValue(''),
    getApiKey: vi.fn().mockReturnValue('admin-key'),
  }
}

function renderCatalog() {
  return render(
    <ConfigContext.Provider value={{ baseUrl: 'http://localhost:8000', setBaseUrl: vi.fn() }}>
      <AuthContext.Provider value={makeAuthState()}>
        <MemoryRouter>
          <AcademicCatalog />
        </MemoryRouter>
      </AuthContext.Provider>
    </ConfigContext.Provider>,
  )
}

describe('AcademicCatalog', () => {
  beforeEach(() => {
    mockedListAdminCourses.mockReset()
    mockedListAdminSections.mockReset()
    mockedUpsertAdminCourse.mockReset()
    mockedUpsertAdminSection.mockReset()

    mockedListAdminCourses.mockResolvedValue([
      {
        course_id: 'MATH-5',
        title: 'Grade 5 Mathematics',
        subject: 'math',
        grade_band: '5',
        curriculum_package_id: null,
        tags: ['fractions'],
        updated_at: '2026-03-19T00:00:00Z',
        section_count: 1,
      },
    ])
    mockedListAdminSections.mockResolvedValue([
      {
        classroom_id: 'SEC-5A',
        course_id: 'MATH-5',
        title: 'Grade 5A',
        grade_level: '5',
        subject: 'math',
        tags: ['cohort-a'],
        updated_at: '2026-03-19T00:00:00Z',
        course_title: 'Grade 5 Mathematics',
        teacher_count: 1,
        learner_count: 24,
      },
    ])
  })

  it('renders course and section listings', async () => {
    renderCatalog()

    expect(await screen.findByText('SEC-5A')).toBeInTheDocument()
    expect(screen.getAllByText('Grade 5 Mathematics')).toHaveLength(2)
    expect(screen.getByText('SEC-5A')).toBeInTheDocument()
    expect(screen.getByText('1 teachers / 24 learners')).toBeInTheDocument()
  })

  it('creates a new course', async () => {
    mockedUpsertAdminCourse.mockResolvedValue({
      course_id: 'SCI-6',
      title: 'Grade 6 Science',
      subject: 'science',
      grade_band: '6',
      curriculum_package_id: null,
      tags: ['ecosystems'],
      updated_at: '2026-03-19T00:00:00Z',
      section_count: 0,
    })

    renderCatalog()

    await screen.findByText('SEC-5A')
    await userEvent.clear(screen.getByLabelText('Course ID'))
    await userEvent.type(screen.getByLabelText('Course ID'), 'SCI-6')
    await userEvent.clear(screen.getByLabelText('Course title'))
    await userEvent.type(screen.getByLabelText('Course title'), 'Grade 6 Science')
    await userEvent.type(screen.getByLabelText('Course subject'), 'science')
    await userEvent.type(screen.getByLabelText('Grade band'), '6')
    await userEvent.type(screen.getByLabelText('Course tags'), 'ecosystems')
    await userEvent.click(screen.getByRole('button', { name: 'Create course' }))

    await waitFor(() => {
      expect(mockedUpsertAdminCourse).toHaveBeenCalledWith(
        expect.objectContaining({ baseUrl: 'http://localhost:8000' }),
        'SCI-6',
        expect.objectContaining({
          course_id: 'SCI-6',
          title: 'Grade 6 Science',
          subject: 'science',
          grade_band: '6',
          tags: ['ecosystems'],
        }),
      )
    })
  })

  it('creates a new section', async () => {
    mockedUpsertAdminSection.mockResolvedValue({
      classroom_id: 'SEC-6B',
      course_id: 'MATH-5',
      title: 'Grade 6B',
      grade_level: '6',
      subject: 'math',
      tags: ['cohort-b'],
      updated_at: '2026-03-19T00:00:00Z',
      course_title: 'Grade 5 Mathematics',
      teacher_count: 0,
      learner_count: 0,
    })

    renderCatalog()

    await screen.findByText('SEC-5A')
    await userEvent.type(screen.getByLabelText('Section ID'), 'SEC-6B')
    await userEvent.clear(screen.getByLabelText('Section course ID'))
    await userEvent.type(screen.getByLabelText('Section course ID'), 'MATH-5')
    await userEvent.clear(screen.getByLabelText('Section title'))
    await userEvent.type(screen.getByLabelText('Section title'), 'Grade 6B')
    await userEvent.type(screen.getByLabelText('Grade level'), '6')
    await userEvent.type(screen.getByLabelText('Section tags'), 'cohort-b')
    await userEvent.click(screen.getByRole('button', { name: 'Create section' }))

    await waitFor(() => {
      expect(mockedUpsertAdminSection).toHaveBeenCalledWith(
        expect.objectContaining({ baseUrl: 'http://localhost:8000' }),
        'SEC-6B',
        expect.objectContaining({
          classroom_id: 'SEC-6B',
          course_id: 'MATH-5',
          title: 'Grade 6B',
          grade_level: '6',
          tags: ['cohort-b'],
        }),
      )
    })
  })
})
