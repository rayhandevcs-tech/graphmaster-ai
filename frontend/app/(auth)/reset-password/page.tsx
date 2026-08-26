"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ShieldCheck } from "lucide-react";

import { authApi, errorMessage } from "@/lib/api";
import { hasErrors, passwordChecklist, PASSWORD_MIN } from "@/lib/auth/validation";
import { AuthShell } from "@/components/auth/auth-shell";
import { PasswordField } from "@/components/auth/password-field";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";

/**
 * Choosing a new password with a reset token.
 *
 * The token is the credential, and it arrives in the query string — so this
 * page never asks for the email address as well. Asking would imply the two
 * are checked together, which they are not, and would hand a phishing copy of
 * this page a second field worth stealing.
 *
 * On success the server has revoked every session for the account. That is the
 * right behaviour after a password change and it is why this page sends the
 * student to sign in rather than pretending they are already there.
 */
export default function ResetPasswordPage() {
  return (
    <AuthShell>
      <Suspense fallback={<Skeleton className="h-96 rounded-xl" />}>
        <ResetForm />
      </Suspense>
    </AuthShell>
  );
}

function ResetForm() {
  const router = useRouter();
  const token = useSearchParams().get("token") ?? "";

  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [errors, setErrors] = useState<Record<string, string | undefined>>({});
  const [failure, setFailure] = useState<Error | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  if (!token) {
    return (
      <Card>
        <CardHeader>
          <CardTitle as="h1" className="text-2xl">
            This link is incomplete
          </CardTitle>
          <CardDescription>
            The reset link needs the token that came with it. Open the link from your email again,
            or ask for a new one.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button asChild>
            <Link href="/forgot-password">Send a new link</Link>
          </Button>
        </CardContent>
      </Card>
    );
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFailure(null);

    const found: Record<string, string | undefined> = {};
    if (passwordChecklist(password).some((check) => !check.met)) {
      found.new_password = `Use at least ${PASSWORD_MIN} characters, including a letter and a number.`;
    }
    if (confirmPassword !== password) {
      found.confirm_password = "These two passwords do not match.";
    }
    setErrors(found);
    if (hasErrors(found)) return;

    setSubmitting(true);
    try {
      await authApi.confirmPasswordReset({ token, new_password: password });
      setDone(true);
    } catch (caught) {
      setFailure(caught instanceof Error ? caught : new Error(String(caught)));
      setSubmitting(false);
    }
  }

  if (done) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-2xl">
            <ShieldCheck className="text-success size-5" aria-hidden />
            Password updated
          </CardTitle>
          <CardDescription>
            Every device signed into this account has been signed out, including this one. Sign in
            with your new password to continue.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button size="lg" onClick={() => router.replace("/login")}>
            Sign in
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-2xl">Choose a new password</CardTitle>
        <CardDescription>Make it one you have not used on this account before.</CardDescription>
      </CardHeader>

      <CardContent>
        <form onSubmit={handleSubmit} className="flex flex-col gap-5" noValidate>
          {failure ? (
            <Alert variant="destructive">
              <AlertTitle>Could not update your password</AlertTitle>
              <AlertDescription>
                {errorMessage(failure)} If the link has expired, request a new one.
              </AlertDescription>
            </Alert>
          ) : null}

          <PasswordField
            id="new_password"
            label="New password"
            autoComplete="new-password"
            value={password}
            onChange={setPassword}
            error={errors.new_password}
            showChecklist
          />

          <PasswordField
            id="confirm_password"
            label="Confirm new password"
            autoComplete="new-password"
            value={confirmPassword}
            onChange={setConfirmPassword}
            error={errors.confirm_password}
          />

          <Button type="submit" size="lg" disabled={submitting}>
            {submitting ? <Spinner label="Updating your password" /> : "Update password"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
