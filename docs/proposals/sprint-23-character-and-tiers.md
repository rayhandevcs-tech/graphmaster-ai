# Sprint 23 Design Review — The character, and the four tier moments

Required before implementation by the standing frontend directive.

## 1. What was asked for

> *"crown/flower/hammer গুলো realistic লাগছে না — fun, animated, full-avatar,
> 3D, Duolingo-র মতো চাই। আর profile avatar-টাও সুন্দর না।"*

Two complaints, one cause. Both the character and the three tier props are
drawn as **flat single-colour shapes with no volume**, and the character is a
head-and-shoulders bust inside a circle. Duolingo's characters read as objects
in a space: they have bodies, they have weight, and light falls on them.

## 2. A recommendation I am withdrawing

Earlier in this project I recommended **Lottie** for this work, on the
reasoning that it was already named in the stack and would give a 3D-ish
result cheaply. Having now read what is actually in the repository, that was
wrong, and I would rather say so than quietly build the other thing.

Four reasons:

1. **There are no Lottie files, and no way to author them here.** Lottie JSON
   comes out of After Effects. Hand-writing it is strictly worse than
   hand-writing SVG, which is what it compiles down to anyway.
2. **It cannot theme.** A Lottie document is wall-to-wall hard-coded colour
   values. This project bans colour literals outside `globals.css` and
   enforces it with `tests/design-tokens.test.ts`, precisely so the interface
   works in dark mode. A Lottie character would be the one thing on the page
   that ignores the theme.
3. **`lottie-web` is around 250 KB gzipped** to render animations the
   `framer-motion` already in the bundle can render.
4. **The existing system is good and would have to be thrown away.** The
   storyboards are data (`lib/motion/storyboards.ts`), the sequence hook
   handles reduced motion, skip and replay, and the sound cues fire on the
   right beats. Lottie would mean either replacing all of that or running two
   animation systems next to each other.

**What actually produces the Duolingo feel** is not the file format. It is
full-body characters, chunky props with visible volume, squash-and-stretch, and
overshoot on arrival. All four are available in SVG plus the motion vocabulary
this codebase already has.

## 3. Where the flatness comes from

| Thing | Today | Why it reads flat |
|---|---|---|
| Character | 96×96 bust in a circle | No body, so no stance and no weight |
| Crown | `lucide-react` `<Crown/>` | A 2px stroke icon; UI furniture, not treasure |
| Hammer | `lucide-react` `<Hammer/>` | Same — and a tool, where the spec wants a toy mallet |
| Flower | 5 ellipses, one fill | Petals are flat lozenges with no curl or overlap |
| Stage | Character floats | No ground, so nothing has weight to land with |

## 4. How volume is drawn without a single colour literal

Every shade has to come from a token. Three techniques, used throughout:

```
1. currentColor + opacity   fill="currentColor" fill-opacity=".18"   → shadow side
2. SVG gradient of one hue  <stop stop-color="currentColor" stop-opacity="1|.55">
3. token utilities          className="fill-primary/85"              → planes behind
```

A gradient whose stops are both `currentColor` at different opacities gives a
lit side and a shadow side of *whatever colour the theme happens to be*. That
is how a crown can look like gold leaf in light mode and burnished gold in dark
mode without the file knowing either colour.

Each gradient needs a **unique DOM id** — two celebrations on one page with
`id="crownFace"` in both would make the second one paint with the first one's
gradient. `useId()` per instance.

## 5. The character

### 5.1 One component, two builds

`AvatarCharacter` is used in nine places, most of them 32–40px in a list. A
full body at 32px is a smudge. So:

```
<AvatarCharacter variant="bust" />     ← default; every existing call site
<AvatarCharacter variant="figure" />   ← the celebration stage, the profile hero
```

**One file, one head.** The head, hair, face and accessories are drawn once and
both builds use them; the figure adds a torso, arms and legs beneath. Two
components would drift — which is exactly how six avatar SVGs came to be
referenced by a database that no file ever matched (Sprint 14, finding F1).

### 5.2 The figure, at 96×140

```
        ╭───────╮        hair, with a highlight band on the lit side
       │ ◕   ◕ │        head — same drawing as the bust
        ╰──┬──╯
      ／  ███  ＼        arms, posable: rest / cheer / brace / guard
     ／   ███   ＼
          ███           torso: gradient, dark at the waist
         ██ ██          legs, slightly apart — a stance, not a pedestal
        ▂▂▂▂▂▂▂         ground shadow: an ellipse, not a drop-shadow
```

Four arm poses, because the arms are what make a body read as reacting:

| Pose | Used by |
|---|---|
| `rest` | idle, and every list |
| `cheer` | crown, flower — both arms up |
| `brace` | steady — hands at the hips |
| `guard` | hammer — one arm crossed over the head, before contact |

The **ground shadow is a separate ellipse**, not a CSS drop-shadow, so it can
be animated independently: it widens and fades as the character rises and
tightens as it lands. That single trick does more for perceived weight than
any amount of gradient.

## 6. The three props, redrawn

**Crown** — a band, five points, and a gem on the centre point. The band is
split into a lit face and a shadow face by a gradient; the points get a
lighter inner facet. It reads as a solid object because the left and right
sides are different values.

**Flower** — petals in two layers, the back layer rotated 36° and darker. A
curled tip on each front petal (one bezier, not an ellipse) and a stippled
centre. Overlap is what makes a flower look like a flower.

**Mallet** — this one has a rule attached. FR-7.6 says the hammer must never
read as harm, so it is deliberately a *toy*: an oversized rounded head with a
highlight, a fat wooden handle, and comic proportions no real tool has. A
realistic claw hammer is the one thing this prop must not become — which is
worth writing down, because "make it more realistic" is exactly what was
asked for and is the wrong answer for this specific object.

## 7. Motion — what changes and what does not

**The storyboards do not change.** Same beats, same timings, same order. FR-7.7
is asserted against `HAMMER_RECOVERY` coming before `HAMMER_MESSAGE` and both
before `SETTLED`, and that test keeps passing untouched. What changes is what
each beat *draws*.

Added on each beat:

| Beat | Now also |
|---|---|
| `arrive` | figure drops in with the shadow spreading beneath it |
| `crown` | figure squashes as the crown lands; shadow widens on the compression |
| `bloom` | petals stagger open, back layer first |
| `nod` | shadow tightens and releases with the nod |
| `bonk` | squash on contact, shadow flattens; mallet rebounds past vertical |
| `recover` | shadow snaps back as the figure springs up |

All of it goes through `DURATION` and `EASE`. Nothing introduces a new number.

## 8. Accessibility

- The whole stage stays `aria-hidden`. The headline is real text, present in
  the DOM from the first frame and revealed by opacity — a screen-reader user
  and a student who skips get the same words at the same time. Unchanged, and
  worth restating because it is the property most easily broken by adding
  drawing.
- `prefers-reduced-motion` still lands on the settled frame with no controls.
  The figure has an explicit settled pose; it must not settle mid-swing.
- No meaning in colour alone: each tier is named in the text beside it.
- The figure's ground shadow is drawn with `fill-opacity`, never a filter —
  `filter: drop-shadow` costs a repaint per frame on a phone.

## 9. Tradeoffs

**No WebGL.** Real 3D would need three.js (~150 KB), a light rig, and a
fallback path for the same phones this product is used on. The volume asked
for is *perceived* volume, and shading plus a shadow buys almost all of it at
a few kilobytes of markup.

**Not photoreal, on purpose.** The character stays a stylised duotone with no
skin tone — for a platform used by one cohort after another, having no skin
tone to get wrong is the right default, not a compromise.

**The bust stays the default.** A full figure everywhere would look worse in
every list on the leaderboard. The figure earns its place on the two screens
where the character is the subject.

## 10. Order of work

1. The figure, its poses and its shadow — `components/avatars/character.tsx`
2. The three props — `components/gamification/tier-props.tsx`
3. The stage: depth, shadow choreography, the props wired to the beats
4. Profile and dashboard hero use the figure
5. Docs
