import { useState } from 'react'
import { getResume, putResume } from './api/resumeApi'
import './App.css'

const EMPTY_PAYLOAD = {
  basics: {
    fullName: '',
    email: '',
    phone: '',
    location: '',
    links: [],
  },
  summary: '',
  skills: [] as string[],
  experience: [],
  projects: [],
  education: [],
  achievements: [],
}

function App() {
  const [sessionId, setSessionId] = useState('demo')
  const [payloadText, setPayloadText] = useState(
    JSON.stringify(EMPTY_PAYLOAD, null, 2)
  )
  const [version, setVersion] = useState<number | null>(null)
  const [status, setStatus] = useState('')

  async function handleLoad() {
    try {
      setStatus('Loading…')
      const data = await getResume(sessionId)
      setPayloadText(JSON.stringify(data.payload, null, 2))
      setVersion(data.version)
      setStatus(`Loaded version ${data.version}`)
    } catch (err) {
      setStatus(err instanceof Error ? err.message : 'Load failed')
    }
  }

  async function handleSave() {
    try {
      setStatus('Saving…')
      const payload = JSON.parse(payloadText)
      const data = await putResume(sessionId, payload)
      setVersion(data.version)
      setStatus(`Saved version ${data.version}`)
    } catch (err) {
      setStatus(err instanceof Error ? err.message : 'Save failed')
    }
  }

  return (
    <main style={{ maxWidth: 720, margin: '2rem auto', fontFamily: 'system-ui' }}>
      <h1>Resume Builder</h1>
      <label>
        Session ID{' '}
        <input
          value={sessionId}
          onChange={(e) => setSessionId(e.target.value)}
        />
      </label>
      <div style={{ marginTop: '0.75rem', display: 'flex', gap: '0.5rem' }}>
        <button type="button" onClick={handleLoad}>
          Load
        </button>
        <button type="button" onClick={handleSave}>
          Save
        </button>
      </div>
      <p>{status}{version !== null ? ` (v${version})` : ''}</p>
      <textarea
        value={payloadText}
        onChange={(e) => setPayloadText(e.target.value)}
        rows={28}
        style={{ width: '100%', fontFamily: 'monospace' }}
      />
    </main>
  )
}

export default App