export type ResumeItem = {
  id: string
  status?: string
  [key: string]: unknown
}

export type ResumeSection = {
  title: string
  items: ResumeItem[]
}

export type ResumePayload = {
  schemaVersion: 3
  intake?: {
    status?: string
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
}

export function isResumePayload(value: unknown): value is ResumePayload {
  if (!value || typeof value !== 'object') return false
  const payload = value as Partial<ResumePayload>
  return Boolean(
    payload.schemaVersion === 3 &&
      payload.inventory?.basics &&
      payload.inventory?.sections &&
      payload.resume?.includedIds &&
      Array.isArray(payload.resume?.sectionOrder)
  )
}
