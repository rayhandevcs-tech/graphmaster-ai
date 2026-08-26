"use client";

import { useId, useState } from "react";
import { Check, Eye, EyeOff } from "lucide-react";

import { passwordChecklist } from "@/lib/auth/validation";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

/**
 * A password field that says what it wants before it is wrong.
 *
 * The requirements are shown as a live checklist rather than as an error after
 * submission. A rule a student has to discover by failing is a rule they
 * experience as the product being difficult, and password rules are the first
 * thing a new account asks of them.
 *
 * The reveal toggle is a real button with a label that changes with its state,
 * not an icon that toggles silently — and it never leaves the field revealed
 * when the form is re-rendered.
 */
export function PasswordField({
  id,
  label,
  value,
  onChange,
  autoComplete,
  error,
  showChecklist = false,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  autoComplete: "new-password" | "current-password";
  error?: string;
  showChecklist?: boolean;
}) {
  const [revealed, setRevealed] = useState(false);
  const checklistId = useId();
  const errorId = `${id}-error`;

  const checks = passwordChecklist(value);
  const describedBy = [error ? errorId : null, showChecklist ? checklistId : null]
    .filter(Boolean)
    .join(" ");

  return (
    <div className="flex flex-col gap-2">
      <Label htmlFor={id}>{label}</Label>

      <div className="relative">
        <Input
          id={id}
          name={id}
          type={revealed ? "text" : "password"}
          autoComplete={autoComplete}
          required
          value={value}
          onChange={(event) => onChange(event.target.value)}
          aria-invalid={Boolean(error)}
          aria-describedby={describedBy || undefined}
          className="pr-11"
        />
        <button
          type="button"
          onClick={() => setRevealed((shown) => !shown)}
          // The label states the action, not the state: a button called
          // "Password hidden" reads as a status to a screen reader.
          aria-label={revealed ? "Hide password" : "Show password"}
          aria-pressed={revealed}
          className="text-muted-foreground hover:text-foreground absolute inset-y-0 right-0 flex w-11 items-center justify-center rounded-r-md transition-colors"
        >
          {revealed ? (
            <EyeOff className="size-4" aria-hidden />
          ) : (
            <Eye className="size-4" aria-hidden />
          )}
        </button>
      </div>

      {showChecklist ? (
        <ul id={checklistId} className="flex flex-wrap gap-x-4 gap-y-1">
          {checks.map((check) => (
            <li
              key={check.label}
              className={cn(
                "flex items-center gap-1.5 text-xs transition-colors",
                check.met ? "text-success" : "text-muted-foreground",
              )}
            >
              <Check
                className={cn("size-3.5", check.met ? "opacity-100" : "opacity-30")}
                aria-hidden
              />
              {check.label}
              <span className="sr-only">{check.met ? " — met" : " — not yet"}</span>
            </li>
          ))}
        </ul>
      ) : null}

      {error ? (
        <p id={errorId} className="text-destructive text-sm">
          {error}
        </p>
      ) : null}
    </div>
  );
}
