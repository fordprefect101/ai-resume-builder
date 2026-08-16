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

  if (name === 'exclude_project_from_resume') {
    const res = await fetch(
      `${API_BASE}/resume/${encodeURIComponent(sessionId)}/tools/exclude_project`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ projectId: args.projectId }),
      }
    )
    if (!res.ok) throw new Error(`exclude failed: ${res.status}`)
    return res.json()
  }

  if (name === 'include_project_on_resume') {
    const res = await fetch(
      `${API_BASE}/resume/${encodeURIComponent(sessionId)}/tools/include_project`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ projectId: args.projectId }),
      }
    )
    if (!res.ok) throw new Error(`include failed: ${res.status}`)
    return res.json()
  }

  if (name === 'add_project') {
    const res = await fetch(
      `${API_BASE}/resume/${encodeURIComponent(sessionId)}/tools/add_project`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(args),
      }
    )
    if (!res.ok) throw new Error(`add_project failed: ${res.status}`)
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
  // GA-style: arguments finished for a function call
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