const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8081';

export type ResumeResponse = {
  sessionId: string;
  payload: unknown;
  version: number;
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