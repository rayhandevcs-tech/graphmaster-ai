# Sprint 19 Design Proposal — Writing Consistency Assessment

**Status:** Proposed. Awaiting approval. **No implementation code has been
written, no migration created, no API contract or frontend touched.**

**Author:** Architecture review, Sprint 19 design phase
**Reviewed against:** Sprints 15–18 as merged (`2d7be54`), migration 4
(`883a835f73c9`), `docs/architecture/10-assessment-architecture.md` rev 1.3

---

## 0. Executive summary

The brief asks for explainable writing-consistency signals for teachers. The
architecture supports it, and most of what it needs already exists. But the
review turned up five things that change the shape of the sprint, and two of
them are defects in what is already merged.

**R1 — Split the feature in two. The analyzer measures; the comparison
compares.** A cross-submission analyzer cannot exist inside the current
contract without breaking the property that `assessment_version` depends on
(§3.1). One analyzer produces a per-submission *profile* of numbers; a
separate, pure comparison layer reads a series of those profiles at teacher
request time. Nothing about a comparison is ever stored.

**R2 — No new tables, no new columns, no migration.**
`assessment_details.analyzer_status` is JSONB and already carries each
analyzer's metrics. The profile is metrics. Migration 5 is not needed and
should not be written (§4).

**R3 — `ASSESSMENT_TEACHER_ONLY_ANALYZERS` is not sufficient to satisfy C2.**
`Settings.analyzer_audience()` returns `STUDENT` for any analyzer not named in
a list. A deployment that forgets one environment variable shows students
their own consistency profile. C2 says *never*; a default that can flip is not
never. Sprint 19 must add a hard floor in code that no environment can raise
(§3.6). **This is a defect in the merged rollout mechanism, not a new
requirement.**

**R4 — `AssessmentResult.for_audience()` is never called anywhere in the
application.** The filter is written and unit-tested, but has no call site,
because no endpoint reads assessment data yet. C2's enforcement point does not
currently exist. Sprint 19 must therefore ship **no HTTP endpoint at all** —
the same posture Sprint 18 took — and the teacher read surface lands in Sprint
20 where `for_audience` is wired once for every analyzer rather than twice
(§3.7).

**R5 — Cut the signal set roughly in half.** Function-word stylometry,
cross-student overlap and any timing or keystroke signal should be rejected,
for reasons given per signal in §2. What survives is the set that is already
measured, already explainable, and already defensible.

Two facts should govern how the finished feature is talked about, and both
belong in the UI copy, not only in this document:

- **The platform causes the shifts it would be measuring.** A course whose
  purpose is to raise target-vocabulary use and writing quality produces
  changed writing in the students it succeeds with. The base rate of "sudden
  linguistic change" among *successful learners* on this platform is high, not
  low (§7.1).
- **A consistent profile is not evidence of anything.** A student assisted
  uniformly from their first submission has a perfectly stable baseline —
  because the baseline is itself assisted. There is no clean baseline, ever
  (§7.2). If teachers read "consistent" as "cleared", the feature has done
  harm in the opposite direction from the one everyone worries about.

---

## 1. Problem definition

### 1.1 What "writing consistency" means here

**A measurement of how one student's measurable writing characteristics move
across their own submissions over time.** Nothing more. Specifically: a small
set of numbers computed from each submission, placed beside the same numbers
from that student's earlier submissions, with the spread and the sample size
shown alongside.

It is a *longitudinal view of quantities the platform already computes*. It is
not a new kind of judgement about writing; it is the existing judgements
plotted against time and against a personal baseline.

### 1.2 What it does not mean

It is not, and no component may internally compute:

- a probability, likelihood or score that text was machine-generated;
- an authorship attribution or verification decision;
- a risk, integrity, suspicion or misconduct value under any name;
- a comparison of one student's writing against another student's writing;
- a binary or ordinal flag whose meaning is "look at this one".

The last is the subtle one. A "review flag" with no label attached is still a
verdict — it says *this student, not those students*. C5 permits observations
and indicators; an indicator that ranks students by deviation is an accusation
with the wording removed. **The system must never sort or filter students by
any consistency measure** (§6.4).

### 1.3 Educational purpose

Three uses, all of which a teacher could serve today by reading twenty
submissions by hand, and none of which involve suspicion:

1. **Did the teaching land?** A student told in feedback to use trend
   vocabulary — does their subsequent writing show it? The platform already
   generates that feedback; it has never shown whether it was acted on.
2. **Is this student developing or plateauing?** Vocabulary coverage rising
   while sentence complexity is flat is a different teaching problem from the
   reverse, and neither is visible from a list of final scores.
3. **Which attempt should I read?** A teacher with thirty students and two
   hundred submissions needs somewhere to start. "This attempt differs most
   from the student's own previous work" is a reading order, not a
   verdict — and it is only useful if it is presented as one.

### 1.4 Limitations, stated up front

These are properties of the method, not of the implementation, and no amount
of engineering removes them:

| Limitation | Consequence |
|---|---|
| Answers are 150–250 words (`TARGET_WORD_COUNT_MIN/MAX`) | Stylometric measures over a few hundred words are dominated by noise. Authorship methods are generally unreliable below roughly a thousand words per sample. |
| Prompts differ | A pie chart demands proportion language; a line chart demands trend language. Two answers to different graphs are not two samples of the same task. |
| Input methods differ | An OCR'd handwritten answer and a typed one differ in spelling, punctuation and sentence segmentation for reasons that have nothing to do with the writer. |
| Learners are learning | See §7.1. Change is the intended outcome. |
| Many students are writing in a second language | L2 writing has higher intra-writer variance, and improves faster under instruction. The false-positive burden falls unevenly (§6.5). |
| No baseline is known clean | See §7.2. |

### 1.5 Naming

**Recommendation: the analyzer is named `writing_profile`, not
`writing_consistency`.**

"Consistency" has an antonym, and the antonym is what a teacher reads on a bad
day. "Inconsistent" is an accusation in an academic register in a way that "a
change in this student's writing profile" is not. The *sprint* and this
document keep the brief's name; the code identifier, the metric keys, the
stored `analyzer_status` key and every string a teacher can see use **profile**
and **change since**, never **consistency**, **deviation** or **anomaly**.

This is not cosmetic. `subtype` and metric keys are stable analytics slugs —
`docs/architecture/10-assessment-architecture.md` §8 — so they outlive any
copy rewrite. A key called `consistency_anomaly_score` would still be in the
database in three years when someone builds a report from column names.

---

## 2. Signal catalogue

Each signal is evaluated, not assumed. Verdicts: **approve**, **approve with
constraints**, **defer**, **reject**.

| # | Signal | Verdict | One-line reason |
|---|---|---|---|
| S1 | Lexical diversity trajectory (MATTR) | Approve | Already computed; explainable; the single most informative measure at this length. |
| S2 | Sentence-complexity trajectory | Approve | Already computed; two independent measures; explainable by example. |
| S3 | Target-vocabulary coverage trajectory | Approve | Already stored; the closest signal to the actual teaching goal. |
| S4 | Mechanical-accuracy trajectory | Approve with constraints | Already stored; must never be combined with S1–S3 into a composite. |
| S5 | Verbatim self-overlap between a student's own attempts | Approve with constraints | The most explainable signal there is — you can show both spans. Must be framed as revision behaviour, not reuse detection. |
| S6 | Off-corpus / rare-word incidence | Defer | Explainable, but the false-positive sources (chart labels, proper nouns, L1 coinages) need measuring against real submissions before it is shown to anyone. |
| S7 | Function-word profile distance (Burrows's Delta and relatives) | **Reject** | This *is* authorship attribution. Least explainable, most sample-hungry, and the one signal whose only interpretation is the one C1 forbids. |
| S8 | Timing, keystroke or paste telemetry | **Reject** | Not collected, needs frontend instrumentation the brief forbids, and is a surveillance escalation this feature has no mandate for. |
| S9 | Cross-student text overlap within a class | **Reject for Sprint 19** | Collusion detection. Different consent posture, different legal basis, O(n²) cost, and an institutional policy decision rather than an engineering one. |

### S1 — Lexical diversity trajectory

- **Description.** Moving-average type–token ratio for the submission, placed
  against the mean and spread of the student's own prior MATTR values.
- **Rationale.** Vocabulary range is a stated learning objective, and MATTR is
  the length-robust way to measure it. Of everything available at 150–250
  words, this is the measure with the best signal-to-noise ratio.
- **Data source.** `WritingQuality.mattr` — computed today, on the shared
  spaCy `Doc`. No new computation.
- **Method.** Read the existing value. The comparison layer computes the
  student's prior mean, standard deviation and n, and reports the current
  value beside them.
- **Explainability.** The number, the prior values it is compared with, the
  dates, and the submissions they came from. A teacher can click through to
  every data point.
- **Confidence limitations.** MATTR is unstable below roughly 100 words. Short
  answers must not produce a profile at all (§7.3).

### S2 — Sentence-complexity trajectory

- **Description.** Mean sentence length and subordination ratio against the
  student's own history.
- **Rationale.** Sentence structure is a quarter of the existing writing
  score, and the two measures move for different reasons — long simple
  sentences and short complex ones are different writing, and one number
  cannot say so.
- **Data source.** `WritingQuality.mean_sentence_length`,
  `WritingQuality.subordination_ratio`. Both already computed.
- **Method.** As S1.
- **Explainability.** Both are demonstrable by quoting a sentence. "Your
  average sentence went from 14 words to 26; here is a 26-word one" is a
  teaching conversation.
- **Confidence limitations.** Sentence segmentation on OCR'd handwriting is
  unreliable — missing full stops merge sentences and inflate both measures.
  Comparisons must be gated on input method (§5.4).

### S3 — Target-vocabulary coverage trajectory

- **Description.** `vocabulary_percentage` and the set of target terms
  detected, over time.
- **Rationale.** This is the platform's actual teaching objective. If any
  trajectory deserves a teacher's screen, it is this one.
- **Data source.** `scores.vocabulary_percentage` and
  `scores.detected_terms` — already stored, and already the approved basis for
  vocabulary analytics (CLAUDE.md rule 34: count `detected_terms`, never
  re-scan the answer).
- **Method.** Read the stored values. **No re-detection.**
- **Explainability.** Total, and the terms themselves.
- **Confidence limitations.** Confounded by the graph: different graphs carry
  different required target sets, so raw coverage is only comparable within a
  graph or after normalising by the required-target count. Use the percentage,
  never the raw count.

### S4 — Mechanical-accuracy trajectory

- **Description.** Spelling and grammar issue density per 100 words over time.
- **Rationale.** A change in mechanical accuracy is the most legible thing to
  a teacher, and it is a genuine teaching signal on its own terms.
- **Data source.** `assessment_details.spelling_score`, `.grammar_score`,
  `assessment_issues` counts by category. Already stored.
- **Method.** Read stored scores. Where a score is `NULL` the analyzer did not
  run and the point is absent, never zero (rule 32, §11.1).
- **Explainability.** The issues themselves, which are already stored with
  spans and explanations.
- **Confidence limitations.** Grammar is `GRAMMAR_PROVIDER=none` by default,
  so most deployments have no grammar series at all. Spelling density on OCR'd
  handwriting measures the OCR engine as much as the student.
- **Constraint.** **S4 must never be summed or averaged with S1–S3.** A
  composite across dimensions is a risk score with a friendly name — a single
  number whose only use is ranking, and whose components cannot be recovered
  from it. Each measure is reported and plotted separately, always.

### S5 — Verbatim self-overlap between attempts

- **Description.** The proportion of this submission's text that appears
  verbatim (or near-verbatim) in the same student's earlier submission for the
  same graph.
- **Rationale.** A student re-attempting a graph is the platform's designed
  improvement path (CLAUDE.md rule 19). A teacher currently cannot tell
  whether attempt three was rewritten or resubmitted with two words changed,
  and that is the single most useful thing to know when marking a re-attempt.
- **Data source.** `submissions.answer_text` for the same `(user_id,
  graph_id)`, earlier `submitted_at`.
- **Method.** Normalised shingling (word n-grams, n=5) with a Jaccard or
  containment coefficient. Deterministic, no model, no network. Evidence is
  the matching spans, which can be shown side by side.
- **Explainability.** Total. Both texts are the student's own and both are
  already visible to the teacher.
- **Confidence limitations.** None worth noting on the measurement itself —
  it is exact. The risk is entirely in the framing.
- **Constraint.** **High self-overlap is not a finding.** It is the expected
  shape of a revision. The surface must read "attempt 3 keeps 78% of attempt
  2" and must never label it. It compares a student only against *themselves*
  — cross-student comparison is S9 and is rejected.

### S6 — Off-corpus / rare-word incidence — *defer*

Words in the answer that are outside the curated vocabulary, outside the
chart's own labels, and outside a general high-frequency band. Genuinely
useful ("did you mean this?" is a teaching prompt), genuinely explainable
(here are the words). But three false-positive sources are large and unmeasured
on real data: chart series labels and axis terms the student is *supposed* to
quote, proper nouns (place names in the corpus already break the spell
checker), and L1-influenced coinages from second-language writers — which
would concentrate the noise on exactly the students least able to challenge it.

**Recommendation:** compute it dark in Sprint 19 if capacity allows, expose it
to nobody, and decide in a later sprint from the measured distribution. This
is what the `dark` audience stage exists for.

### S7 — Function-word profile distance — *reject*

The classic stylometric signal: rates of *the*, *of*, *and*, *to*, compared
against a personal baseline by Burrows's Delta or a similar metric.

Rejected on three independent grounds, any one of which is sufficient:

1. **It is authorship attribution.** Its published purpose, its literature and
   its only defensible interpretation are "was this written by the same person".
   C1 forbids the system from computing such a value internally. A Delta
   distance is that value with the label removed.
2. **It fails C4.** "Your rate of definite articles moved 1.4 standard
   deviations" is not explainable to a teacher, let alone to a student in an
   appeal. There is no evidence to show — the evidence *is* the statistic.
3. **The samples are far too small.** Delta is unreliable below about a
   thousand words; these answers are a fifth of that, and the between-prompt
   variance swamps the between-author variance at this length. It would
   produce numbers, and the numbers would be noise wearing a lab coat.

### S8 — Timing, keystroke and paste telemetry — *reject*

Not collected today. `submissions` records `submitted_at` but no start time,
so even elapsed time is unavailable. Collecting it requires frontend
instrumentation, which the brief explicitly places out of scope, and it is a
categorical escalation: from *analysing work a student chose to submit* to
*recording how they produced it*. That is a different consent conversation and
a different legal basis, and this feature has no mandate for it.

### S9 — Cross-student overlap — *reject for Sprint 19*

Technically the same shingling as S5, pointed at other students. Rejected
because it changes what the system is: S5 compares a student with themselves;
S9 compares students with each other, which is collusion detection under a
different name, needs an institutional policy decision about disclosure and
retention, is O(n²) in a class, and would produce its first output as a list
of student pairs — which is a ranking of suspicion, exactly what §1.2 rules
out. If the institution ever wants it, it is its own sprint with its own
approval, not a bullet inside this one.

---

## 3. Assessment architecture

### 3.1 The constraint that decides the shape

`assessment_version` fingerprints the analyzer set, the grammar provider and
language, the confidence floor and the issue cap
(`app/assessment/__init__.py`). Its purpose is that a stored result is
*reproducible*: given the row's version and the same input, the same
configuration produces the same output.

An analyzer that reads the student's history breaks that. Re-run the same
submission a month later and it returns different numbers under the same
version string, because the history moved. The version would then fingerprint
something that no longer determines the result — which makes it worse than
useless, because it would still *look* like a guarantee.

There are three further reasons the same way:

- **The Protocol forbids it.** `Analyzer.run` is documented as pure and
  synchronous, with no I/O except through an injected provider. A database read
  from inside a synchronous analyzer called from an async request is either a
  blocking call on the event loop or a second session — both are worse than
  the alternative below.
- **Ordering.** A history-reading analyzer makes submission *n*'s result
  depend on submissions 1…*n*−1. Delete an old submission and every later
  result silently becomes wrong, with no way to know.
- **Testability.** The existing analyzer suite runs without a database. One
  analyzer that needs one would end that property for the whole package.

### 3.2 The two-layer split — recommended

```
  ┌─ Layer 1 — measurement (assessment time, pure) ──────────────────────┐
  │  app/assessment/analyzers/writing_profile.py                         │
  │    WritingProfileAnalyzer(Analyzer)                                  │
  │      reads ctx.doc, ctx.writing, ctx.detection, ctx.text             │
  │      returns AnalyzerOutput(status=OK, metrics={…},                  │
  │                             score=None, issues=())                   │
  │      → persisted by the existing repository into                     │
  │        assessment_details.analyzer_status['writing_profile']         │
  └──────────────────────────────────────────────────────────────────────┘
                                    │
                     (nothing joins these at write time)
                                    │
  ┌─ Layer 2 — comparison (read time, pure, live) ───────────────────────┐
  │  app/assessment/consistency/                                         │
  │    profile.py     Profile value object; parse/validate from metrics  │
  │    compare.py     baseline(series) → Baseline | None                 │
  │                   change(current, baseline) → Change                 │
  │    gating.py      comparability rules (§5.4)                         │
  │  app/repositories/assessment.py  (extended, not replaced)            │
  │    profile_series(submission_ids) → list[ProfileRow]                 │
  └──────────────────────────────────────────────────────────────────────┘
```

Layer 1 is an ordinary analyzer and needs no new machinery. Layer 2 is a set
of pure functions over a list of profiles plus one repository query — the same
shape as the Sprint 18 teacher-analytics foundation (`issue_frequency`,
`score_summary`, `score_series`), which is deliberately query-and-function with
no endpoint.

**Consequences of the split, all of them wanted:**

- No comparison is ever stored, so no verdict can ever be stored (C1, C5).
- Analytics are computed live, as CLAUDE.md rule 36 requires.
- Deleting or adding a submission re-bases every comparison automatically.
- The analyzer stays deterministic, so §3.1 holds.
- The feature can accumulate profiles dark for a term before anything is
  built on top of them — which is necessary anyway, because a consistency
  feature with no history is a feature with no output (§8.1).

### 3.3 Analyzer contract compliance

| Contract point | How `writing_profile` satisfies it |
|---|---|
| `name: str` | `"writing_profile"` — the key in configuration, in `analyzer_status`, and in `analyzer_audiences`. |
| `run(ctx) -> AnalyzerOutput` | Reads `ctx.writing`, `ctx.detection`, `ctx.doc`; returns metrics only. |
| Pure and synchronous | No I/O of any kind. No provider, no network, no database. |
| Shares the parse | Reads `ctx.doc`; never calls `get_nlp()`. |
| Issues | **Emits none.** It has nothing to tell the student, and by C2 it must not. |
| `score` | **`None`, permanently.** See below. |
| `status` | `OK` when a profile was computed; `SKIPPED` when the answer is too short to profile (§7.3). Never `FAILED` for a short answer — that is a fact about the answer, not a fault. |

**`score` is `None` by design and this is a load-bearing decision.**
`AnalyzerOutput.score` is a 0–100 diagnostic figure and the repository writes
it into a per-analyzer column. A 0–100 "consistency score" is a risk score
inverted: one number, monotone, orderable, whose low end means *this one*. It
would also require a `consistency_score` column, which is the migration this
proposal is arguing is unnecessary. Returning `None` closes both doors at
once, structurally — `SCORE_COLUMNS` has no entry for `writing_profile`, so
there is nowhere for a scalar to go even if someone later returns one.

### 3.4 Registry, supervisor, failure isolation

Nothing new. One line in `BUILDERS`, one name appended to
`ASSESSMENT_ANALYZERS`. The supervisor already contains every exception as
that analyzer's own `FAILED` outcome, already times the run against
`ASSESSMENT_ANALYZER_BUDGET_MS`, and already stamps the audience onto the
result. A profile analyzer that throws costs a teacher one data point and
costs the student nothing.

Layer 2 needs its own containment, because it runs in a request the supervisor
never sees. Rule: **a comparison that cannot be computed returns "no baseline",
never an error and never a zero.** Missing data is the normal case here, not
the exceptional one.

### 3.5 Versioning

Adding `writing_profile` to `ASSESSMENT_ANALYZERS` changes the
`assessment_version` digest automatically — the analyzer set is already
fingerprint material. No change to `app/assessment/__init__.py` is required,
and `ASSESSMENT_VERSION` stays `"1.0.0"`: the established policy is that the
base string is reserved for a change to the result *format*, and the
fingerprint carries configuration.

**But a trend feature exposes a gap the existing scheme does not cover.** The
fingerprint records *which* analyzers ran, not *how* they computed. That has
been acceptable so far because an issue count from one release is comparable
with an issue count from the next. It is not acceptable for a baseline: if a
release changes how a profile metric is computed, the old points and the new
points are different quantities, and a chart drawn through both is a lie in
the same way an interpolated trend line across missing data is a lie.

**Proposed rule, symmetrical with the approved §11.1 rule:**

> A comparison never crosses an `assessment_version` boundary. Where the
> version changes within a student's series, the series **breaks** there — the
> new segment starts a new baseline. It is never bridged and never interpolated.

This costs a student their baseline when a deployment changes configuration,
which is the honest outcome: their baseline genuinely no longer exists.

### 3.6 Feature flags, and the audience defect

Existing mechanism:

```python
def analyzer_audience(self, name: str) -> AnalyzerAudience:
    if name in self._named("ASSESSMENT_DARK_ANALYZERS"):
        return AnalyzerAudience.DARK
    if name in self._named("ASSESSMENT_TEACHER_ONLY_ANALYZERS"):
        return AnalyzerAudience.TEACHER
    return AnalyzerAudience.STUDENT          # ← the default
```

For the six analyzers that exist today, defaulting to `STUDENT` is right —
they produce corrections a student should see. For `writing_profile` it is
wrong, and wrong in the one direction C2 says must never happen. A deployment
that adds the analyzer to `ASSESSMENT_ANALYZERS` and forgets
`ASSESSMENT_TEACHER_ONLY_ANALYZERS` publishes every student's profile to that
student. One missing environment variable, no error, no warning.

**Proposed fix — a floor in code that no environment can raise:**

```python
#: Analyzers whose output may never reach a student, whatever the environment
#: says. The staged-rollout lists move an analyzer *down* the ladder; they
#: cannot move one of these up. C2 says never, and a default that a missing
#: variable can flip is not never.
NEVER_STUDENT_ANALYZERS: Final = frozenset({"writing_profile"})
```

applied as the first branch of `analyzer_audience`, returning `TEACHER` (or
`DARK` if also listed dark — most restrictive still wins). Cost: about eight
lines and one test. It is the difference between C2 being a configuration
convention and C2 being a property of the build.

Two flags are then needed, and they are deliberately separate:

| Setting | Default | Effect |
|---|---|---|
| `writing_profile` in `ASSESSMENT_ANALYZERS` | **absent** | Whether profiles are measured and stored at all. |
| `CONSISTENCY_ANALYTICS_ENABLED` | `false` | Whether the Layer 2 comparison functions may be called. |

Separate because the useful order is *collect first, expose later*: profiles
must accumulate for weeks before a baseline exists for anyone. One flag would
force the choice between an empty feature and no collection.

### 3.7 What Sprint 19 does *not* build

**No HTTP endpoint, no schema, no router.** Reasons:

1. `for_audience()` has no call site in the application today (R4). The first
   endpoint to read assessment data must wire it, and that endpoint is the
   general assessment read surface planned for Sprint 20. Building a
   consistency-only endpoint first means wiring the audience filter twice, in
   two places, with two chances to get it wrong — and the brief forbids a
   parallel path.
2. It is the precedent Sprint 18 and the analytics foundation already set:
   *"No endpoint exposes it yet — that is the next sprint — but the queries
   exist, are tested against a real database"* (§13).
3. The brief requires "no production activation by default". Nothing activates
   more thoroughly than a route.

Sprint 19 delivers: the analyzer, the comparison functions, the repository
query, the configuration, the regression suite, and the documentation. Sprint
20 exposes assessment — all of it — through one audience-filtered surface.

---

## 4. Storage model

### 4.1 Decision: reuse. No migration.

| Candidate | Decision | Justification |
|---|---|---|
| New `writing_profiles` table | **Rejected** | One row per submission, one-to-one with `assessment_details`, whose entire purpose is to be the one-row-per-submission diagnostic header. A second such table is the duplicate storage model the brief forbids, and would need its own cascade, its own index and its own join on every read. |
| New columns on `assessment_details` | **Rejected** | Six to nine float columns for one analyzer, where every other analyzer's measurements live in `analyzer_status`. It would also invite a `consistency_score` column, which §3.3 argues against. |
| New `consistency_findings` table | **Rejected** | This would store comparisons. Comparisons must not be stored (§3.2) — a stored comparison is a stored verdict with a timestamp, and it goes stale the moment the next submission lands. |
| **`assessment_details.analyzer_status['writing_profile']['metrics']`** | **Adopted** | Already exists, already JSONB on PostgreSQL, already written by `AssessmentRepository.create_for`, already carries exactly this shape for six other analyzers. **Zero schema change.** |
| S5 self-overlap source data | **Reuse** | `submissions.answer_text`, `user_id`, `graph_id`, `submitted_at` — all present. See §4.3 on the index. |

`create_for` already writes `{name: out.to_dict() for name, out in
result.analyzers.items()}`, and `to_dict()` already includes `metrics` rounded
to four decimal places. **The profile persists with no repository change at
all.** The only repository work is the read query.

### 4.2 The one honest caveat

Reading a class's profiles means selecting `analyzer_status` for a set of
submission ids and extracting the metrics in Python, rather than a JSONB path
query in SQL. That is deliberate and matches existing practice: the unit suite
runs on SQLite where `JSONType` degrades to plain `JSON`, and the repository
already avoids dialect-specific SQL for exactly this reason (see the
`score_series` note on timezone conversion).

Volume: a class of 30 students with 10 submissions each is 300 small rows —
the same order as `score_series` already reads. If a cohort-wide query over a
full term ever becomes slow, the mitigation is an **expression index** on
`(analyzer_status -> 'writing_profile')`, which is forward-only, adds no
column, and can be added when there is a measurement justifying it. It is not
needed now and should not be written speculatively.

### 4.3 Indexes and constraints

None required. Existing coverage is sufficient:

- `assessment_details.submission_id` is `UNIQUE` — the profile inherits it.
- `ix_assessment_details_status` covers the status filter.
- S5's history read — this student, this graph, earlier — is served by
  `ix_submissions_user_submitted (user_id, submitted_at)`, with `graph_id` as a
  residual predicate. There is **no** composite `(user_id, graph_id)` index and
  one is not proposed: the index narrows to a single student's submissions, of
  which there are tens, and adding a column to serve a filter at that
  cardinality is a migration bought with no measurement.

**No `CHECK` constraint can protect a JSON blob's contents**, so the profile's
shape is validated in Python at read time by the `Profile` value object, which
returns `None` for a malformed or absent blob rather than raising. This
follows CLAUDE.md rule 27: a malformed rule is inert, never fatal. A profile
written by an older release with a different metric set must degrade to "no
profile", not break a teacher's page.

### 4.4 What is deliberately not stored

- Any comparison, delta, distance, deviation or z-score.
- Any baseline. Baselines are derived at read time from the series.
- Any flag, indicator, ranking or ordering of students.
- Any label, verdict, or free-text conclusion.

The database holds measurements. Every judgement is made by a person looking
at them.

---

## 5. Analytics model

All figures live, none cached — CLAUDE.md rule 36. All figures obey §11.1:
every metric reports an `assessed_count`, trend lines break rather than
interpolate, and missing data renders as unavailable rather than zero.

### 5.1 Personal view (teacher looking at one student)

The primary surface. For each approved measure: the series of values with
dates, the current value, the prior mean and spread, and **n**. Rendered as
lines that break at every gap and at every `assessment_version` boundary.

`baseline` is `None` — never zero, never "average" — when the student has
fewer than `CONSISTENCY_MIN_BASELINE` prior comparable submissions. The
correct rendering of a first submission is **"no baseline yet"**, and it will
be the majority state for most of a term.

### 5.2 Class view

Distribution — median and interquartile range — of each measure across the
class, **per graph**, because graph type confounds every measure (§5.4). Its
purpose is teaching: *"this class's sentence complexity is flat across four
assignments"* is a curriculum finding.

**Never a per-student ranking by deviation.** The class view shows a
distribution and the teacher's own students within it; it does not sort them
by distance from it.

Suppressed entirely below `CONSISTENCY_MIN_CLASS_SAMPLES` (proposed: 5
students with a profile). With three students, "the class distribution"
identifies individuals and means nothing statistically.

### 5.3 Cohort and trend

Aggregation of §5.2 across classes a teacher owns, subject to the existing
rule that a class the caller does not teach is **refused, not returned empty**
(CLAUDE.md rule 33). Buckets are computed in the service layer in
`PLATFORM_TIMEZONE`, as `score_series` already establishes — a cohort must roll
over together.

Engagement is measured against enrolment (rule 35): "8 of 30 students have
enough submissions for a baseline" is the honest headline, and it will be a
small number for most of a term.

### 5.4 Comparability gating

**Two submissions are comparable only when all four hold.** Where any fails,
the pair is excluded from the baseline and the reason is shown:

| Gate | Why |
|---|---|
| Same `assessment_version` | §3.5 — different versions measure different quantities. |
| Same `input_method` | An OCR'd answer and a typed one differ in spelling and sentence segmentation for reasons that are not the student. |
| Same `graph_type` — or the measure is graph-invariant | A pie chart and a line chart demand different language. S1 and S2 tolerate mixing better than S3 does; S3 must be gated to the same graph or normalised by required-target count. |
| Both above `CONSISTENCY_MIN_WORDS` | §7.3 — below it the measures are noise. |

The gates are the feature's main defence against its own false positives, and
they will exclude a great deal of data. That is the correct outcome, and the
count of excluded pairs must be shown, not hidden: a baseline built from two
of a student's nine submissions must say so.

### 5.5 Handling missing history

The dominant case, and the one most likely to be got wrong. Three rules, all
inherited from decisions already approved:

1. **No baseline is `None`, never `0`, never "consistent".** (Rule 32.)
2. **A series breaks at every gap and every version boundary.** Never
   interpolated. (§11.1.)
3. **No backfill.** Submissions scored before this analyzer existed carry no
   profile and never will. Recomputing profiles from stored `answer_text`
   would produce points under a version that never assessed them, which is the
   step change §11.1 exists to prevent.

---

## 6. Privacy and ethics review

### 6.1 What changes, and what does not

**No new data is collected.** Every input is text and metadata the platform
already stores for scoring. No new field is added to a submission, no
telemetry is added to the frontend, and — unlike Sprint 18's remote grammar
provider — **nothing leaves the deployment.** The profile is computed locally
from a parse that has already happened.

That is the strongest privacy claim available and it should be stated plainly
in the documentation, because it is the question an institution will ask first.

### 6.2 What genuinely changes

The platform moves from *marking each piece of work* to *characterising a
student's writing over time*. That is a real change in kind even with no new
data, and it should not be minimised: a longitudinal profile is a more
sensitive artefact than the submissions it is derived from, because it
supports inferences none of them supports alone.

The mitigations are the ones already in the design — nothing stored but
measurements, nothing derived but at read time, nothing visible but to a
teacher who already has the right to read every one of those submissions in
full.

### 6.3 Auditability

**Recommendation for Sprint 19:** structured application logging of every
Layer 2 computation — who asked, for which student, when. Cheap, immediate, no
schema change, and enough to answer "who looked at this" during the pilot.

**Deferred:** a persisted, queryable access log. It needs a table, a retention
policy and an institutional decision about who may read it, and building it
speculatively before anyone can even reach the feature over HTTP is the wrong
order. It should be decided alongside the Sprint 20 endpoint.

### 6.4 Misuse scenarios and mitigations

| Scenario | Mitigation |
|---|---|
| A panel screenshotted into a misconduct hearing as evidence | Every surface carries the limitation text (§7.2) in the surface itself, not in a help page. Measurements with no verdict are much harder to misquote than a score. |
| The feature becomes a de facto AI detector by folk interpretation | No composite index (§S4), no ranking (§5.2), no ordinal indicator (§1.2). There is no single number to reinterpret. |
| A teacher confronts a student with "your writing changed" | This is the residual risk and engineering cannot remove it. Reduced by framing every measure as a teaching observation, by showing n and spread beside every figure, and by never presenting a change as notable in itself. |
| Consistency figures leak into an export and circulate by email | Sprint 19 ships no export path. CLAUDE.md rule 39 already restricts submission exports to scores and metadata; extend it explicitly: **exports carry no consistency figures.** Test at §9.9. |
| A student requests their own data and receives a profile they were never meant to see | A subject access request is a legal right and the profile is their personal data. This needs a documented answer before the feature goes live — it is Open Question Q4 (§11). |

### 6.5 Equity

L2 writers have higher intra-writer variance and improve faster under
instruction, so they will show more and larger changes than L1 writers for
entirely benign reasons. Any surface that draws attention to change therefore
draws it disproportionately to second-language students — on a platform whose
users are university students practising academic English, likely a large
proportion of them.

This is a reason to present measurements rather than notability, and it is a
reason the pilot must measure the distribution of changes by cohort before the
feature is promoted past `teacher` audience.

---

## 7. False positive and false negative analysis

### 7.1 Strongest false-positive sources

**FP1 — Learning. The dominant source, and it is the product working.**
The platform's purpose is to raise target-vocabulary use and writing quality.
A student who improves shows changed vocabulary, changed sentence structure and
changed accuracy — the exact profile of a "sudden linguistic change". Among
students the course succeeds with, the base rate of large change is high.
*Mitigation:* never label change; show direction, and remember that upward
movement on measures the platform teaches is the success case, not the
suspicious one.

**FP2 — The platform's own feedback caused the change.**
A student told in feedback to use *fluctuate* and *plateau* who then uses them
has shifted their vocabulary profile *because the system instructed them to*.
This is not a hypothetical: `generate_feedback` names missing target terms on
every scored submission. *Mitigation:* the personal view should show the
feedback given on the previous submission alongside the change — turning the
feature's largest false-positive source into its most useful teaching output.
This is the single best idea in this document and it should survive review.

**FP3 — Prompt change.** Different graph, different required language.
*Mitigation:* §5.4 gating.

**FP4 — Input-method change.** Handwriting → typing, or `was_ocr_edited`
changing. Spelling density, punctuation and sentence segmentation all move.
*Mitigation:* §5.4 gating on `input_method`; and note that CLAUDE.md rule 20
means a `failed` OCR submission that the student typed into still records
handwriting as the input method — so the gate must read the recorded method,
not infer it.

**FP5 — Length variation.** MATTR and issue density are unstable at short
lengths; a 60-word answer and a 240-word answer are not two samples of one
distribution. *Mitigation:* `CONSISTENCY_MIN_WORDS`.

**FP6 — Legitimate revision.** High self-overlap on a re-attempt is the
designed behaviour (rule 19). *Mitigation:* framing, per S5.

### 7.2 Strongest false-negative source — and why it is fatal to any misconduct reading

**There is no clean baseline.** A student who has used assistance since their
first submission has a perfectly stable profile, because the baseline is
itself assisted. Consistency measurement cannot detect uniform assistance —
not poorly, but *in principle*, since it measures change and there is none.

Two consequences, and the second matters more:

1. The feature cannot find what a misconduct reading would want it to find.
2. **A stable profile is not evidence of anything, and will be read as
   evidence of something.** "Consistent" will be taken as "cleared". That is
   an active harm in the opposite direction from the one the constraints
   guard against, and the only defence is to say so on the surface itself:

   > These measurements show how this student's writing has changed. They
   > cannot show why, and a stable profile is not evidence that anything is or
   > is not the case.

Secondary false negatives: assistance affecting content but not measured form;
a student who edits assisted text into their own register; and gating (§5.4)
correctly excluding the comparison that would have shown a change.

### 7.3 Unavoidable limitations

- **Sample size.** 150–250 words per submission, and typically a handful of
  submissions. Every interval will be wide, and the honest presentation shows
  the width rather than the point.
- **Multiple comparisons.** Six measures × many students × many submissions
  produces "unusual" readings by chance at a predictable rate. *Mitigation:*
  do not test for unusualness at all — show values, not p-values. This is
  another reason no threshold and no flag should exist.
- **No ground truth.** The platform has no labelled corpus of assisted and
  unassisted work, so the false-positive rate of any threshold is unknown and
  unknowable here. *Mitigation:* have no thresholds. It is also why the
  `dark` stage must run for a real term before promotion.

### 7.4 Mitigation summary

| Risk | Mitigation | Where |
|---|---|---|
| Small samples | `CONSISTENCY_MIN_WORDS`, `CONSISTENCY_MIN_BASELINE` | §5.4 |
| Confounds | Four comparability gates | §5.4 |
| Composite reinterpreted as risk | No composite; measures reported separately | §S4 |
| Ranking as accusation | No ordering by any measure | §5.2 |
| Verdict language creeping in | Forbidden-vocabulary test over source and emitted strings | §9.5 |
| Student exposure | `NEVER_STUDENT_ANALYZERS` floor + `for_audience` + no endpoint | §3.6, §3.7 |
| Score contamination | `score=None`, no `SCORE_COLUMNS` entry, D1 tests | §3.3, §9.1 |

---

## 8. Rollout strategy

### 8.1 Dark launch

**Stage 1 — off (ship state).** `writing_profile` is **not** in the default
`ASSESSMENT_ANALYZERS`. `CONSISTENCY_ANALYTICS_ENABLED=false`. A deployment
that pulls the release gets exactly today's behaviour, and
`assessment_version` does not move.

**Stage 2 — dark, one deployment, one term.** Add `writing_profile` to
`ASSESSMENT_ANALYZERS` **and** to `ASSESSMENT_DARK_ANALYZERS`. Profiles are
computed and stored; nobody sees anything. This stage is not optional and not
short: the feature needs history before it can produce output, and the
distributions in §7 are currently unmeasured.

**Stage 3 — teacher, after review of Stage 2 data.** Move to
`ASSESSMENT_TEACHER_ONLY_ANALYZERS`, enable `CONSISTENCY_ANALYTICS_ENABLED`,
expose through the Sprint 20 surface. Requires the Stage 2 distributions to be
reviewed by a person.

**There is no Stage 4.** `writing_profile` never reaches a student, and
`NEVER_STUDENT_ANALYZERS` makes that a property of the build (§3.6).

### 8.2 Migration strategy

**No migration.** `alembic check` must report no new upgrade operations, and
that is a CI assertion, not an intention. Migration 5 remains unwritten and
unclaimed.

### 8.3 Monitoring

| Signal | Why |
|---|---|
| `writing_profile` duration vs `ASSESSMENT_ANALYZER_BUDGET_MS` (250ms) | The supervisor already logs a breach. Expect 1–3ms. |
| Rate of `SKIPPED` (answer too short to profile) | If most answers are skipped, `CONSISTENCY_MIN_WORDS` is wrong. |
| Proportion of students with a usable baseline | The honest measure of whether the feature has anything to say yet. |
| Distribution of each measure's change, overall and by cohort | The §6.5 equity check, and the evidence for Stage 3. |
| Pairs excluded by each gate | A gate excluding everything is a gate that is wrong. |

### 8.4 Rollback

Remove `writing_profile` from `ASSESSMENT_ANALYZERS`. Effects: profiles stop
being written; stored profiles become inert data in a JSON blob nothing reads;
`assessment_version` returns to its previous digest; comparisons return "no
baseline". **No data loss, no score movement, no migration to reverse, and
nothing to undo in the database.** This is the main practical dividend of
storing nothing but measurements.

---

## 9. Regression protection plan

Extending the existing files, not creating parallel ones. Every test below is
a named commitment.

**In `tests/unit/test_assessment_isolation.py`** (the executable form of D1):

1. `test_the_score_is_identical_whether_or_not_the_profile_analyzer_runs` —
   parametrised over the existing five-answer `CORPUS`, comparing `Score`
   field by field with the analyzer present and absent.
2. `test_the_profile_analyzer_emits_no_issues_and_no_score` — structural:
   `output.score is None` and `output.issues == ()` for every corpus answer.
3. `test_no_score_column_exists_for_the_profile_analyzer` —
   `"writing_profile" not in SCORE_COLUMNS`, so a scalar has nowhere to go
   even if one is returned later.
4. `test_the_profile_analyzer_is_deterministic` — the same text twice yields
   identical metrics. This is what §3.1's reproducibility rests on.
5. `test_no_verdict_vocabulary_anywhere` — scans the module source, every
   metric key and every emitted string against
   `{"ai", "gpt", "chatgpt", "cheat", "plagiar", "risk", "suspicio",
   "misconduct", "integrity", "authentic", "probability", "human_written"}`.
   Extends the existing D4 test rather than adding a new mechanism.

**In `tests/unit/test_config.py`:**

6. `test_the_profile_analyzer_can_never_be_student_visible` — asserts
   `analyzer_audience("writing_profile")` is not `STUDENT` under every
   configuration, **including one that names it in a student list and one that
   names nothing at all.** This is the C2 guarantee.

**In `tests/integration/test_assessment_persistence.py`:**

7. `test_a_profile_changes_nothing_awarded` — two students, identical
   vocabulary and writing quality, wildly different profiles, driven through
   the API: identical `Score` rows, identical `xp_events` sums, identical
   `users.total_xp`, identical tiers, identical leaderboard positions. Mirrors
   Sprint 18's `TestGrammarChangesNothingAwarded`.
8. `test_a_student_result_never_carries_a_profile` — `for_audience(STUDENT)`
   over a result containing a profile, under every audience configuration.
9. `test_exports_carry_no_consistency_figures` — over CSV, and over Excel and
   PDF where the optional libraries are present.

**In a new `tests/unit/test_assessment_consistency.py`** (Layer 2, pure
functions, no database):

10. `test_a_first_submission_has_no_baseline` — returns `None`, never `0`.
11. `test_a_baseline_never_crosses_an_assessment_version_boundary` (§3.5).
12. `test_each_comparability_gate_excludes_and_says_why` (§5.4), one case per
    gate.
13. `test_a_malformed_stored_profile_is_inert` — an old or corrupt blob yields
    "no profile", never an exception (rule 27).
14. `test_a_class_view_is_suppressed_below_the_minimum_sample` (§5.2).
15. `test_no_function_orders_students_by_any_measure` — the structural form of
    §1.2, asserted over the module's public surface.

**Coverage:** the sprint holds the project at **95%+**, as Sprint 18 did
(99.05% at `b73c484`). Layer 1 and Layer 2 are both pure functions and should
reach 100%, as `app/assessment/grammar/` did.

---

## 10. Proposed scope

**In scope:** the `writing_profile` analyzer (S1–S5); the
`app/assessment/consistency/` comparison functions with their gates; one
repository read method; `NEVER_STUDENT_ANALYZERS` and the three new settings;
the fifteen tests above; documentation — a new §15 in
`docs/architecture/10-assessment-architecture.md`, `backend/.env.example`,
`docs/PROJECT_PLAN.md`, and the CLAUDE.md rules this establishes.

**Out of scope, explicitly:** any HTTP endpoint or schema (§3.7); any
migration (§4.1); any frontend work; S6 beyond dark computation; S7, S8 and S9
(§2); any stored comparison, flag or ranking; any export path; any backfill.

**Estimated shape:** roughly 5 new modules and 4 modified, around 700 lines of
implementation, around 1,100 lines of test. Smaller than Sprint 18, because
the storage and rollout machinery it needs already exists.

---

## 11. Open questions for the approver

These are product calls. Each has a recommended default; implementation can
proceed on the defaults if you would rather not decide now.

| # | Question | Recommended default |
|---|---|---|
| Q1 | Is the reduced signal set (S1–S5, S6 dark, S7–S9 rejected) accepted? | As proposed |
| Q2 | Is `writing_profile` accepted as the code identifier, with "consistency" kept only as the sprint name? | Yes (§1.5) |
| Q3 | Is "no endpoint in Sprint 19" accepted, deferring the teacher surface to Sprint 20's audience-filtered read layer? | Yes (§3.7) |
| Q4 | A student's subject access request would reach their profile. What is the platform's answer, and does it need to be documented before Stage 2? | Document before Stage 2 begins |
| Q5 | Should FP2's mitigation — showing the previous submission's feedback beside the change — be in Sprint 19 or deferred with the UI? | Design it now, surface it in Sprint 20 |
| Q6 | Should `NEVER_STUDENT_ANALYZERS` be fixed in Sprint 19, or split into its own change since it corrects merged Sprint 17 behaviour? | Fix it in Sprint 19; it is eight lines and C2 depends on it |
| Q7 | How long must Stage 2 (dark) run before promotion is considered? | One full teaching term, with the §8.3 distributions reviewed by a person |

---

*No implementation code, migration, API contract or frontend change accompanies
this document. Implementation begins on approval.*
