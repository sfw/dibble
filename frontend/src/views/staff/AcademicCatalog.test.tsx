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
  upsertAdminCourse,
  updateAdminSectionMemberships,
  upsertAdminSection,
} from '../../api'

vi.mock('../../api', () => ({
  getAdminSectionMemberships: vi.fn(),
  listAdminCourses: vi.fn(),
  listAdminSections: vi.fn(),
  upsertAdminCourse: vi.fn(),
  updateAdminSectionMemberships: vi.fn(),
  upsertAdminSection: vi.fn(),
}))

const mockedGetAdminSectionMemberships = vi.mocked(getAdminSectionMemberships)
const mockedListAdminCourses = vi.mocked(listAdminCourses)
const mockedListAdminSections = vi.mocked(listAdminSections)
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
    mockedGetAdminSectionMemberships.mockResolvedValue({
      classroom_id: 'SEC-5A',
      teachers: [{ user_id: 'teacher-1', display_name: 'Ms. Rivera' }],
      learners: [{ user_id: 'learner-1', display_name: 'Ava Learner' }],
    })
    mockedUpdateAdminSectionMemberships.mockResolvedValue({
      classroom_id: 'SEC-5A',
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
    mockedUpdateAdminSectionMemberships.mockResolvedValue({
      classroom_id: 'SEC-6B',
      teachers: [],
      learners: [],
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
    expect(mockedUpdateAdminSectionMemberships).toHaveBeenCalledWith(
      expect.objectContaining({ baseUrl: 'http://localhost:8000' }),
      'SEC-6B',
      {
        teacher_user_ids: [],
        learner_user_ids: [],
      },
    )
  })

  it('loads and saves section memberships while editing', async () => {
    mockedUpsertAdminSection.mockResolvedValue({
      classroom_id: 'SEC-5A',
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
      classroom_id: 'SEC-5A',
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
    expect(await screen.findByDisplayValue('teacher-1')).toBeInTheDocument()
    expect(screen.getByDisplayValue('learner-1')).toBeInTheDocument()

    await userEvent.clear(screen.getByLabelText('Teacher user IDs'))
    await userEvent.type(screen.getByLabelText('Teacher user IDs'), 'teacher-2')
    await userEvent.clear(screen.getByLabelText('Learner user IDs'))
    await userEvent.type(screen.getByLabelText('Learner user IDs'), 'learner-2')
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
