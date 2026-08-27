"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

import { useAuth } from "@/lib/auth/context";
import { safeNextPath } from "@/lib/auth/redirect";
import { homePathForRole, roleCanVisit } from "@/lib/auth/roles";
import { ApiError, errorMessage } from "@/lib/api";
import { AuthShell, AuthSwitch } from "@/components/auth/auth-shell";
import { PasswordField } from "@/components/auth/password-field";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";

export default function LoginPage() {
  return (
    <AuthShell>
      {/* `useSearchParams` opts a page into client rendering; the boundary
          keeps that to the form rather than to the whole route. The fallback
          is the card's own shape, so the page does not jump when it resolves. */}
      <Suspense fallback={<Skeleton className="h-[26rem] rounded-xl" />}>
        <LoginForm />
      </Suspense>
    </AuthShell>
  );
}

function LoginForm() {
  const { signIn } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<ApiError | Error | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const fieldErrors = error instanceof ApiError ? error.fieldErrors : {};

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      const user = await signIn({ email, password });
      // Two separate questions, deliberately. `safeNextPath` asks whether the
      // destination is on this site at all; `roleCanVisit` asks whether this
      // person may open it. A stale link to a teacher's screen passes the
      // first and fails the second, and used to land a student on "This page
      // is not for your account" as their first impression after signing in.
      const home = homePathForRole(user.role);
      const next = safeNextPath(searchParams.get("next"), home);
      router.replace(roleCanVisit(next, user.role) ? next : home);
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error(String(caught)));
      setSubmitting(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle as="h1" className="text-2xl">
            Welcome back
          </CardTitle>
          <CardDescription>Sign in to keep your streak going.</CardDescription>
        </CardHeader>

        <CardContent>
          <form onSubmit={handleSubmit} className="flex flex-col gap-5" noValidate>
            {error ? (
              <Alert variant="destructive">
                <AlertTitle>Could not sign you in</AlertTitle>
                {/* Whatever the server said, and never more specific than it
                    was: "no account with that email" would answer a question
                    nobody signed in should be able to ask. */}
                <AlertDescription>{errorMessage(error)}</AlertDescription>
              </Alert>
            ) : null}

            <div className="flex flex-col gap-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                name="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                aria-invalid={Boolean(fieldErrors.email)}
                aria-describedby={fieldErrors.email ? "email-error" : undefined}
              />
              {fieldErrors.email ? (
                <p id="email-error" className="text-destructive text-sm">
                  {fieldErrors.email}
                </p>
              ) : null}
            </div>

            <div className="flex flex-col gap-2">
              <PasswordField
                id="password"
                label="Password"
                autoComplete="current-password"
                value={password}
                onChange={setPassword}
                error={fieldErrors.password}
              />
              <Link
                href="/forgot-password"
                className="text-muted-foreground hover:text-foreground self-end text-sm underline-offset-4 hover:underline"
              >
                Forgot your password?
              </Link>
            </div>

            <Button type="submit" size="lg" disabled={submitting}>
              {submitting ? <Spinner label="Signing in" /> : "Sign in"}
            </Button>
          </form>
        </CardContent>
      </Card>

      <AuthSwitch prompt="No account yet?" href="/register" label="Create one" />
    </div>
  );
}
