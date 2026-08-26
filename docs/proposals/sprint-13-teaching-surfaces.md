# Sprint 13 Design Review — The Teaching Surfaces

**Status: design review, pre-implementation.** Produced before any Sprint 13
component was written, as the frontend design directive requires: wireframes,
layout rationale, component hierarchy, UX decisions, mobile behaviour,
accessibility decisions and tradeoffs.

**Reviewed against:** Sprints 11 and 12 as merged (`b2da889`), the analytics
and leaderboard schemas in `frontend/types/api.ts`, and
`docs/architecture/04-api-design.md`.

**Scope:** teacher dashboard · analytics · submission review · graph manager ·
vocabulary manager · export UI · leaderboard (4 scopes) · admin users.

---

## 0. Executive summary

The student's half of the product is a *practice loop*: one graph, one answer,
one mark, and a reward that makes the next attempt attractive. The staff half
is not a loop at all. A teacher opens this product between lessons with one
question — **who needs me, and what do I say to them** — and the API already
answers it. The risk in this sprint is not missing data. It is building seven
screens that each present a correct table and leave that question unanswered.

Six decisions follow from that, and they shape everything below.

**D1 — The teacher's landing screen is a triage list, not a statistics page.**
Named students first, ranked by what a teacher can act on today. Class figures
sit *beneath* the names, as the context that explains them. Statistics-first is
the default this directive rules out, and it is also simply worse: an average
of 61 tells a teacher nothing about which lesson to plan.

**D2 — Every analytics card states a question, an answer and an
interpretation, and the interpretation is derived, never written.** It is a
pure function of the data with its own tests, for the same reason
`feedback.py` is: a caption that says "scores are improving" beside a flat line
is worse than no caption. Where the data cannot support a claim, the card says
so in those words.

**D3 — Absence is a first-class value, everywhere.** `average_final_score` is
nullable and `TrendPoint` carries the `submission_count` it was taken over.
A missing average renders as `—`, never `0`; a trend line **breaks** across a
day nobody submitted rather than drawing a line through it. This is already the
platform's rule (PROJECT_PLAN §1.4 decision 10, CLAUDE.md rule 32) and it is
the single most likely thing to be lost when a chart is wired up quickly.

**D4 — The leaderboard is the one staff-adjacent surface that must feel like a
game.** Podium, drawn characters, level rings, and the student's own rank
pinned where they can always see it. And no reward tier, ever — FR-7.6. A
hammer beside a name in front of the cohort is the humiliation the whole reward
design was built to avoid.

**D5 — Product invariants become interface affordances rather than error
messages.** A graph with no required target term cannot be published (rule 12),
so the publish control is disabled *with the reason attached*, not enabled and
then refused. A vocabulary term is deactivated, never deleted (rule 10), so the
control says "Deactivate" and the deactivated terms stay visible behind a
filter. An export format the deployment cannot produce (rule 38) is disabled
from `GET /reports/capabilities`, not discovered through a 503.

**D6 — Dense data gets two presentations, not one responsive compromise.**
Below `md` a roster is a list of cards; at `md` and above it is a table with
grouped columns. Same component, same data, same sort. A table squeezed into
390px is the horizontal scroll the directive forbids, and a stack of cards on a
27-inch monitor wastes the comparison a teacher came for.

---

## 1. What the API can truthfully say

Everything below is already served. No backend work is in this sprint. The
column that matters is the third one.

| Endpoint | Gives | What a teacher can be told
|---|---|---|
| `GET /analytics/class/{id}` | `enrolled_student_count`, `active_student_count`, averages, `reward_tier_distribution`, `engagement`, `trend[]`, `students[]` | Who has not started, how the class is moving, and every student's own line |
| `GET /analytics/trends` | `points[]` with `date`, `submission_count`, two averages | Whether scores are improving — and where the evidence is missing |
| `GET /analytics/vocabulary-usage` | `most_used[]`, `least_used[]`, `unused_term_count` | **Which curated words nobody reached for.** Invisible to any report built from what students *did* write |
| `GET /assessment/issues` | Issue frequencies per class | The mistakes worth a lesson |
| `GET /assessment/scores`, `/trend/{analyzer}` | Per-analyzer class scores over time | Whether spelling, sentences or graph accuracy is the weak axis |
| `GET /leaderboard`, `/leaderboard/me` | Ranked entries + the caller's own rank | Standing, including from outside the visible page |
| `GET /reports/capabilities` | Which of CSV/Excel/PDF this deployment can build | Which buttons may be enabled |

Two fields deserve singling out because the interface is the only place their
value is realised:

- **`unused_term_count`.** A report of the vocabulary students used is a report
  of the syllabus that landed. This is the other half — the syllabus that did
  not. It is the strongest teaching signal in the API and it gets a card of its
  own, not a row in a table.
- **`engagement.inactive_student_count`.** Counted against *enrolment*
  (rule 35), so "half the class never started" cannot hide behind "everyone who
  practised, practised a lot". It is the first number on the teacher's screen.

### 1.1 The attention signal, defined

There is no "students at risk" endpoint, and this sprint does not add one. The
signal is derived in `lib/insights/attention.ts` from the roster the class
report already returns — a pure function, unit-tested, so the rule is
inspectable rather than buried in a component.

```
neverStarted : submission_count === 0
struggling   : average_final_score !== null && average_final_score < 50
goneQuiet    : submission_count > 0 && days(now − last_submission_at) >= 7
```

Three properties of that definition are deliberate:

1. **A student appears in exactly one group** — the first they match, in the
   order above. A list that names the same person three times reads as three
   problems.
2. **The order is by what the evidence supports acting on.** A student who
   never started leaves nothing to teach from and needs a different
   intervention entirely. A struggling student comes with their own writing
   attached, so a teacher can open it and respond today. A quiet student is an
   absence, which is real but the least specific.
3. **`< 50` is not invented.** It is the platform's own hammer boundary
   (CLAUDE.md rule 5). A second, unrelated threshold on a teacher's screen
   would rank students against a rule the marking never used.

And one thing the definition refuses: **a student with no average is never
"struggling"**. `null` is not a low score (rule 32). They are in *never
started*, which is a different sentence to a different student.

---

## 2. Information architecture

The teacher's navigation already exists in `lib/nav.ts` and its order was
chosen in Sprint 11. This review confirms it rather than changing it:

```
Dashboard · Submissions · Graphs · Vocabulary · Analytics   (+ Users, admin)
   who        their work    what     the words     the class
  needs me                 they                     over time
                        practise on
```

Frequency descending, left to right. Analytics sits fifth deliberately — it is
the screen a teacher visits weekly, not the screen they land on. The dashboard
carries the two figures they need daily so that the trip is unnecessary most
days.

Two routes are *not* added:

- **No `/teacher/classes`.** Class selection is a control in the page header,
  present on every teaching screen and remembered between them. A teacher with
  one class should never navigate to choose it; a teacher with four switches in
  place without losing the screen they were reading.
- **No `/teacher/exports`.** Export is an action on the thing being exported,
  offered where the data is, not a destination with a form that asks which data
  you meant. The report *history* is a panel inside analytics, because that is
  where a teacher looks when a file did not arrive.

---

## 3. Wireframes

### 3.1 Teacher dashboard — `/teacher/dashboard`

The whole of D1. What is happening → why it matters → what to do next, all
above the fold.

```
DESKTOP (≥1024px)
┌──────────────────────────────────────────────────────────────────────────┐
│ Teaching                                   [ Class 10B ▾ ] [ Last 30 days ▾]│
│ 31 enrolled · 18 practised this month                                    │
├──────────────────────────────────────────────────────────────────────────┤
│ ┌── 13 students need you ──────────────────────────┐ ┌── This month ───┐ │
│ │                                                   │ │ Participation   │ │
│ │ ● NOT STARTED · 9                                 │ │      58%        │ │
│ │   ┌───────────────────────────────────────────┐   │ │ ▓▓▓▓▓▓░░░░      │ │
│ │   │ (◕) Amina Yusuf      no marked work       │   │ │ 18 of 31        │ │
│ │   │ (◕) Daniel Osei      no marked work       │   │ ├─────────────────┤ │
│ │   │ (◕) …6 more          [ Show all ]         │   │ │ Average score   │ │
│ │   └───────────────────────────────────────────┘   │ │      61         │ │
│ │                                                   │ │ ╭─╮   ╭╮        │ │
│ │ ● FINDING IT HARD · 3                             │ │ ╯ ╰───╯╰──      │ │
│ │   ┌───────────────────────────────────────────┐   │ │ 30-day trend    │ │
│ │   │ (◕) Priya Nair    avg 41 · 4 attempts  →  │   │ ├─────────────────┤ │
│ │   │ (◕) Tom Becker    avg 47 · 2 attempts  →  │   │ │ Vocabulary      │ │
│ │   └───────────────────────────────────────────┘   │ │      54%        │ │
│ │                                                   │ │ of target terms │ │
│ │ ● GONE QUIET · 1                                  │ └─────────────────┘ │
│ │   ┌───────────────────────────────────────────┐   │                     │
│ │   │ (◕) Lena Fischer  last worked 12 days ago │   │                     │
│ │   └───────────────────────────────────────────┘   │                     │
│ └───────────────────────────────────────────────────┘                     │
├──────────────────────────────────────────────────────────────────────────┤
│ ┌── Worth a lesson ─────────────────┐ ┌── Words nobody used ───────────┐ │
│ │ Most frequent issues, this class  │ │ 7 of 34 target terms went      │ │
│ │ ▸ Comparative form        23      │ │ unused this month              │ │
│ │ ▸ Missing units on axis   18      │ │  plateau · surge · marginally  │ │
│ │ ▸ Sentence run-on         11      │ │  …4 more                       │ │
│ │              [ Open analytics → ] │ │        [ See vocabulary → ]    │ │
│ └───────────────────────────────────┘ └────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────┘
```

**Layout rationale.** The attention list takes two thirds of the width and the
first screen; the class figures take one third and are deliberately *quiet* —
no card borders competing with the list, one number each, a sparkline rather
than a chart. A teacher reads left, gets names, and acts. The figures answer
"is this normal?" without ever being the thing that greets them.

Each attention group is a labelled section, not a colour band. `● NOT STARTED ·
9` states the count and the reason in words; the dot repeats it in colour for
speed, and carries no information of its own (NFR-4.6).

Each row is a link to that student's submissions, pre-filtered. The `→` is the
affordance; the whole row is the target. "Finding it hard" rows carry the
evidence — `avg 41 · 4 attempts` — because the teacher's next action is to read
one of those four.

**Wording.** "Finding it hard", not "at risk", "struggling" or "low
performers". These names are read aloud in staff rooms and occasionally over a
teacher's shoulder by the student in question. The same instinct that governs
the hammer tier governs this list.

```
MOBILE (390px)
┌────────────────────────────┐
│ Teaching                   │
│ Class 10B ▾ · 30 days ▾    │
│ 31 enrolled · 18 practised │
├────────────────────────────┤
│ 58% ▓▓▓▓▓▓░░░ participation│   ← one strip, three figures,
│ 61 avg · 54% vocabulary    │      no cards
├────────────────────────────┤
│ 13 students need you       │
│                            │
│ NOT STARTED · 9            │
│ ┌────────────────────────┐ │
│ │ (◕) Amina Yusuf      → │ │   56px rows
│ │ (◕) Daniel Osei      → │ │
│ │ [ Show all 9 ]         │ │
│ └────────────────────────┘ │
│ FINDING IT HARD · 3        │
│ ┌────────────────────────┐ │
│ │ (◕) Priya Nair       → │ │
│ │     avg 41 · 4 attempts│ │
│ └────────────────────────┘ │
│ …                          │
├────────────────────────────┤
│ [ Worth a lesson       ▸ ] │   ← collapsed
│ [ Words nobody used    ▸ ] │
└────────────────────────────┘
   ▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁
   Home  Work  Graphs  ⋯      bottom nav (Sprint 11)
```

On a phone the three class figures collapse into a single strip above the
names — still first in the reading order, still answering "what is happening",
but costing one line instead of a column. The two lower cards become
progressive disclosure: their headline is the finding, and the detail is one
tap away.

### 3.2 Analytics — `/teacher/analytics`

D2, applied consistently. Every card is a question.

```
DESKTOP
┌──────────────────────────────────────────────────────────────────────────┐
│ Analytics            [ Class 10B ▾ ] [ 1 Aug – 26 Aug ▾ ]  [ Export ▾ ]  │
│ Computed now, from 214 marked submissions.                               │
├──────────────────────────────────────────────────────────────────────────┤
│ ┌── Is the class practising? ──────────────────────────────────────────┐ │
│ │  18 of 31 students                                                   │ │
│ │  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░                                      │ │
│ │  13 enrolled students have no marked work in this period. Those who  │ │
│ │  did practise averaged 11.9 attempts each.                           │ │
│ └──────────────────────────────────────────────────────────────────────┘ │
│ ┌── Are scores improving? ─────────────────────────────────────────────┐ │
│ │  100 ┤                                          ╭──╮                 │ │
│ │      │            ╭────╮        ┆ ┆            ╭╯  ╰─                │ │
│ │   50 ┤    ╭───────╯    ╰────────┆ ┆────────────╯                     │ │
│ │      │────╯                     ┆ ┆  ← no submissions, 12–14 Aug     │ │
│ │    0 ┼────┬────┬────┬────┬────┬─┴─┴─┬────┬────┬────                  │ │
│ │  Average final score, by day. The gap is three days nobody           │ │
│ │  submitted — the line breaks rather than guessing across it.         │ │
│ │  Up 9 points from the first week to the last.       [ Data table ▾ ] │ │
│ └──────────────────────────────────────────────────────────────────────┘ │
│ ┌── Which words are they reaching for? ──┐ ┌── And which never? ───────┐ │
│ │ rise           ████████████  84        │ │ 7 of 34 terms unused      │ │
│ │ increase       ██████████    71        │ │                           │ │
│ │ fall           ████████      55        │ │ plateau      · surge      │ │
│ │ significantly  █████         31        │ │ marginally   · levelled   │ │
│ │ …                                      │ │ off · trough · steadily   │ │
│ │ Counted from what the marker detected, │ │                           │ │
│ │ not a re-scan of the answers.          │ │ Seven curated terms no    │ │
│ │                                        │ │ student used once. Worth  │ │
│ │                                        │ │ a lesson before the next  │ │
│ │                                        │ │ set of graphs.            │ │
│ └────────────────────────────────────────┘ └───────────────────────────┘ │
│ ┌── Where are the marks landing? ──────────────────────────────────────┐ │
│ │  ▓▓▓▓▓▓▓▓▓ 31%  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓ 44%  ▓▓▓▓▓ 15%  ▓▓▓ 10%              │ │
│ │  Crown        Flower           Steady      Practice                  │ │
│ │  Distribution across 214 marked attempts, not across students.       │ │
│ └──────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────┘
```

**Why the interpretation line is generated.** "Up 9 points from the first week
to the last" is computed by comparing the first and last non-empty windows,
and it is *suppressed* when there are fewer than two windows with data — in
which case the card says "Not enough marked work yet to show a direction."
`lib/insights/narrate.ts` owns those sentences and is unit-tested against flat,
rising, falling, sparse and empty series. This is CLAUDE.md rule 17 applied to
a teacher instead of a student: never claim something that did not happen, in
either direction.

**Why the tier card says "not across students".** A tier distribution is the
one figure on this screen that could be misread as a ranking of people. It
counts *attempts*, and the caption says so. Per-student tier counts appear
nowhere on a shared screen (FR-7.6).

Mobile: one card per row, charts at `h-56`, the two vocabulary cards stack with
"which never" first — it is the shorter card and the stronger finding.

### 3.3 Submission review — `/teacher/submissions`

```
DESKTOP — queue                          DETAIL (drill-in, own route)
┌────────────────────────────────┐      ┌─────────────────────────────────┐
│ Submissions      [Class ▾][⇩]  │      │ ← All submissions               │
│ [All][Scored][Failed][Draft]   │      │ Priya Nair · Rainfall by month  │
├────────────────────────────────┤      │ Handwritten · marked 2 days ago │
│ ┌────────────────────────────┐ │      ├─────────────────────────────────┤
│ │(◕) Priya Nair          41  │ │      │ ┌── 41 ──┐ ┌ Vocabulary 4/12  ┐ │
│ │    Rainfall by month       │ │      │ │  ring  │ │ Writing 58       │ │
│ │    ✍ handwritten · 2d ago  │ │      │ └────────┘ └──────────────────┘ │
│ ├────────────────────────────┤ │      ├─────────────────────────────────┤
│ │(◕) Tom Becker          —   │ │      │ What she wrote                  │
│ │    Sales Q3                │ │      │ ┌─────────────────────────────┐ │
│ │    ⌨ typed · recognition   │ │      │ │ The graph show a rise in    │ │
│ │      failed · 3d ago       │ │      │ │ ~~~~ (grammar)              │ │
│ └────────────────────────────┘ │      │ │ rainfall over the perid …   │ │
│                                │      │ │           ~~~~ (spelling)   │ │
│ 1–20 of 214      [ ‹ 1 2 3 › ] │      │ └─────────────────────────────┘ │
└────────────────────────────────┘      │ 6 issues · 3 spelling, 2 …      │
                                        └─────────────────────────────────┘
```

The queue rows carry the score, the graph, the input method and the age —
enough to choose which to open without opening any. A `—` where a score would
be is a submission that was never marked; it is not a zero, and the row says
why (`recognition failed`). Rule 20 is visible here: a failed handwriting
submission still shows `✍ handwritten` even after the student typed into it.

The detail screen reuses `HighlightedAnswer` from the student's result page,
with the assessment's issue spans layered on top of the detected vocabulary.
Two annotation layers over one text is the only genuinely new interaction in
this sprint; the fallback when they overlap is that vocabulary wins the
underline and the issue is listed beneath, because the marked-up text must stay
readable as *the student's writing*.

### 3.4 Graph manager — `/teacher/graphs`

```
┌──────────────────────────────────────────────────────────────┐
│ Graphs                              [ + New graph ]          │
│ [All][Published][Draft]                                      │
├──────────────────────────────────────────────────────────────┤
│ ┌──────────────────────┐ ┌──────────────────────┐            │
│ │ ╭╮  ╭─╮              │ │  ▁▃▅▇                │            │
│ │ ╯╰──╯ ╰─  (preview)  │ │  ▁▃▅▇  (preview)     │            │
│ │ Rainfall by month    │ │ Sales Q3             │            │
│ │ ● Published · 12 req │ │ ○ Draft · 0 required │            │
│ │   target terms       │ │   target terms       │            │
│ │ 48 attempts · avg 63 │ │ ⚠ Add at least one   │            │
│ │            [ Edit ]  │ │   required term to   │            │
│ │                      │ │   publish  [ Edit ]  │            │
│ └──────────────────────┘ └──────────────────────┘            │
└──────────────────────────────────────────────────────────────┘
```

Cards, not rows, because a graph *is* a picture — the live Chart.js preview is
the fastest identifier and the existing `GraphChart` renders it for free. D5 in
one frame: the draft card carries the publish precondition as a sentence on the
card, before the teacher has tried and been refused.

### 3.5 Vocabulary manager — `/teacher/vocabulary`

Seven categories as the primary axis, because that is how the syllabus is
organised and how the marker groups its feedback.

```
┌──────────────────────────────────────────────────────────────┐
│ Vocabulary          [ + Add term ]  [ Show deactivated ○ ]   │
│ [ All 34 ][ Trend 9 ][ Comparison 6 ][ Degree 5 ] …          │
├──────────────────────────────────────────────────────────────┤
│ TREND · 9 terms                                              │
│ ┌──────────────────────────────────────────────────────────┐ │
│ │ increase      lemma increase        84 uses    ⋯          │ │
│ │ plateau       lemma plateau      ⚠ 0 uses      ⋯          │ │
│ │ level off     phrase · lemma level off  3 uses ⋯          │ │
│ │ soar          lemma soar   · deactivated       ⋯          │ │
│ └──────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

Three invariants are visible in that sketch. `phrase` is shown as a **derived
badge**, never an editable control (rule 13). The lemma is displayed on every
row because a hand-set lemma must not be silently re-derived when the term is
edited — the edit form warns when a change to the term would alter a lemma the
teacher set by hand. And `soar · deactivated` is still listed, greyed, with
"Reactivate" in its menu: terms are soft-deleted because historical scores
point at them (rule 10), and a manager that hides them makes an irreversible
action look like a deletion.

`⚠ 0 uses` joins this screen to the analytics finding — the same fact, at the
place where a teacher can do something about it.

### 3.6 Leaderboard — `/leaderboard` (student-facing)

D4. This one is allowed to be loud.

```
MOBILE (390px)                          DESKTOP adds ranks 4–20 in two columns
┌────────────────────────────┐
│ Leaderboard                │
│ [Global][Class][Week][Month]│  ← 4 scopes, chips
│ Week of 24–30 Aug          │
├────────────────────────────┤
│         ╭───╮              │
│    ╭───╮│ ◕ │╭───╮         │   podium: drawn characters,
│    │ ◕ ││ 1 ││ ◕ │         │   gold / silver / bronze rings
│    │ 2 │╰───╯│ 3 │         │
│    ╰───╯     ╰───╯         │
│  Sara     Amir     Joy     │
│  1,240    1,480    980 XP  │
├────────────────────────────┤
│  4 (◕) Daniel      920 XP  │   48px rows
│  5 (◕) Lena        870 XP  │
│  6 (◕) Tom         840 XP  │
│  …                         │
├════════════════════════════┤
│ ▸ 14 (◕) You       410 XP  │   ← sticky, always visible
│   Level 6 · 60 XP to rank 13│
└────────────────────────────┘
```

The sticky "you" bar is the single most important element: `GET
/leaderboard/me` returns the caller's rank even when it falls outside the
visible page, and a board that requires a student to scroll to find themselves
— or worse, cannot show them at all — is demotivating in exactly the way this
platform is trying not to be. The distance to the next rank is the motivational
payload; it is computed from the entry above and is omitted, not faked, when
the student is rank 1 or unranked.

**No reward tier appears anywhere on this screen** (rule 31, FR-7.6). What
appears is level, XP for the period, and rank. A student who has not practised
in the period is unranked, and the bar says "Practise once this week to join
the board" — an invitation, not an empty row.

The avatars are the drawn `AvatarCharacter` from Sprint 12, not
`avatar.image_url`: those SVGs have never existed in this repository, so a
board built on them would show twenty sets of initials.

### 3.7 Admin users — `/admin/users`

The most CRUD-shaped screen in the product, and the one most at risk of
becoming AdminLTE. It stays a list of people: name, role, class, last seen,
status — with the destructive controls behind a menu and confirmed by name.
Role changes are the only genuinely dangerous action, so the form refuses to
let an administrator remove their own admin role, in the browser, with the
reason stated rather than by disabling the control silently.

### 3.8 Export

Not a screen. A `[ Export ▾ ]` control in the analytics and submissions
headers, offering only the formats `GET /reports/capabilities` reports, with the
unavailable ones listed as disabled and labelled "not installed on this server"
(rule 38). Requesting one opens a small panel that polls the report row and
offers the download when it is ready — and it states, before the click, that
**a submission export carries scores and metadata, never the answers**
(rule 39). A teacher who expects the writing and opens a file without it will
report a bug otherwise.

---

## 4. Component hierarchy

New, in dependency order. Everything else is reused from Sprints 10–12.

```
lib/
  insights/
    attention.ts        pure: StudentRow[] → { neverStarted, struggling, goneQuiet }
    narrate.ts          pure: series/report → interpretation sentence | null
    format.ts (existing) extended with compact counts
  charts/
    series.ts           TrendPoint[] → ChartData, BREAKING at submission_count 0
  hooks/
    use-class-scope.ts  the class + date-range selection, shared across screens

components/
  insight/
    insight-card.tsx    question + answer + interpretation + optional chart slot
    metric.tsx          one figure, `—` when null, optional delta
    distribution-bar.tsx segmented bar with labels (tiers, participation)
    finding-list.tsx    ranked "worth a lesson" list
  teaching/
    scope-bar.tsx       class picker + date range, sticky, on every teaching screen
    attention-panel.tsx the triage list; groups from lib/insights/attention
    student-row.tsx     card < md, table row ≥ md (D6)
    roster-table.tsx    the ≥md presentation, sortable
  submissions/
    submission-queue.tsx / queue-row.tsx / status-chip.tsx
    assessment-detail.tsx / issue-list.tsx / annotated-answer.tsx
  graphs/
    graph-card.tsx / graph-form.tsx / target-picker.tsx
  vocabulary/
    category-tabs.tsx / term-row.tsx / term-form.tsx
  leaderboard/
    podium.tsx / rank-row.tsx / your-rank.tsx / scope-tabs.tsx
  admin/
    user-row.tsx / role-form.tsx
  ui/ (new primitives)
    table.tsx · select.tsx · dialog.tsx · switch.tsx · tooltip.tsx
```

`insight-card.tsx` is the load-bearing one. Every analytics section and both
lower dashboard cards are one, which is what keeps the "question / answer /
interpretation" contract from being a convention that erodes by the fourth
screen — a card without an interpretation slot filled is visibly incomplete.

---

## 5. Mobile behaviour

Reviewed at 390, 768 and desktop, as required.

| | 390px | 768px | ≥1024px |
|---|---|---|---|
| Teacher dashboard | figures strip → attention list → 2 collapsed cards | figures as 3 tiles, list full width | 2/3 list + 1/3 figures, cards side by side |
| Analytics | 1 card/row, charts `h-56` | 1 card/row, charts `h-64`, vocab cards paired | vocab cards paired, others full width |
| Submissions | cards, no table | cards | table ≥ md, detail in a right pane |
| Graphs | 1 card/row | 2 columns | 3 columns |
| Vocabulary | category chips scroll-x, terms as cards | table | table |
| Leaderboard | podium row + list + sticky you-bar | same, wider podium | podium + 2-column list |
| Admin users | cards | table | table |

**Rules that hold everywhere.** No horizontal page scroll at any width — wide
content scrolls inside its own container, which is already how
`ChartDataTable` behaves. Row targets are 56px on phones and never below 44px.
The `scope-bar` is sticky under the header on teaching screens, because a
teacher scrolling a roster who has forgotten which class they are looking at
has to scroll back to find out. The existing bottom navigation covers the
teacher's five destinations without change.

---

## 6. Accessibility decisions

- **The podium's DOM order is 1, 2, 3.** The visual arrangement puts first in
  the centre using CSS `order`; a screen reader and the tab sequence get rank
  order. Reversing this is the classic podium bug.
- **Every risk group is named, not coloured.** "Not started · 9" is the label;
  the dot adds speed for sighted users and carries nothing alone (NFR-4.6).
- **Every chart keeps its data table.** `ChartPanel` already provides the
  toggle and it is reused unchanged, so the analytics screen is fully readable
  without seeing a canvas.
- **Filter results announce.** Changing scope or date range updates a polite
  live region — "18 of 31 students, 214 submissions" — because otherwise the
  only feedback for a keyboard user is that numbers they cannot see have moved.
- **`—` is announced as absence.** As on the student dashboard, an em dash gets
  an `sr-only` "no marked work yet"; a bare `—` is read inconsistently across
  screen readers and silently by some.
- **Destructive confirmations are typed, not hovered.** Deactivating a term or
  changing a role confirms in a dialog with the name written out, focus trapped
  and restored, `Escape` cancelling.
- **Reduced motion.** The only new motion is the dashboard's staggered card
  reveal and the podium's rise; both already route through `Reveal` and the
  `useReducedMotion` hook from Sprint 12, which renders the settled state.
- **Focus visibility.** Existing `--ring` token, unchanged; the new sticky
  elements get `scroll-margin-top` so a focused row is never parked under the
  sticky scope bar.

---

## 7. Tradeoffs

**Live analytics means every filter change refetches (rule 36).** Accepted —
a cached figure is stale exactly when a teacher wants it. Mitigated with
TanStack's `placeholderData: keepPreviousData` so the previous numbers stay on
screen, dimmed, instead of collapsing to skeletons on every range change.

**The attention signal is derived in the browser.** It costs a rule that lives
in two places if the backend ever grows its own. The alternative — adding an
endpoint — is backend work in a frontend sprint, and the thresholds are
pedagogical judgements a deployment may want to differ on. Isolating it in one
tested pure module is the compromise; promoting it to the API is a Sprint 14
question.

**Two annotation layers over one answer text.** Vocabulary highlights and
assessment issues can overlap. Rather than build a span-merging algorithm,
vocabulary wins the inline treatment and issues are listed beneath with their
quoted fragment. Less elegant, but the student's writing stays legible, which
is the point of showing it.

**The podium costs vertical space on a phone.** About 140px before the first
ranked row. Accepted: this is the one screen whose job is to feel like a game,
and the sticky you-bar means the student's own standing is never the thing
pushed off screen.

**Seven screens in one sprint.** The mitigation is the build order below and
the discipline of pushing each increment — a design review is worth little if
the work implementing it is lost to a recycled container, which has already
happened twice in this project.

---

## 8. Build order

Each row is a commit, validated and pushed before the next begins.

| # | Increment | Why here |
|---|---|---|
| 1 | `lib/insights/*`, `lib/charts/series.ts` + tests | Pure, testable, everything depends on it |
| 2 | `ui/` primitives (table, select, dialog, switch, tooltip) | Shared by five screens |
| 3 | `insight/*` + `teaching/scope-bar` | The contract that keeps the cards honest |
| 4 | Teacher dashboard | The highest-value screen; proves 1–3 |
| 5 | Leaderboard | Independent of the teaching stack; unblocks students |
| 6 | Analytics + export control | Depends on 3 |
| 7 | Submission review + assessment detail | The largest surface |
| 8 | Graph manager, vocabulary manager | Authoring |
| 9 | Admin users | Smallest, and gated on the `ui/` work |
| 10 | Docs: `06-frontend-architecture.md` §9, PROJECT_PLAN | Record |
