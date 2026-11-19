import { apiErrorMessage } from '../api/resumeApi'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8081'

type ToolCall = {
  call_id: string
  name: string
  arguments: string
}

export async function runResumeTool(
  sessionId: string,
  name: string,
  argsJson: string
): Promise<unknown> {
  const args = JSON.parse(argsJson || '{}') as Record<string, unknown>

  if (name === 'search_resume_context') {
    const res = await fetch(
      `${API_BASE}/resume/${encodeURIComponent(sessionId)}/tools/search_context`,
      {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: args.query ?? '',
          section: args.section ?? null,
        }),
      }
    )
    if (!res.ok) throw new Error(await apiErrorMessage(res, `context search failed: ${res.status}`))
    return res.json()
  }

  if (name === 'set_basics') {
    throw new Error('Personal details are edited in the form, not by voice')
  }

  if (name === 'set_skills') {
    const res = await fetch(
      `${API_BASE}/resume/${encodeURIComponent(sessionId)}/tools/set_skills`,
      {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          skills: args.skills ?? [],
          confirmedEmpty: args.confirmedEmpty ?? false,
        }),
      }
    )
    if (!res.ok) throw new Error(await apiErrorMessage(res, `set_skills failed: ${res.status}`))
    return res.json()
  }

  if (name === 'complete_intake') {
    const res = await fetch(
      `${API_BASE}/resume/${encodeURIComponent(sessionId)}/tools/complete_intake`,
      {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          confirmedSkippedSections: args.confirmedSkippedSections ?? [],
        }),
      }
    )
    if (!res.ok) throw new Error(await apiErrorMessage(res, `complete_intake failed: ${res.status}`))
    return res.json()
  }

  if (name === 'exclude_from_resume') {
    const res = await fetch(
      `${API_BASE}/resume/${encodeURIComponent(sessionId)}/tools/exclude_from_resume`,
      {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ section: args.section, itemId: args.itemId }),
      }
    )
    if (!res.ok) throw new Error(await apiErrorMessage(res, `exclude failed: ${res.status}`))
    return res.json()
  }

  if (name === 'include_on_resume') {
    const res = await fetch(
      `${API_BASE}/resume/${encodeURIComponent(sessionId)}/tools/include_on_resume`,
      {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ section: args.section, itemId: args.itemId }),
      }
    )
    if (!res.ok) throw new Error(await apiErrorMessage(res, `include failed: ${res.status}`))
    return res.json()
  }

  if (name === 'add_item') {
    const res = await fetch(
      `${API_BASE}/resume/${encodeURIComponent(sessionId)}/tools/add_item`,
      {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          section: args.section,
          fields: args.fields ?? {},
          confirmedEmptyFields: args.confirmedEmptyFields ?? [],
        }),
      }
    )
    if (!res.ok) throw new Error(await apiErrorMessage(res, `add_item failed: ${res.status}`))
    return res.json()
  }

  if (name === 'reorder_sections') {
    const res = await fetch(
      `${API_BASE}/resume/${encodeURIComponent(sessionId)}/tools/reorder_sections`,
      {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sectionOrder: args.sectionOrder }),
      }
    )
    if (!res.ok) throw new Error(await apiErrorMessage(res, `reorder_sections failed: ${res.status}`))
    return res.json()
  }

  if (name === 'reorder_items') {
    const res = await fetch(
      `${API_BASE}/resume/${encodeURIComponent(sessionId)}/tools/reorder_items`,
      {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          section: args.section,
          itemIds: args.itemIds,
        }),
      }
    )
    if (!res.ok) throw new Error(await apiErrorMessage(res, `reorder_items failed: ${res.status}`))
    return res.json()
  }

  const projectTools: Record<string, Record<string, unknown>> = {
    add_project: {
      section: args.section,
      itemId: args.itemId,
      name: args.name,
      technologies: args.technologies ?? [],
      bullets: args.bullets ?? [],
    },
    rename_project: {
      section: args.section,
      itemId: args.itemId,
      projectId: args.projectId,
      name: args.name,
    },
    archive_project: {
      section: args.section,
      itemId: args.itemId,
      projectId: args.projectId,
    },
    reorder_projects: {
      section: args.section,
      itemId: args.itemId,
      projectIds: args.projectIds ?? [],
    },
  }
  if (name in projectTools) {
    // Leave section out when the assistant did not send it; the server defaults to experience.
    const body = Object.fromEntries(
      Object.entries(projectTools[name]).filter(([, value]) => value !== undefined)
    )
    const res = await fetch(
      `${API_BASE}/resume/${encodeURIComponent(sessionId)}/tools/${name}`,
      {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }
    )
    if (!res.ok) throw new Error(await apiErrorMessage(res, `${name} failed: ${res.status}`))
    return res.json()
  }

  throw new Error(`unknown tool: ${name}`)
}

export type ToolTiming = {
  name: string
  ms: number
  charsToAssistant: number
  ok: boolean
}

/**
 * What the voice model is sent after a tool runs. The full server reply (the whole
 * resume) goes to the screen only; the model gets the short `assistantResult`
 * because everything sent into a call stays in its memory.
 */
export function resultForAssistant(output: unknown): Record<string, unknown> {
  if (output && typeof output === 'object') {
    const record = output as Record<string, unknown>
    if (typeof record.error === 'string') {
      return { ok: false, error: record.error.slice(0, 200) }
    }
    const short = record.assistantResult
    if (short && typeof short === 'object') {
      return short as Record<string, unknown>
    }
  }
  // Never fall back to the full reply: a minimal acknowledgement is always safe.
  return { ok: true }
}

// Tool calls still running. The call must never be hung up while this is above 0.
let runningTools = 0

export function toolsAreRunning(): boolean {
  return runningTools > 0
}

export async function handleToolCallEvent(
  dc: RTCDataChannel,
  sessionId: string,
  event: Record<string, unknown>,
  onResult?: (result: unknown) => void,
  onTiming?: (timing: ToolTiming) => void,
  onEndRequest?: () => void
) {
  if (event.type !== 'response.function_call_arguments.done') return
  const started = performance.now()

  const call: ToolCall = {
    call_id: String(event.call_id ?? ''),
    name: String(event.name ?? ''),
    arguments: String(event.arguments ?? '{}'),
  }
  if (!call.call_id || !call.name) return

  // Hanging up is handled in the browser: nothing to run on the server, and no reply is
  // sent to the model because the call is about to close.
  if (call.name === 'end_voice_session') {
    onEndRequest?.()
    return
  }

  let output: unknown
  runningTools += 1
  try {
    output = await runResumeTool(sessionId, call.name, call.arguments)
  } catch (err) {
    output = { error: err instanceof Error ? err.message : 'tool failed' }
  } finally {
    runningTools -= 1
  }

  onResult?.(output)

  // What the voice model will read: everything in outputText stays in the call.
  const outputText = JSON.stringify(resultForAssistant(output))
  const timing: ToolTiming = {
    name: call.name,
    ms: Math.round(performance.now() - started),
    charsToAssistant: outputText.length,
    ok: !(output && typeof output === 'object' && 'error' in output),
  }
  console.info('[timing] tool', timing)
  onTiming?.(timing)

  dc.send(
    JSON.stringify({
      type: 'conversation.item.create',
      item: {
        type: 'function_call_output',
        call_id: call.call_id,
        output: outputText,
      },
    })
  )
  dc.send(JSON.stringify({ type: 'response.create' }))
}
