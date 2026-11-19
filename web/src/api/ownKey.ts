// Bring your own key: the person's OpenAI key lives only in this tab (sessionStorage) and is
// sent in a header with each request to our API. The server uses it for that request only.
import { API_BASE } from './resumeApi'

const STORE = 'ownOpenAIKey'
export const NEED_KEY_EVENT = 'own-key-needed'
export const KEY_CHANGED_EVENT = 'own-key-changed'

export function getOwnKey(): string | null {
  try {
    return sessionStorage.getItem(STORE)
  } catch {
    return null
  }
}

export function setOwnKey(key: string | null): void {
  try {
    if (key) sessionStorage.setItem(STORE, key)
    else sessionStorage.removeItem(STORE)
  } catch {
    /* private mode: the key just won't be remembered */
  }
  window.dispatchEvent(new Event(KEY_CHANGED_EVENT))
}

let installed = false

// Wraps fetch once: adds the key to calls to our API only, and tells the page when the daily
// limit says the person can add a key.
export function installOwnKeyFetch(): void {
  if (installed) return
  installed = true
  const original = window.fetch.bind(window)
  window.fetch = async (input, init) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url
    if (!url.startsWith(API_BASE)) return original(input, init)
    const key = getOwnKey()
    let nextInit = init
    if (key) {
      const headers = new Headers(init?.headers ?? (input instanceof Request ? input.headers : undefined))
      headers.set('X-OpenAI-Key', key)
      nextInit = { ...init, headers }
    }
    const res = await original(input, nextInit)
    if (res.status === 429) {
      try {
        const body = (await res.clone().json()) as { detail?: unknown }
        if (typeof body.detail === 'string' && body.detail.includes('your own OpenAI key')) {
          window.dispatchEvent(new Event(NEED_KEY_EVENT))
        }
      } catch {
        /* not our limit message */
      }
    }
    return res
  }
}
