import { API_BASE } from './resumeApi'

export type AuthUser = {
  email: string
  emailVerified: boolean
  resumeSessionId: string | null
}

export type AuthPayload = {
  ok?: boolean
  message?: string
  detail?: string
  devVerifyUrl?: string
  devResetUrl?: string
  user?: AuthUser
  sessionId?: string
  payload?: unknown
  version?: number
}

async function parseAuth(res: Response, fallback: string): Promise<AuthPayload> {
  const body = (await res.json().catch(() => ({}))) as AuthPayload
  if (!res.ok) {
    const message =
      typeof body.detail === 'string' && body.detail.trim()
        ? body.detail
        : fallback
    const error = new Error(message) as Error & AuthPayload
    error.devVerifyUrl = body.devVerifyUrl
    error.devResetUrl = body.devResetUrl
    throw error
  }
  return body
}

function post(path: string, body: unknown) {
  return fetch(`${API_BASE}${path}`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export async function getMe(): Promise<AuthUser | null> {
  const res = await fetch(`${API_BASE}/auth/me`, { credentials: 'include' })
  const body = (await parseAuth(res, 'Could not load account')) as {
    user?: AuthUser | null
  }
  return body.user ?? null
}

export async function signup(email: string, password: string) {
  return parseAuth(await post('/auth/signup', { email, password }), 'Signup failed')
}

export async function login(email: string, password: string) {
  return parseAuth(await post('/auth/login', { email, password }), 'Login failed')
}

export async function logout() {
  return parseAuth(await post('/auth/logout', {}), 'Logout failed')
}

export async function verifyEmail(token: string) {
  return parseAuth(await post('/auth/verify', { token }), 'Verify failed')
}

export async function forgotPassword(email: string) {
  return parseAuth(await post('/auth/forgot', { email }), 'Reset request failed')
}

export async function resetPassword(token: string, password: string) {
  return parseAuth(
    await post('/auth/reset', { token, password }),
    'Reset failed'
  )
}

export async function resendVerify(email: string) {
  return parseAuth(
    await post('/auth/resend-verify', { email }),
    'Could not resend verification'
  )
}

export async function claimResume(sessionId: string): Promise<AuthPayload> {
  return parseAuth(
    await post('/auth/claim', { sessionId }),
    'Could not save resume to this account'
  )
}
