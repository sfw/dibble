import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { getTeacherSection, getTeacherSections } from '../api'
import type { DataSource } from '../app/workspace'
import { asMessage } from '../lib/formatters'
import { demoTeacherClassroom, demoTeacherClassrooms } from '../sample-data'
import type { FrontendConfig, TeacherSectionOverview, TeacherSectionReadModel } from '../types'

export function useTeacherSections({
  config,
  onDataSourceChange,
}: {
  config: FrontendConfig
  onDataSourceChange: (source: DataSource) => void
}) {
  const hasBootstrapped = useRef(false)
  const [classrooms, setClassrooms] = useState<TeacherSectionOverview[]>(demoTeacherClassrooms)
  const [selectedSectionId, setSelectedSectionId] = useState(demoTeacherClassroom.section_id)
  const [classroom, setClassroom] = useState<TeacherSectionReadModel>(demoTeacherClassroom)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const applyDemoFallback = useCallback(
    (message: string) => {
      setClassrooms(demoTeacherClassrooms)
      setSelectedSectionId(demoTeacherClassroom.section_id)
      setClassroom(demoTeacherClassroom)
      setError(message)
      onDataSourceChange('demo')
    },
    [onDataSourceChange],
  )

  const loadSection = useCallback(
    async (sectionId: string) => {
      setLoading(true)
      setError('')

      try {
        const nextSection = await getTeacherSection(config, sectionId)
        setClassroom(nextSection)
        setSelectedSectionId(sectionId)
        onDataSourceChange('live')
      } catch (caughtError) {
        if (!config.useDemoFallback) {
          setError(asMessage(caughtError))
          return
        }

        applyDemoFallback(`${asMessage(caughtError)} Showing a demo section instead.`)
      } finally {
        setLoading(false)
      }
    },
    [applyDemoFallback, config, onDataSourceChange],
  )

  const loadSections = useCallback(async () => {
    setLoading(true)
    setError('')

    try {
      const nextSections = await getTeacherSections(config)
      setClassrooms(nextSections)
      const activeSectionId = nextSections[0]?.section_id ?? demoTeacherClassroom.section_id
      const nextSection = await getTeacherSection(config, activeSectionId)
      setSelectedSectionId(activeSectionId)
      setClassroom(nextSection)
      onDataSourceChange('live')
    } catch (caughtError) {
      if (!config.useDemoFallback) {
        setError(asMessage(caughtError))
        return
      }

      applyDemoFallback(`${asMessage(caughtError)} Showing demo section data instead.`)
    } finally {
      setLoading(false)
    }
  }, [applyDemoFallback, config, onDataSourceChange])

  useEffect(() => {
    if (hasBootstrapped.current) {
      return
    }

    hasBootstrapped.current = true
    void loadSections()
  }, [loadSections])

  const selectedOverview = useMemo(
    () =>
      classrooms.find((item) => item.section_id === selectedSectionId) ??
      classrooms[0] ??
      demoTeacherClassrooms[0],
    [classrooms, selectedSectionId],
  )

  return {
    classrooms,
    selectedSectionId,
    selectedOverview,
    classroom,
    loading,
    error,
    loadSections,
    loadSection,
    setSelectedSectionId,
  }
}
