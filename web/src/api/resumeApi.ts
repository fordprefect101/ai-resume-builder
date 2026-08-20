const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8081';

export { API_BASE }

const creds: RequestInit = { credentials: 'include' }

export type ResumeResponse = {
  sessionId: string;
  payload: unknown;
  version: number;
  mode?: 'intake' | 'edit';
};

export async function apiErrorMessage(
  res: Response,
  fallback: string
): Promise<string> {
  try {
    const body = (await res.json()) as { detail?: unknown }
    const detail = body?.detail
    if (typeof detail === 'string' && detail.trim()) return detail
    if (Array.isArray(detail)) {
      const messages = detail
        .map((item) => {
          if (typeof item === 'string') return item
          if (item && typeof item === 'object' && 'msg' in item) {
            return String((item as { msg?: unknown }).msg ?? '')
          }
          return ''
        })
        .filter(Boolean)
      if (messages.length) return messages.join('; ')
    }
  } catch {
    /* keep fallback */
  }
  return fallback
}

async function parseOk(res: Response, fallback: string): Promise<ResumeResponse> {
  if (!res.ok) {
    throw new Error(await apiErrorMessage(res, fallback))
  }
  return res.json()
}

export async function getResume(sessionId: string): Promise<ResumeResponse> {
  const res = await fetch(`${API_BASE}/resume/${encodeURIComponent(sessionId)}`, creds);
  return parseOk(res, `GET failed: ${res.status}`);
}

export async function putResume(
  sessionId: string,
  payload: unknown
): Promise<ResumeResponse> {
  const res = await fetch(`${API_BASE}/resume/${encodeURIComponent(sessionId)}`, {
    ...creds,
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ payload }),
  });
  return parseOk(res, `PUT failed: ${res.status}`);
}

export async function startIntake(): Promise<ResumeResponse> {
  const res = await fetch(`${API_BASE}/intake/start`, {
    ...creds,
    method: 'POST',
  });
  return parseOk(res, `Start intake failed: ${res.status}`);
}

export async function importResumePdf(file: File): Promise<ResumeResponse> {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${API_BASE}/import-resume-pdf`, {
    ...creds,
    method: 'POST',
    body: form,
  });
  return parseOk(res, `PDF import failed: ${res.status}`);
}

async function postResumeTool(
  sessionId: string,
  tool: string,
  body: unknown
): Promise<ResumeResponse> {
  const res = await fetch(
    `${API_BASE}/resume/${encodeURIComponent(sessionId)}/tools/${tool}`,
    {
      ...creds,
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }
  );
  return parseOk(res, `${tool} failed: ${res.status}`);
}

export function setItemIncluded(
  sessionId: string,
  section: string,
  itemId: string,
  included: boolean
): Promise<ResumeResponse> {
  return postResumeTool(
    sessionId,
    included ? 'include_on_resume' : 'exclude_from_resume',
    { section, itemId }
  );
}

export function reorderResumeSections(
  sessionId: string,
  sectionOrder: string[]
): Promise<ResumeResponse> {
  return postResumeTool(sessionId, 'reorder_sections', { sectionOrder });
}

export function reorderResumeItems(
  sessionId: string,
  section: string,
  itemIds: string[]
): Promise<ResumeResponse> {
  return postResumeTool(sessionId, 'reorder_items', { section, itemIds });
}

export async function updateResumeBasics(
  sessionId: string,
  basics: {
    fullName: string
    email: string
    phone: string
    location: string
    github: string
    linkedin: string
  }
): Promise<ResumeResponse> {
  const res = await fetch(
    `${API_BASE}/resume/${encodeURIComponent(sessionId)}/basics`,
    {
      ...creds,
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...basics, verify: true }),
    }
  )
  if (!res.ok) {
    throw new Error(await apiErrorMessage(res, `Update basics failed: ${res.status}`))
  }
  return res.json()
}