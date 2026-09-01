import type { ResumePayload } from '../types/resume'

export const EMPTY_PAYLOAD: ResumePayload = {
  schemaVersion: 4,
  intake: { status: 'not_started', basicsVerified: false },
  inventory: {
    basics: {
      fullName: '',
      email: '',
      phone: '',
      location: '',
      links: [],
    },
    skills: [] as string[],
    sections: {
      experience: { title: 'Experience', items: [] },
      projects: { title: 'Projects', items: [] },
      education: { title: 'Education', items: [] },
      achievements: { title: 'Achievements', items: [] },
    },
  },
  resume: {
    title: 'General Resume',
    summary: '',
    includedIds: {
      experience: [] as string[],
      projects: [] as string[],
      education: [] as string[],
      achievements: [] as string[],
    },
    sectionOrder: ['experience', 'projects', 'education', 'achievements'],
  },
  facts: [],
  claims: [],
  variants: {},
}
