# Pre-Sprint 14 Product Design Audit

**Scope:** every screen shipped in Sprints 10–13.
**Method:** the built application driven in a real browser against a seeded
cohort of 12 students, 48 attempts and two classes — at 1440px, 768px and
390px, in light and dark, with DOM measurements taken per screen (horizontal
overflow, page height, `<h1>` count, interactive targets under 44px, live
regions). Source read where the screenshot raised a question.
**Nothing in this document was fixed while auditing it.** It is a findings
report for Sprint 14 to schedule.

**Reviewed at:** `74c1009`.

---

## 0. Executive summary

The product is in better shape than its worst screen suggests. Nine of the ten
screens are coherent, on-token and mobile-safe; **horizontal overflow measured
zero on every screen at every width**, which is the failure this kind of audit
usually opens with.

The audit turned up one defect that outranks everything else, and it is not a
matter of taste.

> **F1 — Six avatar images referenced by the database have never existed in
> this repository.** `frontend/public/` contains one file: `robots.txt`.
> Every `<AvatarImage src={avatar.image_url}>` in the product resolves to a
> 404 and falls back to initials. Sprint 12 discovered this, drew
> `AvatarCharacter` to replace it, and wired it into the reward sequences —
> and Sprint 13 wired it into the leaderboard — but **the avatar picker, the
> profile, the dashboard hero and the site header were never migrated.**
>
> The consequence: the registration step where a student chooses their
> character shows six identical grey circles reading "NA", "NA", "AR", "AR",
> "NA", "AR". The same student is a drawn character on the leaderboard and two
> grey letters on their own dashboard.

Everything else is ordinary sprint debt. The three next-largest items are a
copy bug that can read "4 of the 0 required target terms", a touch-target class
that never got the 44px treatment the rest of the system got, and a practice
library that shows no graphs in a product about reading graphs.

**Recommended Sprint 14 shape:** a half-day "one avatar" pass (F1, F2, F14),
a half-day of copy and empty-state guards (F3–F6), then the deployment work as
planned. F7–F9 are the mobile pass. Everything below P2 is optional.

---

## 1. Screens ranked, weakest to strongest

Ranked by severity of what is wrong, not by how much work each screen was.

| # | Screen | Verdict | Headline problem |
|---|---|---|---|
| 1 | **Registration** | ⛔ Blocked by F1 | The avatar step — the entire reason the gendered-avatar feature exists — is six grey "NA" circles. No `<h1>`. |
| 2 | **Profile** | ⛔ Blocked by F1 | "Your character" is three grey circles; one is simultaneously *selected* and *locked*; the class is never named. |
| 3 | **Results** | ⚠️ Copy defect | Can read "You used 4 of the 0 required target terms". Two cards render a heading with nothing under it. |
| 4 | **Practice Library** | ⚠️ Mobile + IA | Nine sub-44px filter chips; four rows of filters before the first card on a phone; cards show a type icon, never the graph. |
| 5 | **Settings** | ◐ Structural | 2,705px of single column on a 1440px screen, no section navigation, no loading or error state. |
| 6 | **Practice Workspace** | ◐ Minor | The task sits below the fold on the left while the composer is top-right; the disabled CTA reads as enabled. |
| 7 | **Student Dashboard** | ✓ Strong | Initials where the character should be (F1). Four figures to one decimal place. |
| 8 | **Teacher Dashboard** | ✓ Strong | "What is worth a lesson?" is empty for most real deployments and says so, correctly, but the card still leads with a question it cannot answer. |
| 9 | **Analytics** | ✓ Strong | Thirty daily x-axis labels; one long scroll with no in-page navigation. |
| 10 | **Leaderboard** | ★ Strongest | Nothing above P3. The podium, the sticky own-rank bar and the invitation for unranked students all hold up. |

---

## 2. Findings

Severity: **P0** ships broken · **P1** visibly wrong or unusable for some users
· **P2** costs quality · **P3** polish.

### F1 · P0 · The avatar system is half-migrated
**Screens:** Registration, Profile, Student Dashboard, every page header.
**Components:** `components/avatars/avatar-picker.tsx:131`,
`components/dashboard/hero-panel.tsx:40`, `components/layout/user-menu.tsx:52`.

`avatars.image_url` in the seed points at `/avatars/boy-default.svg` and five
siblings. `frontend/public/` holds only `robots.txt`; `GET
/avatars/girl-default.svg` returns **404**. The fallback is
`avatar.name.slice(0, 2)`, so the picker labels every option with the first two
letters of the character's name — "Nadia", "Nadia the Scholar" and "Nadia the
Explorer" all render as **NA**.

`components/avatars/character.tsx` already solves this: it draws each `code` as
a token-coloured SVG with five expressions, and `avatarCodeFromUrl()` recovers
the code from the stored path. Five files use it; four files still do not.

**Fix:** migrate the four. No new asset, no migration, no backend change.

### F2 · P0 · A locked avatar can appear as the selected one
**Screen:** Profile. **Component:** `components/avatars/avatar-picker.tsx`.

Observed: "Nadia the Explorer" rendered with the selected ring *and* a
`🔒 Level 25` badge, for a level-8 student. The tile reconciles neither state.
Whether this is reachable in production depends on the API refusing a locked
selection; the interface should not depend on that being true.

### F3 · P1 · "You used 4 of the 0 required target terms"
**Screen:** Results. **Component:** `components/results/vocabulary-panel.tsx`.

The sentence interpolates a denominator without guarding zero. A graph with no
required targets should not be publishable (CLAUDE.md rule 12), so this is
reachable only through legacy or directly-seeded rows — but the copy is wrong
whenever it is reachable, and the guard costs one branch.

### F4 · P1 · Cards that render a heading and nothing else
**Screens:** Results (×2), Settings (×1).

- **Feedback** — `components/results/feedback-panel.tsx` renders its title and
  an empty body when `strengths`, `improvements` and `next_step` are all empty.
- **The XP card on a revisit** — `result-view.tsx:185` is a full-height card
  holding one centred sentence, so a revisited result has a large empty box
  where the awards were.
- ~~**How your work is marked**~~ — **withdrawn on implementation.** The card
  is already guarded: `settings-view.tsx:110` renders it only when `weighting`
  is non-null, so a failed rubric fetch hides the whole card rather than
  leaving a heading over nothing. The audit was wrong about this one.

None of these is a crash; all three read as a page that failed to finish
loading.

### F5 · P1 · Filter chips never got the 44px treatment
**Screens:** Practice Library (9 chips), Submissions, Vocabulary,
Achievements, Admin. **Component:** `components/ui/filter-chips.tsx:52`.

Measured at 390px: **17 interactive targets under 44px on the practice
library**, of which nine are filter chips measuring exactly 30px
(`px-3 py-1.5 text-xs`).

This is a **design-system inconsistency**, not only an accessibility one.
Sprint 13 raised `Button` to a 44px floor until `sm:` and gave the
leaderboard's scope chips `min-h-11` — but `FilterChips`, the most-used filter
control in the product, kept its original height. Two chip components now
disagree about touch.

### F6 · P1 · An empty state that can state a falsehood
**Screen:** Student Dashboard. **Component:**
`components/dashboard/achievement-strip.tsx`.

Rendered for a student with nine marked descriptions and 1,536 XP:

> **Your first one is close** — Finishing a single description unlocks one.

Both sentences are false for that student. The empty state assumes "no
achievements" means "no practice", and the two come apart whenever the
achievement rules and the practice history disagree — exactly the case a
teacher will report.

### F7 · P2 · The practice library shows no graphs
**Screen:** Practice Library. **Component:**
`components/practice/graph-card.tsx`.

Each card carries a 40px type glyph and the words "Pie chart". In a product
whose entire subject is reading charts, the library of charts is a list of
labels. The cause is structural — `GraphSummary` carries no `chart_data`, so
there is nothing to draw without N detail requests — and the same constraint
forced the same compromise on the teacher's graph manager.

**This is the one finding that needs a backend decision**, and it belongs in
Sprint 14's scope discussion rather than in a component: either
`GraphSummary` gains a thumbnail payload, or the API grows a rendered preview.

### F8 · P2 · Four rows of filters before any content on a phone
**Screen:** Practice Library.

At 390px: title, blurb, "Surprise me", search, `FILTER` label, five type chips
on two rows, four level chips on two rows — the first graph card begins at
roughly 700px, most of a screen and a half down. Two filter groups that are
each single-select are a candidate for one row of chips plus a "More filters"
disclosure.

### F9 · P2 · Settings is one 2,705px column
**Screen:** Settings.

Six unrelated cards stacked in a single column occupying ~55% of a 1440px
viewport. Changing a password means scrolling past appearance, motion, sound
and the rubric. There is no section navigation and no anchors. On desktop this
is a two-column layout or a left rail; on mobile the ordering is right but the
page would benefit from collapsing the explanatory cards.

Related: the **Motion** card contains no control at all — it explains an OS
setting. Correct behaviour, but it reads as a settings card that lost its
switch.

### F10 · P2 · A 500 shows a skeleton for several seconds
**Screens:** all query-backed screens. **Component:** `app/providers.tsx`.

**Partly withdrawn on implementation.** The symptom was real: while auditing,
`GET /submissions/{id}` returned 500 and the result page rendered a **bare
skeleton with no indication anything was wrong** for about three seconds.

The diagnosis was not. `app/providers.tsx` already refuses to retry any 4xx
(`error.status < 500` returns false) and caps the rest at two attempts. There
is no default-schedule bug to fix, and the remaining wait is the deliberate
price of retrying genuine transport failures. Left as it is.

### F11 · P2 · Authentication pages have no `<h1>`
**Screens:** `/login`, `/register`. Measured `h1=0` on both.
**Component:** `components/auth/auth-shell.tsx`.

The visible title is styled text, not a heading, so the document outline of the
first screen a user meets starts at `<h2>` or lower. Screen-reader users
navigating by heading find nothing.

### F12 · P2 · The task is below the fold while the composer is not
**Screen:** Practice Workspace.

At 1440px the chart occupies the left column and **"Your task — Describe the
chart in at least 150 words"** sits beneath it, below the fold, while the
answer box is top-right and immediately usable. A student can begin writing
without ever having seen the instruction. The composer's own hint ("aim for
150–250") is a *different* number from the task's, sourced from the rubric
endpoint — they agreed here by luck.

### F13 · P3 · The disabled submit button reads as enabled
**Screen:** Practice Workspace. **Component:** `components/ui/button.tsx`.

`disabled:opacity-50` over `bg-primary` produces a light purple that scans as a
live call-to-action; only the helper text below ("Write your description
first.") says otherwise.

### F14 · P3 · `initials()` exists three times
**Components:** `lib/format.ts`, `components/dashboard/hero-panel.tsx:151`,
`components/layout/user-menu.tsx:20`.

Sprint 13 added the shared one — with first-and-last-initial logic, because two
students in a class can share a first name — without retiring the two local
copies, which take the first two letters of the first word.

### F15 · P3 · Four dashboard figures to one decimal place
**Screen:** Student Dashboard. `85.6%`, `97.6%`, `83.7%` in 30px type. Decimals
carry no decision here and cost the tiles their scannability.

### F16 · P3 · Analytics x-axis at 30 daily labels
**Screen:** Analytics. A 30-day range prints 30 date labels; legible at 1440px,
cramped by 768px. `chooseGranularity` already exists and switches to weekly at
46 days — the threshold is simply generous.

---

## 3. Cross-cutting assessment

### 3.1 Visual hierarchy — **strong**
One tinted hero per screen, one primary action, consistent card elevation, a
single type scale. The reward tier card is the only saturated surface on the
results page, which is the correct place to spend it. No screen has competing
primary buttons.

### 3.2 Information architecture — **strong, two gaps**
Navigation order is frequency-descending for both roles and the same list feeds
the header and the phone bar. Gaps: the profile never names the student's class
(F2 group), and Settings has no internal structure (F9).

### 3.3 Mobile UX — **good, with one systemic defect**
Zero horizontal overflow at 390px across all ten screens. Bottom navigation
fits five teacher destinations legibly. Dense tables reflow to cards below
`md` — the queue, vocabulary and user list all ship both presentations. The
defect is F5: the touch floor was applied to buttons and to one chip component,
not to the chip component used everywhere else.

### 3.4 Accessibility — **strong, three gaps**
Data-table alternatives on every chart; `role="status"` announcements on scope
and filter changes; the podium's DOM order is 1-2-3 with only CSS reordering
it; em dashes carry `sr-only` readings; reduced motion renders settled frames
rather than fast ones. Gaps: F5 (touch targets), F11 (no `<h1>` on auth), and
the empty cards in F4, which give a screen reader a heading with no content.

### 3.5 Consistency — **the weakest dimension**
Three unresolved forks, all from features that were half-migrated rather than
badly designed: two avatar systems (F1), two chip touch rules (F5), three
`initials` implementations (F14).

### 3.6 Empty states — **good where they exist**
`EmptyState` is used on nine views with icon, explanation and an action.
Missing on `settings-view` and `result-view`; wrong in one case (F6); and three
cards render nothing rather than an empty state (F4).

### 3.7 Loading states — **near-complete**
Skeletons matched to final layout on twelve of thirteen view components;
`settings-view` has none. `placeholderData: keepPreviousData` on the teaching
screens keeps figures on screen during a refetch instead of collapsing to
skeletons — the right call, applied consistently.

### 3.8 Error states — **complete in shape, wrong in timing**
Every query-backed view has a destructive `Alert` with a retry button, and 404
is distinguished from 500 in the copy. F10 is the timing problem, not the
presentation.

### 3.9 Dark mode — **strong**
Every colour is a token defined in both themes and enforced by
`tests/design-tokens.test.ts`. Verified on analytics and admin: chart series
lift correctly, the tier bar holds its four hues, card elevation still reads.
No screen was found using a literal colour.

### 3.10 Gamification — **strong on the surfaces that got it**
XP ring, streak, level progress, four tier storyboards ending in recovery,
sound muted by default, a podium and a sticky own-rank bar. The gap is that the
*character* — the element that carries the personality — is present in exactly
two places and absent from the three where a student sees themselves (F1).

### 3.11 Educational UX — **strong**
The rubric is read from the server rather than hardcoded; the results page
names the terms used and missed; the tier explains that it comes from
vocabulary rather than the final score; the teacher's screens say what was
measured over how many submissions. F7 is the one place the teaching subject is
not visible in the teaching interface.

### 3.12 Conversion to practice — **strong**
Every student surface ends in a route to practice: dashboard hero, "Surprise
me", the results footer, the achievements empty state, the leaderboard's
invitation for unranked students. No screen is a dead end.

---

## 4. Technical debt

| Item | Where | Cost |
|---|---|---|
| Two avatar systems | 4 files on the old one, 5 on the new | F1, F2 |
| Two chip touch rules | `ui/filter-chips.tsx` vs `leaderboard-view.tsx` | F5 |
| Three `initials()` | `lib/format.ts` + 2 local | F14 |
| Retry policy | `app/providers.tsx` | F10 |
| `GraphSummary` carries no chart data | API shape | F7, and the same compromise in the teacher manager |
| Dead animation classes | `ui/dropdown-menu.tsx:28` | `animate-in` without the plugin; inert |
| Writing consistency unsurfaced | endpoint exists, no screen | Feature shipped, unreachable |
| 3 high advisories | `sharp` via `next` | Pre-existing; fix is a major upgrade |

---

## 5. Recommended improvements, in order

**Do first — half a day, no new dependencies**
1. **F1** Migrate `avatar-picker`, `hero-panel` and `user-menu` to
   `AvatarCharacter` + `avatarCodeFromUrl`. Delete the `image_url` reads.
2. **F2** Make a tile that is both locked and selected impossible to render.
3. **F3** Guard the zero denominator.
4. **F4** Give all three cards an empty state, or hide the card.
5. **F6** Condition the achievement empty state on practice history.

**Do next — the mobile and a11y pass**
6. **F5** One touch rule for every chip; retire the duplicate.
7. **F11** A real `<h1>` on the auth shell.
8. **F8** One filter row plus a disclosure on the library.
9. **F10** `retry: (count, error) => count < 1 && !error.isClientError`.

**Do if Sprint 14 has room**
10. **F9** Two-column settings at `lg:` with a section rail.
11. **F12** Move the task prompt above the composer, or into the composer's
    header.
12. **F14**, **F15**, **F16**, **F13** — one commit of polish.

**Needs a decision, not an implementation**
13. **F7** Does `GraphSummary` gain a thumbnail? This is the only finding that
    changes an API contract, and it is the difference between a library of
    charts and a library of labels.

---

## 6. What this audit did not cover

- Formal contrast measurement. Token pairs were designed to AA and the
  stylesheet is enforced, but no automated contrast run was made — that belongs
  in Sprint 14's audit task.
- Screen-reader transcript testing with a real reader (NVDA/VoiceOver).
- Keyboard traversal of every screen; focus behaviour was verified on dialogs
  and the sticky bars only.
- Performance under a throttled network.
- The 768px breakpoint was measured for overflow but not reviewed screen by
  screen.
