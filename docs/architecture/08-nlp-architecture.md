# NLP Architecture

## 1. Purpose

The NLP pipeline evaluates a learner's written graph description using **spaCy**, producing the vocabulary and structural scores stored in `nlp_analyses` (see [02-database-schema.md](./02-database-schema.md) §4.3) that drive the feedback view ([06-frontend-architecture.md](./06-frontend-architecture.md)) and the XP award for a submission ([09-gamification-architecture.md](./09-gamification-architecture.md)).

This pipeline runs **per submission**, triggered asynchronously as described in [05-backend-architecture.md](./05-backend-architecture.md) §5.

## 2. Pipeline Stages

```mermaid
sequenceDiagram
    participant API as FastAPI
    participant Q as Job Queue
    participant W as NLP Worker (spaCy)
    participant DB as PostgreSQL

    API->>Q: enqueue nlp_scoring job {submission_id}
    Q->>W: deliver job
    W->>DB: fetch submission.response_text + graph_prompt (target_vocabulary, ocr structured_labels)
    W->>W: spaCy pipeline: tokenize, POS-tag, lemmatize, parse
    W->>W: compute lexical diversity
    W->>W: compute academic/target vocabulary coverage
    W->>W: compute grammar signal score
    W->>W: compute structure score
    W->>W: generate feedback_summary
    W->>DB: upsert nlp_analyses; update submissions.status=scored, overall_score
    W->>API: (via DB state) triggers gamification XP award
```

## 3. Linguistic Processing

- **Tokenization, POS tagging, lemmatization, dependency parsing**: performed by spaCy's standard English pipeline, forming the basis for every downstream metric — lemmas normalize vocabulary counting (e.g., "increased"/"increasing"/"increase" count toward one vocabulary item), and POS tags identify content words (nouns, verbs, adjectives, adverbs) versus function words for diversity metrics.
- **Sentence segmentation**: used to assess paragraph structure (§3.4) and to generate targeted, sentence-level feedback rather than only a single document-level score.

## 4. Scoring Metrics

### 4.1 Lexical Diversity Score
- Computed via a type-token ratio variant (e.g., MTLD or a moving-average TTR) over content-word lemmas, which is more stable across varying response lengths than a raw type-token ratio.
- Rewards varied vocabulary usage over repetition, independent of whether the "right" words were used — captured separately in §4.2.

### 4.2 Academic / Target Vocabulary Score
- Two components combined into `academic_vocabulary_score`:
  1. **General academic register**: coverage of terms from a curated academic word list appropriate for graph-description writing (e.g., "fluctuate," "surpass," "proportion," "significant").
  2. **Prompt-specific target vocabulary**: coverage of `graph_prompts.target_vocabulary`, cross-referenced against `ocr_extractions.structured_labels` so the pipeline can confirm the learner referenced the chart's actual subject matter (e.g., did they mention "renewable energy" and "2010–2020" for a prompt with those OCR-extracted labels) rather than writing generically.
- Matched terms are recorded in `nlp_analyses.target_vocabulary_hits` (JSONB) for transparent, explainable feedback ("You used 4 of 8 key terms").

### 4.3 Grammar Signal Score
- A heuristic score derived from the dependency parse: sentence well-formedness signals (presence of a main verb, subject-verb agreement patterns detectable via POS/morphology, run-on sentence detection via clause counting), **not** a full grammar-correction system.
- Framed explicitly as a *signal*, not a definitive grammar checker — the architecture leaves room to later swap in or augment with a dedicated grammar-checking model without changing the pipeline's I/O contract.

### 4.4 Structure Score
- Evaluates adherence to graph-description writing conventions: an opening overview sentence, body paragraph(s) covering key trends/comparisons, and appropriate use of comparison/trend language.
- Detected via sentence position + lexical cues (e.g., trend verbs like "rose," "declined," "remained stable" appearing in body sentences; overview-style phrasing like "overall" or "in general" appearing early).

### 4.5 Composite Score
`submissions.overall_score` is a weighted composite of the four metrics above, computed by the worker and written back to `submissions` in the same transaction as the `nlp_analyses` insert:

| Component | Default Weight |
|---|---|
| Lexical diversity | 20% |
| Academic/target vocabulary | 35% |
| Grammar signal | 20% |
| Structure | 25% |

Weights are configuration, not hardcoded, so the rubric can be tuned without a code deploy — see extensibility notes in §6.

## 5. Feedback Generation

`nlp_analyses.feedback_summary` is generated from the same computed metrics — a template-driven natural-language summary (not free-form generative text) that:
- Highlights which target vocabulary terms were used vs. missed (from §4.2)
- Flags the weakest-scoring dimension for the learner to focus on next
- Avoids exposing raw internal metric names, translating scores into learner-facing language (e.g., "Try using more comparison language like 'in contrast to' or 'whereas'")

## 6. Extensibility for Future ML-Based Scoring

The pipeline's I/O contract — `response_text` in, a fixed set of named scores + `feedback_summary` out — is intentionally decoupled from the *method* used to compute them. This allows individual metrics to be upgraded independently without touching the API, database schema, or frontend:

- The grammar signal score (§4.3) is the most likely first candidate to be replaced by a dedicated grammar-checking model or fine-tuned classifier.
- The structure score (§4.4) could later incorporate a trained classifier over paragraph structure instead of lexical-cue heuristics.
- Any such upgrade only changes the NLP worker's internals and bumps `nlp_analyses.engine_version`, exactly as described for OCR engine upgrades in [07-ocr-architecture.md](./07-ocr-architecture.md) §3.5.

## 7. Failure Handling

Consistent with the OCR worker's approach ([07-ocr-architecture.md](./07-ocr-architecture.md) §5): unhandled exceptions during scoring mark the submission `status = 'failed'` with an error message rather than leaving it stuck `pending`, and processing is idempotent (upsert keyed by `submission_id`) to tolerate at-least-once job redelivery per [05-backend-architecture.md](./05-backend-architecture.md) §5.
