# Assessment Architecture

> **Revision 1.3** — the framework (Sprint 15), the first three diagnostic
> analyzers and their storage (Sprint 16), graph accuracy (Sprint 17), and the
> grammar provider chain (Sprint 18). The API surface is proposed but not yet
> built; no endpoint in this document exists.

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

## 6. The diagnostic analyzers

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

### 6.4 Graph accuracy

The analyzer with the most educational value and the most dangerous failure
mode. Telling a student their reading of a trend is wrong, when it was right,
is worse than saying nothing — so almost every rule in it is a reason *not* to
reach a verdict.

**Claims come from the vocabulary detector.** Every direction, peak and
comparison term the student used has already been found and located; those
occurrences *are* the claims. The analyzer does not look for direction words a
second way, because two detectors disagreeing about one sentence would make the
result indefensible to the student — the same reasoning as rule 34.

The seven vocabulary categories map onto four kinds of claim:

| Categories | Claim | Checked against |
|---|---|---|
| `increase`, `decrease`, `stability`, `fluctuation` | trend | The series' net movement and turning points |
| `peak` | peak | The label of the maximum reading |
| `lowest` | trough | The label of the minimum reading |
| `comparison` | comparison | Whether one series is above the other at *every* reading |

**Attribution comes first, and often fails.** A claim on a one-series chart
needs no resolution — there is nothing else it could be about. Otherwise the
sentence must name exactly one series through a *distinctive* word: one that
appears in that series' label and no other. Two series in one sentence with a
trend claim between them is a guess, and a guess is not worth telling a student
they misread their chart.

**Everything else is `unverified`.** No ordered axis (a pie chart is a
snapshot; a bar chart's categories may be in any order); a peak with no year
named ("numbers peaked" is true of every series that has a maximum); a range of
years rather than a point; two lines that cross; a comparison with no
direction. Each records *why*, so a teacher looking at a false negative can see
whether the fault was the sentence or the data.

**Correct claims are stored too.** "You read four trends and got three right"
is the educational figure and cannot be recovered from the errors alone.

#### What counts as movement

Net change is measured against the series' **typical level**, not against its
own range. Against the range, a genuinely flat series is the worst case:
readings of 230, 240, 235, 250 span only 20, so a net rise of 20 reads as 100%
movement — the flatter the line, the more confidently it is called a trend, and
a student who correctly wrote "remained stable" is contradicted. Against the
mean, that series moves 8% and is stable, while 5 to 410 moves 247% and is not.

This was found by running the analyzer against a real chart, not by reasoning
about it, and `test_a_nearly_level_series_is_stable` is what keeps it fixed.

#### Comparisons are pairwise

"Was hydroelectric higher than wind" is a question about two series. Asking
whether either is above *everything else* answers a different question and, on
a three-series chart where one line overtakes another, leaves every comparison
unchecked. `ChartFacts.dominant(a, b)` compares the pair, and returns nothing
where they cross.

#### Severity

Graph accuracy is the first analyzer to emit `HIGH`: a student who reports the
opposite trend, or inverts a comparison, has described a different chart. A
claim about a *level* series — "output increased" where it did not move much —
is `MEDIUM`: wrong, but not an inversion, and there was less to see.

Corrections are phrased as what the chart shows, never as an accusation. A
misread trend is the most useful thing this platform can tell somebody, and it
is only useful if they read it.

### 6.5 Grammar

The only analyzer with an outbound dependency, and the only one a deployment
can switch off without editing the analyzer list. Both facts shape it.

#### The provider chain

`app/assessment/grammar/` holds a provider abstraction modelled on the OCR
chain, for the same reasons:

| Provider | `GRAMMAR_PROVIDER` | What it is |
|---|---|---|
| `DisabledGrammarProvider` | `none` *(default)* | No engine here. A real object, not a null check. |
| `LocalLanguageToolProvider` | `local` | A LanguageTool HTTP server inside your own network. |
| `RemoteLanguageToolProvider` | `remote` | A hosted LanguageTool. Student writing leaves the building. |

`is_available()` answers a *configuration* question and is probed at startup;
`check()` answers a *per-submission* question and may fail at any time.
Keeping them apart is what lets a server with no grammar engine report "not
installed here" while a server whose engine has just fallen over reports a
fault — and only one of those is worth waking someone for.

The analyzer never names an implementation. `build_grammar_provider` chooses
one and the analyzer receives it, so every path through the analyzer — a
timeout, a 502, a truncated JSON document, no engine at all — is exercised
against a fake with no network, no JVM and no container.

A misconfiguration degrades to `none` rather than raising, with the exception
of `remote` without an endpoint, which is refused at boot. Choosing `remote`
is a decision that student writing leaves the institution, and a deployment
that made it needs to know immediately if it is not actually happening.

#### The findings are narrower than LanguageTool's

Three kinds of match are dropped rather than reported, and each is dropped
because another analyzer already owns that ground:

- **Misspellings.** `spelling` owns them, with an exemption set built from
  this exercise's curated vocabulary and the chart's own labels — information
  LanguageTool does not have. It would flag "Sylhet" and half the target
  terms, and reporting them under `grammar` would relabel a spelling mistake
  as a grammar mistake and corrupt the analytics slug.
- **Style and register.** LanguageTool's style rules are tuned for general
  English prose: they object to the passive voice, to long sentences and to
  hedging, which is the register academic graph description is *taught in*.
  `word_usage` covers register with domain knowledge instead. FR-5's rule
  that acceptable variation is never penalised is not served by reporting
  those quietly — it is served by not reporting them.
- **Locale violations.** en-GB versus en-US is a deployment's choice, not a
  student's error.

Anything the rule table has never seen is still reported, as `grammar_error`
at `LOW` — kept, but not guessed into a specific subtype whose analytics would
then be wrong.

The subtype is derived from LanguageTool's **rule identifier**, which it keeps
stable, rather than from the message, which is localised and rewritten between
releases. A year of "the mistakes this class makes most" is grouped by that
slug.

#### Two things that only show up in production

**The timeout is a total budget, not a per-attempt one.** A three-second
timeout with one retry would otherwise permit six seconds of waiting, and this
call happens inside the request that is scoring a submission. Each attempt
gets whatever is left, so the configured number is the worst case however many
attempts are made. Only transient failures are retried: a 4xx means the
request itself is wrong, and repeating it spends the budget to be told so
again.

**Offsets arrive in UTF-16 code units.** LanguageTool is a Java service, and
Java counts strings in UTF-16. For ordinary prose that is identical to
Python's indexing, but one emoji in an answer shifts every subsequent offset
by one and every highlight after it lands on the wrong words. The conversion
table is built only when the text actually contains a character outside the
basic plane, so the common case pays nothing.

#### The grammar figure

`grammar_score` is on `assessment_details` beside the other diagnostic scores,
and `grammar_accuracy_percentage` and `grammar_issue_count` sit in that row's
`analyzer_status` metrics. Accuracy is measured per **word** rather than per
sentence: sentence counts come from the parser's own segmentation, and a
run-on sentence — itself a grammar finding — would shrink the denominator and
flatter the answer that contained it.

Only findings that assert a mistake *and* clear the confidence floor count
against it. Marking a student down for a note captioned "we are not sure about
this", or for one that explicitly says they did nothing wrong, is the
contradiction the severity scale exists to prevent.

Answers under 25 words are checked but not scored. One error in six words is
83% accuracy, and printed beside work a student did well that number says more
about the answer's length than about its grammar.

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
| `ASSESSMENT_ANALYZERS` | `vocabulary,writing,spelling,sentence,word_usage,graph_accuracy,grammar` | Names, in order. Same idiom as `OCR_PROVIDER_ORDER`. |
| `ASSESSMENT_DARK_ANALYZERS` | *(empty)* | Runs and is stored; shown to nobody. |
| `ASSESSMENT_TEACHER_ONLY_ANALYZERS` | *(empty)* | Shown to teachers, withheld from students. |
| `ASSESSMENT_ISSUE_CONFIDENCE_FLOOR` | `0.6` | Below it, recorded but not shown. |
| `ASSESSMENT_MAX_ISSUES_PER_CATEGORY` | `25` | A wall of corrections teaches nothing. |
| `ASSESSMENT_ANALYZER_BUDGET_MS` | `250` | Observed; see §6.1. |
| `GRAMMAR_PROVIDER` | `none` | `none` · `local` · `remote`. See §6.5. |
| `GRAMMAR_HOST` / `GRAMMAR_PORT` | `localhost` / `8081` | Where the local engine listens. |
| `GRAMMAR_API_URL` | *(empty)* | Base URL. Required for `remote`; overrides host/port for `local`. |
| `GRAMMAR_TIMEOUT_SECONDS` | `3.0` | **Total** budget for one check, retries included. |
| `GRAMMAR_MAX_RETRIES` | `1` | Remote only, inside the budget above. Local never retries. |
| `GRAMMAR_MAX_CHARS` | `20000` | Longer answers are truncated, not refused. |
| `GRAMMAR_HEALTH_TTL_SECONDS` | `60` | A negative health probe expires, so a late-starting engine recovers. |
| `GRAMMAR_LANGUAGE` | `en-GB` | Part of the assessment fingerprint — see §3. |

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
| `graph_accuracy_claims` | One row per claim about the chart, correct ones included |

`assessment_details` carries only the five categories the assessment engine
introduces. The vocabulary and writing scores stay on `scores`: a second copy
is a second thing to keep in step, and two columns that can disagree about one
number are worse than one.

A `NULL` category score means *this analyzer did not run here* — a different
fact from `0.0`, which means it ran and the work was poor. `analyzer_status`
records what ran, how long it took and why it stopped, which is what makes "no
grammar issues" distinguishable from "grammar was never installed".

A contradicted claim is linked to the correction it produced; a correct or
unverified one carries no issue, which a `CHECK` constraint enforces. The link
is matched on the span and the claim type at write time rather than threaded
through the engine as an object reference — the issue and the claim are
separate frozen values, and an identity between them would exist only to
survive this one write.

Writes join the scoring transaction. The assessment and the score it
accompanies land together or not at all — and when the assessment cannot be
built, the score still lands alone, which is the same shape a submission
marked before this feature existed has.

### 11.1 Reading assessment data back

Two rules govern every figure derived from these tables, both approved as
product decisions rather than inferred:

1. **Every assessment metric is reported with an `assessed_count`.** No
   submission scored before sprint 16 carries an assessment, and there is no
   backfill, so any average is over a subset.
2. **A trend line breaks where `assessed_count` is zero. It is never
   interpolated.** Silently averaging over "the ones that have data" puts a
   step change on the day the engine was enabled, which reads as a sudden
   improvement in the cohort.

Missing assessment data is rendered as **unavailable**, never as zero. A
student who was marked before this existed did not score nothing.

## 12. Privacy, deployment and operational limits

Grammar is the first part of this platform that can send a student's writing
somewhere else, so its constraints are recorded here rather than left to a
deployment to discover.

### 12.1 Privacy

`GRAMMAR_PROVIDER=remote` posts the student's answer to a third party. That is
a data-protection decision for whoever runs the institution's deployment, and
it is why:

- the default is `none`, and neither engine is enabled by an image;
- `local` exists at all — a LanguageTool container inside your own network
  gives the same findings with nothing leaving it;
- nothing about the student travels with the text. No name, no identifier, no
  submission id, no class. The request carries the answer, the language and a
  service-level user agent, and nothing else;
- the endpoint never appears in an issue, a failure detail or anything a
  teacher's screen renders. Failure messages name the *type* of failure, and
  `tests/unit/test_grammar_providers.py` asserts the hostname is absent.

### 12.2 Deployment

    docker compose --profile grammar up

starts a LanguageTool container and nothing else changes; set
`GRAMMAR_PROVIDER=local` to use it. It is deliberately outside the default
stack: it is a JVM with a few hundred megabytes of dictionaries, which is a
poor trade for a developer working on the submission pipeline.

n-gram data is not configured. It is several gigabytes and buys confusion-pair
rules this analyzer does not report anyway.

### 12.3 Operational limitations

Two, both real and both worth stating plainly.

**The check blocks the event loop.** `analyse()` is synchronous and is called
directly from an async service, so a grammar request occupies the worker for
its duration — up to `GRAMMAR_TIMEOUT_SECONDS`. With the default provider this
costs nothing, and with a local engine it is a few tens of milliseconds. With
a remote engine on a slow link it is the whole budget, and other requests on
that worker wait. The bounded total budget is what keeps this survivable
rather than unbounded; moving `analyse()` onto a worker thread is the actual
fix, and it belongs in a change that can be load-tested on its own rather than
bundled with a feature. Until then, `remote` in production wants more workers
than `none` does.

**The health probe is per-process.** Each worker probes and caches
independently, so an engine that comes back up is noticed within
`GRAMMAR_HEALTH_TTL_SECONDS` by each worker separately rather than all at
once.

## 13. Teacher analytics

`AssessmentRepository` carries the aggregation a class report is built from.
No endpoint exposes it yet — that is the next sprint — but the queries exist,
are tested against a real database, and obey §11.1:

| Method | Answers |
|---|---|
| `issue_frequency(ids, category=…)` | The commonest mistakes, most frequent first. Grouped by `subtype`. |
| `score_summary(ids, analyzer)` | A mean, **with** the `assessed_count` it was taken over. |
| `score_series(ids, analyzer)` | Every assessed score with its timestamp, unbucketed. |

`score_summary` returns `average=None` — never `0.0` — when nothing was
assessed, and rows with a NULL score are excluded from both figures rather
than averaged in as noughts. A class whose grammar was never checked is not a
class that scored nothing.

`score_series` is deliberately unbucketed. A trend line's periods are
boundaries in `PLATFORM_TIMEZONE` — a cohort must roll over together — and
expressing that in SQL would push a timezone conversion into the database,
where SQLite and PostgreSQL disagree about how to do it. The service layer
buckets in the platform's zone, the way every other date already is.

Asking for an analyzer with no score column raises rather than returning
nothing: answering "no data" for a misspelled name would report a working
class as one with nothing to show, which is the same lie an empty forbidden
report tells.

## 14. What is built

`vocabulary` and `writing` are adapters over what the engine already computes,
and they emit **no issues**. Missing vocabulary is already carried by
`scores.missing_terms` and the feedback; re-emitting it here would put one
fact in the API twice and double-count it in the teacher analytics. Their job
is to put the existing scores into the assessment's shape so a consumer sees
one complete picture.

`spelling`, `sentence`, `word_usage` and `graph_accuracy` are the analyzers
that find something without help. `grammar` finds something when an engine is
configured, and says so plainly when one is not. The six that need no network
run in roughly three milliseconds on a warmed process, because they share the
parse that has already happened.

Still to come: the integrity engine (sprint 19), and the API and analytics
surfaces that read any of it.
