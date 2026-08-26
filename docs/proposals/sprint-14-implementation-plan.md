# Sprint 14 — Implementation Plan

Written before any code was changed. Derived from
[`sprint-14-ui-audit.md`](./sprint-14-ui-audit.md), re-read against the source
at `864f78f`.

## 1. Affected screens

| Screen | Route | Findings |
|---|---|---|
| Registration | `/register` | F1 (picker), F2, F3/F11 |
| Login | `/login` | F11 |
| Forgot / reset password | `/forgot-password`, `/reset-password` | F11 |
| Profile | `/profile` | F1 (picker), F2 |
| Student dashboard | `/dashboard` | F1 (hero), F6 |
| Every authenticated page | header | F1 (`user-menu`) |
| Results | `/submissions/[id]` | F4, F6 |
| Practice library | `/practice` | F5 |
| Submissions queue | `/teacher/submissions` | F5 |
| Vocabulary manager | `/teacher/vocabulary` | F5 |
| Achievements | `/achievements` | F5 |
| Admin users | `/admin/users` | F5 |
| Leaderboard | `/leaderboard` | F5 (duplicate chip) |
| Settings | `/settings` | F6 (rubric card) |

## 2. Change inventory

**F1 — one avatar system.** Four call sites move to `AvatarCharacter`:
`avatars/avatar-picker.tsx`, `dashboard/hero-panel.tsx`, `layout/user-menu.tsx`,
and `results/result-view.tsx` (already correct). `components/ui/avatar.tsx`
keeps `Avatar`/`AvatarFallback` — the teacher rosters use initials
deliberately, and initials for a *name* are correct where the drawn character
is unavailable. **`AvatarImage` is removed entirely**, because every use of it
is a 404.

`AvatarCharacter` needs one addition: it renders a code, and the picker has an
`AvatarWithLock` whose `code` is already on the payload. No new API.

**F2 — locked and selected made unrepresentable.** The tile currently derives
`locked` from `is_unlocked` and reads `is_selected` independently, so both can
be true. Replace the two booleans with one derived state —
`selected | available | locked` — so the impossible pair has no representation.

**F3 / F11 — headings.** `CardTitle` gains an `as` prop. Each auth page renders
its title as `<h1>`. No layout change, no restructure.

**F4 — the zero denominator.** `vocabulary-panel.tsx:29` gets a branch: with no
required targets the sentence describes what *was* used rather than a ratio.

**F5 — one touch rule.** Extract the chip into `components/ui/chip.tsx` with a
44px floor until `sm:`. `FilterChips` composes it; the leaderboard's scope row
composes it. The duplicate implementation goes.

**F6 — empty states that cannot lie.**
- `achievement-strip` takes the attempt count and words the empty state from
  practice history, not from the achievement count.
- `feedback-panel` renders an empty state instead of a bare heading.
- `result-view`'s revisit card stops being full height.
- `settings-view`'s rubric card hides when the rubric is unavailable.

**Phase B — consistency.** After A: one `initials()`, one chip, one card radius
scale, one icon size per context. Audit by grep rather than by eye.

**Phase D — accessibility.** Re-measure sub-44px targets at 390px on every
screen; verify one `<h1>` per page; keyboard-traverse the changed components.

**Phase E — bundle.** Baseline recorded before the first change; compared after.

## 3. Risks

| # | Risk | Mitigation |
|---|---|---|
| R1 | `AvatarCharacter` is 6 fixed codes; a catalogue row added later renders a fallback look | Already handled — `lookFor()` falls back by gender prefix |
| R2 | Removing `AvatarImage` breaks a call site I did not find | `grep` for every usage before deleting; typecheck is the backstop |
| R3 | The chip refactor changes rendered markup and breaks tests that query chips | Chips are queried by accessible name and `aria-pressed`, both preserved |
| R4 | Raising chip height reflows dense filter rows on mobile | Verified by screenshot at 390px, not by assumption |
| R5 | An empty-state change alters copy a test asserts | Run the suite after each increment, not at the end |
| R6 | Scope creep into P2 layout work | Phase C is limited to what the audit named; no new features |

## 4. Order

A1 avatar system · A2 locked/selected · A3 headings · A4 denominator ·
A5 chips · A6 empty states · B consistency sweep · D a11y re-measure ·
E bundle comparison. Each increment: typecheck, lint, test, commit, push.
