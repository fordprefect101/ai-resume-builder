const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8081'

export type RealtimeHandles = {
  pc: RTCPeerConnection
  dc: RTCDataChannel
  mode: 'intake' | 'edit'
  stop: () => void
}

export async function startRealtimeSession(
  sessionId: string,
  onEvent: (event: Record<string, unknown>) => void
): Promise<RealtimeHandles> {
  const tokenRes = await fetch(`${API_BASE}/realtime/token?sessionId=${encodeURIComponent(sessionId)}`)
  if (!tokenRes.ok) throw new Error(`token failed: ${tokenRes.status}`)
  const tokenData = await tokenRes.json()
  const ephemeralKey = tokenData.value as string
  const mode = tokenData.mode === 'intake' ? 'intake' : 'edit'
  if (!ephemeralKey) throw new Error('no ephemeral key in token response')

  const pc = new RTCPeerConnection()

  const audioEl = document.createElement('audio')
  audioEl.autoplay = true
  document.body.appendChild(audioEl)
  pc.ontrack = (e) => {
    audioEl.srcObject = e.streams[0]
  }

  const ms = await navigator.mediaDevices.getUserMedia({ audio: true })
  pc.addTrack(ms.getTracks()[0])

  const dc = pc.createDataChannel('oai-events')
  dc.addEventListener('open', () => {
    dc.send(JSON.stringify({ type: 'response.create' }))
  })
  dc.addEventListener('message', (e) => {
    try {
      const event = JSON.parse(e.data as string) as Record<string, unknown>
      onEvent(event)
    } catch {
      // ignore non-JSON
    }
  })

  const offer = await pc.createOffer()
  await pc.setLocalDescription(offer)

  const sdpResponse = await fetch('https://api.openai.com/v1/realtime/calls', {
    method: 'POST',
    body: offer.sdp,
    headers: {
      Authorization: `Bearer ${ephemeralKey}`,
      'Content-Type': 'application/sdp',
    },
  })
  if (!sdpResponse.ok) {
    throw new Error(`realtime calls failed: ${sdpResponse.status}`)
  }

  const answer = { type: 'answer' as const, sdp: await sdpResponse.text() }
  await pc.setRemoteDescription(answer)

  const stop = () => {
    dc.close()
    pc.close()
    ms.getTracks().forEach((t) => t.stop())
    audioEl.remove()
  }

  return { pc, dc, mode, stop }
}