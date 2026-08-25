# Assessment Architecture

> **Revision 1.0** — the framework as built in Sprint 15. The storage schema
> and the API surface are proposed but **not yet approved**, and nothing in
> this document describes a table or an endpoint that exists.

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

### 5.1 `AnalyzerOutput.status`

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

## 6. The supervisor

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

### 6.1 The time budget is observed, not enforced

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

## 7. Issues

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

## 8. Academic integrity is not in this package

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

## 9. Configuration

| Setting | Default | Effect |
|---|---|---|
| `ASSESSMENT_ENABLED` | `true` | Master switch. Off is exactly today's behaviour. |
| `ASSESSMENT_ANALYZERS` | `vocabulary,writing` | Names, in order. Same idiom as `OCR_PROVIDER_ORDER`. |
| `ASSESSMENT_ISSUE_CONFIDENCE_FLOOR` | `0.6` | Below it, recorded but not shown. |
| `ASSESSMENT_MAX_ISSUES_PER_CATEGORY` | `25` | A wall of corrections teaches nothing. |
| `ASSESSMENT_ANALYZER_BUDGET_MS` | `250` | Observed; see §6.1. |
| `GRAMMAR_PROVIDER` | `none` | `none` · `local` · `remote`. |

An unknown analyzer name is logged and skipped rather than raising: a typo in
a deployment's environment must not cost a student the submission that
happened to hit it, which is the rule a malformed achievement rule already
follows. An analyzer named twice is built once — running it twice would double
every issue it finds.

## 10. What Sprint 15 shipped

`vocabulary` and `writing` are adapters over what the engine already computes,
and they emit **no issues**. Missing vocabulary is already carried by
`scores.missing_terms` and the feedback; re-emitting it here would put one
fact in the API twice and double-count it in the teacher analytics. Their job
is to put the existing scores into the assessment's shape so a consumer sees
one complete picture, and to exercise the framework end to end before anything
new is measured.

The diagnostic analyzers, the storage schema and the API surface follow in
sprints 16 to 20.
