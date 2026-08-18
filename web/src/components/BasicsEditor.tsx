import { useEffect, useMemo, useState } from 'react'
import {
  githubHandleFromPayload,
  isBasicsVerified,
  linkedinUrlFromPayload,
  type ResumePayload,
} from '../types/resume'

type BasicsForm = {
  fullName: string
  email: string
  phone: string
  location: string
  github: string
  linkedin: string
}

type Props = {
  payload: ResumePayload
  busy: boolean
  onConfirm: (basics: BasicsForm) => void
  onDirtyChange?: (dirty: boolean) => void
}

function formFromPayload(payload: ResumePayload): BasicsForm {
  const { basics } = payload.inventory
  return {
    fullName: basics.fullName || '',
    email: basics.email || '',
    phone: basics.phone || '',
    location: basics.location || '',
    github: githubHandleFromPayload(payload),
    linkedin: linkedinUrlFromPayload(payload),
  }
}

export function BasicsEditor({ payload, busy, onConfirm, onDirtyChange }: Props) {
  const saved = useMemo(() => formFromPayload(payload), [payload])
  const [edited, setEdited] = useState<BasicsForm | null>(null)
  const form = edited ?? saved
  const verified = isBasicsVerified(payload)
  const dirty =
    form.fullName !== saved.fullName ||
    form.email !== saved.email ||
    form.phone !== saved.phone ||
    form.location !== saved.location ||
    form.github !== saved.github ||
    form.linkedin !== saved.linkedin

  useEffect(() => {
    setEdited(null)
  }, [saved])

  useEffect(() => {
    onDirtyChange?.(dirty)
  }, [dirty, onDirtyChange])

  function update<K extends keyof BasicsForm>(key: K, value: BasicsForm[K]) {
    setEdited((current) => ({ ...(current ?? saved), [key]: value }))
  }

  const ready = Boolean(form.fullName.trim()) && !busy
  const status = verified && !dirty ? 'verified' : 'pending'

  return (
    <section className="editor-card basics-card">
      <header className="basics-heading">
        <h3>Personal details</h3>
        <span className={`basics-status ${status}`}>
          {status === 'verified' ? 'Confirmed' : 'Confirm to continue'}
        </span>
      </header>
      <p className="basics-copy">
        Review these yourself. Voice and resume edits stay locked until you
        confirm them.
      </p>
      <form
        className="basics-form"
        onSubmit={(event) => {
          event.preventDefault()
          if (!ready) return
          onConfirm(form)
        }}
      >
        <label>
          Full name
          <input
            value={form.fullName}
            autoComplete="name"
            required
            onChange={(event) => update('fullName', event.target.value)}
          />
        </label>
        <label>
          Email
          <input
            type="email"
            value={form.email}
            autoComplete="email"
            onChange={(event) => update('email', event.target.value)}
          />
        </label>
        <label>
          Phone
          <input
            value={form.phone}
            autoComplete="tel"
            onChange={(event) => update('phone', event.target.value)}
          />
        </label>
        <label>
          Location
          <input
            value={form.location}
            autoComplete="address-level2"
            onChange={(event) => update('location', event.target.value)}
          />
        </label>
        <label>
          LinkedIn
          <input
            value={form.linkedin}
            placeholder="linkedin.com/in/you"
            onChange={(event) => update('linkedin', event.target.value)}
          />
        </label>
        <label>
          GitHub
          <input
            value={form.github}
            placeholder="username"
            onChange={(event) => update('github', event.target.value)}
          />
        </label>
        <button className="primary-action" type="submit" disabled={!ready || (verified && !dirty)}>
          {verified && !dirty ? 'Confirmed' : 'Save and confirm'}
        </button>
      </form>
    </section>
  )
}
