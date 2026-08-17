import type { ResumeItem, ResumePayload } from '../types/resume'

type Props = {
  payload: ResumePayload
}

function text(value: unknown): string {
  return typeof value === 'string' ? value : ''
}

function list(value: unknown): string[] {
  return Array.isArray(value)
    ? value.map((item) => String(item)).filter(Boolean)
    : []
}

function dateRange(item: ResumeItem): string {
  return [text(item.startDate), text(item.endDate)].filter(Boolean).join(' – ')
}

function ItemHeader({
  primary,
  secondary,
  meta,
}: {
  primary: string
  secondary?: string
  meta?: string
}) {
  return (
    <div className="resume-item-heading">
      <div>
        <strong>{primary || 'Untitled item'}</strong>
        {secondary && <span>{secondary}</span>}
      </div>
      {meta && <time>{meta}</time>}
    </div>
  )
}

function ResumeItemView({
  section,
  item,
}: {
  section: string
  item: ResumeItem
}) {
  const bullets = list(item.bullets)

  if (section === 'experience') {
    return (
      <article className="resume-item">
        <ItemHeader
          primary={text(item.title)}
          secondary={[text(item.company), text(item.location)]
            .filter(Boolean)
            .join(' · ')}
          meta={dateRange(item)}
        />
        {bullets.length > 0 && (
          <ul>{bullets.map((bullet) => <li key={bullet}>{bullet}</li>)}</ul>
        )}
      </article>
    )
  }

  if (section === 'projects') {
    const technologies = list(item.technologies)
    return (
      <article className="resume-item">
        <ItemHeader
          primary={text(item.name)}
          secondary={technologies.join(' · ')}
        />
        {text(item.description) && <p>{text(item.description)}</p>}
        {bullets.length > 0 && (
          <ul>{bullets.map((bullet) => <li key={bullet}>{bullet}</li>)}</ul>
        )}
      </article>
    )
  }

  if (section === 'education') {
    return (
      <article className="resume-item">
        <ItemHeader
          primary={text(item.degree)}
          secondary={[text(item.institution), text(item.location)]
            .filter(Boolean)
            .join(' · ')}
          meta={dateRange(item)}
        />
      </article>
    )
  }

  if (section === 'achievements') {
    return (
      <article className="resume-item">
        <ItemHeader
          primary={text(item.title)}
          meta={text(item.date)}
        />
        {text(item.description) && <p>{text(item.description)}</p>}
      </article>
    )
  }

  return (
    <article className="resume-item">
      <ItemHeader
        primary={text(item.title) || text(item.name)}
        meta={text(item.date) || dateRange(item)}
      />
      {text(item.description) && <p>{text(item.description)}</p>}
      {bullets.length > 0 && (
        <ul>{bullets.map((bullet) => <li key={bullet}>{bullet}</li>)}</ul>
      )}
    </article>
  )
}

export function ResumePreview({ payload }: Props) {
  const { basics, skills, sections } = payload.inventory
  const { includedIds, sectionOrder, summary } = payload.resume
  const contact = [basics.email, basics.phone, basics.location].filter(Boolean)

  return (
    <div className="resume-paper" aria-label="Live resume preview">
      <header className="resume-header">
        <h1>{basics.fullName || 'Your Name'}</h1>
        {contact.length > 0 && <p>{contact.join(' · ')}</p>}
        {basics.links.length > 0 && (
          <nav aria-label="Profile links">
            {basics.links.map((link) => (
              <a key={`${link.label}-${link.url}`} href={link.url}>
                {link.label}
              </a>
            ))}
          </nav>
        )}
      </header>

      {summary && (
        <section className="resume-section">
          <h2>Summary</h2>
          <p>{summary}</p>
        </section>
      )}

      {skills.length > 0 && (
        <section className="resume-section">
          <h2>Skills</h2>
          <p>{skills.join(' · ')}</p>
        </section>
      )}

      {sectionOrder.map((sectionKey) => {
        const section = sections[sectionKey]
        if (!section) return null
        const visible = new Set(includedIds[sectionKey] ?? [])
        const items = section.items.filter((item) => visible.has(item.id))
        if (items.length === 0) return null

        return (
          <section className="resume-section" key={sectionKey}>
            <h2>{section.title}</h2>
            {items.map((item) => (
              <ResumeItemView
                key={item.id}
                section={sectionKey}
                item={item}
              />
            ))}
          </section>
        )
      })}
    </div>
  )
}
