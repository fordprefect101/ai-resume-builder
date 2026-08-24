import type { ReactNode } from 'react'
import type { AuthUser } from '../../api/authApi'
import { VoiceOrb } from '../voice'

type Props = {
  user: AuthUser | null
  status: string
  onLogout: () => void
  onOpenAuth: () => void
  onOpenSaved: () => void
  onVoiceStart: () => void
  authModal: ReactNode
}

export function LandingScreen({
  user,
  status,
  onLogout,
  onOpenAuth,
  onOpenSaved,
  onVoiceStart,
  authModal,
}: Props) {
  const hasSaved = Boolean(user?.resumeSessionId)

  return (
    <main className="intake-landing">
      <header className="landing-topbar">
        <div className="brand-mark">Resume companion</div>
        <div className="landing-account">
          {user ? (
            <>
              <span className="account-chip">{user.email}</span>
              <button className="ghost-action" type="button" onClick={onLogout}>
                Log out
              </button>
            </>
          ) : (
            <button type="button" onClick={onOpenAuth}>
              Log in
            </button>
          )}
        </div>
      </header>

      <div className="landing-shell">
        <section className="intake-card">
          <div className="landing-hero">
            <p className="eyebrow">For your next chapter</p>
            <h1>Let’s build your resume.</h1>
            <p className="intro">
              Tell me about yourself. I’ll help turn what you know into
              something you can show.
            </p>
            <div className="landing-orb">
              <VoiceOrb mood="idle" size="sm" />
            </div>
          </div>

          <div className={hasSaved ? 'intake-actions with-saved' : 'intake-actions'}>
            {hasSaved ? (
              <>
                <button
                  className="intake-option primary"
                  type="button"
                  onClick={onOpenSaved}
                >
                  <strong>Open your resume</strong>
                  <span>Continue the one saved to this account</span>
                </button>
                <button
                  className="intake-option"
                  type="button"
                  onClick={onVoiceStart}
                >
                  <strong>Start with your voice</strong>
                  <span>Opens your saved resume to keep building</span>
                </button>
              </>
            ) : (
              <button
                className="intake-option primary"
                type="button"
                onClick={onVoiceStart}
              >
                <strong>Start with your voice</strong>
                <span>Answer one question at a time</span>
              </button>
            )}
          </div>

          <p className="landing-hint">
            Guest work stays in this visit. Save when you want to keep it.
          </p>
          {status && (
            <p
              className={
                status.toLowerCase().includes('saved') ||
                status.toLowerCase().includes('verified')
                  ? 'landing-status ok'
                  : 'landing-status'
              }
            >
              {status}
            </p>
          )}
        </section>
      </div>
      {authModal}
    </main>
  )
}
