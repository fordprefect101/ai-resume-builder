# Writing team test set

The fixed inputs every writing-team step is measured against. The stories are fictional.
Real speech is stranger than anything written here, so add real cases (and every new
real failure) over time; do not tune prompts only to these.

## Stories: `cases/*.json`

| Field | Meaning |
|-------|---------|
| `id`, `profession`, `hardCase` | Name, profession (`tech` for now) and which hard case it covers |
| `entry` | The job or project the story is about. Its company and title may appear in a point without a fact |
| `story` | Chunks of what the person said: `{ id, source, text }`, source one of `voice`, `typed`, `followup`, `imported` |
| `mustCapture` | Phrases a good analyst must turn into facts. Each `phrase` appears word for word in the story; `kind` and `owner` are the labels a good fact would carry. `project` (optional) says which project a phrase belongs to |
| `mustNotClaim` | Things the story never says (a number, a tool, "led"). A good writer must not produce them |
| `missing` | What a good follow-up question would ask about |

Hard cases covered: rambling product description, we versus I, no numbers, lots of
numbers, two projects mixed, very short answer, imperfect English, plus really did lead,
numbers said in words, and tools by nickname.

## Traps: `traps.json`

Honest points paired with exaggerated ones over the same facts. `codeShouldCatch` says
whether `api/writing/rules.py` is expected to flag the exaggeration (and with which codes).
`false` marks a known gap that only an AI checker can close. Used to measure the checker
(false negatives: exaggerations let through; false positives: honest points rejected).

## Measuring with the real model

`python evals/run_writing_evals.py` runs the whole writing team on every story and the
trap points, next to today's one-pass tidy-up, and reports each figure as a mean over
`--runs` (3 by default) with its worst case. It costs money, so it prints an estimate and
stops until you add `--yes`. The key and model settings are read from `api/.env` or your
shell, only when the command runs.

| Option | Meaning |
|--------|---------|
| `--yes` | really run |
| `--runs N` | repeat everything N times |
| `--only ID` | one story |
| `--show` | also print the points written |
| `--no-baseline`, `--no-traps` | skip today's tidy-up, or the checker trap points |
| `--save-baseline` | keep this report as the bar (`reports/baseline.json`) |
| `--tolerance X` | slack allowed on invention rates, for run-to-run noise |

Reports are saved in `reports/` and record the models and prompt versions used. Later runs
are compared to `reports/baseline.json`, and the command exits with a failure if the
invention rate (or the words-the-story-never-said count) got worse. Follow-up questions are
printed beside what a good question should ask about; reading them is on you, they are not
scored. `run_analyst.py` and `run_writer.py` test those two stages alone.

The comparison with today's path is fair but not perfect: its input is the story split
into sentences, standing in for the voice assistant's own summarising, which cannot be
reproduced. Its cost is not measured.

## Checks

`python evals/run_evals.py` runs `writing_cases_valid`: the files are well formed, every
phrase is really in its story, nothing in `mustNotClaim` is, every core hard case is
covered, the rules keep every phrase as a fact, pass every honest trap point and catch
every exaggeration marked as catchable.
