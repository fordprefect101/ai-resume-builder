import { useEffect, useRef, useState, type FormEvent } from 'react'
import {
  forgotPassword,
  login,
  resendVerify,
  resetPassword,
  signup,
  type AuthPayload,
  type AuthUser,
} from '../../api/authApi'

type Mode = 'login' | 'signup' | 'forgot' | 'reset' | 'check-email'

type Props = {
  title: string
  initialMode?: Mode
  resetToken?: string
  onClose: () => void
  onAuthenticated: (user: AuthUser) => void
}

export function AuthModal({
  title,
  initialMode = 'login',
  resetToken,
  onClose,
  onAuthenticated,
}: Props) {
  const [mode, setMode] = useState<Mode>(resetToken ? 'reset' : initialMode)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [status, setStatus] = useState('')
  const [devLink, setDevLink] = useState('')
  const [busy, setBusy] = useState(false)
  const panelRef = useRef<HTMLElement>(null)

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    panelRef.current?.querySelector<HTMLInputElement>('input')?.focus()
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  function captureDev(result: AuthPayload | (Error & AuthPayload)) {
    const url = result.devVerifyUrl || result.devResetUrl
    if (url) setDevLink(url)
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setStatus('')
    try {
      if (mode === 'signup') {
        const result = await signup(email, password)
        captureDev(result)
        setMode('check-email')
        setStatus(
          result.message ||
            'Open the verification link to finish. Until email is wired, use the link below.'
        )
        return
      }
      if (mode === 'login') {
        const result = await login(email, password)
        if (result.user) onAuthenticated(result.user)
        return
      }
      if (mode === 'forgot') {
        const result = await forgotPassword(email)
        captureDev(result)
        setStatus(
          result.message ||
            'If that email exists, a reset link is ready below.'
        )
        return
      }
      if (mode === 'reset' && resetToken) {
        await resetPassword(resetToken, password)
        setMode('login')
        setStatus('Password updated. Log in with your new password.')
        return
      }
      if (mode === 'check-email') {
        const result = await resendVerify(email)
        captureDev(result)
        setStatus(result.message || 'A new verification link is ready below.')
      }
    } catch (err) {
      const error = err as Error & AuthPayload
      captureDev(error)
      setStatus(error.message)
    } finally {
      setBusy(false)
    }
  }

  const copy =
    mode === 'signup'
      ? 'Create an account so you can keep this resume and come back later.'
      : mode === 'forgot'
        ? 'We’ll make a reset link. Until email is wired, it shows up below.'
        : mode === 'reset'
          ? 'Choose a new password, then log in.'
          : mode === 'check-email'
            ? 'Open the verification link to finish. Email delivery isn’t wired yet.'
            : title.startsWith('Keep')
              ? 'Log in or sign up to save this resume to your account.'
              : 'Log in with the email and password for this account.'

  return (
    <div
      className="auth-overlay"
      role="dialog"
      aria-modal="true"
      aria-label={title}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <section className="auth-card" ref={panelRef}>
        <header className="auth-heading">
          <h2>{title}</h2>
          <button type="button" onClick={onClose} aria-label="Close">
            ×
          </button>
        </header>
        <p className="auth-copy">{copy}</p>
        <form className="auth-form" onSubmit={handleSubmit}>
          {mode !== 'reset' && (
            <label>
              Email
              <input
                type="email"
                value={email}
                autoComplete="email"
                required
                onChange={(event) => setEmail(event.target.value)}
              />
            </label>
          )}
          {(mode === 'login' || mode === 'signup' || mode === 'reset') && (
            <label>
              Password
              <input
                type="password"
                value={password}
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                minLength={8}
                required
                onChange={(event) => setPassword(event.target.value)}
              />
            </label>
          )}
          <button className="primary-action" type="submit" disabled={busy}>
            {busy
              ? 'Working…'
              : mode === 'signup'
                ? 'Create account'
                : mode === 'forgot'
                  ? 'Send reset link'
                  : mode === 'reset'
                    ? 'Update password'
                    : mode === 'check-email'
                      ? 'Resend verification link'
                      : 'Log in'}
          </button>
        </form>
        {status && <p className="auth-status">{status}</p>}
        {devLink && (
          <p className="auth-dev-link">
            <a href={devLink}>Open verification / reset link</a>
          </p>
        )}
        {mode !== 'check-email' && (
          <nav className="auth-switch">
            {mode !== 'login' && (
              <button type="button" onClick={() => setMode('login')}>
                Log in
              </button>
            )}
            {mode !== 'signup' && (
              <button type="button" onClick={() => setMode('signup')}>
                Sign up
              </button>
            )}
            {mode === 'login' && (
              <button type="button" onClick={() => setMode('forgot')}>
                Forgot password
              </button>
            )}
          </nav>
        )}
        {mode === 'check-email' && (
          <nav className="auth-switch">
            <button type="button" onClick={() => setMode('login')}>
              Already verified? Log in
            </button>
          </nav>
        )}
      </section>
    </div>
  )
}
