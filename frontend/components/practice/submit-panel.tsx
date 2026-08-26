"use client";

import { useEffect, useRef, useState } from "react";
import { CircleAlert, Send } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";

/**
 * Submitting, with the one warning that matters shown before it happens.
 *
 * Marking is exactly-once and final: the submission freezes, XP is awarded, and
 * a second attempt is a *new* submission rather than a rescore (04-api-design
 * §3.6). A student who did not know that and pressed the button expecting to
 * revise afterwards has lost the attempt, so the confirmation is inline rather
 * than a modal — one extra keystroke, and it never traps focus on a phone.
 */
export function SubmitPanel({
  onSubmit,
  submitting,
  disabled,
  disabledReason,
  error,
}: {
  onSubmit: () => void;
  submitting: boolean;
  disabled: boolean;
  disabledReason?: string;
  error?: React.ReactNode;
}) {
  const [confirming, setConfirming] = useState(false);
  const confirmRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    if (confirming) confirmRef.current?.focus();
  }, [confirming]);

  return (
    <div className="flex flex-col gap-3">
      {error}

      {confirming ? (
        <div className="border-secondary/40 bg-secondary/10 flex flex-col gap-3 rounded-lg border p-4">
          <div className="flex flex-col gap-1">
            <p className="text-sm font-medium">Send this for marking?</p>
            <p className="text-muted-foreground text-sm text-pretty">
              It is marked once and cannot be edited afterwards. If you want to improve it, you can
              practise the same graph again as a new attempt.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button ref={confirmRef} type="button" onClick={onSubmit} disabled={submitting}>
              {submitting ? <Spinner label="Marking your answer" /> : <Send aria-hidden />}
              Yes, mark it
            </Button>
            <Button
              type="button"
              variant="ghost"
              onClick={() => setConfirming(false)}
              disabled={submitting}
            >
              Keep writing
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          <Button
            type="button"
            size="lg"
            onClick={() => setConfirming(true)}
            disabled={disabled || submitting}
            className="w-full sm:w-auto"
          >
            <Send aria-hidden />
            Submit for marking
          </Button>
          {disabled && disabledReason ? (
            <p className="text-muted-foreground inline-flex items-center gap-1.5 text-xs">
              <CircleAlert className="size-3.5 shrink-0" aria-hidden />
              {disabledReason}
            </p>
          ) : null}
        </div>
      )}
    </div>
  );
}

/** A refused submission, phrased for the student rather than the log. */
export function SubmitError({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Alert variant="destructive">
      <AlertTitle>{title}</AlertTitle>
      <AlertDescription>{children}</AlertDescription>
    </Alert>
  );
}
