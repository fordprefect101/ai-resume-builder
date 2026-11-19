import { useState } from 'react'
import type { ResumePayload } from '../../types/resume'
import {
  analyzeJobDescription,
  getClaimProvenance,
  getVersionHistory,
  mutateResume,
  restoreVersion,
  type VersionEntry,
} from '../../api/resumeApi'

type ChatEntry = {
  role: 'user' | 'assistant'
  text: string
  diff?: string[]
}

type Props = {
  sessionId: string
  payload: ResumePayload
  contentLocked: boolean
  onPayload: (payload: unknown, version: number) => void
  onStatus: (msg: string) => void
  activeVariantId: string | null
  onVariantChange: (id: string | null) => void
}

export function IntelligencePanel({
  sessionId,
  payload,
  contentLocked,
  onPayload,
  onStatus,
  activeVariantId,
  onVariantChange,
}: Props) {
  const [input, setInput] = useState('')
  const [jdText, setJdText] = useState('')
  const [busy, setBusy] = useState(false)
  const [chat, setChat] = useState<ChatEntry[]>([])
  const [versions, setVersions] = useState<VersionEntry[]>([])
  const [provenance, setProvenance] = useState<{ claim: string; facts: string[] } | null>(
    null
  )

  async function handleMutate() {
    const text = input.trim()
    if (!text || contentLocked) return
    setBusy(true)
    setChat((prev) => [...prev, { role: 'user', text }])
    setInput('')
    try {
      const res = await mutateResume(sessionId, text)
      const reply =
        res.clarification ||
        (res.diff?.length
          ? `Applied:\n${res.diff.map((d) => `• ${d}`).join('\n')}`
          : 'No changes applied.')
      setChat((prev) => [
        ...prev,
        { role: 'assistant', text: reply, diff: res.diff },
      ])
      if (res.payload && res.mutated) {
        onPayload(res.payload, res.version)
      }
      onStatus(res.mutated ? 'Career data updated' : 'Awaiting clarification')
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'That change did not work'
      setChat((prev) => [...prev, { role: 'assistant', text: msg }])
      onStatus(msg)
    } finally {
      setBusy(false)
    }
  }

  async function loadVersions() {
    try {
      const res = await getVersionHistory(sessionId)
      setVersions(res.versions)
    } catch (err) {
      onStatus(err instanceof Error ? err.message : 'Could not load versions')
    }
  }

  async function handleRestore(version: number) {
    setBusy(true)
    try {
      const res = await restoreVersion(sessionId, version)
      onPayload(res.payload, res.version)
      onStatus(`Went back to the version from ${version === 0 ? 'the start' : `step ${version}`}`)
      await loadVersions()
    } catch (err) {
      onStatus(err instanceof Error ? err.message : 'Restore failed')
    } finally {
      setBusy(false)
    }
  }

  async function handleJdAnalyze() {
    if (!jdText.trim() || contentLocked) return
    setBusy(true)
    try {
      const res = await analyzeJobDescription(sessionId, jdText)
      onPayload(res.payload, res.version)
      if (res.variantId) onVariantChange(res.variantId)
      onStatus('Made a version tailored to that job')
    } catch (err) {
      onStatus(err instanceof Error ? err.message : 'Could not tailor to that job')
    } finally {
      setBusy(false)
    }
  }

  async function showProvenance(claimId: string) {
    try {
      const res = await getClaimProvenance(sessionId, claimId)
      const claim = res.claim as { content?: string }
      const facts = (res.facts as Array<{ content?: string }>).map(
        (f) => f.content || ''
      )
      setProvenance({ claim: claim.content || '', facts: facts.filter(Boolean) })
    } catch (err) {
      onStatus(err instanceof Error ? err.message : 'Could not show where this line came from')
    }
  }

  const variants = Object.values(payload.variants ?? {})
  // Every line the person can ask about: points and generated lines alike.
  const lines = (payload.claims ?? []).filter((c) => c.content)

  function when(iso: string | null) {
    if (!iso) return 'Earlier'
    const d = new Date(iso)
    return Number.isNaN(d.getTime()) ? 'Earlier' : d.toLocaleString()
  }

  return (
    <section className="intelligence-panel">
      <header>
        <p className="eyebrow">Smart tools</p>
        <h2>Change your resume in plain words</h2>
      </header>

      <div className="intel-chat-log">
        {chat.length === 0 && (
          <p className="muted">
            Type what you want changed, for example &quot;Add Redis to my ChaiShots
            project&quot; or &quot;Move AWS above Docker in skills&quot;.
          </p>
        )}
        {chat.map((entry, i) => (
          <div key={`${entry.role}-${i}`} className={`intel-msg intel-msg-${entry.role}`}>
            <strong>{entry.role === 'user' ? 'You' : 'Assistant'}</strong>
            <pre>{entry.text}</pre>
          </div>
        ))}
      </div>

      <div className="intel-input-row">
        <textarea
          value={input}
          disabled={contentLocked || busy}
          placeholder="What should change?"
          rows={3}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) void handleMutate()
          }}
        />
        <button
          type="button"
          className="primary-action"
          disabled={contentLocked || busy || !input.trim()}
          onClick={() => void handleMutate()}
        >
          Make the change
        </button>
      </div>

      <details className="intel-section">
        <summary>Tailor to a job</summary>
        <p className="muted">
          Paste a job description. You get a separate version of your resume
          aimed at that job; your main resume stays as it is.
        </p>
        <textarea
          value={jdText}
          disabled={contentLocked || busy}
          placeholder="Paste the job description here…"
          rows={5}
          onChange={(e) => setJdText(e.target.value)}
        />
        <button
          type="button"
          disabled={contentLocked || busy || !jdText.trim()}
          onClick={() => void handleJdAnalyze()}
        >
          Make a version for this job
        </button>
      </details>

      {variants.length > 0 && (
        <div className="intel-section">
          <h3>Your versions</h3>
          <div className="variant-tabs">
            <button
              type="button"
              className={!activeVariantId ? 'active' : ''}
              onClick={() => onVariantChange(null)}
            >
              Main resume
            </button>
            {variants.map((v) => (
              <button
                key={v.id}
                type="button"
                className={activeVariantId === v.id ? 'active' : ''}
                onClick={() => onVariantChange(v.id)}
              >
                {v.name}
              </button>
            ))}
          </div>
        </div>
      )}

      {lines.length > 0 && (
        <details className="intel-section">
          <summary>Why is this line here?</summary>
          <p className="muted">
            Pick a line to see the facts about you that it is based on.
          </p>
          <ul className="claim-list">
            {lines.map((c) => (
              <li key={c.id}>
                <p>{c.content}</p>
                <button type="button" onClick={() => void showProvenance(c.id)}>
                  Show the facts behind it
                </button>
              </li>
            ))}
          </ul>
          {provenance && (
            <div className="provenance-box">
              <strong>Line</strong>
              <p>{provenance.claim}</p>
              <strong>Based on</strong>
              {provenance.facts.length === 0 ? (
                <p className="muted">No saved facts for this line yet.</p>
              ) : (
                <ul>
                  {provenance.facts.map((f) => (
                    <li key={f}>{f}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </details>
      )}

      <details
        className="intel-section"
        onToggle={(e) => {
          if ((e.target as HTMLDetailsElement).open) void loadVersions()
        }}
      >
        <summary>History</summary>
        <p className="muted">Every change is saved. You can go back to any earlier point.</p>
        <ul className="version-list">
          {versions.map((v) => (
            <li key={v.version}>
              <span>{when(v.createdAt)}</span>
              <span>{v.summary || 'Change saved'}</span>
              <button type="button" onClick={() => void handleRestore(v.version)}>
                Go back to this
              </button>
            </li>
          ))}
          {versions.length === 0 && <li>No changes recorded yet</li>}
        </ul>
      </details>
    </section>
  )
}
