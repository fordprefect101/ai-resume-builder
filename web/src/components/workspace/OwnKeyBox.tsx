import { useEffect, useState } from 'react'
import { KEY_CHANGED_EVENT, NEED_KEY_EVENT, getOwnKey, setOwnKey } from '../../api/ownKey'

// Shown when the daily free limit is reached (or a key is already in use): paste your own
// OpenAI key. It stays in this browser tab only and is sent with each request, never stored.
export default function OwnKeyBox() {
  const [open, setOpen] = useState(false)
  const [hasKey, setHasKey] = useState(() => Boolean(getOwnKey()))
  const [draft, setDraft] = useState('')

  useEffect(() => {
    const onNeed = () => setOpen(true)
    const onChange = () => setHasKey(Boolean(getOwnKey()))
    window.addEventListener(NEED_KEY_EVENT, onNeed)
    window.addEventListener(KEY_CHANGED_EVENT, onChange)
    return () => {
      window.removeEventListener(NEED_KEY_EVENT, onNeed)
      window.removeEventListener(KEY_CHANGED_EVENT, onChange)
    }
  }, [])

  if (!open && !hasKey) return null

  if (!open) {
    return (
      <button className="own-key-chip" type="button" onClick={() => setOpen(true)}>
        Using your own key
      </button>
    )
  }

  const save = () => {
    const key = draft.trim()
    if (!key.startsWith('sk-')) return
    setOwnKey(key)
    setDraft('')
    setOpen(false)
  }

  return (
    <div className="own-key-box" role="dialog" aria-label="Use your own OpenAI key">
      <p>
        {hasKey
          ? 'Your own OpenAI key is in use for this tab.'
          : "You've used today's free limit. Add your own OpenAI key to keep going."}{' '}
        It stays in this browser tab only, is sent with each request, and is never saved on our server.
      </p>
      {!hasKey && (
        <input
          type="password"
          autoComplete="off"
          placeholder="sk-…"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
        />
      )}
      <div className="own-key-actions">
        {!hasKey && (
          <button type="button" onClick={save} disabled={!draft.trim().startsWith('sk-')}>
            Use this key
          </button>
        )}
        {hasKey && (
          <button type="button" onClick={() => { setOwnKey(null); setOpen(false) }}>
            Remove my key
          </button>
        )}
        <button type="button" onClick={() => setOpen(false)}>Close</button>
      </div>
    </div>
  )
}
