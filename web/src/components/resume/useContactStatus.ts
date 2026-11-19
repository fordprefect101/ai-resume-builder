import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchContactStatus, recheckContactDetails } from '../../api/resumeApi'
import type { ContactStatus, ProjectLinks } from '../../types/resume'

const POLL_MS = 3000
const MAX_POLLS = 7

// Only these fields have an "exists" lookup. LinkedIn and phone stay "looks right".
const LOOKED_UP = ['email', 'github', 'portfolio'] as const

function lookupsPending(status: ContactStatus, links: ProjectLinks): boolean {
  const detailsPending = LOOKED_UP.some((field) => {
    const level = status.fields[field].level
    return level === 'unchecked' || level === 'looks_right'
  })
  const linksPending = Object.values(links).some(
    (link) => link.level === 'unchecked' || link.level === 'looks_right'
  )
  return detailsPending || linksPending
}

export type ContactChecksState = {
  status: ContactStatus | null
  projectLinks: ProjectLinks
  error: string
  checking: boolean
  recheck: () => Promise<void>
  /** Replace the project link badges with a fresher answer from the server. */
  setProjectLinks: (links: ProjectLinks) => void
}

/**
 * The server's badges for the contact details and for project links. `savedKey`
 * changes whenever the saved details or project links change; the badges are then
 * fetched and re-asked every few seconds until the background lookups have an
 * answer (or MAX_POLLS passes).
 */
export function useContactStatus(
  sessionId: string,
  savedKey: string
): ContactChecksState {
  const [status, setStatus] = useState<ContactStatus | null>(null)
  const [projectLinks, setProjectLinks] = useState<ProjectLinks>({})
  const [error, setError] = useState('')
  // Checking until the lookups for the current savedKey have finished, or while a
  // recheck runs.
  const [checkedKey, setCheckedKey] = useState<string | null>(null)
  const [rechecking, setRechecking] = useState(false)
  const checking = checkedKey !== savedKey || rechecking
  const run = useRef(0)

  const poll = useCallback(
    async (id: number, key: string) => {
      for (let attempt = 0; attempt < MAX_POLLS; attempt += 1) {
        try {
          const next = await fetchContactStatus(sessionId)
          if (run.current !== id) return
          setStatus(next.contactStatus)
          setProjectLinks(next.projectLinks)
          setError('')
          if (!lookupsPending(next.contactStatus, next.projectLinks)) break
        } catch (err) {
          if (run.current !== id) return
          setError(err instanceof Error ? err.message : 'Could not load the checks')
          break
        }
        await new Promise((resolve) => window.setTimeout(resolve, POLL_MS))
        if (run.current !== id) return
      }
      if (run.current === id) {
        setCheckedKey(key)
        setRechecking(false)
      }
    },
    [sessionId]
  )

  useEffect(() => {
    run.current += 1
    const id = run.current
    void poll(id, savedKey)
    return () => {
      run.current += 1
    }
  }, [poll, savedKey])

  const recheck = useCallback(async () => {
    run.current += 1
    const id = run.current
    setRechecking(true)
    try {
      await recheckContactDetails(sessionId)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not start the checks')
      setRechecking(false)
      return
    }
    // Give the background run a moment before the first look.
    await new Promise((resolve) => window.setTimeout(resolve, 1500))
    if (run.current === id) void poll(id, savedKey)
  }, [poll, savedKey, sessionId])

  return { status, projectLinks, error, checking, recheck, setProjectLinks }
}
