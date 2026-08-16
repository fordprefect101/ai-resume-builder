import { useRef, useState } from 'react'
import { getResume, putResume } from './api/resumeApi'
import { startRealtimeSession, type RealtimeHandles } from './voice/realtimeSession'
import { handleToolCallEvent } from './voice/handleRealtimeTools'
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
  const voiceRef = useRef<RealtimeHandles | null>(null)
  const [voiceStatus, setVoiceStatus] = useState('Voice off')
  const [transcriptLog, setTranscriptLog] = useState<string[]>([])
  const sessionIdRef = useRef(sessionId)
  sessionIdRef.current = sessionId
  
  async function handleStartVoice() {
    try {
      setVoiceStatus('Connecting…')
      const holder: { current: RealtimeHandles | null } = { current: null }
  
      const handles = await startRealtimeSession(sessionIdRef.current, async (event) => {
        const type = String(event.type ?? '')
        if (
          type.includes('transcript') ||
          type.includes('transcription') ||
          type === 'response.output_audio_transcript.done' ||
          type === 'conversation.item.input_audio_transcription.completed'
        ) {
          setTranscriptLog((prev) => [
            ...prev.slice(-50),
            `${type}: ${JSON.stringify(event).slice(0, 200)}`,
          ])
        }
        console.log('realtime event', event)
  
        if (holder.current?.dc) {
          await handleToolCallEvent(
            holder.current.dc,
            sessionIdRef.current,
            event,
            (result) => {
              const payload = (result as { payload?: unknown })?.payload
              if (payload) {
                setPayloadText(JSON.stringify(payload, null, 2))
                setStatus('Updated via voice tool')
              }
            }
          )
        }
      })
  
      holder.current = handles
      voiceRef.current = handles
      setVoiceStatus('Listening — speak now')
    } catch (err) {
      setVoiceStatus(err instanceof Error ? err.message : 'Voice failed')
    }
  }

  function handleStopVoice() {
    voiceRef.current?.stop()
    voiceRef.current = null
    setVoiceStatus('Voice off')
  }
  
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
      <div style={{ marginTop: '0.75rem', display: 'flex', gap: '0.5rem' }}>
        <button type="button" onClick={handleStartVoice}>
          Start voice
        </button>
        <button type="button" onClick={handleStopVoice}>
          Stop voice
        </button>
      </div>
      <p>{voiceStatus}</p>
      <pre style={{ maxHeight: 160, overflow: 'auto', fontSize: 12 }}>
        {transcriptLog.join('\n') || 'Transcript events will appear here'}
      </pre>
      <p>
        {status}
        {version !== null ? ` (v${version})` : ''}
      </p>
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