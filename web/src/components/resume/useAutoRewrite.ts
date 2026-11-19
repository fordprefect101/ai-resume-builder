import { useCallback, useEffect, useRef, useState } from 'react'
import { rewriteEntry, RewriteError, type RewriteTarget } from '../../api/resumeApi'
import type { ResumePayload } from '../../types/resume'

/** What the editor needs to show and drive the rewrite on each entry. */
export type RewriteControls = ReturnType<typeof useAutoRewrite>

/** What the editor shows on one entry while the writing team works on it. */
export type RewriteState =
  | { kind: 'writing' }
  | { kind: 'confirm'; message: string }
  | { kind: 'error'; message: string }

export function targetKey(t: RewriteTarget): string {
  return `${t.section}:${t.itemId}:${t.projectId ?? ''}`
}

type Story = { id?: string; text?: string; source?: string }

/** The entries that carry the person's own words (not just old summarised points). */
function storySignatures(payload: ResumePayload): Map<string, string> {
  const out = new Map<string, string>()
  const sections = payload.inventory?.sections ?? {}
  const sig = (story: Story[] | undefined) => {
    const own = (story ?? []).filter((c) => c.source && c.source !== 'legacy')
    return own.length ? own.map((c) => `${c.id}:${(c.text ?? '').length}`).join('|') : ''
  }
  for (const section of ['experience', 'projects']) {
    for (const item of sections[section]?.items ?? []) {
      const s = sig(item.story as Story[] | undefined)
      if (s) out.set(targetKey({ section, itemId: item.id }), s)
      for (const project of item.projects ?? []) {
        const ps = sig(project.story as Story[] | undefined)
        if (ps) out.set(targetKey({ section, itemId: item.id, projectId: project.id }), ps)
      }
    }
  }
  return out
}

function parseKey(key: string): RewriteTarget {
  const [section, itemId, projectId] = key.split(':')
  return { section, itemId, projectId: projectId || null }
}

const STATE_WORDS = {
  tooMany: 'You have used the writing team a lot this hour. Please try again a little later.',
  failed: 'The writing team could not finish. Your current points are untouched.',
}

/**
 * Runs the writing team in the background after an entry's story changes, and
 * from the "Rewrite points" button. Never runs while a voice call is open (the
 * endpoint is slow and the call must stay responsive); it waits for the call to end.
 */
export function useAutoRewrite(
  payload: ResumePayload,
  sessionId: string,
  ready: boolean,
  voiceActive: boolean,
  onPayload: (payload: unknown, version: number) => void
) {
  const [states, setStates] = useState<Record<string, RewriteState>>({})
  const seen = useRef<Map<string, string> | null>(null)
  const pending = useRef<Set<string>>(new Set())
  const running = useRef<Set<string>>(new Set())
  const lastSession = useRef(sessionId)
  const onPayloadRef = useRef(onPayload)
  useEffect(() => {
    onPayloadRef.current = onPayload
  })

  const setState = useCallback((key: string, state: RewriteState | null) => {
    setStates((prev) => {
      const next = { ...prev }
      if (state) next[key] = state
      else delete next[key]
      return next
    })
  }, [])

  const run = useCallback(
    async (
      target: RewriteTarget,
      options: { force?: boolean; replaceEdited?: boolean } = {}
    ): Promise<void> => {
      const key = targetKey(target)
      if (running.current.has(key)) {
        pending.current.add(key) // run once more when this one ends
        return
      }
      running.current.add(key)
      let retried = false
      try {
        for (;;) {
          setState(key, { kind: 'writing' })
          let again = false
          try {
            const res = await rewriteEntry(sessionId, target, options)
            if (res.payload) onPayloadRef.current(res.payload, res.version)
            setState(key, null)
          } catch (err) {
            const status = err instanceof RewriteError ? err.status : 0
            if (status === 409 && /confirm/i.test((err as Error).message)) {
              setState(key, {
                kind: 'confirm',
                message:
                  'You wrote or edited some of these points. Replace them with a fresh version?',
              })
            } else if (status === 409 && !retried) {
              again = true // the entry changed meanwhile: run again once
            } else if (status === 409) {
              setState(key, {
                kind: 'error',
                message: 'This entry kept changing while it was being written. Try again.',
              })
            } else if (status === 429) {
              setState(key, { kind: 'error', message: STATE_WORDS.tooMany })
            } else if (status === 502) {
              setState(key, { kind: 'error', message: STATE_WORDS.failed })
            } else {
              setState(key, {
                kind: 'error',
                message: err instanceof Error ? err.message : STATE_WORDS.failed,
              })
            }
          }
          if (again) {
            retried = true
            continue
          }
          if (pending.current.delete(key)) continue // the story changed while writing
          break
        }
      } finally {
        running.current.delete(key)
      }
    },
    [sessionId, setState]
  )

  useEffect(() => {
    if (lastSession.current !== sessionId) {
      lastSession.current = sessionId
      seen.current = null
      pending.current.clear()
      setStates({})
    }
    if (!ready) return
    const now = storySignatures(payload)
    if (seen.current === null) {
      seen.current = now // what was already saved when this resume opened is not new
      return
    }
    for (const [key, sig] of now) {
      if (seen.current.get(key) !== sig) pending.current.add(key)
    }
    seen.current = now
    if (voiceActive) return
    for (const key of [...pending.current]) {
      pending.current.delete(key)
      void run(parseKey(key))
    }
  }, [payload, sessionId, ready, voiceActive, run])

  return {
    states,
    run,
    dismiss: (key: string) => setState(key, null),
    /** Hand a saved payload (from another request) to the app. */
    sessionId,
    applyPayload: (payload: unknown, version: number) => onPayloadRef.current(payload, version),
  }
}
