import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { MemoryRouter } from 'react-router'
import { AcademicCatalog } from './AcademicCatalog'
import { AuthContext } from '../../contexts/AuthContext'
import { ConfigContext } from '../../contexts/ConfigContext'
import type { AuthState } from '../../hooks/useAuth'
import {
  getAdminSectionMemberships,
  listAdminCourses,
  listAdminSections,
  listStrands,
  listUsers,
  upsertAdminCourse,
  updateAdminSectionMemberships,
  upsertAdminSection,
} from '../../api'

vi.mock('../../api', () => ({
  getAdminSectionMemberships: vi.fn(),
  listAdminCourses: vi.fn(),
  listAdminSections: vi.fn(),
  listStrands: vi.fn(),
  listUsers: vi.fn(),
  upsertAdminCourse: vi.fn(),
  updateAdminSectionMemberships: vi.fn(),
  upsertAdminSection: vi.fn(),
}))

const mockedGetAdminSectionMemberships = vi.mocked(getAdminSectionMemberships)
const mockedListAdminCourses = vi.mocked(listAdminCourses)
const mockedListAdminSections = vi.mocked(listAdminSections)
const mockedListStrands = vi.mocked(listStrands)
const mockedListUsers = vi.mocked(listUsers)
const mockedUpsertAdminCourse = vi.mocked(upsertAdminCourse)
const mockedUpdateAdminSectionMemberships = vi.mocked(updateAdminSectionMemberships)
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
    mockedGetAdminSectionMemberships.mockReset()
    mockedListAdminCourses.mockReset()
    mockedListAdminSections.mockReset()
    mockedListStrands.mockReset()
    mockedListUsers.mockReset()
    mockedUpsertAdminCourse.mockReset()
    mockedUpdateAdminSectionMemberships.mockReset()
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
        section_id: 'SEC-5A',
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
    mockedListStrands.mockResolvedValue([])
    mockedListUsers.mockResolvedValue([
      {
        user_id: 'teacher-1',
        display_name: 'Ms. Rivera',
        role: 'teacher',
        learner_id: null,
        section_ids: ['SEC-5A'],
        created_at: '2026-03-19T00:00:00Z',
        updated_at: '2026-03-19T00:00:00Z',
      },
      {
        user_id: 'teacher-2',
        display_name: 'Mr. Song',
        role: 'teacher',
        learner_id: null,
        section_ids: [],
        created_at: '2026-03-19T00:00:00Z',
        updated_at: '2026-03-19T00:00:00Z',
      },
      {
        user_id: 'learner-1',
        display_name: 'Ava Learner',
        role: 'learner',
        learner_id: 'ava-1',
        section_ids: ['SEC-5A'],
        created_at: '2026-03-19T00:00:00Z',
        updated_at: '2026-03-19T00:00:00Z',
      },
      {
        user_id: 'learner-2',
        display_name: 'Mina',
        role: 'learner',
        learner_id: 'mina-2',
        section_ids: [],
        created_at: '2026-03-19T00:00:00Z',
        updated_at: '2026-03-19T00:00:00Z',
      },
    ])
    mockedGetAdminSectionMemberships.mockResolvedValue({
      section_id: 'SEC-5A',
      teachers: [{ user_id: 'teacher-1', display_name: 'Ms. Rivera' }],
      learners: [{ user_id: 'learner-1', display_name: 'Ava Learner' }],
    })
    mockedUpdateAdminSectionMemberships.mockResolvedValue({
      section_id: 'SEC-5A',
      teachers: [],
      learners: [],
    })
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
    await userEvent.type(screen.getByLabelText('Subject', { selector: '#course-subject' }), 'science')
    await userEvent.type(screen.getByLabelText('Grade band'), '6')
    await userEvent.type(screen.getByLabelText('Tags', { selector: '#course-tags' }), 'ecosystems')
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

  it('loads and saves section memberships while editing', async () => {
    mockedUpsertAdminSection.mockResolvedValue({
      section_id: 'SEC-5A',
      course_id: 'MATH-5',
      title: 'Grade 5A',
      grade_level: '5',
      subject: 'math',
      tags: ['cohort-a'],
      updated_at: '2026-03-19T00:00:00Z',
      course_title: 'Grade 5 Mathematics',
      teacher_count: 1,
      learner_count: 1,
    })
    mockedUpdateAdminSectionMemberships.mockResolvedValue({
      section_id: 'SEC-5A',
      teachers: [{ user_id: 'teacher-2', display_name: 'Mr. Song' }],
      learners: [{ user_id: 'learner-2', display_name: 'Mina' }],
    })

    renderCatalog()

    await screen.findByText('SEC-5A')
    await userEvent.click(screen.getByTitle('Edit section'))

    await waitFor(() => {
      expect(mockedGetAdminSectionMemberships).toHaveBeenCalledWith(
        expect.objectContaining({ baseUrl: 'http://localhost:8000' }),
        'SEC-5A',
      )
    })
    expect(await screen.findByText('Ms. Rivera (teacher-1)')).toBeInTheDocument()
    expect(screen.getByText('Ava Learner (learner-1)')).toBeInTheDocument()

    await userEvent.click(screen.getByLabelText('Remove teacher teacher-1'))
    await userEvent.click(screen.getByLabelText('Remove learner learner-1'))
    await userEvent.type(screen.getByLabelText('Teacher picker'), 'teacher-2')
    await userEvent.click(screen.getByRole('button', { name: 'Add teacher' }))
    await userEvent.type(screen.getByLabelText('Learner picker'), 'learner-2')
    await userEvent.click(screen.getByRole('button', { name: 'Add learner' }))
    await userEvent.click(screen.getByRole('button', { name: 'Save section' }))

    await waitFor(() => {
      expect(mockedUpdateAdminSectionMemberships).toHaveBeenCalledWith(
        expect.objectContaining({ baseUrl: 'http://localhost:8000' }),
        'SEC-5A',
        {
          teacher_user_ids: ['teacher-2'],
          learner_user_ids: ['learner-2'],
        },
      )
    })
  })
})
