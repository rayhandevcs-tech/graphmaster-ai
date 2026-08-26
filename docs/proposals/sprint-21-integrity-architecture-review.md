# Architecture Review — The Academic Integrity Engine

**Status:** architecture review, pre-implementation. No code written.
**Reviewed at:** `0af1e91`.
**Author:** Principal engineering review, requested before Sprint 19 implementation.

---

## 0. The finding that changes the brief

The brief asks for an Academic Integrity Engine as "Sprint 19, the next major
feature", listing five signals and four hard constraints.

**Sprint 19 was designed, reviewed, approved and built.** It is in this
repository. Its design record is
[`docs/proposals/sprint-19-writing-consistency.md`](./sprint-19-writing-consistency.md)
and its implementation is documented in
[`10-assessment-architecture.md`](../architecture/10-assessment-architecture.md) §15.
It shipped under the name **Writing Consistency**, and the reason it is not
called an integrity engine is the subject of §1 of that review.

Four of the five requested signals already exist. The fifth was formally
rejected, with reasons that still hold. All four hard constraints in the brief
are already properties of the merged code — two of them enforced in a way no
environment variable can undo.

Building a new engine to these five signals would therefore do the two things
the brief explicitly forbids: **create a duplicate system**, and **redesign
existing architecture**.

| Requested signal | Status in the repository |
|---|---|
| 1 · Vocabulary sophistication deviation | **Built.** `analyzers/writing_profile.py` (MATTR) + target-coverage trajectory. S1 + S3, approved. |
| 2 · Writing style change — sentence length, readability, grammar quality, vocabulary complexity | **Built.** S2 + S4, approved with the constraint that mechanical accuracy is never merged into a composite. |
| 3 · Behaviour signals — edit count, editing duration, OCR corrections, interaction patterns | **Rejected as S8**, and *not collected*. No column in `submissions` records a start time, an edit count or any interaction. One narrow exception is stored and unsurfaced: `was_ocr_edited` and the preserved `ocr_text` (§4.4). |
| 4 · Graph relevance | **Built, and stronger than asked.** `analyzers/graph_accuracy.py` (492 lines) verifies each located claim against chart facts rather than scoring generic-ness. |
| 5 · Historical consistency | **Built.** `assessment/consistency/` — `profile.py`, `compare.py`, `gating.py`, `overlap.py`. |

**What is genuinely missing is not an engine. It is a surface, a legal answer
and a term of evidence.** That is the sprint this review proposes.

---

## 1. Repository state

`0af1e91`, branch `claude/graphmaster-platform-9aba5t`.

| | |
|---|---|
| Backend | Sprints 1–9 core, 15–20 assessment. 156 Python modules. |
| Frontend | Sprints 10–13. 189 TypeScript modules. |
| Tests | 1,580 backend · 267 frontend · 99% coverage |
| Migrations | 4, forward-only, round-tripped from empty in CI |
| CI | 7 jobs — lint, secret scan, backend tests with an 80% floor, migrations, frontend build and tests, generated-type drift, compose |
| Containers | `backend/Dockerfile`, `frontend/Dockerfile`, `docker-compose.yml`, exercised by a CI job |
| External services | None required. Grammar is optional and off by default. |

### 1.1 The assessment framework, as merged

```
app/assessment/
├── engine.py, supervisor.py, registry.py, protocol.py, result.py
├── audience.py          ← who may see which analyzer's output
├── chart.py, claims.py  ← chart reduced to facts; located claims
├── issues.py, text.py
├── analyzers/
│   ├── spelling.py  sentence.py  word_usage.py  vocabulary.py
│   ├── grammar.py   writing.py   graph_accuracy.py
│   └── writing_profile.py        ← Signals 1, 2, 5 (per-submission measures)
└── consistency/
    ├── profile.py   ← the series of profiles for one student
    ├── compare.py   ← current against baseline. Nothing stored.
    ├── gating.py    ← which prior submissions are comparable at all
    └── overlap.py   ← verbatim self-overlap (S5)
```

The split is the load-bearing decision of Sprint 19: **the analyzer measures,
the comparison compares.** A per-submission analyzer produces a profile of
numbers that go into `assessment_details.analyzer_status` (JSONB, no
migration); a separate, pure comparison layer reads a series of them at teacher
request time. **Nothing about a comparison is ever stored.**

### 1.2 The four constraints the brief sets are already enforced

| Brief's constraint | Where it lives today |
|---|---|
| Never claim a submission is AI-generated | C1 of the Sprint 19 review. S7 (function-word/Burrows's Delta) was rejected *because* it is authorship attribution with the label removed. No composite, no threshold, no ordering of students exists in the code. |
| Never accuse a student | The endpoint returns observations with their limits in the payload. No verdict field exists to accuse with. |
| Never influence score, XP, achievements, leaderboard | Structural: the consistency layer has no write path into `scores`, `xp_events` or `leaderboard_entries`. It is read-only at request time. |
| Teacher-facing only | `NEVER_STUDENT_ANALYZERS = frozenset({"writing_profile"})` in `core/config.py` — a **hard floor in code**, added in Sprint 19 precisely because a default that a missing environment variable can flip is not "never". |

There is no stage at which a student sees this. That is a property of the
build, not of the configuration.

---

## 2. What remains

### 2.1 Backend — three items, none of them an engine

| # | Item | Why it is not code |
|---|---|---|
| R1 | **Decision 12** — the subject access request answer. A student's writing profile is their personal data. PROJECT_PLAN §1.4 marks this *"undecided; must be settled before stage 2"*. | A data-protection position, then a paragraph in the privacy notice. |
| R2 | **Decision 14** — how long the dark stage runs and against what evidence. Currently *"one full teaching term, with the §15.7 distributions reviewed by a person"*. | A measurement protocol and a review, not a feature. |
| R3 | **Stage 2 → 3 promotion.** Two environment variables and the evidence to justify moving them. | Configuration, gated on R1 and R2. |

### 2.2 Frontend — the surface that does not exist

`GET /assessment/submissions/{id}/consistency` is implemented, tested and
teacher-gated. **No screen calls it.** This is the item my Sprint 14 audit
recorded as *"Writing consistency unsurfaced — endpoint exists, no screen"*,
and it is the whole of the user-visible work in this area.

### 2.3 Frontend — Sprint 14 as originally planned

Deployment guides, API docs, README, and the accessibility and responsive
audit. The audit is now done; the rest is not.

### 2.4 Audit findings

Six were carried forward in the brief. My audit raised sixteen; the mapping
matters because four raised findings are not in the brief's list, and one of
them is a WCAG item.

| Brief | Audit | Severity | In brief's list? |
|---|---|---|---|
| F1 Avatar migration | F1 | **P0** | Yes |
| F2 Selected + locked | F2 | **P0** | Yes |
| F3 Results copy | F3 | P1 | Yes |
| F4 Empty states | F4 + F6 | P1 | Yes |
| F5 Disabled CTA | F13 | P3 | Yes |
| F6 UI consistency / duplicates | F5 + F14 | P1 / P3 | Yes |
| — | **F11 no `<h1>` on `/login`, `/register`** | P2 | **No — and it is a WCAG 1.3.1 / 2.4.6 item** |
| — | F10 retry policy shows a skeleton on a 500 | P2 | No |
| — | F7 practice library shows no graphs | P2 | No — needs an API decision |
| — | F8, F9, F12, F15, F16 | P2–P3 | No |

**F11 should be added to the fix list.** The brief requires WCAG compliance,
and the first two screens a user meets have no top-level heading.

---

## 3. Final project completion assessment

| Area | Complete | Notes |
|---|---|---|
| Backend domain | **100%** | Every specified function reachable over the API, tested, green in CI |
| Assessment engine | **100%** | Seven analyzers, audience filtering, failure isolation, versioning |
| Writing consistency | **100% built, 0% exposed** | Stage 1 of 3 by design |
| Gamification | **100%** | XP ledger, tiers, achievements, streaks, four leaderboard scopes |
| Analytics | **100%** | Class, platform, vocabulary, trends, exports |
| Student frontend | **~95%** | Blocked by F1/F2 at registration and profile |
| Teacher frontend | **100%** | Dashboard, analytics, review, authoring, exports |
| Admin frontend | **100%** | Roles, class assignment, account status |
| Integrity surface | **0%** | The subject of this review |
| Deployment | **~60%** | Containers and compose exist and are CI-exercised; production guides, API docs and the hardening pass do not |

**Overall: the product is functionally complete and not yet deliverable.**
The gap is deployment documentation and six audit fixes, not features.

---

## 4. Proposal — Sprint 21: the Integrity Review surface

Not a new engine. A teacher-facing surface over what exists, plus the two
non-engineering decisions that gate it.

### 4.1 What it is

One route, `/teacher/submissions/[id]` gaining an **Integrity** tab, visible
only when the deployment has reached stage 3. It reads two endpoints that both
already exist:

- `GET /assessment/submissions/{id}/consistency` — the five trajectory
  measures, each with its baseline, its difference, and `excluded` counts by
  reason.
- `GET /assessment/submissions/{id}` — the `graph_accuracy` analyzer's located
  claims and verdicts, already rendered on the Findings tab.

### 4.2 What it must show, and what it must never show

| Must | Must never |
|---|---|
| Each measure with its own baseline and n | A composite score, an index, a percentage, a "risk" |
| `no baseline yet` where n is below `CONSISTENCY_MIN_BASELINE` | `0`, "consistent", or a green tick standing in for absence |
| The two limitations in the payload, on the screen | The limitations in a help page |
| The excluded count and its reason | A silent comparison across an engine or chart-type change |
| Both spans, side by side, for self-overlap | The word "plagiarism", "AI", "cheating", or "suspicious" |
| The platform's own feedback that named the terms (decision 13) | An ordering of students by anything on this screen |

**The absence of a ranking is the design.** Any list ordered by any of these
measures is a ranking of suspicion regardless of its column header, and §1.2 of
the Sprint 19 review rules it out. The surface is reachable only from one
student's own submission.

### 4.3 Design direction (for implementation, not now)

The existing `InsightCard` contract — question, answer, derived interpretation
— is the right primitive and already carries the honesty rule. Each measure is
one card: *"Has their vocabulary range changed?"* → the figure and its
baseline → a derived sentence that says what the data supports and nothing
more, including *"not enough comparable prior work to say"*, which will be the
answer for most of a term.

Self-overlap is the one bespoke component: two panes of the student's own text
with the shared span marked in both. It reuses `AnnotatedAnswer`'s span
discipline (sorted, clipped, non-overlapping).

Tokens, dark mode, the 44px floor and the reduced-motion rules all come from
the existing system. No new colour, no new type scale, no new motion.

### 4.4 On Signal 3 — behaviour

**Recommend rejecting again.** The three grounds from S8 are unchanged:

1. **Not collected.** `submissions` has `submitted_at` and `scored_at` and no
   start time. Edit count, editing duration and interaction patterns require
   new columns *and* frontend instrumentation.
2. **It is a categorical escalation** — from analysing work a student chose to
   submit, to recording how they produced it. Different consent basis,
   different privacy notice, and it lands hardest on students who write slowly
   because English is their second language.
3. **It is the least explainable signal in the set.** "You edited 47 times" has
   no defensible interpretation in an appeal.

**There is one honest narrow slice, and it is already in the database and on
the API payload — but rendered nowhere.** `submissions.ocr_text` preserves the
unedited machine reading and `was_ocr_edited` records whether the student
changed it. `SubmissionDetail` carries both; no frontend component reads
either.

Showing the original recognition beside the corrected answer is a fact about a
document the student chose to submit, it needs no telemetry, no new column and
no consent change — and it is genuinely useful to a teacher for a reason that
has nothing to do with integrity: it shows what the recogniser got wrong.
**Recommend adding it to the submission review as an ordinary teaching
affordance**, not as a behaviour signal, and not on the Integrity tab.

If the institution later wants behavioural telemetry, it is its own sprint with
its own ethics approval — not a bullet inside this one.

---

## 5. Database impact

**No migration. No new table. No new column.**

| Concern | Answer |
|---|---|
| Profiles | Already written to `assessment_details.analyzer_status` (JSONB) when `writing_profile` is on the roster |
| Comparisons | Computed at request time and never stored — the dividend of storing only measurements |
| New tables | None. A `integrity_flags` table would be the ranking §4.2 forbids, materialised. |
| Indexes | The comparison reads a student's prior submissions; `submissions(user_id, scored_at)` already supports it |
| Retention | Profiles die with the assessment row. Rollback is removing the analyzer name — stored profiles become inert JSON nothing reads |
| Migration count | Stays at 4 |

The one database-adjacent question is R1: a subject access request must be able
to return a student's profiles. They are inside a JSONB column on a row keyed
by submission, so extraction is a query, not a schema change — but it needs
writing down before stage 2.

---

## 6. API impact

**No new endpoint. No changed contract.**

| Endpoint | Change |
|---|---|
| `GET /assessment/submissions/{id}/consistency` | None. Already teacher-gated, already 503s where the layer is off. |
| `GET /assessment/submissions/{id}` | None. |
| Everything else | None. |

Frontend additions: `assessmentApi.consistency()` already exists in
`lib/api/assessment.ts` and has never been called. `queryKeys.assessmentConsistency()`
already exists. **The client is written; only the screen is missing.**

The 503-versus-empty distinction matters and is already implemented: a
deployment that has not enabled the comparison layer returns 503, because an
empty comparison and a switched-off one look identical and only the first is a
fact about the student. The UI must render those two states differently.

---

## 7. Risk analysis

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| K1 | **A teacher reads a measure as an accusation** | High | Severe — a student is confronted | Limitations in the payload and on screen; no composite; no ranking; wording tested. This is the risk the whole design is shaped around. |
| K2 | **The platform's own feedback causes the change it then measures** | Certain | Invalidates the figure | Decision 13: show the feedback that named the terms beside the change. Turns the largest false-positive source into teaching output. |
| K3 | **Promotion before enough data** | Medium | Figures that are noise | Decision 14 gates stage 3 on a term of measured distributions reviewed by a person |
| K4 | **A missing environment variable exposes profiles to students** | Low | Severe | Already closed: `NEVER_STUDENT_ANALYZERS` is a code floor |
| K5 | **Scope creep back toward detection** | Medium | Destroys the defensibility | S7, S8, S9 are rejected in a committed document; this review restates them |
| K6 | **SAR arrives before an answer exists** | Medium | Compliance exposure | R1 blocks stage 2 |
| K7 | **Second-language writers over-flagged** | Medium | Equity harm concentrated on the least able to challenge | S6 deferred for exactly this; the gating layer excludes non-comparable priors |
| K8 | **Audit F1 ships to an examiner** | Certain if unfixed | Reputational — the first screen is visibly broken | Fix before anything else (§12) |

---

## 8. Rollout strategy

The staged ladder already exists in `10-assessment-architecture.md` §15.8.
Nothing here changes it.

| Stage | Configuration | Sees it | Gate to leave |
|---|---|---|---|
| **1 — off** *(today)* | `writing_profile` absent from `ASSESSMENT_ANALYZERS` | Nothing measured | R1 answered |
| **2 — dark** | on the roster **and** in `ASSESSMENT_DARK_ANALYZERS` | Nobody | One teaching term, §15.7 distributions reviewed by a person (R2) |
| **3 — teacher** | `ASSESSMENT_TEACHER_ONLY_ANALYZERS` + `CONSISTENCY_ANALYTICS_ENABLED=true` | Teachers, administrators | — |

There is no stage 4. Rollback at any point is removing the name from
`ASSESSMENT_ANALYZERS`: profiles stop being written, stored ones become inert,
comparisons answer "no baseline". No data loss, no migration to reverse.

**Consequence for scheduling: the surface can be built at stage 1, but it
cannot be honestly demonstrated until stage 3.** Build it behind the same
capability check the endpoint uses, and it renders the 503 state until the
deployment is promoted.

---

## 9. Testing strategy

| Layer | What is tested | Why |
|---|---|---|
| Existing backend | Already covered — gating, exclusion reasons, null baselines, audience filtering | No new backend code |
| **Wording tests** | The rendered surface contains none of: "AI", "generated", "plagiar", "cheat", "suspicious", "risk", "likely", "probability" | Same technique as the leaderboard's no-tier test, which reads rendered text |
| **Absence tests** | `no baseline yet` renders where n is below the floor; never `0`, never "consistent" | The project's rule 32, at the level of a measure |
| **503 vs empty** | A disabled deployment renders "not enabled here", not "nothing found" | Only one of those is a fact about the student |
| **No-composite test** | No element renders a single number derived from more than one measure | Structural guard against the thing C1 forbids |
| **No-ranking test** | The surface exposes no sortable list of students | §4.2 |
| Accessibility | Both text panes readable as prose; overlap spans listed beneath | The `AnnotatedAnswer` precedent |
| Manual | One teacher walkthrough against real stage-2 data before promotion | Decision 14's "reviewed by a person" |

---

## 10. Dissertation and evaluation implications

This is where the recommendation is strongest, and it cuts against building a
detector.

**An AI-detection engine would be an evaluation liability.** It cannot be
validated: there is no ground-truth corpus of known-clean and known-assisted
submissions from this cohort, no baseline is known clean, and at 150–250 words
the statistics are unreliable — the three reasons PROJECT_PLAN §1.3b already
records for ruling it out. A dissertation that ships an unvalidatable classifier
invites the examiner's first question and has no answer to it.

**Writing consistency is defensible on exactly the ground the detector is
not.** It measures learning trajectories — vocabulary range, sentence
complexity, target coverage, mechanical accuracy over time — which is the
platform's actual research question: *does gamified practice improve academic
graph description?* The same measures that would be weak evidence of
authorship are strong evidence of learning.

Three concrete implications:

1. **Stage 2 data is the evaluation dataset.** A term of dark collection
   produces per-student trajectories across every measure. That is the
   longitudinal evidence chapter, and it exists whether or not stage 3 is ever
   reached.
2. **The rejection is itself a contribution.** A documented design review that
   evaluates nine signals and rejects three on stated grounds — authorship
   attribution, surveillance escalation, collusion detection — is a stronger
   ethics chapter than an implemented detector. It demonstrates judgement.
3. **The reflexivity finding is publishable.** K2 — that the platform's own
   feedback causes the vocabulary shift it later measures — is a real
   methodological result about instrumented learning platforms, and this system
   is instrumented to demonstrate it.

---

## 11. Recommended implementation order

### Phase A — Audit fixes *(recommended first; see §12)*
1. F1 · avatar migration — four files onto `AvatarCharacter`
2. F2 · locked-and-selected made unrepresentable
3. F3 · zero-denominator guard
4. F4 · the three empty cards, and the false achievement empty state
5. F6 · one chip touch rule; retire the duplicate `initials()`
6. F5 · disabled CTA
7. **F11 · `<h1>` on the auth shell** — add to the list; WCAG
8. F10 · retry once, never on 4xx

### Phase B — Deployment (original Sprint 14)
9. Production Dockerfiles and compose hardening
10. Hosting guides · API docs · README
11. Automated contrast run, keyboard traversal, the audit items §6 of the audit deferred

### Phase C — Integrity, non-engineering first
12. **R1** — the SAR answer, written down *(blocks everything after)*
13. **R2** — the measurement protocol for stage 2
14. Promote to stage 2. Collect for one teaching term.

### Phase D — The surface *(buildable in parallel with C, demonstrable only after)*
15. The Integrity tab against the existing endpoints, behind the capability check
16. Wording, absence, 503-vs-empty, no-composite and no-ranking tests
17. Decision 13's feedback-beside-the-change panel

### Explicitly not scheduled
Behaviour telemetry (S8), function-word distance (S7), cross-student overlap
(S9), and any composite, index or flag.

---

## 12. Should the audit fixes come before Sprint 19?

**Yes — unambiguously, and the reasoning is not about effort.**

1. **Two are P0 and one is on the first screen a new user meets.** The avatar
   picker at registration is six identical grey circles. Any evaluator,
   examiner or pilot teacher meets that defect before anything else in the
   product.
2. **Phase A is roughly a day. Phase C's first gate is a term.** The
   integrity work cannot be finished sooner regardless of when it starts —
   stage 2 needs a teaching term of data before stage 3 is defensible. There is
   no schedule in which delaying the fixes buys anything.
3. **The fixes remove duplication the integrity surface would otherwise
   inherit.** F1 and F6 are half-migrations. A new teacher-facing screen built
   before them would have to choose which avatar system and which chip rule to
   use, and would deepen both forks.
4. **The integrity surface is not demonstrable yet.** Built today it renders
   its 503 state on every deployment. Fixing a visibly broken registration flow
   is worth more this week than a screen nobody can see output from.

**Recommendation: Phase A, then Phase B, then R1 and R2 in parallel with
whatever follows, promote to stage 2 as early as possible so the term-long
clock starts, and build the surface while it runs.**

The single highest-value action available today is **promoting to stage 2**,
because it is the only task whose cost is measured in months and it is blocked
on one written decision rather than on any code.
