import type { StudentRow } from "@/types/api";

/**
 * Who needs the teacher today.
 *
 * There is no "students at risk" endpoint and this does not add one — the
 * signal is derived from the roster `GET /analytics/class/{id}` already
 * returns. It lives here, as a pure function with its own tests, rather than
 * inside a component, because it is a *pedagogical* rule: it decides which
 * names a teacher reads first, and a rule with that much weight should be
 * inspectable in one file.
 *
 * Three properties are deliberate.
 *
 * 1. **A student belongs to exactly one group** — the first they match, in the
 *    order below. A list that names the same person three times reads as three
 *    problems.
 * 2. **The order is by what the evidence supports acting on.** A student who
 *    never started leaves nothing to teach from and needs a different
 *    intervention. One who is finding it hard arrives with their own writing
 *    attached, so a teacher can open it and respond today. One who has gone
 *    quiet is an absence, which is real but the least specific.
 * 3. **A missing average is never a low one.** `average_final_score` is `null`
 *    for a student with no marked work (CLAUDE.md rule 32), and `null < 50` is
 *    `true` in JavaScript. Comparing without the explicit guard would file
 *    every student who has not started under "finding it hard" — a sentence
 *    about work they have not done.
 */

/** The score below which the platform itself calls an attempt a practice tier. */
export const HARD_BELOW_SCORE = 50;

/** Days of silence before a student who *had* been practising is surfaced. */
export const QUIET_AFTER_DAYS = 7;

export type AttentionGroupId = "never-started" | "finding-it-hard" | "gone-quiet";

export interface AttentionEntry {
  student: StudentRow;
  /** Whole days since their last marked work. `null` when there is none. */
  quietDays: number | null;
}

export interface AttentionGroup {
  id: AttentionGroupId;
  /** Read aloud in staff rooms, and occasionally over a student's shoulder. */
  label: string;
  /** What the group means, in one line, for the panel's description. */
  description: string;
  entries: AttentionEntry[];
}

const GROUP_ORDER: readonly AttentionGroupId[] = ["never-started", "finding-it-hard", "gone-quiet"];

const GROUP_TEXT: Record<AttentionGroupId, { label: string; description: string }> = {
  "never-started": {
    label: "Not started",
    description: "Enrolled, with no marked work at all in this period.",
  },
  "finding-it-hard": {
    label: "Finding it hard",
    description: `Practising, but averaging below ${HARD_BELOW_SCORE}.`,
  },
  "gone-quiet": {
    label: "Gone quiet",
    description: `Nothing marked for ${QUIET_AFTER_DAYS} days or more.`,
  },
};

const DAY_MS = 86_400_000;

/** Whole days between a timestamp and now. `null` for absent or unparseable input. */
export function daysSince(iso: string | null | undefined, now: number): number | null {
  if (!iso) return null;
  const when = new Date(iso).getTime();
  if (Number.isNaN(when)) return null;
  // A clock a little behind the server's is ordinary; negative ages are not.
  return Math.max(0, Math.floor((now - when) / DAY_MS));
}

/** Which group a student falls in, or `null` when they need nothing. */
export function classify(student: StudentRow, now: number = Date.now()): AttentionGroupId | null {
  if (student.submission_count === 0) return "never-started";

  const average = student.average_final_score;
  if (average !== null && average !== undefined && average < HARD_BELOW_SCORE) {
    return "finding-it-hard";
  }

  const quiet = daysSince(student.last_submission_at, now);
  if (quiet !== null && quiet >= QUIET_AFTER_DAYS) return "gone-quiet";

  return null;
}

/**
 * The roster, split into the groups a teacher acts on.
 *
 * Groups with nobody in them are dropped rather than rendered empty: "Gone
 * quiet · 0" is a reassurance the first time and noise every time after.
 *
 * Within a group students are ordered by how much they need it — longest
 * silence first, lowest average first — so the top of each list is where to
 * start, not an alphabetical accident.
 */
export function triage(students: StudentRow[], now: number = Date.now()): AttentionGroup[] {
  const buckets = new Map<AttentionGroupId, AttentionEntry[]>();

  for (const student of students) {
    const group = classify(student, now);
    if (group === null) continue;
    const entry: AttentionEntry = {
      student,
      quietDays: daysSince(student.last_submission_at, now),
    };
    const existing = buckets.get(group);
    if (existing) existing.push(entry);
    else buckets.set(group, [entry]);
  }

  return GROUP_ORDER.flatMap((id) => {
    const entries = buckets.get(id);
    if (!entries || entries.length === 0) return [];
    return [{ id, ...GROUP_TEXT[id], entries: entries.sort(orderWithin(id)) }];
  });
}

function orderWithin(group: AttentionGroupId) {
  return (a: AttentionEntry, b: AttentionEntry): number => {
    if (group === "finding-it-hard") {
      return (a.student.average_final_score ?? 0) - (b.student.average_final_score ?? 0);
    }
    if (group === "gone-quiet") return (b.quietDays ?? 0) - (a.quietDays ?? 0);
    return a.student.full_name.localeCompare(b.student.full_name);
  };
}

/** How many students are in the list at all — the panel's headline figure. */
export function attentionCount(groups: AttentionGroup[]): number {
  return groups.reduce((total, group) => total + group.entries.length, 0);
}
