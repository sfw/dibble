import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { getTeacherClassroom, getTeacherClassrooms } from '../api'
import type { DataSource } from '../app/workspace'
import { asMessage } from '../lib/formatters'
import { demoTeacherClassroom, demoTeacherClassrooms } from '../sample-data'
import type { FrontendConfig, TeacherClassroomOverview, TeacherClassroomReadModel } from '../types'

export function useTeacherClassroom({
  config,
  onDataSourceChange,
}: {
  config: FrontendConfig
  onDataSourceChange: (source: DataSource) => void
}) {
  const hasBootstrapped = useRef(false)
  const [classrooms, setClassrooms] = useState<TeacherClassroomOverview[]>(demoTeacherClassrooms)
  const [selectedClassroomId, setSelectedClassroomId] = useState(demoTeacherClassroom.classroom_id)
  const [classroom, setClassroom] = useState<TeacherClassroomReadModel>(demoTeacherClassroom)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const applyDemoFallback = useCallback(
    (message: string) => {
      setClassrooms(demoTeacherClassrooms)
      setSelectedClassroomId(demoTeacherClassroom.classroom_id)
      setClassroom(demoTeacherClassroom)
      setError(message)
      onDataSourceChange('demo')
    },
    [onDataSourceChange],
  )

  const loadClassroom = useCallback(
    async (classroomId: string) => {
      setLoading(true)
      setError('')

      try {
        const nextClassroom = await getTeacherClassroom(config, classroomId)
        setClassroom(nextClassroom)
        setSelectedClassroomId(classroomId)
        onDataSourceChange('live')
      } catch (caughtError) {
        if (!config.useDemoFallback) {
          setError(asMessage(caughtError))
          return
        }

        applyDemoFallback(`${asMessage(caughtError)} Showing a demo classroom instead.`)
      } finally {
        setLoading(false)
      }
    },
    [applyDemoFallback, config, onDataSourceChange],
  )

  const loadClassrooms = useCallback(async () => {
    setLoading(true)
    setError('')

    try {
      const nextClassrooms = await getTeacherClassrooms(config)
      setClassrooms(nextClassrooms)
      const activeClassroomId = nextClassrooms[0]?.classroom_id ?? demoTeacherClassroom.classroom_id
      const nextClassroom = await getTeacherClassroom(config, activeClassroomId)
      setSelectedClassroomId(activeClassroomId)
      setClassroom(nextClassroom)
      onDataSourceChange('live')
    } catch (caughtError) {
      if (!config.useDemoFallback) {
        setError(asMessage(caughtError))
        return
      }

      applyDemoFallback(`${asMessage(caughtError)} Showing demo classroom data instead.`)
    } finally {
      setLoading(false)
    }
  }, [applyDemoFallback, config, onDataSourceChange])

  useEffect(() => {
    if (hasBootstrapped.current) {
      return
    }

    hasBootstrapped.current = true
    void loadClassrooms()
  }, [loadClassrooms])

  const selectedOverview = useMemo(
    () =>
      classrooms.find((item) => item.classroom_id === selectedClassroomId) ??
      classrooms[0] ??
      demoTeacherClassrooms[0],
    [classrooms, selectedClassroomId],
  )

  return {
    classrooms,
    selectedClassroomId,
    selectedOverview,
    classroom,
    loading,
    error,
    loadClassrooms,
    loadClassroom,
    setSelectedClassroomId,
  }
}
