import { useRef, useState } from 'react'
import {
  getResume,
  importResumePdf,
  putResume,
  startIntake,
} from './api/resumeApi'
import { startRealtimeSession, type RealtimeHandles } from './voice/realtimeSession'
import { handleToolCallEvent } from './voice/handleRealtimeTools'
import './App.css'

const EMPTY_PAYLOAD = {
  schemaVersion: 3,
  intake: { status: 'not_started' },
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
}

function App() {
  const [screen, setScreen] = useState<'landing' | 'workspace'>('landing')
  const [sessionId, setSessionId] = useState('demo')
  const [payloadText, setPayloadText] = useState(
    JSON.stringify(EMPTY_PAYLOAD, null, 2)
  )
  const [version, setVersion] = useState<number | null>(null)
  const [status, setStatus] = useState('')
  const voiceRef = useRef<RealtimeHandles | null>(null)
  const [voiceStatus, setVoiceStatus] = useState('Voice off')
  const [transcriptLog, setTranscriptLog] = useState<string[]>([])
  const pdfInputRef = useRef<HTMLInputElement | null>(null)
  const sessionIdRef = useRef(sessionId)
  sessionIdRef.current = sessionId
  
  async function handleStartVoice(targetSessionId = sessionIdRef.current) {
    try {
      setVoiceStatus('Connecting…')
      sessionIdRef.current = targetSessionId
      const holder: { current: RealtimeHandles | null } = { current: null }
  
      const handles = await startRealtimeSession(targetSessionId, async (event) => {
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
                const intakeStatus = (
                  payload as { intake?: { status?: string } }
                ).intake?.status
                if (intakeStatus === 'complete') {
                  setVoiceStatus(
                    'Intake complete — reconnect voice to continue in edit mode'
                  )
                }
              }
            }
          )
        }
      })
  
      holder.current = handles
      voiceRef.current = handles
      setVoiceStatus(
        handles.mode === 'intake'
          ? 'Intake listening — speak now'
          : 'Edit listening — speak now'
      )
    } catch (err) {
      setVoiceStatus(err instanceof Error ? err.message : 'Voice failed')
    }
  }

  async function handleVoiceIntake() {
    try {
      setStatus('Creating intake session…')
      const data = await startIntake()
      setSessionId(data.sessionId)
      sessionIdRef.current = data.sessionId
      setPayloadText(JSON.stringify(data.payload, null, 2))
      setVersion(data.version)
      setScreen('workspace')
      setStatus('Intake session created')
      await handleStartVoice(data.sessionId)
    } catch (err) {
      setStatus(err instanceof Error ? err.message : 'Could not start intake')
    }
  }

  async function handlePdfSelected(file: File | undefined) {
    if (!file) return
    try {
      setStatus('Importing PDF…')
      const data = await importResumePdf(file)
      setSessionId(data.sessionId)
      sessionIdRef.current = data.sessionId
      setPayloadText(JSON.stringify(data.payload, null, 2))
      setVersion(data.version)
      setScreen('workspace')
      setStatus('PDF imported — ready to edit')
    } catch (err) {
      setStatus(err instanceof Error ? err.message : 'PDF import failed')
    } finally {
      if (pdfInputRef.current) pdfInputRef.current.value = ''
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
  if (screen === 'landing') {
    return (
      <main className="intake-landing">
        <section className="intake-card">
          <p className="eyebrow">Conversational resume builder</p>
          <h1>How would you like to begin?</h1>
          <p className="intro">
            Bring an existing resume, or build one through a guided voice
            conversation.
          </p>
          <div className="intake-actions">
            <button
              className="intake-option primary"
              type="button"
              onClick={handleVoiceIntake}
            >
              <strong>Start from voice</strong>
              <span>Answer one question at a time</span>
            </button>
            <button
              className="intake-option"
              type="button"
              onClick={() => pdfInputRef.current?.click()}
            >
              <strong>I have a PDF</strong>
              <span>Import it and continue in edit mode</span>
            </button>
            <input
              ref={pdfInputRef}
              hidden
              type="file"
              accept="application/pdf,.pdf"
              onChange={(event) =>
                handlePdfSelected(event.target.files?.[0])
              }
            />
          </div>
          {status && <p className="landing-status">{status}</p>}
        </section>
      </main>
    )
  }

  return (
    <main style={{ maxWidth: 720, margin: '2rem auto', fontFamily: 'system-ui' }}>
      <div className="workspace-heading">
        <h1>Resume Builder</h1>
        <button type="button" onClick={() => setScreen('landing')}>
          Back to start
        </button>
      </div>
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
        <button type="button" onClick={() => handleStartVoice()}>
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