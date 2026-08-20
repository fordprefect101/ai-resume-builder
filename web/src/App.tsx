import { useEffect, useRef, useState } from 'react'
import {
  claimResume,
  getMe,
  logout,
  verifyEmail,
  type AuthUser,
} from './api/authApi'
import {
  getResume,
  importResumePdf,
  putResume,
  reorderResumeItems,
  reorderResumeSections,
  setItemIncluded,
  updateResumeBasics,
  startIntake,
} from './api/resumeApi'
import { AuthModal } from './components/AuthModal'
import { ResumeEditor } from './components/ResumeEditor'
import { ResumePreview } from './components/ResumePreview'
import {
  isBasicsVerified,
  isResumePayload,
  type ResumePayload,
} from './types/resume'
import { startRealtimeSession, type RealtimeHandles } from './voice/realtimeSession'
import { handleToolCallEvent } from './voice/handleRealtimeTools'
import './App.css'

const EMPTY_PAYLOAD: ResumePayload = {
  schemaVersion: 3,
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
}

function App() {
  const [screen, setScreen] = useState<'landing' | 'workspace'>('landing')
  const [sessionId, setSessionId] = useState('demo')
  const [payloadText, setPayloadText] = useState(
    JSON.stringify(EMPTY_PAYLOAD, null, 2)
  )
  const [payload, setPayload] = useState<ResumePayload>(EMPTY_PAYLOAD)
  const [busyAction, setBusyAction] = useState('')
  const [basicsDirty, setBasicsDirty] = useState(false)
  const [version, setVersion] = useState<number | null>(null)
  const [status, setStatus] = useState('')
  const voiceRef = useRef<RealtimeHandles | null>(null)
  const [voiceStatus, setVoiceStatus] = useState('Voice off')
  const [transcriptLog, setTranscriptLog] = useState<string[]>([])
  const [user, setUser] = useState<AuthUser | null>(null)
  const [authOpen, setAuthOpen] = useState(false)
  const [authTitle, setAuthTitle] = useState('Log in')
  const [resetToken, setResetToken] = useState('')
  const pdfInputRef = useRef<HTMLInputElement | null>(null)
  const sessionIdRef = useRef(sessionId)
  sessionIdRef.current = sessionId
  const contentLocked = !isBasicsVerified(payload) || basicsDirty

  useEffect(() => {
    if (!contentLocked || !voiceRef.current) return
    voiceRef.current.stop()
    voiceRef.current = null
    setVoiceStatus('Voice off')
  }, [contentLocked])

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const verifyToken = params.get('verify')
    const reset = params.get('reset')

    async function boot() {
      if (verifyToken) {
        try {
          const result = await verifyEmail(verifyToken)
          if (result.user) setUser(result.user)
          setStatus('Email verified')
          const pending = localStorage.getItem('pendingClaimSessionId')
          if (pending && pending !== 'demo') {
            try {
              const claimed = await claimResume(pending)
              localStorage.removeItem('pendingClaimSessionId')
              if (claimed.sessionId && claimed.payload) {
                setSessionId(claimed.sessionId)
                sessionIdRef.current = claimed.sessionId
                applyPayload(claimed.payload)
                setVersion(claimed.version ?? null)
                setScreen('workspace')
                setStatus('Resume saved to your account')
              }
            } catch (err) {
              setStatus(
                err instanceof Error ? err.message : 'Could not save to this account'
              )
            }
          }
        } catch (err) {
          setStatus(err instanceof Error ? err.message : 'Could not verify email')
          setAuthOpen(true)
        }
        window.history.replaceState({}, '', window.location.pathname)
      }
      if (reset) {
        setResetToken(reset)
        setAuthTitle('Reset password')
        setAuthOpen(true)
        window.history.replaceState({}, '', window.location.pathname)
      }
      try {
        const me = await getMe()
        if (me) setUser(me)
      } catch {
        /* stay logged out */
      }
    }

    void boot()
  }, [])

  function applyPayload(nextPayload: unknown) {
    if (!isResumePayload(nextPayload)) {
      throw new Error('Server returned an invalid resume payload')
    }
    setPayload(nextPayload)
    setPayloadText(JSON.stringify(nextPayload, null, 2))
  }
  
  async function handleStartVoice(
    targetSessionId = sessionIdRef.current,
    options?: { skipGate?: boolean }
  ) {
    if (!options?.skipGate && contentLocked) {
      setStatus('Confirm your personal details before starting voice')
      return
    }
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
      setBasicsDirty(false)
      setScreen('workspace')
      setStatus('Confirm your personal details to start voice intake')
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
      setBasicsDirty(false)
      setScreen('workspace')
      setStatus('PDF imported — confirm personal details to continue')
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

  async function handleMoveItem(
    section: string,
    itemId: string,
    direction: -1 | 1
  ) {
    const items = payload.inventory.sections[section]?.items ?? []
    const current = items.map((item) => item.id)
    const index = current.indexOf(itemId)
    const target = index + direction
    if (index < 0 || target < 0 || target >= current.length) return

    const nextOrder = [...current]
    const moved = nextOrder[index]
    nextOrder[index] = nextOrder[target]
    nextOrder[target] = moved

    try {
      setBusyAction(`item-order:${section}:${itemId}`)
      const data = await reorderResumeItems(
        sessionIdRef.current,
        section,
        nextOrder
      )
      applyPayload(data.payload)
      setVersion(data.version)
      setStatus('Item order updated')
    } catch (err) {
      setStatus(err instanceof Error ? err.message : 'Could not reorder items')
    } finally {
      setBusyAction('')
    }
  }

  async function handleConfirmBasics(basics: {
    fullName: string
    email: string
    phone: string
    location: string
    github: string
    linkedin: string
  }) {
    try {
      setBusyAction('basics')
      const data = await updateResumeBasics(sessionIdRef.current, basics)
      applyPayload(data.payload)
      setVersion(data.version)
      setBasicsDirty(false)
      const intakeStatus = (
        data.payload as { intake?: { status?: string } }
      ).intake?.status
      setStatus('Personal details confirmed')
      if (intakeStatus === 'in_progress') {
        await handleStartVoice(sessionIdRef.current, { skipGate: true })
      }
    } catch (err) {
      setStatus(
        err instanceof Error ? err.message : 'Could not save personal details'
      )
    } finally {
      setBusyAction('')
    }
  }

  function openAuth(title: string) {
    setAuthTitle(title)
    setAuthOpen(true)
  }

  async function handleAuthenticated(nextUser: AuthUser) {
    setUser(nextUser)
    setAuthOpen(false)
    const pending = localStorage.getItem('pendingClaimSessionId')
    if (pending && pending !== 'demo') {
      try {
        const claimed = await claimResume(pending)
        localStorage.removeItem('pendingClaimSessionId')
        if (claimed.sessionId && claimed.payload) {
          setSessionId(claimed.sessionId)
          sessionIdRef.current = claimed.sessionId
          applyPayload(claimed.payload)
          setVersion(claimed.version ?? null)
          setScreen('workspace')
          setStatus('Resume saved to your account')
          setUser({ ...nextUser, resumeSessionId: claimed.sessionId })
        }
      } catch (err) {
        setStatus(err instanceof Error ? err.message : 'Could not save to this account')
      }
      return
    }
    if (nextUser.resumeSessionId) {
      try {
        const data = await getResume(nextUser.resumeSessionId)
        setSessionId(data.sessionId)
        sessionIdRef.current = data.sessionId
        applyPayload(data.payload)
        setVersion(data.version)
        setScreen('workspace')
        setStatus(`Signed in as ${nextUser.email}`)
      } catch (err) {
        setStatus(err instanceof Error ? err.message : 'Could not open your resume')
      }
    }
  }

  async function handleSaveToAccount() {
    const currentId = sessionIdRef.current
    if (!currentId || currentId === 'demo') {
      setStatus('Start a resume before saving')
      return
    }
    if (!user) {
      localStorage.setItem('pendingClaimSessionId', currentId)
      openAuth('Save this resume')
      return
    }
    try {
      const claimed = await claimResume(currentId)
      if (claimed.sessionId && claimed.payload) {
        setSessionId(claimed.sessionId)
        sessionIdRef.current = claimed.sessionId
        applyPayload(claimed.payload)
        setVersion(claimed.version ?? null)
      }
      setUser({ ...user, resumeSessionId: claimed.sessionId ?? currentId })
      setStatus('Resume saved to your account')
    } catch (err) {
      setStatus(err instanceof Error ? err.message : 'Could not save to this account')
    }
  }

  async function handleLogout() {
    handleStopVoice()
    await logout().catch(() => undefined)
    localStorage.removeItem('pendingClaimSessionId')
    setUser(null)
    setSessionId('demo')
    sessionIdRef.current = 'demo'
    setPayload(EMPTY_PAYLOAD)
    setPayloadText(JSON.stringify(EMPTY_PAYLOAD, null, 2))
    setVersion(null)
    setScreen('landing')
    setStatus('Signed out. Guest work is not kept.')
  }

  async function handleOpenSavedResume() {
    if (!user?.resumeSessionId) return
    try {
      const data = await getResume(user.resumeSessionId)
      setSessionId(data.sessionId)
      sessionIdRef.current = data.sessionId
      applyPayload(data.payload)
      setVersion(data.version)
      setScreen('workspace')
      setStatus(`Opened resume for ${user.email}`)
    } catch (err) {
      setStatus(err instanceof Error ? err.message : 'Could not open your resume')
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
            conversation. Save to an account when you want to keep it.
          </p>
          {user && (
            <p className="landing-status">
              Signed in as {user.email}
              {user.resumeSessionId ? ' — you have a saved resume.' : ''}
            </p>
          )}
          <div className="intake-actions">
            {user?.resumeSessionId && (
              <button
                className="intake-option primary"
                type="button"
                onClick={handleOpenSavedResume}
              >
                <strong>Open your resume</strong>
                <span>Continue the resume saved to this account</span>
              </button>
            )}
            <button
              className="intake-option primary"
              type="button"
              onClick={handleVoiceIntake}
            >
              <strong>Start from voice</strong>
              <span>Confirm your details, then answer one question at a time</span>
            </button>
            <button
              className="intake-option"
              type="button"
              onClick={() => pdfInputRef.current?.click()}
            >
              <strong>I have a PDF</strong>
              <span>Import it, confirm your details, then continue</span>
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
          <div className="landing-auth">
            {user ? (
              <button type="button" onClick={handleLogout}>
                Log out
              </button>
            ) : (
              <button type="button" onClick={() => openAuth('Log in')}>
                Log in
              </button>
            )}
          </div>
          {status && <p className="landing-status">{status}</p>}
        </section>
        {authOpen && (
          <AuthModal
            title={authTitle}
            initialMode={authTitle.startsWith('Save') ? 'signup' : 'login'}
            resetToken={resetToken}
            onClose={() => {
              setAuthOpen(false)
              setResetToken('')
            }}
            onAuthenticated={handleAuthenticated}
          />
        )}
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
              disabled={contentLocked}
              onClick={() => handleStartVoice()}
            >
              Start voice
            </button>
          )}
          <button type="button" onClick={handleSaveToAccount}>
            Save
          </button>
          {user ? (
            <button type="button" onClick={handleLogout}>
              Log out
            </button>
          ) : (
            <button type="button" onClick={() => openAuth('Log in')}>
              Log in
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
          contentLocked={contentLocked}
          onConfirmBasics={handleConfirmBasics}
          onBasicsDirtyChange={setBasicsDirty}
          onMoveSection={handleMoveSection}
          onMoveItem={handleMoveItem}
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
      {authOpen && (
        <AuthModal
          title={authTitle}
          initialMode={authTitle.startsWith('Save') ? 'signup' : 'login'}
          resetToken={resetToken}
          onClose={() => {
            setAuthOpen(false)
            setResetToken('')
          }}
          onAuthenticated={handleAuthenticated}
        />
      )}
    </main>
  )
}

export default App