import { useEffect, useMemo, useState } from 'react'
import {
  githubHandleFromPayload,
  isBasicsVerified,
  linkedinUrlFromPayload,
  portfolioUrlFromPayload,
  type BasicsInput as BasicsForm,
  type ContactField,
  type ContactStatus,
  type ResumePayload,
} from '../../types/resume'
import type { ContactChecksState } from './useContactStatus'

type Props = {
  payload: ResumePayload
  contact: ContactChecksState
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
    portfolio: portfolioUrlFromPayload(payload),
  }
}

const LEVEL_LABEL: Record<string, string> = {
  looks_right: 'Looks right',
  exists: 'Exists',
  warning: 'Warning',
  broken: 'Fix this',
}

/** The server's verdict on one field. Hidden while the field has unsaved edits. */
function Badge({
  status,
  field,
  hidden,
}: {
  status: ContactStatus | null
  field: ContactField
  hidden: boolean
}) {
  const result = status?.fields[field]
  if (hidden || !result || result.level === 'empty' || result.level === 'unchecked') {
    return null
  }
  return (
    <span className={`contact-badge ${result.level}`}>
      <strong>{LEVEL_LABEL[result.level]}</strong>
      {result.message ? ` · ${result.message}` : ''}
    </span>
  )
}

export function BasicsEditor({
  payload,
  contact,
  busy,
  onConfirm,
  onDirtyChange,
}: Props) {
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
    form.linkedin !== saved.linkedin ||
    form.portfolio !== saved.portfolio

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
          <Badge status={contact.status} field="email" hidden={form.email !== saved.email} />
        </label>
        <label>
          Phone
          <input
            value={form.phone}
            autoComplete="tel"
            onChange={(event) => update('phone', event.target.value)}
          />
          <Badge status={contact.status} field="phone" hidden={form.phone !== saved.phone} />
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
          <Badge status={contact.status} field="linkedin" hidden={form.linkedin !== saved.linkedin} />
          <span className="contact-hint">
            LinkedIn can't be checked automatically. Open the link yourself to
            make sure it's you.
          </span>
        </label>
        <label>
          GitHub
          <input
            value={form.github}
            placeholder="username"
            onChange={(event) => update('github', event.target.value)}
          />
          <Badge status={contact.status} field="github" hidden={form.github !== saved.github} />
        </label>
        <label>
          Portfolio website
          <input
            value={form.portfolio}
            placeholder="yoursite.com"
            autoComplete="url"
            onChange={(event) => update('portfolio', event.target.value)}
          />
          <Badge status={contact.status} field="portfolio" hidden={form.portfolio !== saved.portfolio} />
        </label>
        <div className="contact-actions">
          <button className="primary-action" type="submit" disabled={!ready || (verified && !dirty)}>
            {verified && !dirty ? 'Confirmed' : 'Save and confirm'}
          </button>
          <button
            type="button"
            className="contact-recheck"
            disabled={dirty || contact.checking}
            onClick={() => void contact.recheck()}
          >
            {contact.checking ? 'Checking…' : 'Check again'}
          </button>
        </div>
        {contact.error && <p className="contact-error">{contact.error}</p>}
      </form>
    </section>
  )
}
