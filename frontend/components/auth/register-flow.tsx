"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, PartyPopper } from "lucide-react";

import { ApiError, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth/context";
import { hasErrors, validateRegistration, type FieldErrors } from "@/lib/auth/validation";
import { AvatarPicker } from "@/components/avatars/avatar-picker";
import { AuthSwitch } from "@/components/auth/auth-shell";
import { GenderChoice } from "@/components/auth/gender-choice";
import { PasswordField } from "@/components/auth/password-field";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/utils";
import type { Gender } from "@/types/api";

/**
 * Creating an account, in two steps.
 *
 * The split is forced by the API and turns out to be the better flow anyway:
 * the avatar catalogue is an authenticated endpoint, because which avatars
 * exist for you depends on your gender and which are unlocked depends on your
 * level. There is no catalogue to show before the account exists.
 *
 * So step one creates the account and signs the student in, and step two is
 * the first thing they do as themselves. It is genuinely skippable —
 * registration already assigns the default avatar for their gender (FR-2.2),
 * so "Skip for now" leaves them with a character rather than with nothing, and
 * the same picker is on their profile page for later.
 *
 * Once step two is reached there is no going back to step one: the account has
 * been created. The step indicator says "2 of 2" rather than offering a Back
 * button that could only lie about what it would undo.
 */
type Step = "account" | "avatar";

export function RegisterFlow() {
  const [step, setStep] = useState<Step>("account");
  const [name, setName] = useState("");

  return step === "account" ? (
    <AccountStep
      onCreated={(fullName) => {
        setName(fullName);
        setStep("avatar");
      }}
    />
  ) : (
    <AvatarStep name={name} />
  );
}

function StepMarker({ current }: { current: 1 | 2 }) {
  return (
    <div className="flex items-center gap-3">
      <span className="text-muted-foreground text-xs font-medium tracking-widest uppercase">
        Step {current} of 2
      </span>
      <span className="flex flex-1 gap-1.5" aria-hidden>
        {[1, 2].map((index) => (
          <span
            key={index}
            className={cn(
              "h-1 flex-1 rounded-full transition-colors",
              index <= current ? "bg-primary" : "bg-muted",
            )}
          />
        ))}
      </span>
    </div>
  );
}

function AccountStep({ onCreated }: { onCreated: (fullName: string) => void }) {
  const { register } = useAuth();
  const formRef = useRef<HTMLFormElement | null>(null);

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [gender, setGender] = useState<Gender | null>(null);
  const [classCode, setClassCode] = useState("");

  const [errors, setErrors] = useState<FieldErrors>({});
  const [failure, setFailure] = useState<Error | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFailure(null);

    const found = validateRegistration({
      fullName,
      email,
      password,
      confirmPassword,
      gender,
      classCode,
    });
    setErrors(found);

    if (hasErrors(found)) {
      // Move the caret to the first thing that needs attention. Without this a
      // long form scrolled past its own errors reports nothing at all to
      // someone using a keyboard.
      const firstInvalid = formRef.current?.querySelector<HTMLElement>('[aria-invalid="true"]');
      firstInvalid?.focus();
      return;
    }

    setSubmitting(true);
    try {
      await register({
        full_name: fullName.trim(),
        email: email.trim(),
        password,
        gender: gender as Gender,
        class_code: classCode.trim() || null,
      });
      onCreated(fullName.trim());
    } catch (caught) {
      const error = caught instanceof Error ? caught : new Error(String(caught));
      setFailure(error);
      // The server validates all of this again, and its messages are more
      // specific than ours — an already-registered email, a class code that
      // does not exist.
      if (error instanceof ApiError) setErrors(error.fieldErrors);
      setSubmitting(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader className="gap-4">
          <StepMarker current={1} />
          <div className="flex flex-col gap-1.5">
            <CardTitle className="text-2xl">Create your account</CardTitle>
            <CardDescription>
              Free for students. You will be practising in under a minute.
            </CardDescription>
          </div>
        </CardHeader>

        <CardContent>
          <form ref={formRef} onSubmit={handleSubmit} className="flex flex-col gap-5" noValidate>
            {failure ? (
              <Alert variant="destructive">
                <AlertTitle>Could not create your account</AlertTitle>
                <AlertDescription>{errorMessage(failure)}</AlertDescription>
              </Alert>
            ) : null}

            <Field
              id="full_name"
              label="Full name"
              autoComplete="name"
              value={fullName}
              onChange={setFullName}
              error={errors.full_name}
            />

            <Field
              id="email"
              label="Email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={setEmail}
              error={errors.email}
            />

            <PasswordField
              id="password"
              label="Password"
              autoComplete="new-password"
              value={password}
              onChange={setPassword}
              error={errors.password}
              showChecklist
            />

            <PasswordField
              id="confirm_password"
              label="Confirm password"
              autoComplete="new-password"
              value={confirmPassword}
              onChange={setConfirmPassword}
              error={errors.confirm_password}
            />

            <GenderChoice
              value={gender}
              onChange={setGender}
              error={errors.gender}
              describedById="gender-hint"
            />

            <Field
              id="class_code"
              label="Class code"
              optional="If your teacher gave you one"
              autoComplete="off"
              value={classCode}
              onChange={setClassCode}
              error={errors.class_code}
            />

            <Button type="submit" size="lg" disabled={submitting}>
              {submitting ? <Spinner label="Creating your account" /> : "Create account"}
            </Button>
          </form>
        </CardContent>
      </Card>

      <AuthSwitch prompt="Already have an account?" href="/login" label="Sign in" />
    </div>
  );
}

function AvatarStep({ name }: { name: string }) {
  const router = useRouter();
  const [chosen, setChosen] = useState(false);

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader className="gap-4">
          <StepMarker current={2} />
          <div className="flex flex-col gap-1.5">
            <CardTitle className="flex items-center gap-2 text-2xl">
              <PartyPopper className="text-primary size-5" aria-hidden />
              You are in{name ? `, ${name.split(/\s+/)[0]}` : ""}
            </CardTitle>
            <CardDescription>
              Pick the character that celebrates your results. Some are locked until you level up —
              you can change this any time from your profile.
            </CardDescription>
          </div>
        </CardHeader>

        <CardContent className="flex flex-col gap-6">
          <AvatarPicker onSelected={() => setChosen(true)} />

          <Button asChild size="lg">
            <Link href="/dashboard">
              {chosen ? "Start practising" : "Skip for now"}
              <ArrowRight aria-hidden />
            </Link>
          </Button>
        </CardContent>
      </Card>

      <p className="text-muted-foreground text-center text-sm">
        {/* `replace`, not `push`: this flow is finished and the browser's back
            button must not walk back into a half-created account. */}
        <button
          type="button"
          onClick={() => router.replace("/practice")}
          className="text-primary font-medium underline-offset-4 hover:underline"
        >
          Or go straight to a graph
        </button>
      </p>
    </div>
  );
}

function Field({
  id,
  label,
  value,
  onChange,
  error,
  type = "text",
  autoComplete,
  optional,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  error?: string;
  type?: string;
  autoComplete: string;
  optional?: string;
}) {
  const errorId = `${id}-error`;
  const hintId = `${id}-hint`;

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-baseline justify-between gap-3">
        <Label htmlFor={id}>{label}</Label>
        {optional ? (
          <span id={hintId} className="text-muted-foreground text-xs">
            {optional}
          </span>
        ) : null}
      </div>

      <Input
        id={id}
        name={id}
        type={type}
        autoComplete={autoComplete}
        required={!optional}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        aria-invalid={Boolean(error)}
        aria-describedby={
          [error ? errorId : null, optional ? hintId : null].filter(Boolean).join(" ") || undefined
        }
      />

      {error ? (
        <p id={errorId} className="text-destructive text-sm">
          {error}
        </p>
      ) : null}
    </div>
  );
}
