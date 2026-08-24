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
import { AuthModal } from './components/auth'
import { LandingScreen } from './components/landing'
import { WorkspaceScreen } from './components/workspace'
import type { VoiceMood } from './components/voice'
import { EMPTY_PAYLOAD } from './constants/emptyPayload'
import {
  isBasicsVerified,
  isResumePayload,
  type ResumePayload,
} from './types/resume'
import { startRealtimeSession, type RealtimeHandles } from './voice/realtimeSession'
import { handleToolCallEvent } from './voice/handleRealtimeTools'
import './styles/app.css'

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
  const [voiceActive, setVoiceActive] = useState(false)
  const [voiceMood, setVoiceMood] = useState<VoiceMood>('idle')
  const [voiceCaption, setVoiceCaption] = useState('Ready when you are.')
  const [transcriptLog, setTranscriptLog] = useState<string[]>([])
  const [user, setUser] = useState<AuthUser | null>(null)
  const [authOpen, setAuthOpen] = useState(false)
  const [authTitle, setAuthTitle] = useState('Log in')
  const [resetToken, setResetToken] = useState('')
  const pdfInputRef = useRef<HTMLInputElement | null>(null)
  const sessionIdRef = useRef(sessionId)
  sessionIdRef.current = sessionId
  const contentLocked = !isBasicsVerified(payload) || basicsDirty
  const doneTimer = useRef<number | null>(null)

  function setVoice(mood: VoiceMood, caption?: string) {
    setVoiceMood(mood)
    if (caption) setVoiceCaption(caption)
    else if (mood === 'idle') setVoiceCaption('Ready when you are.')
    else if (mood === 'listening') setVoiceCaption("I'm listening.")
    else if (mood === 'understanding')
      setVoiceCaption("I'm piecing this together…")
    else if (mood === 'clarifying')
      setVoiceCaption('Tell me a little more about that.')
    else if (mood === 'done') setVoiceCaption("Nice. I've got it.")
  }

  useEffect(() => {
    if (!contentLocked || !voiceRef.current) return
    voiceRef.current.stop()
    voiceRef.current = null
    setVoiceActive(false)
    setVoice('idle')
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
      setVoice('clarifying', 'Confirm your details first, then we can talk.')
      return
    }
    try {
      setVoice('understanding', 'Connecting…')
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

        if (type === 'response.function_call_arguments.done') {
          setVoice('understanding')
        }

        if (holder.current?.dc) {
          await handleToolCallEvent(
            holder.current.dc,
            sessionIdRef.current,
            event,
            (result) => {
              const nextPayload = (result as { payload?: unknown })?.payload
              if (nextPayload) {
                applyPayload(nextPayload)
                setStatus('Got it — your resume updated')
                if (doneTimer.current) window.clearTimeout(doneTimer.current)
                setVoice('done')
                doneTimer.current = window.setTimeout(() => {
                  if (voiceRef.current) setVoice('listening')
                }, 1600)
                const intakeStatus = (
                  nextPayload as { intake?: { status?: string } }
                ).intake?.status
                if (intakeStatus === 'complete') {
                  setVoice(
                    'done',
                    'Nice. Intake is done — stop voice, then start again to edit.'
                  )
                }
              }
            }
          )
        }
      })

      holder.current = handles
      voiceRef.current = handles
      setVoiceActive(true)
      setVoice(
        'listening',
        handles.mode === 'intake'
          ? "I'm listening — tell me about your skills."
          : "I'm listening — what should we change?"
      )
    } catch (err) {
      setVoiceActive(false)
      setVoice(
        'clarifying',
        err instanceof Error ? err.message : 'Voice could not start'
      )
    }
  }

  async function handleVoiceIntake() {
    try {
      setStatus('Setting up your workspace…')
      const data = await startIntake()
      setSessionId(data.sessionId)
      sessionIdRef.current = data.sessionId
      applyPayload(data.payload)
      setVersion(data.version)
      setBasicsDirty(false)
      setScreen('workspace')
      setStatus('Confirm your personal details to start')
      setVoice('clarifying', 'Confirm your details first, then we can talk.')
    } catch (err) {
      setStatus(err instanceof Error ? err.message : 'Could not start')
    }
  }

  async function handlePdfSelected(file: File | undefined) {
    if (!file) return
    try {
      setStatus('Importing your PDF…')
      const data = await importResumePdf(file)
      setSessionId(data.sessionId)
      sessionIdRef.current = data.sessionId
      applyPayload(data.payload)
      setVersion(data.version)
      setBasicsDirty(false)
      setScreen('workspace')
      setStatus('Imported — confirm personal details to continue')
      setVoice('clarifying', 'Confirm your details, then we can keep going.')
    } catch (err) {
      setStatus(err instanceof Error ? err.message : 'PDF import failed')
    } finally {
      if (pdfInputRef.current) pdfInputRef.current.value = ''
    }
  }

  function handleStopVoice() {
    voiceRef.current?.stop()
    voiceRef.current = null
    setVoiceActive(false)
    setVoice('idle')
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
      const next = JSON.parse(payloadText)
      const data = await putResume(sessionId, next)
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
      setStatus(currentlyIncluded ? 'Hidden from resume' : 'Shown on resume')
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
      setVoice('done', 'Details confirmed. Ready when you are.')
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
        setStatus(`Welcome back, ${nextUser.email}`)
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
      openAuth('Keep this resume')
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
      setStatus('Saved to your account')
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

  const authModal = authOpen ? (
    <AuthModal
      title={authTitle}
      initialMode={authTitle.startsWith('Keep') ? 'signup' : 'login'}
      resetToken={resetToken}
      onClose={() => {
        setAuthOpen(false)
        setResetToken('')
      }}
      onAuthenticated={handleAuthenticated}
    />
  ) : null

  if (screen === 'landing') {
    return (
      <LandingScreen
        user={user}
        status={status}
        pdfInputRef={pdfInputRef}
        onLogout={handleLogout}
        onOpenAuth={() => openAuth('Welcome back')}
        onOpenSaved={handleOpenSavedResume}
        onVoiceStart={handleVoiceIntake}
        onPickPdf={() => pdfInputRef.current?.click()}
        onPdfSelected={handlePdfSelected}
        authModal={authModal}
      />
    )
  }

  return (
    <WorkspaceScreen
      user={user}
      payload={payload}
      status={status}
      sessionId={sessionId}
      payloadText={payloadText}
      version={version}
      busyAction={busyAction}
      contentLocked={contentLocked}
      voiceActive={voiceActive}
      voiceMood={voiceMood}
      voiceCaption={voiceCaption}
      transcriptLog={transcriptLog}
      onConfirmBasics={handleConfirmBasics}
      onBasicsDirtyChange={setBasicsDirty}
      onMoveSection={handleMoveSection}
      onMoveItem={handleMoveItem}
      onToggleItem={handleToggleItem}
      onStartVoice={() => handleStartVoice()}
      onStopVoice={handleStopVoice}
      onSaveToAccount={handleSaveToAccount}
      onLogout={handleLogout}
      onOpenAuth={() => openAuth('Welcome back')}
      onGoHome={() => {
        handleStopVoice()
        setScreen('landing')
      }}
      onSessionIdChange={setSessionId}
      onPayloadTextChange={setPayloadText}
      onLoad={handleLoad}
      onSaveJson={handleSave}
      authModal={authModal}
    />
  )
}

export default App
