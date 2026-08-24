import type { ReactNode } from 'react'
import type { AuthUser } from '../../api/authApi'
import type { ResumePayload } from '../../types/resume'
import { ResumeEditor, ResumePreview } from '../resume'
import { VoiceOrb, type VoiceMood } from '../voice'

type Props = {
  user: AuthUser | null
  payload: ResumePayload
  status: string
  sessionId: string
  payloadText: string
  version: number | null
  busyAction: string
  contentLocked: boolean
  voiceActive: boolean
  voiceMood: VoiceMood
  voiceCaption: string
  transcriptLog: string[]
  onConfirmBasics: (basics: {
    fullName: string
    email: string
    phone: string
    location: string
    github: string
    linkedin: string
  }) => void
  onBasicsDirtyChange: (dirty: boolean) => void
  onMoveSection: (section: string, direction: -1 | 1) => void
  onMoveItem: (section: string, itemId: string, direction: -1 | 1) => void
  onToggleItem: (section: string, itemId: string, included: boolean) => void
  onStartVoice: () => void
  onStopVoice: () => void
  onSaveToAccount: () => void
  onLogout: () => void
  onOpenAuth: () => void
  onGoHome: () => void
  onSessionIdChange: (value: string) => void
  onPayloadTextChange: (value: string) => void
  onLoad: () => void
  onSaveJson: () => void
  authModal: ReactNode
}

export function WorkspaceScreen({
  user,
  payload,
  status,
  sessionId,
  payloadText,
  version,
  busyAction,
  contentLocked,
  voiceActive,
  voiceMood,
  voiceCaption,
  transcriptLog,
  onConfirmBasics,
  onBasicsDirtyChange,
  onMoveSection,
  onMoveItem,
  onToggleItem,
  onStartVoice,
  onStopVoice,
  onSaveToAccount,
  onLogout,
  onOpenAuth,
  onGoHome,
  onSessionIdChange,
  onPayloadTextChange,
  onLoad,
  onSaveJson,
  authModal,
}: Props) {
  return (
    <main className="builder-workspace">
      <header className="builder-toolbar">
        <div className="toolbar-title">
          <p className="eyebrow">Your resume</p>
          <h1>{payload.resume.title || 'General Resume'}</h1>
        </div>
        <div className="toolbar-actions">
          <div className="toolbar-voice">
            <VoiceOrb mood={voiceMood} caption={voiceCaption} size="sm" />
            {voiceActive ? (
              <button type="button" onClick={onStopVoice}>
                Stop voice
              </button>
            ) : (
              <button
                className="primary-action"
                type="button"
                disabled={contentLocked}
                onClick={onStartVoice}
              >
                Start voice
              </button>
            )}
          </div>
          <button type="button" onClick={onSaveToAccount}>
            {user ? 'Save' : 'Keep this'}
          </button>
          {user ? (
            <>
              <span className="account-chip toolbar">{user.email}</span>
              <button className="ghost-action" type="button" onClick={onLogout}>
                Log out
              </button>
            </>
          ) : (
            <button type="button" onClick={onOpenAuth}>
              Log in
            </button>
          )}
          <button className="ghost-action" type="button" onClick={onGoHome}>
            Home
          </button>
        </div>
      </header>

      <div className="builder-status" role="status">
        <span>{status || 'Your changes stay with this resume as you go.'}</span>
      </div>

      <div className="builder-split">
        <ResumeEditor
          payload={payload}
          busyAction={busyAction}
          contentLocked={contentLocked}
          onConfirmBasics={onConfirmBasics}
          onBasicsDirtyChange={onBasicsDirtyChange}
          onMoveSection={onMoveSection}
          onMoveItem={onMoveItem}
          onToggleItem={onToggleItem}
          onStartVoice={onStartVoice}
        />
        <section className="preview-pane">
          <div className="preview-pane-heading">
            <div>
              <p className="eyebrow">Live preview</p>
              <h2>Your document</h2>
            </div>
            <span>Updates as you talk</span>
          </div>
          <div className="paper-stage">
            <ResumePreview payload={payload} />
          </div>
        </section>
      </div>

      <details className="developer-tools">
        <summary>
          Developer tools{version !== null ? ` · v${version}` : ''}
        </summary>
        <div className="developer-toolbar">
          <label>
            Session ID
            <input
              value={sessionId}
              onChange={(event) => onSessionIdChange(event.target.value)}
            />
          </label>
          <button type="button" onClick={onLoad}>
            Load
          </button>
          <button type="button" onClick={onSaveJson}>
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
          onChange={(event) => onPayloadTextChange(event.target.value)}
          rows={20}
        />
      </details>
      {authModal}
    </main>
  )
}
