import { useCallback, useEffect, useRef, useState } from 'react'

import {
  createAssignment,
  getLearnerAssignments,
  getTeacherAssignments,
  updateAssignmentStatus,
} from '../api'
import { asMessage } from '../lib/formatters'
import type {
  Assignment,
  AssignmentCreate,
  AssignmentStatus,
  FrontendConfig,
} from '../types'

export function useLearnerAssignments({
  config,
  learnerId,
}: {
  config: FrontendConfig
  learnerId: string
}) {
  const hasBootstrapped = useRef(false)
  const [assignments, setAssignments] = useState<Assignment[]>([])
  const [hasMore, setHasMore] = useState(false)
  const [loading, setLoading] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    if (!learnerId) return
    setLoading(true)
    setError('')
    try {
      const page = await getLearnerAssignments(config, learnerId)
      setAssignments(page.items)
      setHasMore(page.has_more)
    } catch (e) {
      setError(asMessage(e))
    } finally {
      setLoading(false)
    }
  }, [config, learnerId])

  const loadMore = useCallback(async () => {
    if (!hasMore || !learnerId) return
    setLoadingMore(true)
    try {
      const page = await getLearnerAssignments(config, learnerId, 20, assignments.length)
      setAssignments((prev) => [...prev, ...page.items])
      setHasMore(page.has_more)
    } catch (e) {
      setError(asMessage(e))
    } finally {
      setLoadingMore(false)
    }
  }, [config, learnerId, assignments.length, hasMore])

  const updateStatus = useCallback(async (assignmentId: string, status: AssignmentStatus) => {
    try {
      const updated = await updateAssignmentStatus(config, assignmentId, status)
      setAssignments((prev) =>
        prev.map((a) => (a.assignment_id === assignmentId ? updated : a)),
      )
      return updated
    } catch (e) {
      setError(asMessage(e))
      return null
    }
  }, [config])

  useEffect(() => {
    if (hasBootstrapped.current && !learnerId) return
    hasBootstrapped.current = true
    void load()
  }, [learnerId, load])

  return { assignments, hasMore, loading, loadingMore, error, loadMore, updateStatus, refresh: load }
}

export function useTeacherAssignments({
  config,
}: {
  config: FrontendConfig
}) {
  const hasBootstrapped = useRef(false)
  const [assignments, setAssignments] = useState<Assignment[]>([])
  const [hasMore, setHasMore] = useState(false)
  const [loading, setLoading] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const page = await getTeacherAssignments(config)
      setAssignments(page.items)
      setHasMore(page.has_more)
    } catch (e) {
      setError(asMessage(e))
    } finally {
      setLoading(false)
    }
  }, [config])

  const loadMore = useCallback(async () => {
    if (!hasMore) return
    setLoadingMore(true)
    try {
      const page = await getTeacherAssignments(config, 50, assignments.length)
      setAssignments((prev) => [...prev, ...page.items])
      setHasMore(page.has_more)
    } catch (e) {
      setError(asMessage(e))
    } finally {
      setLoadingMore(false)
    }
  }, [config, assignments.length, hasMore])

  const create = useCallback(async (payload: AssignmentCreate) => {
    setCreating(true)
    setError('')
    try {
      const assignment = await createAssignment(config, payload)
      setAssignments((prev) => [assignment, ...prev])
      return assignment
    } catch (e) {
      setError(asMessage(e))
      return null
    } finally {
      setCreating(false)
    }
  }, [config])

  const updateStatus = useCallback(async (assignmentId: string, status: AssignmentStatus) => {
    try {
      const updated = await updateAssignmentStatus(config, assignmentId, status)
      setAssignments((prev) =>
        prev.map((a) => (a.assignment_id === assignmentId ? updated : a)),
      )
      return updated
    } catch (e) {
      setError(asMessage(e))
      return null
    }
  }, [config])

  useEffect(() => {
    if (hasBootstrapped.current) return
    hasBootstrapped.current = true
    void load()
  }, [load])

  return { assignments, hasMore, loading, loadingMore, creating, error, loadMore, create, updateStatus, refresh: load }
}
