import type { BasicsInput, ContactStatus, ProjectLinks } from '../types/resume'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8081';

export { API_BASE }

const creds: RequestInit = { credentials: 'include' }

export type ResumeResponse = {
  sessionId: string;
  payload: unknown;
  version: number;
  mode?: 'intake' | 'edit';
};

export async function apiErrorMessage(
  res: Response,
  fallback: string
): Promise<string> {
  try {
    const body = (await res.json()) as { detail?: unknown }
    const detail = body?.detail
    if (typeof detail === 'string' && detail.trim()) return detail
    if (Array.isArray(detail)) {
      const messages = detail
        .map((item) => {
          if (typeof item === 'string') return item
          if (item && typeof item === 'object' && 'msg' in item) {
            return String((item as { msg?: unknown }).msg ?? '')
          }
          return ''
        })
        .filter(Boolean)
      if (messages.length) return messages.join('; ')
    }
  } catch {
    /* keep fallback */
  }
  return fallback
}

async function parseOk(res: Response, fallback: string): Promise<ResumeResponse> {
  if (!res.ok) {
    throw new Error(await apiErrorMessage(res, fallback))
  }
  return res.json()
}

export async function getResume(sessionId: string): Promise<ResumeResponse> {
  const res = await fetch(`${API_BASE}/resume/${encodeURIComponent(sessionId)}`, creds);
  return parseOk(res, `GET failed: ${res.status}`);
}

export async function putResume(
  sessionId: string,
  payload: unknown
): Promise<ResumeResponse> {
  const res = await fetch(`${API_BASE}/resume/${encodeURIComponent(sessionId)}`, {
    ...creds,
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ payload }),
  });
  return parseOk(res, `PUT failed: ${res.status}`);
}

export async function startIntake(): Promise<ResumeResponse> {
  const res = await fetch(`${API_BASE}/intake/start`, {
    ...creds,
    method: 'POST',
  });
  return parseOk(res, `Start intake failed: ${res.status}`);
}

async function postResumeTool(
  sessionId: string,
  tool: string,
  body: unknown
): Promise<ResumeResponse> {
  const res = await fetch(
    `${API_BASE}/resume/${encodeURIComponent(sessionId)}/tools/${tool}`,
    {
      ...creds,
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }
  );
  return parseOk(res, `${tool} failed: ${res.status}`);
}

export function setItemIncluded(
  sessionId: string,
  section: string,
  itemId: string,
  included: boolean
): Promise<ResumeResponse> {
  return postResumeTool(
    sessionId,
    included ? 'include_on_resume' : 'exclude_from_resume',
    { section, itemId }
  );
}

export function reorderResumeSections(
  sessionId: string,
  sectionOrder: string[]
): Promise<ResumeResponse> {
  return postResumeTool(sessionId, 'reorder_sections', { sectionOrder });
}

export function reorderResumeItems(
  sessionId: string,
  section: string,
  itemIds: string[]
): Promise<ResumeResponse> {
  return postResumeTool(sessionId, 'reorder_items', { section, itemIds });
}

export type ContactChecks = {
  contactStatus: ContactStatus
  projectLinks: ProjectLinks
}

export async function fetchContactStatus(
  sessionId: string
): Promise<ContactChecks> {
  const res = await fetch(
    `${API_BASE}/resume/${encodeURIComponent(sessionId)}/contact-status`,
    creds
  )
  if (!res.ok) {
    throw new Error(await apiErrorMessage(res, `Contact status failed: ${res.status}`))
  }
  const body = (await res.json()) as Partial<ContactChecks>
  return {
    contactStatus: body.contactStatus as ContactStatus,
    projectLinks: body.projectLinks ?? {},
  }
}

/** "Check again": the server re-runs the lookups in the background. */
export async function recheckContactDetails(sessionId: string): Promise<void> {
  for (const path of ['basics/check', 'links/check']) {
    const res = await fetch(
      `${API_BASE}/resume/${encodeURIComponent(sessionId)}/${path}`,
      { ...creds, method: 'POST' }
    )
    if (!res.ok) {
      throw new Error(await apiErrorMessage(res, `Check again failed: ${res.status}`))
    }
  }
}

/** Mark a project's link as private ("can't be checked"), or undo that. */
export async function setProjectLinkPrivate(
  sessionId: string,
  itemId: string,
  isPrivate: boolean
): Promise<ProjectLinks> {
  const res = await fetch(
    `${API_BASE}/resume/${encodeURIComponent(sessionId)}/tools/set_link_private`,
    {
      ...creds,
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ itemId, private: isPrivate }),
    }
  )
  if (!res.ok) {
    throw new Error(await apiErrorMessage(res, `Could not update the link: ${res.status}`))
  }
  return ((await res.json()) as { projectLinks: ProjectLinks }).projectLinks
}

export async function updateResumeBasics(
  sessionId: string,
  basics: BasicsInput
): Promise<ResumeResponse> {
  const res = await fetch(
    `${API_BASE}/resume/${encodeURIComponent(sessionId)}/basics`,
    {
      ...creds,
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...basics, verify: true }),
    }
  )
  if (!res.ok) {
    throw new Error(await apiErrorMessage(res, `Update basics failed: ${res.status}`))
  }
  return res.json()
}

export type MutateResponse = ResumeResponse & {
  mutated?: boolean
  applied?: unknown[]
  diff?: string[]
  clarification?: string
  traceId?: number
}

export async function mutateResume(
  sessionId: string,
  message: string
): Promise<MutateResponse> {
  const res = await fetch(
    `${API_BASE}/resume/${encodeURIComponent(sessionId)}/mutate`,
    {
      ...creds,
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message }),
    }
  )
  if (!res.ok) {
    throw new Error(await apiErrorMessage(res, `Mutate failed: ${res.status}`))
  }
  return res.json()
}

export type VersionEntry = {
  version: number
  summary: string
  operations: unknown[]
  createdAt: string | null
}

export async function getVersionHistory(sessionId: string): Promise<{
  sessionId: string
  versions: VersionEntry[]
}> {
  const res = await fetch(
    `${API_BASE}/resume/${encodeURIComponent(sessionId)}/versions`,
    creds
  )
  if (!res.ok) {
    throw new Error(await apiErrorMessage(res, `Versions failed: ${res.status}`))
  }
  return res.json()
}

export async function restoreVersion(
  sessionId: string,
  version: number
): Promise<ResumeResponse & { restoredFrom: number }> {
  const res = await fetch(
    `${API_BASE}/resume/${encodeURIComponent(sessionId)}/versions/${version}/restore`,
    { ...creds, method: 'POST' }
  )
  if (!res.ok) {
    throw new Error(await apiErrorMessage(res, `Restore failed: ${res.status}`))
  }
  return res.json()
}

export async function analyzeJobDescription(
  sessionId: string,
  jobDescription: string,
  variantName?: string
): Promise<
  ResumeResponse & {
    analysis: unknown
    variantId?: string
    traceId?: number
  }
> {
  const res = await fetch(
    `${API_BASE}/resume/${encodeURIComponent(sessionId)}/analyze-jd`,
    {
      ...creds,
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        jobDescription,
        createVariant: true,
        variantName,
      }),
    }
  )
  if (!res.ok) {
    throw new Error(await apiErrorMessage(res, `JD analysis failed: ${res.status}`))
  }
  return res.json()
}

export async function getClaimProvenance(
  sessionId: string,
  claimId: string
): Promise<{ claim: unknown; facts: unknown[] }> {
  const res = await fetch(
    `${API_BASE}/resume/${encodeURIComponent(sessionId)}/claims/${encodeURIComponent(claimId)}/provenance`,
    creds
  )
  if (!res.ok) {
    throw new Error(await apiErrorMessage(res, `Provenance failed: ${res.status}`))
  }
  return res.json()
}
export type RewriteTarget = {
  section: string
  itemId: string
  projectId?: string | null
}

export type RewriteResponse = {
  sessionId: string
  version: number
  /** The story has not changed since the points were written: nothing was done. */
  skipped?: boolean
  reason?: string
  payload?: unknown
}

/** A failed rewrite, with the HTTP status so the caller can answer in plain words. */
export class RewriteError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

/**
 * Ask the writing team to (re)write one entry's points from its story. Slow, so it
 * is only ever called from the editor in the background, never from the voice path.
 */
export async function rewriteEntry(
  sessionId: string,
  target: RewriteTarget,
  options: { force?: boolean; replaceEdited?: boolean } = {}
): Promise<RewriteResponse> {
  const res = await fetch(
    `${API_BASE}/resume/${encodeURIComponent(sessionId)}/rewrite`,
    {
      ...creds,
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        section: target.section,
        itemId: target.itemId,
        projectId: target.projectId ?? null,
        force: Boolean(options.force),
        replaceEdited: Boolean(options.replaceEdited),
      }),
    }
  )
  if (!res.ok) {
    throw new RewriteError(
      res.status,
      await apiErrorMessage(res, `Rewrite failed: ${res.status}`)
    )
  }
  return res.json()
}

/**
 * Store the person's typed answer to one of the writing team's questions (or a skip).
 * The server keeps the answer as part of the entry's story and counts it toward the
 * 2-question limit; the caller then lets the writing team rewrite the entry.
 */
export async function answerFollowup(
  sessionId: string,
  target: RewriteTarget,
  questionId: string,
  answer: string,
  skipped = false
): Promise<{ payload: unknown; version: number }> {
  const res = await fetch(
    `${API_BASE}/resume/${encodeURIComponent(sessionId)}/tools/answer_followup`,
    {
      ...creds,
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        section: target.section,
        itemId: target.itemId,
        projectId: target.projectId ?? null,
        questionId,
        storyTurns: skipped ? [] : [answer],
        storySource: 'typed',
        skipped,
      }),
    }
  )
  if (!res.ok) throw new Error(await apiErrorMessage(res, `Could not save the answer: ${res.status}`))
  return res.json()
}
