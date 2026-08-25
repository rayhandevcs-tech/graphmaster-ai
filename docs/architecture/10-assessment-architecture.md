# Assessment Architecture

> **Revision 1.1** — the framework (Sprint 15) plus the first three diagnostic
> analyzers and their storage (Sprint 16). The API surface is proposed but not
> yet built; no endpoint in this document exists.

## 1. What this package is for

`app/nlp` answers *what is this answer worth*. `app/assessment` answers *what
should the student do differently* — grammar, spelling, sentence quality, word
usage and graph accuracy, each located in the student's own text with an
explanation and, where there is one, a correction.

The two are separate packages with a hard boundary between them, and the
boundary is the point.

## 2. The rule everything else follows

**Nothing in this package can change a score.**

The 70/30 rubric in `app/nlp/scoring.py` keeps exactly the two inputs it has
always had. Every analyzer is diagnostic: its findings are reported *beside*
the score, never folded into it.

This is not a stylistic preference. Folding a grammar score into `final_score`
would:

- re-rank every leaderboard, because XP follows the score;
- move students across reward-tier boundaries they have already been shown;
- make every score already in the corpus incomparable with everything scored
  afterwards — and that corpus is the evidence base for the project's
  evaluation.

`tests/unit/test_assessment_isolation.py` asserts it field by field, over a
corpus of five answers chosen to include two that score badly. One of its
tests is structural rather than behavioural: it reads the signature of
`build_score` and fails if a parameter is ever added through which an
assessment could be passed. A behavioural test can only prove that today's
assessment does not move today's score; that one proves the wiring does not
exist.

## 3. Two versions, not one

| Field | Fingerprints | Moves when |
|---|---|---|
| `engine_version` | Weights, tier thresholds, target word count | The **rubric** changes |
| `assessment_version` | Analyzer set, grammar provider, confidence floor, issue cap | The **diagnostic configuration** changes |

Turning on a spelling analyzer changes nothing about how a score was computed.
If it moved `engine_version`, a run of numerically identical scores would be
marked as belonging to a different engine, breaking exactly the cohort
comparison that field exists to protect. So it moves the other one.

Both are fingerprints rather than bare version strings, for the same reason:
the configuration they cover is deployment environment, so two results could
otherwise share a version and be incomparable. Re-ordering the analyzers does
*not* change the fingerprint — the set is what makes two results comparable;
the order only decides which analyzer may read another's output.

## 4. The pipeline

```
Submission → OCR → final text → normalise → spaCy parse ──┐
                                                          │  one Doc
        ┌─────────────────────────────────────────────────┘
        ↓
  detect() ─→ assess() ─→ build_score()      [unchanged, scores the submission]
        │
        └─→ run_assessment() ─→ supervisor ─→ AssessmentResult   [diagnostic]
```

`run_assessment` is called from `app/nlp/analyzer.py` **after** the score has
been computed, and reads the `Doc` that is already parsed. That is the whole
performance story: parsing is the expensive step, and an analyzer that reads
the shared document costs a traversal rather than a parse. An analyzer that
calls `get_nlp()` itself has doubled the cost of the pipeline and should be
rejected in review.

## 5. The analyzer contract

```python
class Analyzer(Protocol):
    name: str
    def run(self, ctx: AssessmentContext) -> AnalyzerOutput: ...
```

`AssessmentContext` carries the text, the shared `Doc`, the normalised text
with its index map, the compiled targets, and the existing engine's own
`DetectionResult` and `WritingQuality`. Passing the last two in is deliberate:
a later analyzer builds on what the vocabulary detector already found rather
than finding it a second way. Two detectors that disagree about the same
sentence make the result indefensible to a student — the same reasoning as
rule 34.

Analyzers are pure and synchronous, take no I/O except through an injected
provider, and never mutate the context. That is what keeps every one of them
testable without HTTP or a database.

### 5.1 Severity

Four levels, on one ordered scale:

| Level | Meaning |
|---|---|
| `info` | **Not a mistake.** A preference, or an observation. |
| `low` | Worth knowing; the reader would not have stumbled. |
| `medium` | A real error against the conventions being taught. |
| `high` | It changes what the writing means, or contradicts the data. |

`INFO` is not the bottom of a ladder of badness — it is the rung that means
the student did nothing wrong. The specification asks that acceptable
stylistic variation is never penalised, and `IssueSeverity.is_mistake` puts
that in the type rather than in a convention an analyzer author has to
remember. `error_count` counts everything above `INFO`, so a student is never
told they made nine mistakes when four of them were suggestions.

### 5.2 `AnalyzerOutput.status`

Four values, because there are four distinct reasons an issue list can be
empty:

| Status | Meaning |
|---|---|
| `ok` | It ran. An empty list means it found nothing. |
| `unavailable` | Not configured on this server — a deployment fact, not a fault. |
| `skipped` | Deliberately not run for this submission. |
| `failed` | It broke. |

`unavailable` and `failed` are kept apart on purpose. Collapsing them would
make "this server has no grammar checker" indistinguishable from "the grammar
checker crashed", and only one of those is worth waking someone for. It also
prevents the worst UI failure available here: telling a student their grammar
is perfect on a server that never checked it.

## 6. The three diagnostic analyzers

### 6.1 Spelling

The hard part is not finding misspellings. It is not finding them in the words
that only look wrong, and the exemption set is built per submission from three
sources: the target vocabulary, the inflections the detector actually matched,
and every word written on the chart. A student describing a chart of
Bangladeshi districts will write the district names; they are the subject, not
typos.

Two traps are worth recording because both were found by testing rather than
by reasoning:

- **spaCy tags an unknown word `PROPN`.** The tagger falls back to proper noun
  for any word it does not recognise — which is exactly what a misspelling is.
  Exempting `PROPN` therefore exempted every typo in the answer. Names are
  identified by the entity recogniser and by capitalisation *away from the
  start of a sentence*, where a capital is a choice rather than a convention.
- **A capitalised word the recogniser declines to claim is ambiguous.**
  "Sylhet" and "Gradualy" look identical to everything this analyzer can see,
  and telling a student their own city is a misspelling of "Sleet" costs far
  more than the typo it might have caught. Those are reported at a confidence
  below the floor: recorded, counted, shown to nobody.

The score is computed over the issues that would actually be displayed. Saying
"we are not confident enough to show this" and then marking a student down for
it is a contradiction, which is why the confidence floor is injected into the
analyzer rather than applied only downstream.

### 6.2 Sentence quality and length

Word count, sentence count, paragraph count and mean sentence length are all
readings off one parse, so the specification's Features 3 and 4 share an
analyzer — two would mean two passes and two chances for the numbers to
disagree.

It reports readability as a Flesch index over a syllable heuristic documented
in `text.py`, including its known error cases. The heuristic is used for one
number that nobody is marked on; being one syllable out moves the index by
about a point.

The missing-overview finding reads `ctx.writing.has_overview` rather than
detecting an overview again. The rubric has already decided, and a second
opinion on the same page would be indefensible to a student.

### 6.3 Word usage

**Every issue this analyzer produces is a suggestion**, and that is a design
decision rather than a limitation. Detecting genuinely incorrect word choice
needs a model this platform does not have; guessing produces confident false
positives, which teach a student to ignore the panel.

Three findings: an over-used word, a conversational register with the academic
alternative, and a narrow lexical range. Two exemptions keep them honest — the
target vocabulary and the chart's own series names are the subject and cannot
be "repetition" — and one distinction does the same for register: a
comparative or superlative is never informal. "The smallest contributor" is how
a comparison between series is *correctly* expressed, and flagging it would
penalise the structure the exercise teaches.

## 7. The supervisor

Every call into an analyzer goes through `app/assessment/supervisor.py`, which:

- times it;
- catches `Exception` and converts it to a `failed` outcome;
- records the reason as the **exception type, never its message**, because a
  message can quote the student's own writing and the detail is bound for
  operator logs and a teacher's screen;
- applies the confidence floor, deduplicates, caps issues per category, and
  orders what survives for reading.

`BaseException` is deliberately not caught: a `KeyboardInterrupt` is the
process being asked to stop, and swallowing it would turn a shutdown into a
hang.

There is a second containment layer above it. `run_assessment` wraps the
construction of the analyzer list and the context, so a malformed
`ASSESSMENT_ANALYZERS` value cannot fail an analysis that would otherwise have
scored perfectly well — it simply returns `None`, the same shape a submission
scored before this feature existed has.

### 7.1 The time budget is observed, not enforced

`ASSESSMENT_ANALYZER_BUDGET_MS` produces a warning and a recorded duration; it
does not cancel the analyzer.

A CPU-bound Python call cannot be preempted from another thread without
leaving the interpreter in an unpredictable state, and killing one mid-parse
would be a worse failure than the slowness it was meant to prevent. Genuine
cancellation belongs to whichever provider does I/O — the grammar client's
socket timeout — where it can be done safely, and that is where it will be
implemented.

Recording the duration is not decoration: it is the evidence for whether the
budget is right, and it is what the deferred-execution decision will be made
from.

## 8. Issues

One frozen dataclass for every analyzer, so the result page can show a single
list ordered by where the problems appear rather than five lists the student
must correlate by eye.

Offsets are half-open indices into the **original submitted text**, so
`text[start:end]` is exactly the span — the same contract the vocabulary
highlights already honour. An analyzer working on normalised text must map its
offsets back through `NormalisedText` before constructing an issue, or the
highlight lands on the wrong words.

Three fields carry rules worth stating:

- **`subtype`** is a stable slug, and it is the analytics grouping key. The
  human wording lives in `explanation` and can be rewritten without breaking a
  year of "the mistakes this class makes most".
- **`severity`** exists so a preference can say it is a preference. Only
  `error` claims the student got something wrong; acceptable stylistic
  variation is a `suggestion` and is never penalised.
- **`confidence`** feeds a configurable floor. Issues below it are recorded
  and *counted* rather than dropped silently, because a floor set too high is
  invisible otherwise and the suppressed count is what says so.

The per-category cap trims by confidence rather than by position: a page of
low-grade guesses at the top of an answer must not crowd out a certain finding
further down. A trimmed category is named in `truncated_categories`, so a
truncated list can be shown as truncated instead of as complete.

## 9. Academic integrity is not in this package

Integrity is teacher-facing. A student must never see a risk score, a
probability, a percentage, or an AI-related label.

The cheapest way to keep that true is structural: `AssessmentResult` — the
object the student's result page is built from — has no integrity field, so
the leak cannot be made by a careless serialiser.
`tests/unit/test_assessment_isolation.py` asserts that no attribute on it
matches an integrity vocabulary, and that no `IssueCategory` names cheating,
AI or risk. A category called `ai_generated` would put an accusation on a
student's screen no matter how the surrounding copy was worded.

When the engine is built it will live in `app/integrity`, behind its own
endpoints and its own role dependency.

## 10. Configuration

| Setting | Default | Effect |
|---|---|---|
| `ASSESSMENT_ENABLED` | `true` | Master switch. Off is exactly today's behaviour. |
| `ASSESSMENT_ANALYZERS` | `vocabulary,writing,spelling,sentence,word_usage` | Names, in order. Same idiom as `OCR_PROVIDER_ORDER`. |
| `ASSESSMENT_DARK_ANALYZERS` | *(empty)* | Runs and is stored; shown to nobody. |
| `ASSESSMENT_TEACHER_ONLY_ANALYZERS` | *(empty)* | Shown to teachers, withheld from students. |
| `ASSESSMENT_ISSUE_CONFIDENCE_FLOOR` | `0.6` | Below it, recorded but not shown. |
| `ASSESSMENT_MAX_ISSUES_PER_CATEGORY` | `25` | A wall of corrections teaches nothing. |
| `ASSESSMENT_ANALYZER_BUDGET_MS` | `250` | Observed; see §6.1. |
| `GRAMMAR_PROVIDER` | `none` | `none` · `local` · `remote`. |

An unknown analyzer name is logged and skipped rather than raising: a typo in
a deployment's environment must not cost a student the submission that
happened to hit it, which is the rule a malformed achievement rule already
follows. An analyzer named twice is built once — running it twice would double
every issue it finds.

### 10.1 Staged rollout

An analyzer moves `dark` → `teacher` → `student` as confidence in its
false-positive rate grows, and back the moment it does not, without a
redeploy. The most restrictive listing wins: a deployment mid-way through a
rollback must not still be showing output someone has just decided to
withdraw.

The audience is **frozen onto the row at assessment time**. Read at display
time instead, a stage that had since moved would retroactively reveal what was
dark when the work was marked. Filtering builds a new result object rather
than omitting fields at serialisation, so a field added to a schema later
cannot leak what an audience was not meant to see.

## 11. Storage

Three tables, added by migration 4 and altering nothing that existed.

| Table | Grain |
|---|---|
| `assessment_details` | One row per submission, mirroring `scores` |
| `assessment_issues` | One row per finding, whichever analyzer found it |
| `graph_accuracy_claims` | One row per claim about the chart (written from sprint 17) |

`assessment_details` carries only the five categories the assessment engine
introduces. The vocabulary and writing scores stay on `scores`: a second copy
is a second thing to keep in step, and two columns that can disagree about one
number are worse than one.

A `NULL` category score means *this analyzer did not run here* — a different
fact from `0.0`, which means it ran and the work was poor. `analyzer_status`
records what ran, how long it took and why it stopped, which is what makes "no
grammar issues" distinguishable from "grammar was never installed".

Writes join the scoring transaction. The assessment and the score it
accompanies land together or not at all — and when the assessment cannot be
built, the score still lands alone, which is the same shape a submission
marked before this feature existed has.

## 12. What is built

`vocabulary` and `writing` are adapters over what the engine already computes,
and they emit **no issues**. Missing vocabulary is already carried by
`scores.missing_terms` and the feedback; re-emitting it here would put one
fact in the API twice and double-count it in the teacher analytics. Their job
is to put the existing scores into the assessment's shape so a consumer sees
one complete picture.

`spelling`, `sentence` and `word_usage` are the first analyzers that find
something. All five run in roughly three milliseconds on a warmed process,
because they share the parse that has already happened.

Still to come: the grammar provider and the graph-accuracy analyzer
(sprints 17–18), the integrity engine (sprint 19), and the API and analytics
surfaces that read any of it.
