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

  throw new Error(`unknown tool: ${name}`)
}

export async function handleToolCallEvent(
  dc: RTCDataChannel,
  sessionId: string,
  event: Record<string, unknown>,
  onResult?: (result: unknown) => void
) {
  if (event.type !== 'response.function_call_arguments.done') return

  const call: ToolCall = {
    call_id: String(event.call_id ?? ''),
    name: String(event.name ?? ''),
    arguments: String(event.arguments ?? '{}'),
  }
  if (!call.call_id || !call.name) return

  let output: unknown
  try {
    output = await runResumeTool(sessionId, call.name, call.arguments)
  } catch (err) {
    output = { error: err instanceof Error ? err.message : 'tool failed' }
  }

  onResult?.(output)

  dc.send(
    JSON.stringify({
      type: 'conversation.item.create',
      item: {
        type: 'function_call_output',
        call_id: call.call_id,
        output: JSON.stringify(output),
      },
    })
  )
  dc.send(JSON.stringify({ type: 'response.create' }))
}
