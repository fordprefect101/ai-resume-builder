import { useState } from 'react'
import { setProjectLinkPrivate } from '../../api/resumeApi'
import { BasicsEditor } from './BasicsEditor'
import { useContactStatus } from './useContactStatus'
import { targetKey, type RewriteControls } from './useAutoRewrite'
import { answerFollowup, type RewriteTarget } from '../../api/resumeApi'
import {
  isBasicsVerified,
  type BasicsInput,
  type DerivedClaim,
  type ProjectLinkView,
  type ResumeItem,
  type ResumePayload,
} from '../../types/resume'

/**
 * The check on one project's link: its badge, the languages GitHub reports for a
 * public repository, and the "this one is private" choice. Information for the
 * person only; it never changes a point and is not printed on the resume.
 */
function ProjectLinkLine({
  link,
  view,
  checking,
  onRecheck,
  onPrivate,
}: {
  link: string
  view: ProjectLinkView
  checking: boolean
  onRecheck: () => void
  onPrivate: (isPrivate: boolean) => void
}) {
  const label: Record<string, string> = {
    looks_right: 'Looks right',
    exists: 'Exists',
    warning: 'Warning',
    broken: 'Fix this',
    private: 'Private',
  }
  const showBadge = view.level !== 'empty' && view.level !== 'unchecked'
  return (
    <div className="project-link-line">
      <small className="project-link-url">{link}</small>
      {showBadge && (
        <span className={`contact-badge ${view.level}`}>
          <strong>{label[view.level]}</strong>
          {view.message ? ` · ${view.message}` : ''}
        </span>
      )}
      {view.languages.length > 0 && (
        <small className="project-link-languages">
          GitHub reports: {view.languages.join(', ')}
        </small>
      )}
      <div className="project-link-actions">
        <label>
          <input
            type="checkbox"
            checked={view.level === 'private'}
            onChange={(event) => onPrivate(event.target.checked)}
          />{' '}
          This repository is private
        </label>
        <button
          type="button"
          className="contact-recheck"
          disabled={checking}
          onClick={onRecheck}
        >
          {checking ? 'Checking…' : 'Check again'}
        </button>
      </div>
    </div>
  )
}

/** "Writing your points…", a plain-words problem, or the "Rewrite points" button. */
function RewriteLine({
  target,
  controls,
  disabled,
}: {
  target: RewriteTarget
  controls: RewriteControls
  disabled: boolean
}) {
  const key = targetKey(target)
  const state = controls.states[key]
  if (state?.kind === 'writing') {
    return (
      <p className="rewrite-line" role="status">
        Writing your points…
      </p>
    )
  }
  return (
    <div className="rewrite-line">
      {state?.kind === 'confirm' && (
        <>
          <span>{state.message}</span>
          <button
            type="button"
            disabled={disabled}
            onClick={() => void controls.run(target, { force: true, replaceEdited: true })}
          >
            Replace my points
          </button>
          <button type="button" onClick={() => controls.dismiss(key)}>
            Keep mine
          </button>
        </>
      )}
      {state?.kind === 'error' && (
        <>
          <span className="contact-error">{state.message}</span>
          <button
            type="button"
            disabled={disabled}
            onClick={() => void controls.run(target, { force: true })}
          >
            Try again
          </button>
        </>
      )}
      {!state && (
        <button
          type="button"
          disabled={disabled}
          onClick={() => void controls.run(target, { force: true })}
        >
          Rewrite points
        </button>
      )}
    </div>
  )
}

const WARNING_TEXT: Record<string, string> = {
  needs_review:
    'This line was simplified because the first version claimed more than you said.',
  unchecked: 'This line was not double-checked.',
}

/**
 * A small note under an entry for each point that needs a look. Information only:
 * it never blocks saving or downloading and is not printed on the resume.
 */
function PointWarnings({
  claims,
  target,
}: {
  claims: DerivedClaim[]
  target: RewriteTarget
}) {
  const flagged = claims
    .filter(
      (claim) =>
        claim.section === target.section &&
        claim.itemId === target.itemId &&
        (claim.projectId ?? null) === (target.projectId ?? null) &&
        claim.status !== undefined &&
        claim.status in WARNING_TEXT
    )
    .sort((a, b) => (a.order ?? 0) - (b.order ?? 0))
  if (flagged.length === 0) return null
  return (
    <ul className="point-warnings" aria-label="Points that need a look">
      {flagged.map((claim) => (
        <li key={claim.id}>
          <span aria-hidden="true">⚠ </span>
          <q>{claim.content}</q> — {WARNING_TEXT[claim.status as string]} Edit it or
          keep it.
        </li>
      ))}
    </ul>
  )
}

const MAX_FOLLOW_UPS = 2

/** The writing team's open questions about one entry, each with a box to answer. */
function FollowUps({
  level,
  target,
  controls,
  disabled,
}: {
  level: { writing?: { questions?: unknown[]; followUpsAsked?: number } }
  target: RewriteTarget
  controls: RewriteControls
  disabled: boolean
}) {
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const left = Math.max(0, MAX_FOLLOW_UPS - (level.writing?.followUpsAsked ?? 0))
  const questions = ((level.writing?.questions ?? []) as { id?: string; text?: string }[])
    .filter((q) => q.id && q.text)
    .slice(0, left)
  if (questions.length === 0) return null

  async function send(id: string, skipped: boolean) {
    setBusy(true)
    setError('')
    try {
      const res = await answerFollowup(
        controls.sessionId, target, id, answers[id] ?? '', skipped
      )
      controls.applyPayload(res.payload, res.version)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save your answer.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="followups">
      {questions.map((q) => (
        <div key={q.id} className="followup">
          <label>
            <span>{q.text}</span>
            <textarea
              rows={2}
              value={answers[q.id!] ?? ''}
              disabled={disabled || busy}
              onChange={(e) => setAnswers((prev) => ({ ...prev, [q.id!]: e.target.value }))}
            />
          </label>
          <button
            type="button"
            disabled={disabled || busy || !(answers[q.id!] ?? '').trim()}
            onClick={() => void send(q.id!, false)}
          >
            Answer
          </button>
          <button type="button" disabled={disabled || busy} onClick={() => void send(q.id!, true)}>
            Skip
          </button>
        </div>
      ))}
      {error && <span className="contact-error">{error}</span>}
    </div>
  )
}

/**
 * Read-only list of a job's projects, active ones first and archived ones dimmed.
 * Projects are added, renamed, archived and reordered by voice for now.
 */
function ProjectList({
  item,
  section,
  rewrite,
  claims,
  disabled,
}: {
  item: ResumeItem
  section: string
  rewrite: RewriteControls
  claims: DerivedClaim[]
  disabled: boolean
}) {
  const projects = item.projects ?? []
  if (projects.length === 0) return null
  const active = projects.filter((project) => project.status !== 'archived')
  const archived = projects.filter((project) => project.status === 'archived')

  return (
    <ul className="editor-projects" aria-label="Projects in this job">
      {[...active, ...archived].map((project) => {
        const points = (project.bullets ?? []).length
        const isArchived = project.status === 'archived'
        const technologies = (project.technologies ?? []).join(' · ')
        return (
          <li
            key={project.id}
            className={isArchived ? 'editor-project archived' : 'editor-project'}
          >
            <strong>{project.name || 'Untitled project'}</strong>
            <small>
              {isArchived ? 'Archived · ' : ''}
              {points === 0
                ? 'no points yet'
                : `${points} point${points === 1 ? '' : 's'}`}
              {technologies ? ` · ${technologies}` : ''}
            </small>
            {!isArchived && (
              <RewriteLine
                target={{ section, itemId: item.id, projectId: project.id }}
                controls={rewrite}
                disabled={disabled}
              />
            )}
            {!isArchived && (
              <PointWarnings
                claims={claims}
                target={{ section, itemId: item.id, projectId: project.id }}
              />
            )}
            {!isArchived && (
              <FollowUps
                level={project}
                target={{ section, itemId: item.id, projectId: project.id }}
                controls={rewrite}
                disabled={disabled}
              />
            )}
          </li>
        )
      })}
    </ul>
  )
}

type Props = {
  payload: ResumePayload
  sessionId: string
  busyAction: string
  contentLocked: boolean
  onConfirmBasics: (basics: BasicsInput) => void
  onBasicsDirtyChange: (dirty: boolean) => void
  onMoveSection: (section: string, direction: -1 | 1) => void
  onMoveItem: (section: string, itemId: string, direction: -1 | 1) => void
  onToggleItem: (section: string, itemId: string, included: boolean) => void
  onStartVoice: () => void
  rewrite: RewriteControls
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
  sessionId,
  busyAction,
  contentLocked,
  onConfirmBasics,
  onBasicsDirtyChange,
  onMoveSection,
  onMoveItem,
  onToggleItem,
  onStartVoice,
  rewrite,
}: Props) {
  const { skills, sections } = payload.inventory
  const { includedIds, sectionOrder } = payload.resume
  const verified = isBasicsVerified(payload)
  // Re-fetch the badges whenever the saved contact details or a project link changes.
  const savedKey = JSON.stringify([
    payload.inventory.basics,
    (sections.projects?.items ?? []).map((item) => [item.id, item.url]),
  ])
  const contact = useContactStatus(sessionId, savedKey)
  const [linkError, setLinkError] = useState('')

  async function handlePrivate(itemId: string, isPrivate: boolean) {
    try {
      contact.setProjectLinks(
        await setProjectLinkPrivate(sessionId, itemId, isPrivate)
      )
      setLinkError('')
    } catch (err) {
      setLinkError(err instanceof Error ? err.message : 'Could not update the link')
    }
  }

  return (
    <aside className="resume-editor" aria-label="Resume sections editor">
      <div className="editor-intro">
        <div>
          <p className="eyebrow">Your story</p>
          <h2>Shape what shows</h2>
        </div>
        <button
          type="button"
          className="voice-add-button"
          disabled={contentLocked}
          onClick={onStartVoice}
        >
          Talk it through
        </button>
      </div>

      <BasicsEditor
        payload={payload}
        contact={contact}
        busy={busyAction === 'basics'}
        onConfirm={onConfirmBasics}
        onDirtyChange={onBasicsDirtyChange}
      />

      <div className={contentLocked ? 'editor-locked' : undefined}>
        {contentLocked && (
          <p className="basics-gate-note">
            {verified
              ? 'Save and confirm your details again to keep editing.'
              : 'Confirm your personal details first — then we can talk and edit.'}
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
                      <div className="editor-item-block" key={item.id}>
                        <div className="editor-item">
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
                        {(sectionKey === 'experience' || sectionKey === 'projects') && (
                          <RewriteLine
                            target={{ section: sectionKey, itemId: item.id }}
                            controls={rewrite}
                            disabled={contentLocked}
                          />
                        )}
                        {(sectionKey === 'experience' || sectionKey === 'projects') && (
                          <FollowUps
                            level={item}
                            target={{ section: sectionKey, itemId: item.id }}
                            controls={rewrite}
                            disabled={contentLocked}
                          />
                        )}
                        <PointWarnings
                          claims={payload.claims ?? []}
                          target={{ section: sectionKey, itemId: item.id }}
                        />
                        <ProjectList
                          item={item}
                          section={sectionKey}
                          rewrite={rewrite}
                          claims={payload.claims ?? []}
                          disabled={contentLocked}
                        />
                        {sectionKey === 'projects' && contact.projectLinks[item.id] && (
                          <ProjectLinkLine
                            link={String(item.url ?? '')}
                            view={contact.projectLinks[item.id]}
                            checking={contact.checking}
                            onRecheck={() => void contact.recheck()}
                            onPrivate={(isPrivate) => void handlePrivate(item.id, isPrivate)}
                          />
                        )}
                      </div>
                    )
                  })}
                </div>
              )}
            </section>
          )
        })}
      </div>
      {linkError && <p className="contact-error">{linkError}</p>}
      </div>
    </aside>
  )
}
