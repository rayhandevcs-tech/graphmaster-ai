/**
 * Word counting, matching the server's rule.
 *
 * The API counts with `\b[\w'-]+\b` (`app/ocr/postprocess.py`), so "well-known"
 * is one word and an apostrophe does not split a contraction. Counting
 * differently here would show a student 214 words while the score was computed
 * over 209, and the length component of the writing score is derived from that
 * number — a disagreement reads as the marking being wrong.
 */
const WORD = /\b[\w'-]+\b/g;

export function countWords(text: string): number {
  return text.match(WORD)?.length ?? 0;
}

/** "1 word" / "214 words". */
export function wordsLabel(count: number): string {
  return count === 1 ? "1 word" : `${count.toLocaleString()} words`;
}
