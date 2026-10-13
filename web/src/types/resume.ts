export type CareerFact = {
  id: string
  content: string
  context?: { section?: string; itemId?: string; field?: string }
  source?: string
}

export type DerivedClaim = {
  id: string
  content: string
  supportedBy: string[]
  variantId?: string
  status?: string
  section?: string
  itemId?: string
  order?: number
}

export type StoryChunk = {
  id: string
  text: string
  source: string
  at: string | null
}

export type WritingState = {
  status: string
  questions: unknown[]
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

export type ResumeItem = {
  id: string
  status?: string
  story?: StoryChunk[]
  writing?: WritingState
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
