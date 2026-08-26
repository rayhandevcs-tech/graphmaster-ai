"use client";

import { useState } from "react";
import Link from "next/link";
import { MailCheck } from "lucide-react";

import { authApi, errorMessage } from "@/lib/api";
import { AuthShell } from "@/components/auth/auth-shell";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";

/**
 * Asking for a reset link.
 *
 * The confirmation is the same sentence whether or not an account exists, and
 * that is not vagueness — a page that said "no account with that email" would
 * be an account-enumeration oracle anyone could query. The server is careful
 * about this; the screen has to be too, which means never adding a friendlier
 * message that leaks what the server withheld.
 *
 * The success state replaces the form rather than sitting above it. A form
 * still offering "Send reset link" after it succeeded invites a second click,
 * and the endpoint is rate-limited.
 */
export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      await authApi.requestPasswordReset({ email: email.trim() });
      setSent(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error(String(caught)));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthShell>
      <div className="flex flex-col gap-6">
        <Card>
          <CardHeader>
            <CardTitle as="h1" className="text-2xl">
              Reset your password
            </CardTitle>
            <CardDescription>
              {sent
                ? "Check your inbox for the next step."
                : "We will email you a link to choose a new one."}
            </CardDescription>
          </CardHeader>

          <CardContent>
            {sent ? (
              <div className="flex flex-col gap-4">
                <div
                  role="status"
                  className="bg-success/10 text-foreground flex items-start gap-3 rounded-lg p-4 text-sm"
                >
                  <MailCheck className="text-success mt-0.5 size-5 shrink-0" aria-hidden />
                  <p className="text-pretty">
                    If an account exists for that email, a reset link has been sent. The link
                    expires, so use it soon.
                  </p>
                </div>

                <Button asChild variant="outline">
                  <Link href="/login">Back to sign in</Link>
                </Button>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="flex flex-col gap-5" noValidate>
                {error ? (
                  <Alert variant="destructive">
                    <AlertTitle>Could not send the link</AlertTitle>
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
                  />
                </div>

                <Button type="submit" size="lg" disabled={submitting}>
                  {submitting ? <Spinner label="Sending" /> : "Send reset link"}
                </Button>
              </form>
            )}
          </CardContent>
        </Card>

        {sent ? null : (
          <p className="text-muted-foreground text-center text-sm">
            Remembered it?{" "}
            <Link
              href="/login"
              className="text-primary font-medium underline-offset-4 hover:underline"
            >
              Sign in
            </Link>
          </p>
        )}
      </div>
    </AuthShell>
  );
}
