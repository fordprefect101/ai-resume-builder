import { useRef, useState } from 'react'
import {
  getResume,
  importResumePdf,
  putResume,
  reorderResumeSections,
  setItemIncluded,
  startIntake,
} from './api/resumeApi'
import { ResumeEditor } from './components/ResumeEditor'
import { ResumePreview } from './components/ResumePreview'
import {
  isResumePayload,
  type ResumePayload,
} from './types/resume'
import { startRealtimeSession, type RealtimeHandles } from './voice/realtimeSession'
import { handleToolCallEvent } from './voice/handleRealtimeTools'
import './App.css'

const EMPTY_PAYLOAD: ResumePayload = {
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
  const [payload, setPayload] = useState<ResumePayload>(EMPTY_PAYLOAD)
  const [busyAction, setBusyAction] = useState('')
  const [version, setVersion] = useState<number | null>(null)
  const [status, setStatus] = useState('')
  const voiceRef = useRef<RealtimeHandles | null>(null)
  const [voiceStatus, setVoiceStatus] = useState('Voice off')
  const [transcriptLog, setTranscriptLog] = useState<string[]>([])
  const pdfInputRef = useRef<HTMLInputElement | null>(null)
  const sessionIdRef = useRef(sessionId)
  sessionIdRef.current = sessionId

  function applyPayload(nextPayload: unknown) {
    if (!isResumePayload(nextPayload)) {
      throw new Error('Server returned an invalid resume payload')
    }
    setPayload(nextPayload)
    setPayloadText(JSON.stringify(nextPayload, null, 2))
  }
  
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
                applyPayload(payload)
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
      applyPayload(data.payload)
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
      applyPayload(data.payload)
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
      applyPayload(data.payload)
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
      applyPayload(data.payload)
      setVersion(data.version)
      setStatus(`Saved version ${data.version}`)
    } catch (err) {
      setStatus(err instanceof Error ? err.message : 'Save failed')
    }
  }

  async function handleToggleItem(
    section: string,
    itemId: string,
    currentlyIncluded: boolean
  ) {
    const actionKey = `${section}:${itemId}`
    try {
      setBusyAction(actionKey)
      const data = await setItemIncluded(
        sessionIdRef.current,
        section,
        itemId,
        !currentlyIncluded
      )
      applyPayload(data.payload)
      setVersion(data.version)
      setStatus(currentlyIncluded ? 'Item hidden from resume' : 'Item shown on resume')
    } catch (err) {
      setStatus(err instanceof Error ? err.message : 'Could not update item')
    } finally {
      setBusyAction('')
    }
  }

  async function handleMoveSection(section: string, direction: -1 | 1) {
    const current = payload.resume.sectionOrder
    const index = current.indexOf(section)
    const target = index + direction
    if (index < 0 || target < 0 || target >= current.length) return

    const nextOrder = [...current]
    const moved = nextOrder[index]
    nextOrder[index] = nextOrder[target]
    nextOrder[target] = moved

    try {
      setBusyAction(`order:${section}`)
      const data = await reorderResumeSections(
        sessionIdRef.current,
        nextOrder
      )
      applyPayload(data.payload)
      setVersion(data.version)
      setStatus('Section order updated')
    } catch (err) {
      setStatus(err instanceof Error ? err.message : 'Could not reorder sections')
    } finally {
      setBusyAction('')
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
    <main className="builder-workspace">
      <header className="builder-toolbar">
        <div>
          <p className="eyebrow">Resume builder</p>
          <h1>{payload.resume.title || 'General Resume'}</h1>
        </div>
        <div className="toolbar-actions">
          <span className="voice-status">{voiceStatus}</span>
          {voiceRef.current ? (
            <button type="button" onClick={handleStopVoice}>
              Stop voice
            </button>
          ) : (
            <button
              className="primary-action"
              type="button"
              onClick={() => handleStartVoice()}
            >
              Start voice
            </button>
          )}
          <button
            type="button"
            onClick={() => {
              handleStopVoice()
              setScreen('landing')
            }}
          >
            Exit
          </button>
        </div>
      </header>

      <div className="builder-status" role="status">
        <span>{status || 'All changes are synchronized'}</span>
        {version !== null && <span>Version {version}</span>}
      </div>

      <div className="builder-split">
        <ResumeEditor
          payload={payload}
          busyAction={busyAction}
          onMoveSection={handleMoveSection}
          onToggleItem={handleToggleItem}
          onStartVoice={() => handleStartVoice()}
        />
        <section className="preview-pane">
          <div className="preview-pane-heading">
            <div>
              <p className="eyebrow">Live preview</p>
              <h2>Resume document</h2>
            </div>
            <span>Updates automatically</span>
          </div>
          <div className="paper-stage">
            <ResumePreview payload={payload} />
          </div>
        </section>
      </div>

      <details className="developer-tools">
        <summary>Developer tools</summary>
        <div className="developer-toolbar">
          <label>
            Session ID
            <input
              value={sessionId}
              onChange={(event) => setSessionId(event.target.value)}
            />
          </label>
          <button type="button" onClick={handleLoad}>
            Load
          </button>
          <button type="button" onClick={handleSave}>
            Save JSON
          </button>
        </div>
        <details>
          <summary>Realtime event log</summary>
          <pre>
            {transcriptLog.join('\n') || 'Transcript events will appear here'}
          </pre>
        </details>
        <textarea
          value={payloadText}
          onChange={(event) => setPayloadText(event.target.value)}
          rows={20}
        />
      </details>
    </main>
  )
}

export default App