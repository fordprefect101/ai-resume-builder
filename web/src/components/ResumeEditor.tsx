import { BasicsEditor } from './BasicsEditor'
import {
  isBasicsVerified,
  type ResumeItem,
  type ResumePayload,
} from '../types/resume'

type Props = {
  payload: ResumePayload
  busyAction: string
  contentLocked: boolean
  onConfirmBasics: (basics: {
    fullName: string
    email: string
    phone: string
    location: string
    github: string
    linkedin: string
  }) => void
  onBasicsDirtyChange: (dirty: boolean) => void
  onMoveSection: (section: string, direction: -1 | 1) => void
  onMoveItem: (section: string, itemId: string, direction: -1 | 1) => void
  onToggleItem: (section: string, itemId: string, included: boolean) => void
  onStartVoice: () => void
}

function itemLabel(section: string, item: ResumeItem): string {
  if (section === 'experience') {
    return [item.title, item.company].filter(Boolean).join(' at ')
  }
  if (section === 'projects') return String(item.name || 'Untitled project')
  if (section === 'education') {
    return [item.degree, item.institution].filter(Boolean).join(' · ')
  }
  return String(item.title || item.name || 'Untitled item')
}

export function ResumeEditor({
  payload,
  busyAction,
  contentLocked,
  onConfirmBasics,
  onBasicsDirtyChange,
  onMoveSection,
  onMoveItem,
  onToggleItem,
  onStartVoice,
}: Props) {
  const { skills, sections } = payload.inventory
  const { includedIds, sectionOrder } = payload.resume
  const verified = isBasicsVerified(payload)

  return (
    <aside className="resume-editor" aria-label="Resume sections editor">
      <div className="editor-intro">
        <div>
          <p className="eyebrow">Resume content</p>
          <h2>Organize your resume</h2>
        </div>
        <button
          type="button"
          className="voice-add-button"
          disabled={contentLocked}
          onClick={onStartVoice}
        >
          Add with voice
        </button>
      </div>

      <BasicsEditor
        payload={payload}
        busy={busyAction === 'basics'}
        onConfirm={onConfirmBasics}
        onDirtyChange={onBasicsDirtyChange}
      />

      <div className={contentLocked ? 'editor-locked' : undefined}>
        {contentLocked && (
          <p className="basics-gate-note">
            {verified
              ? 'Save and confirm your personal details again to keep editing.'
              : 'Confirm your personal details to unlock voice and resume edits.'}
          </p>
        )}

      <section className="editor-card">
        <h3>Skills</h3>
        <div className="skill-chips">
          {skills.length > 0 ? (
            skills.map((skill) => <span key={skill}>{skill}</span>)
          ) : (
            <p>No skills added yet</p>
          )}
        </div>
      </section>

      <div className="editor-section-list">
        {sectionOrder.map((sectionKey, index) => {
          const section = sections[sectionKey]
          if (!section) return null
          const included = new Set(includedIds[sectionKey] ?? [])

          return (
            <section className="editor-card section-card" key={sectionKey}>
              <header>
                <div>
                  <span className="section-position">{index + 1}</span>
                  <h3>{section.title}</h3>
                </div>
                <div className="order-buttons" aria-label={`Reorder ${section.title}`}>
                  <button
                    type="button"
                    aria-label={`Move ${section.title} up`}
                    disabled={index === 0 || Boolean(busyAction)}
                    onClick={() => onMoveSection(sectionKey, -1)}
                  >
                    ↑
                  </button>
                  <button
                    type="button"
                    aria-label={`Move ${section.title} down`}
                    disabled={
                      index === sectionOrder.length - 1 || Boolean(busyAction)
                    }
                    onClick={() => onMoveSection(sectionKey, 1)}
                  >
                    ↓
                  </button>
                </div>
              </header>

              {section.items.length === 0 ? (
                <p className="empty-section">No items yet. Add one with voice.</p>
              ) : (
                <div className="editor-items">
                  {section.items.map((item, itemIndex) => {
                    const isIncluded = included.has(item.id)
                    const actionKey = `${sectionKey}:${item.id}`
                    return (
                      <div className="editor-item" key={item.id}>
                        <label>
                          <input
                            type="checkbox"
                            checked={isIncluded}
                            disabled={busyAction === actionKey}
                            onChange={() =>
                              onToggleItem(sectionKey, item.id, isIncluded)
                            }
                          />
                          <span>
                            <strong>{itemLabel(sectionKey, item)}</strong>
                            <small>{isIncluded ? 'Shown on resume' : 'Hidden'}</small>
                          </span>
                        </label>
                        <div
                          className="order-buttons"
                          aria-label={`Reorder ${itemLabel(sectionKey, item)}`}
                        >
                          <button
                            type="button"
                            aria-label="Move item up"
                            disabled={itemIndex === 0 || Boolean(busyAction)}
                            onClick={() => onMoveItem(sectionKey, item.id, -1)}
                          >
                            ↑
                          </button>
                          <button
                            type="button"
                            aria-label="Move item down"
                            disabled={
                              itemIndex === section.items.length - 1 ||
                              Boolean(busyAction)
                            }
                            onClick={() => onMoveItem(sectionKey, item.id, 1)}
                          >
                            ↓
                          </button>
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </section>
          )
        })}
      </div>
      </div>
    </aside>
  )
}
