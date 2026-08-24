export type VoiceMood =
  | 'idle'
  | 'listening'
  | 'understanding'
  | 'clarifying'
  | 'done'

type Props = {
  mood?: VoiceMood
  caption?: string
  size?: 'sm' | 'md'
}

const CAPTIONS: Record<VoiceMood, string> = {
  idle: 'Ready when you are.',
  listening: "I'm listening.",
  understanding: "I'm piecing this together…",
  clarifying: 'Tell me a little more about that.',
  done: "Nice. I've got it.",
}

export function VoiceOrb({
  mood = 'idle',
  caption,
  size = 'md',
}: Props) {
  const label = caption ?? CAPTIONS[mood]

  return (
    <div className={`voice-orb voice-orb--${size} voice-orb--${mood}`} aria-live="polite">
      <div className="voice-orb-stage" aria-hidden="true">
        <span className="voice-orb-node voice-orb-node--a" />
        <span className="voice-orb-node voice-orb-node--b" />
        <span className="voice-orb-node voice-orb-node--c" />
        <span className="voice-orb-node voice-orb-node--d" />
        <span className="voice-orb-core" />
      </div>
      <p className="voice-orb-caption">{label}</p>
    </div>
  )
}
