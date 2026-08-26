"use client";

import { useQuery } from "@tanstack/react-query";

import { analysisApi, queryKeys } from "@/lib/api";
import type { StudentRubricOut } from "@/types/api";

/**
 * The marking criteria, read from the server rather than written into a
 * component.
 *
 * The weights and the word-count band are deployment configuration — they
 * exist as settings precisely so a study can retune the rubric without a
 * redeploy — so a component that says "70% vocabulary" is a copy that goes on
 * claiming a rubric the server has stopped applying.
 *
 * Cached for the session: it changes when the deployment changes, which is
 * never within one visit. Every screen that mentions the criteria shares this
 * one request.
 */
export function useRubric() {
  return useQuery({
    queryKey: queryKeys.rubric(),
    queryFn: () => analysisApi.rubric(),
    staleTime: Infinity,
    gcTime: Infinity,
    // A screen that mentions the weighting must render without them rather
    // than block on them, so a failure here is quiet by design.
    retry: 1,
  });
}

/** "70% for the words you use, 30% for how it is written." */
export function weightingSentence(rubric: StudentRubricOut | undefined): string | null {
  if (!rubric) return null;
  const vocabulary = Math.round(rubric.vocabulary_weight * 100);
  const writing = Math.round(rubric.writing_weight * 100);
  return `${vocabulary}% of your mark is the target vocabulary you use, ${writing}% is how the description is written.`;
}

/** "150–250 words". */
export function wordBandLabel(rubric: StudentRubricOut | undefined): string | null {
  if (!rubric) return null;
  return `${rubric.target_word_count.min}–${rubric.target_word_count.max} words`;
}
