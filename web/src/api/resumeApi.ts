const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8081';

export type ResumeResponse = {
  sessionId: string;
  payload: unknown;
  version: number;
  mode?: 'intake' | 'edit';
};

export async function getResume(sessionId: string): Promise<ResumeResponse> {
  const res = await fetch(`${API_BASE}/resume/${encodeURIComponent(sessionId)}`);
  if (!res.ok) {
    throw new Error(`GET failed: ${res.status}`);
  }
  return res.json();
}

export async function putResume(
  sessionId: string,
  payload: unknown
): Promise<ResumeResponse> {
  const res = await fetch(`${API_BASE}/resume/${encodeURIComponent(sessionId)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ payload }),
  });
  if (!res.ok) {
    throw new Error(`PUT failed: ${res.status}`);
  }
  return res.json();
}

export async function startIntake(): Promise<ResumeResponse> {
  const res = await fetch(`${API_BASE}/intake/start`, { method: 'POST' });
  if (!res.ok) {
    throw new Error(`Start intake failed: ${res.status}`);
  }
  return res.json();
}

export async function importResumePdf(file: File): Promise<ResumeResponse> {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${API_BASE}/import-resume-pdf`, {
    method: 'POST',
    body: form,
  });
  if (!res.ok) {
    throw new Error(`PDF import failed: ${res.status}`);
  }
  return res.json();
}

async function postResumeTool(
  sessionId: string,
  tool: string,
  body: unknown
): Promise<ResumeResponse> {
  const res = await fetch(
    `${API_BASE}/resume/${encodeURIComponent(sessionId)}/tools/${tool}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }
  );
  if (!res.ok) {
    throw new Error(`${tool} failed: ${res.status}`);
  }
  return res.json();
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