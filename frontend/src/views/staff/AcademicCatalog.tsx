import { useEffect, useMemo, useState } from 'react'
import { BookOpen, Blocks, Edit2, Plus, RefreshCw, Save } from 'lucide-react'
import {
  listAdminCourses,
  listAdminSections,
  upsertAdminCourse,
  upsertAdminSection,
} from '../../api'
import { Badge } from '../../components/ui/badge'
import { Button } from '../../components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card'
import { ErrorBanner } from '../../components/ui/error-banner'
import { Input } from '../../components/ui/input'
import { Label } from '../../components/ui/label'
import type {
  AdminCourseSummary,
  AdminSectionSummary,
  CourseUpsert,
  SectionUpsert,
} from '../../types'
import { useStaffApiConfig } from './useStaffApiConfig'

function parseTags(raw: string): string[] {
  return raw
    .split(',')
    .map((tag) => tag.trim())
    .filter(Boolean)
}

function formatTags(tags: string[]): string {
  return tags.join(', ')
}

function buildCourseDraft(course?: AdminCourseSummary): CourseUpsert {
  return {
    course_id: course?.course_id ?? '',
    title: course?.title ?? '',
    subject: course?.subject ?? '',
    grade_band: course?.grade_band ?? '',
    curriculum_package_id: course?.curriculum_package_id ?? '',
    tags: course?.tags ?? [],
  }
}

function buildSectionDraft(section?: AdminSectionSummary): SectionUpsert {
  return {
    classroom_id: section?.classroom_id ?? '',
    course_id: section?.course_id ?? '',
    title: section?.title ?? '',
    grade_level: section?.grade_level ?? '',
    subject: section?.subject ?? '',
    tags: section?.tags ?? [],
  }
}

export function AcademicCatalog() {
  const apiConfig = useStaffApiConfig()
  const [courses, setCourses] = useState<AdminCourseSummary[]>([])
  const [sections, setSections] = useState<AdminSectionSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [successMessage, setSuccessMessage] = useState('')

  const [editingCourseId, setEditingCourseId] = useState<string | null>(null)
  const [editingSectionId, setEditingSectionId] = useState<string | null>(null)
  const [courseDraft, setCourseDraft] = useState<CourseUpsert>(() => buildCourseDraft())
  const [sectionDraft, setSectionDraft] = useState<SectionUpsert>(() => buildSectionDraft())
  const [courseTagsInput, setCourseTagsInput] = useState('')
  const [sectionTagsInput, setSectionTagsInput] = useState('')

  async function loadCatalog() {
    setLoading(true)
    setError('')
    try {
      const [coursesResult, sectionsResult] = await Promise.all([
        listAdminCourses(apiConfig),
        listAdminSections(apiConfig),
      ])
      setCourses(coursesResult)
      setSections(sectionsResult)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load academic catalog')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadCatalog()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiConfig.baseUrl, apiConfig.apiKey, apiConfig.bearerToken])

  const courseOptions = useMemo(
    () => courses.map((course) => ({ value: course.course_id, label: course.title })),
    [courses],
  )

  async function handleSaveCourse() {
    setSaving(true)
    setError('')
    setSuccessMessage('')
    try {
      await upsertAdminCourse(apiConfig, courseDraft.course_id, {
        ...courseDraft,
        subject: courseDraft.subject?.trim() || undefined,
        grade_band: courseDraft.grade_band?.trim() || undefined,
        curriculum_package_id: courseDraft.curriculum_package_id?.trim() || undefined,
        tags: parseTags(courseTagsInput),
      })
      await loadCatalog()
      setCourseDraft(buildCourseDraft())
      setCourseTagsInput('')
      setEditingCourseId(null)
      setSuccessMessage('Course saved.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save course')
    } finally {
      setSaving(false)
    }
  }

  async function handleSaveSection() {
    setSaving(true)
    setError('')
    setSuccessMessage('')
    try {
      await upsertAdminSection(apiConfig, sectionDraft.classroom_id, {
        ...sectionDraft,
        grade_level: sectionDraft.grade_level?.trim() || undefined,
        subject: sectionDraft.subject?.trim() || undefined,
        tags: parseTags(sectionTagsInput),
      })
      await loadCatalog()
      setSectionDraft(buildSectionDraft())
      setSectionTagsInput('')
      setEditingSectionId(null)
      setSuccessMessage('Section saved.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save section')
    } finally {
      setSaving(false)
    }
  }

  function startCourseEdit(course: AdminCourseSummary) {
    setEditingCourseId(course.course_id)
    setCourseDraft(buildCourseDraft(course))
    setCourseTagsInput(formatTags(course.tags))
  }

  function startSectionEdit(section: AdminSectionSummary) {
    setEditingSectionId(section.classroom_id)
    setSectionDraft(buildSectionDraft(section))
    setSectionTagsInput(formatTags(section.tags))
  }

  return (
    <div className="flex flex-col gap-6">
      <section className="flex flex-col gap-4 rounded-[2rem] border border-border bg-[linear-gradient(135deg,#ffffff_0%,#f4fbf7_55%,#eef7ff_100%)] p-8 shadow-[0_24px_80px_rgba(56,46,24,0.08)] lg:flex-row lg:items-end lg:justify-between">
        <div className="space-y-3">
          <Badge variant="secondary" className="w-fit bg-sky-100 text-sky-900">
            Course and section catalog
          </Badge>
          <div className="space-y-2">
            <h1 className="text-3xl font-semibold tracking-tight text-slate-900">Manage reusable courses and taught sections.</h1>
            <p className="max-w-3xl text-sm leading-6 text-slate-600">
              Courses define the instructional container. Sections are the actual taught offerings that teachers and learners belong to.
            </p>
          </div>
        </div>
        <div className="flex gap-3">
          <Button variant="outline" onClick={() => void loadCatalog()} disabled={loading || saving}>
            <RefreshCw className="h-4 w-4" />
            Refresh
          </Button>
        </div>
      </section>

      <ErrorBanner message={error} />
      {successMessage && (
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          {successMessage}
        </div>
      )}

      <section className="grid gap-6 xl:grid-cols-[1fr_1fr]">
        <Card>
          <CardHeader>
            <CardDescription>Courses</CardDescription>
            <CardTitle className="flex items-center gap-2">
              <BookOpen className="h-5 w-5 text-sky-700" />
              Create or edit course definitions
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <div className="grid gap-3 md:grid-cols-2">
              <div className="flex flex-col gap-2">
                <Label htmlFor="course-id">Course ID</Label>
                <Input
                  id="course-id"
                  value={courseDraft.course_id}
                  onChange={(event) => setCourseDraft((current) => ({ ...current, course_id: event.target.value }))}
                  placeholder="MATH-5"
                />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="course-title">Course title</Label>
                <Input
                  id="course-title"
                  value={courseDraft.title}
                  onChange={(event) => setCourseDraft((current) => ({ ...current, title: event.target.value }))}
                  placeholder="Grade 5 Mathematics"
                />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="course-subject">Course subject</Label>
                <Input
                  id="course-subject"
                  value={courseDraft.subject ?? ''}
                  onChange={(event) => setCourseDraft((current) => ({ ...current, subject: event.target.value }))}
                  placeholder="math"
                />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="course-grade-band">Grade band</Label>
                <Input
                  id="course-grade-band"
                  value={courseDraft.grade_band ?? ''}
                  onChange={(event) => setCourseDraft((current) => ({ ...current, grade_band: event.target.value }))}
                  placeholder="5"
                />
              </div>
              <div className="flex flex-col gap-2 md:col-span-2">
                <Label htmlFor="course-package">Curriculum package</Label>
                <Input
                  id="course-package"
                  value={courseDraft.curriculum_package_id ?? ''}
                  onChange={(event) =>
                    setCourseDraft((current) => ({ ...current, curriculum_package_id: event.target.value }))
                  }
                  placeholder="core-math-2026"
                />
              </div>
              <div className="flex flex-col gap-2 md:col-span-2">
                <Label htmlFor="course-tags">Course tags</Label>
                <Input
                  id="course-tags"
                  value={courseTagsInput}
                  onChange={(event) => setCourseTagsInput(event.target.value)}
                  placeholder="fractions, intervention, grade-5"
                />
              </div>
            </div>
            <div className="flex gap-2">
              <Button onClick={() => void handleSaveCourse()} disabled={saving || !courseDraft.course_id || !courseDraft.title}>
                {editingCourseId ? <Save className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
                {editingCourseId ? 'Save course' : 'Create course'}
              </Button>
              <Button
                variant="outline"
                onClick={() => {
                  setEditingCourseId(null)
                  setCourseDraft(buildCourseDraft())
                  setCourseTagsInput('')
                }}
                disabled={saving}
              >
                Reset
              </Button>
            </div>
            <div className="overflow-x-auto rounded-2xl border border-border">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-left text-xs text-slate-500">
                  <tr>
                    <th className="px-4 py-3">Course</th>
                    <th className="px-4 py-3">Subject</th>
                    <th className="px-4 py-3">Sections</th>
                    <th className="px-4 py-3">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {courses.map((course) => (
                    <tr key={course.course_id} className="border-t">
                      <td className="px-4 py-3">
                        <div className="font-medium text-slate-900">{course.title}</div>
                        <div className="text-xs text-slate-500">{course.course_id}</div>
                      </td>
                      <td className="px-4 py-3 text-slate-600">{course.subject ?? '-'}</td>
                      <td className="px-4 py-3 text-slate-600">{course.section_count}</td>
                      <td className="px-4 py-3">
                        <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => startCourseEdit(course)} title="Edit course">
                          <Edit2 className="h-4 w-4" />
                        </Button>
                      </td>
                    </tr>
                  ))}
                  {!loading && courses.length === 0 && (
                    <tr>
                      <td className="px-4 py-6 text-center text-slate-500" colSpan={4}>
                        No courses yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardDescription>Sections</CardDescription>
            <CardTitle className="flex items-center gap-2">
              <Blocks className="h-5 w-5 text-emerald-700" />
              Create or edit taught section records
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <div className="grid gap-3 md:grid-cols-2">
              <div className="flex flex-col gap-2">
                <Label htmlFor="section-id">Section ID</Label>
                <Input
                  id="section-id"
                  value={sectionDraft.classroom_id}
                  onChange={(event) => setSectionDraft((current) => ({ ...current, classroom_id: event.target.value }))}
                  placeholder="SEC-5A"
                />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="section-course-id">Section course ID</Label>
                <Input
                  id="section-course-id"
                  value={sectionDraft.course_id}
                  onChange={(event) => setSectionDraft((current) => ({ ...current, course_id: event.target.value }))}
                  placeholder={courseOptions[0]?.value ?? 'MATH-5'}
                />
              </div>
              <div className="flex flex-col gap-2 md:col-span-2">
                <Label htmlFor="section-title">Section title</Label>
                <Input
                  id="section-title"
                  value={sectionDraft.title}
                  onChange={(event) => setSectionDraft((current) => ({ ...current, title: event.target.value }))}
                  placeholder="Grade 5A"
                />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="section-grade-level">Grade level</Label>
                <Input
                  id="section-grade-level"
                  value={sectionDraft.grade_level ?? ''}
                  onChange={(event) => setSectionDraft((current) => ({ ...current, grade_level: event.target.value }))}
                  placeholder="5"
                />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="section-subject">Section subject</Label>
                <Input
                  id="section-subject"
                  value={sectionDraft.subject ?? ''}
                  onChange={(event) => setSectionDraft((current) => ({ ...current, subject: event.target.value }))}
                  placeholder="math"
                />
              </div>
              <div className="flex flex-col gap-2 md:col-span-2">
                <Label htmlFor="section-tags">Section tags</Label>
                <Input
                  id="section-tags"
                  value={sectionTagsInput}
                  onChange={(event) => setSectionTagsInput(event.target.value)}
                  placeholder="cohort-a, fractions"
                />
              </div>
            </div>
            <div className="flex gap-2">
              <Button
                onClick={() => void handleSaveSection()}
                disabled={saving || !sectionDraft.classroom_id || !sectionDraft.course_id || !sectionDraft.title}
              >
                {editingSectionId ? <Save className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
                {editingSectionId ? 'Save section' : 'Create section'}
              </Button>
              <Button
                variant="outline"
                onClick={() => {
                  setEditingSectionId(null)
                  setSectionDraft(buildSectionDraft())
                  setSectionTagsInput('')
                }}
                disabled={saving}
              >
                Reset
              </Button>
            </div>
            <div className="overflow-x-auto rounded-2xl border border-border">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-left text-xs text-slate-500">
                  <tr>
                    <th className="px-4 py-3">Section</th>
                    <th className="px-4 py-3">Course</th>
                    <th className="px-4 py-3">People</th>
                    <th className="px-4 py-3">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {sections.map((section) => (
                    <tr key={section.classroom_id} className="border-t">
                      <td className="px-4 py-3">
                        <div className="font-medium text-slate-900">{section.title}</div>
                        <div className="text-xs text-slate-500">{section.classroom_id}</div>
                      </td>
                      <td className="px-4 py-3 text-slate-600">
                        <div>{section.course_title ?? section.course_id}</div>
                        <div className="text-xs text-slate-500">{section.course_id}</div>
                      </td>
                      <td className="px-4 py-3 text-slate-600">
                        {section.teacher_count} teachers / {section.learner_count} learners
                      </td>
                      <td className="px-4 py-3">
                        <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => startSectionEdit(section)} title="Edit section">
                          <Edit2 className="h-4 w-4" />
                        </Button>
                      </td>
                    </tr>
                  ))}
                  {!loading && sections.length === 0 && (
                    <tr>
                      <td className="px-4 py-6 text-center text-slate-500" colSpan={4}>
                        No sections yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      </section>
    </div>
  )
}
