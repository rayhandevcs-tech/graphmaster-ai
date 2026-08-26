import type { DetectedTermOut } from "@/types/api";

/** A run of the answer, either plain or one occurrence of a target term. */
export interface AnswerSegment {
  text: string;
  term: DetectedTermOut | null;
}

interface Span {
  start: number;
  end: number;
  term: DetectedTermOut;
}

/**
 * The student's answer, split into plain runs and detected-term runs.
 *
 * The offsets are real. Normalisation keeps an index back to the original text
 * for every character it touches, precisely so a highlight lands on what the
 * student actually wrote rather than on a cleaned-up copy of it (08-nlp
 * §2, and rule 15 in CLAUDE.md). This function is therefore allowed to trust
 * them — but not blindly: an offset outside the text is dropped rather than
 * rendered, because slicing past the end silently produces an empty span and
 * the answer would come back missing a word with nothing to explain it.
 *
 * Overlaps are resolved longest-first. Two targets can legitimately cover the
 * same words — "rise" inside "sharp rise" — and rendering both would nest one
 * mark inside another and double-count the word visually.
 */
export function splitAnswer(text: string, terms: readonly DetectedTermOut[]): AnswerSegment[] {
  if (!text) return [];

  const spans: Span[] = [];
  for (const term of terms) {
    for (const position of term.positions ?? []) {
      const [start, end] = position;
      if (typeof start !== "number" || typeof end !== "number") continue;
      if (start < 0 || end > text.length || end <= start) continue;
      spans.push({ start, end, term });
    }
  }

  spans.sort((a, b) => a.start - b.start || b.end - a.end);

  const segments: AnswerSegment[] = [];
  let cursor = 0;

  for (const span of spans) {
    if (span.start < cursor) continue;
    if (span.start > cursor) segments.push({ text: text.slice(cursor, span.start), term: null });
    segments.push({ text: text.slice(span.start, span.end), term: span.term });
    cursor = span.end;
  }

  if (cursor < text.length) segments.push({ text: text.slice(cursor), term: null });

  return segments;
}
