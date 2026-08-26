"use client";

import { Progress } from "@/components/ui/progress";
import { Textarea } from "@/components/ui/textarea";
import { SaveStatus, type SaveState } from "./save-status";
import { countWords, wordsLabel } from "@/lib/text/words";
import { cn } from "@/lib/utils";

/** The length the task expects, as the server reports it. */
export interface WordBand {
  min: number;
  max: number;
}

/**
 * The box the answer is written in.
 *
 * Shared by both routes into a submission: a typed attempt starts here empty,
 * and a handwritten one starts here holding whatever the recogniser read. That
 * is FR-4.7 — the extraction is editable text in the same editor, not a
 * read-only preview with a separate "correct it" mode.
 */
export function AnswerEditor({
  id,
  value,
  onChange,
  saveState,
  disabled = false,
  placeholder,
  rows = 14,
  band,
}: {
  id: string;
  value: string;
  onChange: (next: string) => void;
  saveState: SaveState;
  disabled?: boolean;
  placeholder?: string;
  rows?: number;
  band?: WordBand;
}) {
  const words = countWords(value);
  const inBand = band !== undefined && words >= band.min && words <= band.max;

  return (
    <div className="flex flex-col gap-2">
      <Textarea
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
        placeholder={placeholder}
        rows={rows}
        spellCheck
        className="resize-y"
      />

      {band ? (
        <Progress
          value={Math.min(words, band.max)}
          max={band.max}
          size="sm"
          label="Progress towards the expected length"
          valueText={`${words} of the ${band.min} to ${band.max} words this task expects`}
          barClassName={inBand ? "bg-success" : undefined}
        />
      ) : null}

      <div className="flex items-center justify-between gap-4">
        <p
          className={cn("text-xs tabular-nums", inBand ? "text-success" : "text-muted-foreground")}
        >
          {wordsLabel(words)}
          <span className="sr-only"> written so far</span>
          {band ? (
            <span className="text-muted-foreground">
              {" · "}
              {words > band.max
                ? `over the ${band.max} expected`
                : `aim for ${band.min}–${band.max}`}
            </span>
          ) : null}
        </p>
        <SaveStatus state={saveState} />
      </div>
    </div>
  );
}
