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
      const msg = err instanceof Error ? err.message : 'Mutation failed'
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
      onStatus(`Restored version ${version}`)
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
      onStatus(`JD analyzed — variant ${res.variantId ?? 'created'}`)
    } catch (err) {
      onStatus(err instanceof Error ? err.message : 'JD analysis failed')
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
      setProvenance({ claim: claim.content || '', facts })
    } catch (err) {
      onStatus(err instanceof Error ? err.message : 'Provenance unavailable')
    }
  }

  const variants = Object.values(payload.variants ?? {})
  // Item points also live in claims (v5); this list is only for generated ones.
  const generatedClaims = (payload.claims ?? []).filter((c) => !c.itemId)

  return (
    <section className="intelligence-panel">
      <header>
        <p className="eyebrow">Career intelligence</p>
        <h2>Natural language → structured updates</h2>
      </header>

      <div className="intel-chat-log">
        {chat.length === 0 && (
          <p className="muted">
            Try: &quot;Add Redis to my ChaiShots project&quot; or &quot;Move AWS above
            Docker in skills&quot;
          </p>
        )}
        {chat.map((entry, i) => (
          <div key={`${entry.role}-${i}`} className={`intel-msg intel-msg-${entry.role}`}>
            <strong>{entry.role === 'user' ? 'You' : 'System'}</strong>
            <pre>{entry.text}</pre>
          </div>
        ))}
      </div>

      <div className="intel-input-row">
        <textarea
          value={input}
          disabled={contentLocked || busy}
          placeholder="Describe a career update…"
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
          Apply
        </button>
      </div>

      <details className="intel-section" onToggle={(e) => {
        if ((e.target as HTMLDetailsElement).open) void loadVersions()
      }}>
        <summary>Version history</summary>
        <ul className="version-list">
          {versions.map((v) => (
            <li key={v.version}>
              <span>v{v.version}</span>
              <span>{v.summary}</span>
              <button type="button" onClick={() => void handleRestore(v.version)}>
                Restore
              </button>
            </li>
          ))}
          {versions.length === 0 && <li>No versions recorded yet</li>}
        </ul>
      </details>

      <details className="intel-section">
        <summary>Job description tailoring</summary>
        <textarea
          value={jdText}
          disabled={contentLocked || busy}
          placeholder="Paste a job description…"
          rows={5}
          onChange={(e) => setJdText(e.target.value)}
        />
        <button
          type="button"
          disabled={contentLocked || busy || !jdText.trim()}
          onClick={() => void handleJdAnalyze()}
        >
          Analyze &amp; create variant
        </button>
      </details>

      {variants.length > 0 && (
        <div className="intel-section">
          <h3>Resume variants</h3>
          <div className="variant-tabs">
            <button
              type="button"
              className={!activeVariantId ? 'active' : ''}
              onClick={() => onVariantChange(null)}
            >
              Default
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

      {generatedClaims.length > 0 && (
        <details className="intel-section">
          <summary>Generated claims &amp; provenance</summary>
          <ul className="claim-list">
            {generatedClaims.map((c) => (
              <li key={c.id}>
                <p>{c.content}</p>
                <small>Status: {c.status ?? 'pending'}</small>
                <button type="button" onClick={() => void showProvenance(c.id)}>
                  Why this?
                </button>
              </li>
            ))}
          </ul>
          {provenance && (
            <div className="provenance-box">
              <strong>Claim</strong>
              <p>{provenance.claim}</p>
              <strong>Derived from</strong>
              <ul>
                {provenance.facts.map((f) => (
                  <li key={f}>{f}</li>
                ))}
              </ul>
            </div>
          )}
        </details>
      )}

      <p className="muted intel-facts-count">
        {(payload.facts ?? []).length} career facts tracked
      </p>
    </section>
  )
}
