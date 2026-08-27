# Sprint 22 Design Review — Assignment surfaces

Required before implementation by the standing frontend directive. The schema
and the API are already built (`sprint-22-assignments.md`); this is about what
a teacher and a student actually see.

## 1. The problem in the user's words

> *"Teacher graph create করা একটা ঝামেলা — মূল উদ্দেশ্য হওয়া উচিত টিচার অফলাইনে
> স্লাইডে graph দেখাবে, স্টুডেন্ট সিস্টেমে তার description verify করবে।"*

The graph still has to exist in the system — marking needs the target
vocabulary and the chart facts, and neither can be read off a slide. What was
missing is everything *around* it. A teacher had a content library and no way
to say "Section A, this one, by Friday", so every screen answered "what
exists?" when the question in the room was "who has done it?"

## 2. What each screen has to answer

| Screen | The one question |
|---|---|
| `/teacher/assignments` | Which of the things I set are not done yet? |
| `/teacher/assignments/[id]` | **Who** has not done this one? |
| Set-work dialog | How fast can I set this and get back to teaching? |
| Student dashboard | Is anything due? |
| Practice library | Which of these did my teacher actually ask for? |

Nothing on this list is "list the assignments". A list is the shape, not the
question, and building for the shape is how the last audit ended up with
screens ranked weakest-first.

## 3. Wireframes

### 3.1 `/teacher/assignments` — 390px

```
┌ Work you set ───────────────────────────┐
│ Show the graph in your lesson. Set it   │
│ here. Read what they wrote.             │
│                          [ + Set work ] │
├─────────────────────────────────────────┤
│ [All sections] [201·A] [201·B] [305·C]  │   ← chips, 44px, horizontally
├─────────────────────────────────────────┤      scrollable, never wrapping
│ ┌─────────────────────────────────────┐ │      the page
│ │ Week 3 · rainfall     ⟨Due Friday⟩ │ │
│ │ Rainfall by month · English 201·A   │ │
│ │                                     │ │
│ │ ████████████░░░░░░░░░░░░            │ │   ← the loudest thing on the card
│ │ 12 of 30 have submitted             │ │
│ │                                     │ │
│ │ 18 have not started            →    │ │   ← the whole card is the target
│ └─────────────────────────────────────┘ │
│ ┌─────────────────────────────────────┐ │
│ │ Week 2 · population   ⟨No deadline⟩ │ │
│ │ …                                   │ │
└─────────────────────────────────────────┘
```

At `md` and up the cards go two across; at `xl`, three. The card content does
not reflow — only the column count changes — so the same scan works on every
width.

**Why a progress bar and not a percentage.** "40%" is a number a teacher has
to convert back into people before it means anything. A bar with *"12 of 30"*
under it is already people, and it carries the denominator that rule 35 exists
to protect: a class where half the students never started must not be able to
read as a healthy figure.

**Why "18 have not started" is the call to action** rather than "12 have
submitted". The twelve need nothing. The eighteen are the reason the teacher
opened the page.

### 3.2 `/teacher/assignments/[id]` — the progress screen

```
┌──────────────────────────────────────────────────────────────┐
│ ← Work you set                                               │
│ Week 3 · rainfall                                [ Edit ]    │
│ Rainfall by month · English 201, Section A · Due Fri 3 Oct   │
├───────────────────────────────────────┬──────────────────────┤
│ ┌ Not started · 18 ─────────────────┐ │ ┌ This assignment ─┐ │
│ │ Ayesha Rahman                     │ │ │ 12 of 30         │ │
│ │ Karim Uddin                       │ │ │ submitted        │ │
│ │ …                                 │ │ │                  │ │
│ └───────────────────────────────────┘ │ │ 9 marked         │ │
│ ┌ Submitted · 12 ───────────────────┐ │ │ 68% average      │ │
│ │ Nusrat Jahan    82  Marked      → │ │ │ 2 late           │ │
│ │ Rafi Hasan       —  Draft       → │ │ └──────────────────┘ │
│ │ Imran Kabir     55  Marked  Late→ │ │                      │
│ └───────────────────────────────────┘ │                      │
└───────────────────────────────────────┴──────────────────────┘
```

**Not started comes first.** This is the directive's rule — students needing
attention before raw tables — and it is also just true: the submitted list is
a record, the not-started list is a task.

**`—`, never `0`.** A draft that has not been marked has no score. Rendering
it as zero would sort a student who is mid-attempt below one who genuinely
struggled, which rule 32 forbids on the backend and which the UI must not
reintroduce.

**"Late" is a quiet outline chip, never red.** The deadline records lateness
and changes nothing about the mark. A red badge would tell a teacher, at a
glance, to treat it as a penalty — which the product deliberately does not
implement. Its accessible name says so: *"Submitted after the deadline. This
does not affect the score."*

### 3.3 The set-work dialog

Four fields, and two of them are prefilled:

```
┌ Set work ─────────────────────────────┐
│ Section    [ English 201, Section A ▾]│
│ Graph      [ Rainfall by month      ▾]│
│ Title      [ Rainfall by month       ]│  ← prefilled from the graph
│ Due        [ 2026-09-05 ] (optional)  │
│ ▸ Add instructions                    │  ← collapsed; most work needs none
│                                       │
│              [ Cancel ]  [ Set work ] │
└───────────────────────────────────────┘
```

The title prefills from the graph the moment one is chosen, and stops
prefilling once the teacher types — so the common path is *pick, pick, done*
and the custom path is never fought. Only published graphs appear: the backend
refuses a draft, and a picker that offers something the server will reject is
a trap.

### 3.4 Where it lives in the navigation

The teacher nav grows to six: **Dashboard · Assignments · Submissions ·
Graphs · Vocabulary · Analytics.**

Six across a 390px bottom bar is 65px each — above the 44px floor, and the
existing bar is already 56px tall. The short labels are what make it legible:
*Home · Assign · Work · Graphs · Words · Data*. "Assign" is deliberately a
**verb** where "Work" is a noun; two adjacent noun labels ("Tasks", "Work")
were the version that could not be told apart at a glance.

The alternative — reaching assignments only from the dashboard — was rejected.
"Who has submitted?" is the question a teacher opens the app to answer, and a
destination reached through another screen is a destination they stop using.

## 4. Accessibility decisions

- The progress bar is a real `role="progressbar"` with
  `aria-valuenow/min/max` and an `aria-label` reading *"12 of 30 students have
  submitted"* — the figure, not the percentage, because that is what the
  sighted reader gets too.
- Each assignment card is one link wrapping the whole card, not a card with a
  link inside it: one tab stop, one 44px+ target, no nested interactive
  elements for a screen reader to announce twice.
- The section filter is a `radiogroup`, because it is one choice out of a set
  — not a row of buttons that happen to look selected.
- "Not started" and "Submitted" are `h2`-level regions with counts in the
  heading, so a screen reader user hears *"Not started, 18"* without reading
  the list.
- The deadline chip's colour never carries meaning alone: the text says "Due
  Friday" or "Closed", and the chip only tints it.

## 5. Tradeoffs taken

**No bulk actions.** Setting the same graph for four sections at once is a
real want, and it is four taps instead of one. It also needs a multi-select
that doubles the dialog and an error state for "it worked for two of your four
sections". Deferred until a teacher asks for it with four sections in front of
them.

**No per-student reminder.** The not-started list is names, not a "nudge"
button. Sending a student a message is a whole notification system, and
inventing half of one behind a button is worse than not having it.

**No lateness anywhere the student can see it.** The student's own screens
never render "late". The deadline shows before submission, as a plan; after
it, the result screen is about what they wrote. Marking a piece of work late
on the screen a student reads their feedback on is the same humiliation
FR-7.6 rules out of the leaderboard.

**The progress screen is live, not cached.** Same reason as rule 36: a stale
count is stale exactly in the minutes after a lesson, which is when it is
read.

## 6. Order of work

1. `lib/api/assignments.ts`, query keys, types — *regenerated already*
2. Teacher: the list, the progress screen, the set-work dialog, the nav
3. Student: "due" on the dashboard, assignment cards in the practice library,
   `assignment_id` threaded through starting an attempt
4. Docs
