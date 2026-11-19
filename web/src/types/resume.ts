export type CareerFact = {
  id: string
  content: string
  context?: {
    section?: string
    itemId?: string
    field?: string
    projectId?: string | null
  }
  source?: string
  kind?: string
  owner?: string
  quote?: string | null
  storyId?: string | null
}

export type DerivedClaim = {
  id: string
  content: string
  supportedBy: string[]
  variantId?: string
  status?: string
  section?: string
  itemId?: string
  projectId?: string | null
  order?: number
  issues?: unknown[]
  origin?: string
}

export type StoryChunk = {
  id: string
  text: string
  source: string
  at: string | null
}

export type WritingState = {
  status: string
  questions: { id: string; text: string }[] | unknown[]
  followUpsAsked: number
}

export type ResumeVariant = {
  id: string
  name: string
  summary?: string
  includedIds: Record<string, string[]>
  sectionOrder: string[]
  generatedClaims?: string[]
}

export type ResumeProject = {
  id: string
  name: string
  status?: string
  technologies?: string[]
  bullets?: string[]
  story?: StoryChunk[]
  writing?: WritingState
}

export type ResumeItem = {
  id: string
  status?: string
  story?: StoryChunk[]
  writing?: WritingState
  projects?: ResumeProject[]
  [key: string]: unknown
}

export type ResumeSection = {
  title: string
  items: ResumeItem[]
}

export type ResumePayload = {
  schemaVersion: 3 | 4 | 5
  intake?: {
    status?: string
    basicsVerified?: boolean
    basicsConfirmed?: boolean
    [key: string]: unknown
  }
  inventory: {
    basics: {
      fullName: string
      email?: string
      phone?: string
      location?: string
      links: Array<{ label: string; url: string }>
    }
    skills: string[]
    sections: Record<string, ResumeSection>
  }
  resume: {
    title: string
    summary?: string
    includedIds: Record<string, string[]>
    sectionOrder: string[]
  }
  facts?: CareerFact[]
  claims?: DerivedClaim[]
  variants?: Record<string, ResumeVariant>
}

export function isResumePayload(value: unknown): value is ResumePayload {
  if (!value || typeof value !== 'object') return false
  const payload = value as Partial<ResumePayload>
  return Boolean(
    (payload.schemaVersion === 3 ||
      payload.schemaVersion === 4 ||
      payload.schemaVersion === 5) &&
      payload.inventory?.basics &&
      payload.inventory?.sections &&
      payload.resume?.includedIds &&
      Array.isArray(payload.resume?.sectionOrder)
  )
}

export function isBasicsVerified(payload: ResumePayload): boolean {
  return Boolean(
    payload.intake?.basicsVerified || payload.intake?.basicsConfirmed
  )
}

function linkUrl(
  links: Array<{ label?: string; url?: string }> | undefined,
  labels: string[]
): string {
  const found = (links ?? []).find((link) =>
    labels.includes((link.label ?? '').trim().toLowerCase())
  )
  return found?.url ?? ''
}

export function githubHandleFromPayload(payload: ResumePayload): string {
  const url = linkUrl(payload.inventory.basics.links, ['github'])
  const match = url.match(/github\.com\/([^/?#]+)/i)
  return match ? match[1] : url
}

export function linkedinUrlFromPayload(payload: ResumePayload): string {
  return linkUrl(payload.inventory.basics.links, ['linkedin'])
}

export function portfolioUrlFromPayload(payload: ResumePayload): string {
  return linkUrl(payload.inventory.basics.links, ['portfolio'])
}

/** The personal details as typed in the form and sent to the server. */
export type BasicsInput = {
  fullName: string
  email: string
  phone: string
  location: string
  github: string
  linkedin: string
  portfolio: string
}

export type ContactField = 'email' | 'phone' | 'github' | 'linkedin' | 'portfolio'

/**
 * What a badge says, as decided by the server (api/contact/status.py):
 * empty and unchecked show nothing; looks_right and exists are good;
 * warning never blocks; broken blocks "Save and confirm".
 */
export type ContactLevel =
  | 'empty'
  | 'unchecked'
  | 'looks_right'
  | 'exists'
  | 'warning'
  | 'broken'

/**
 * A project's link, as judged by the server (api/contact/project_links.py).
 * Information for the person only: it never changes a point and is not printed on the
 * resume. `languages` is what GitHub reports for a public repository.
 */
export type ProjectLinkView = {
  level: ContactLevel | 'private'
  message: string
  languages: string[]
}

/** Keyed by the project's entry ID. Only projects that have a link appear. */
export type ProjectLinks = Record<string, ProjectLinkView>

export type ContactStatus = {
  fields: Record<ContactField, { level: ContactLevel; message: string }>
  gate: {
    blocked: boolean
    blockers: Array<{ field: ContactField; message: string }>
  }
}

/**
 * A job's projects that are not archived, in stored order. The preview and the
 * editor both use this, so they cannot disagree about what counts as active.
 */
export function activeProjects(item: ResumeItem): ResumeProject[] {
  return (item.projects ?? []).filter(
    (project) => project.id && project.status !== 'archived'
  )
}

export function activeVariantView(payload: ResumePayload, variantId?: string | null) {
  if (!variantId || !payload.variants?.[variantId]) {
    return payload.resume
  }
  const v = payload.variants[variantId]
  return {
    title: v.name,
    summary: v.summary,
    includedIds: v.includedIds,
    sectionOrder: v.sectionOrder,
  }
}
