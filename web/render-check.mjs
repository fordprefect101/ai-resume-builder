// Renders the real resume preview and editor to HTML (no browser) and checks that a
// job's projects are drawn correctly. Run with: npm run check:render
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'

const server = await createServer({
  server: { middlewareMode: true },
  appType: 'custom',
  logLevel: 'error',
})

const results = []
function check(name, ok, detail = '') {
  results.push(ok)
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? `  (${detail})` : ''}`)
}

try {
  const { ResumePreview } = await server.ssrLoadModule(
    '/src/components/resume/ResumePreview.tsx'
  )
  const { ResumeEditor } = await server.ssrLoadModule(
    '/src/components/resume/ResumeEditor.tsx'
  )

  function payload(projects) {
    const chaishots = {
      id: 'exp_chaishots',
      company: 'ChaiShots',
      title: 'Software Engineering Intern',
      bullets: ['Mentored two interns'],
      status: 'active',
    }
    if (projects !== undefined) chaishots.projects = projects
    return {
      schemaVersion: 5,
      intake: { status: 'complete', basicsVerified: true },
      inventory: {
        basics: { fullName: 'Test Person', links: [] },
        skills: [],
        sections: {
          experience: {
            title: 'Experience',
            items: [
              chaishots,
              {
                id: 'exp_hyrefox',
                company: 'HyreFox',
                title: 'AI Tech Intern',
                bullets: ['Worked on ML pipelines'],
                status: 'active',
              },
            ],
          },
          projects: { title: 'Projects', items: [] },
          education: { title: 'Education', items: [] },
          achievements: { title: 'Achievements', items: [] },
        },
      },
      resume: {
        title: 'General Resume',
        includedIds: {
          experience: ['exp_chaishots', 'exp_hyrefox'],
          projects: [],
          education: [],
          achievements: [],
        },
        sectionOrder: ['experience', 'projects', 'education', 'achievements'],
      },
    }
  }

  const rec = {
    id: 'wp_rec',
    name: 'Recommendation engine',
    technologies: ['Redis', 'Python'],
    status: 'active',
    bullets: ['Added Redis caching', 'Added Redis caching'],
  }
  const empty = { id: 'wp_empty', name: 'Empty project', status: 'active', bullets: [] }
  const old = {
    id: 'wp_old',
    name: 'Old project',
    status: 'archived',
    bullets: ['Wrote the old thing'],
  }

  const preview = (data) =>
    renderToStaticMarkup(createElement(ResumePreview, { payload: data }))
  const noop = () => {}
  const editor = (data) =>
    renderToStaticMarkup(
      createElement(ResumeEditor, {
        payload: data,
        busyAction: '',
        contentLocked: false,
        onConfirmBasics: noop,
        onBasicsDirtyChange: noop,
        onMoveSection: noop,
        onMoveItem: noop,
        onToggleItem: noop,
        onStartVoice: noop,
      })
    )

  const withProjects = payload([rec, empty, old])
  const previewHtml = preview(withProjects)
  const editorHtml = editor(withProjects)

  // Preview
  check(
    'preview shows an active project with its technologies and points',
    previewHtml.includes('Recommendation engine') &&
      previewHtml.includes('Redis · Python') &&
      previewHtml.includes('Added Redis caching'),
  )
  check(
    'preview repeats a point that appears twice (no key clash dropping it)',
    previewHtml.split('Added Redis caching').length - 1 === 2,
  )
  check(
    'preview shows the project under its own job, after the job points',
    previewHtml.indexOf('Mentored two interns') <
      previewHtml.indexOf('Recommendation engine') &&
      previewHtml.indexOf('Recommendation engine') <
        previewHtml.indexOf('HyreFox'),
  )
  check(
    'preview leaves off a project with no points and an archived project',
    !previewHtml.includes('Empty project') &&
      !previewHtml.includes('Old project') &&
      !previewHtml.includes('Wrote the old thing'),
  )
  check(
    'a job with no projects looks exactly as before',
    preview(payload(undefined)) === preview(payload([])) &&
      preview(payload([empty, old])) === preview(payload(undefined)),
  )

  // Editor
  check(
    'editor lists the active project with its point count and technologies',
    editorHtml.includes('Recommendation engine') &&
      editorHtml.includes('2 points') &&
      editorHtml.includes('Redis · Python'),
  )
  check(
    'editor shows a project with no points, and an archived one dimmed after the active ones',
    editorHtml.includes('Empty project') &&
      editorHtml.includes('no points yet') &&
      editorHtml.includes('editor-project archived') &&
      editorHtml.includes('Archived') &&
      editorHtml.indexOf('Empty project') < editorHtml.indexOf('Old project'),
  )
  check(
    'editor shows no project list for a job without projects',
    !editor(payload(undefined)).includes('editor-projects') &&
      !editor(payload([])).includes('editor-projects'),
  )
  check(
    'editor keeps the show/hide checkbox and reorder arrows for every job',
    (editorHtml.match(/type="checkbox"/g) ?? []).length === 2 &&
      editorHtml.includes('Move item up') &&
      editorHtml.includes('Move item down'),
  )
} finally {
  await server.close()
}

const passed = results.filter(Boolean).length
console.log(`\n${passed}/${results.length} render checks passed`)
process.exit(passed === results.length ? 0 : 1)
