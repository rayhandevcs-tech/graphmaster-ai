"use client";

import { Textarea } from "@/components/ui/textarea";
import { SaveStatus, type SaveState } from "./save-status";
import { countWords, wordsLabel } from "@/lib/text/words";

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
}: {
  id: string;
  value: string;
  onChange: (next: string) => void;
  saveState: SaveState;
  disabled?: boolean;
  placeholder?: string;
  rows?: number;
}) {
  const words = countWords(value);

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

      <div className="flex items-center justify-between gap-4">
        <p className="text-muted-foreground text-xs tabular-nums">
          {wordsLabel(words)}
          <span className="sr-only"> written so far</span>
        </p>
        <SaveStatus state={saveState} />
      </div>
    </div>
  );
}
