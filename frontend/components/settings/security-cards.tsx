"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { LogOut, ShieldCheck } from "lucide-react";

import { authApi, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth/context";
import { hasErrors, passwordChecklist, PASSWORD_MIN } from "@/lib/auth/validation";
import { PasswordField } from "@/components/auth/password-field";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";

/**
 * Changing your password.
 *
 * The server revokes every session on success — the right behaviour, and the
 * reason this card says so *before* the button rather than reporting it
 * afterwards. Being signed out of your phone is a surprise if you find out by
 * being signed out of your phone.
 */
export function ChangePasswordCard() {
  const { signOut } = useAuth();

  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [errors, setErrors] = useState<Record<string, string | undefined>>({});

  const change = useMutation({
    mutationFn: () => authApi.changePassword({ current_password: current, new_password: next }),
    onSuccess: () => {
      // Every refresh token for this account is now revoked, this browser's
      // included. Staying on the page would mean the next request 401s and
      // bounces them to sign in with no explanation.
      void signOut();
    },
  });

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const found: Record<string, string | undefined> = {};
    if (!current) found.current_password = "Enter your current password.";
    if (passwordChecklist(next).some((check) => !check.met)) {
      found.new_password = `Use at least ${PASSWORD_MIN} characters, including a letter and a number.`;
    }
    if (next && next === current) {
      found.new_password = "Choose a password different from your current one.";
    }
    if (confirm !== next) found.confirm_password = "These two passwords do not match.";

    setErrors(found);
    if (!hasErrors(found)) change.mutate();
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Password</CardTitle>
        <CardDescription>
          Changing it signs you out everywhere, including this device. You will sign in again with
          the new one.
        </CardDescription>
      </CardHeader>

      <CardContent>
        <form onSubmit={submit} className="flex max-w-md flex-col gap-5" noValidate>
          {change.isError ? (
            <Alert variant="destructive">
              <AlertTitle>Your password was not changed</AlertTitle>
              <AlertDescription>{errorMessage(change.error)}</AlertDescription>
            </Alert>
          ) : null}

          <PasswordField
            id="current_password"
            label="Current password"
            autoComplete="current-password"
            value={current}
            onChange={setCurrent}
            error={errors.current_password}
          />

          <PasswordField
            id="new_password"
            label="New password"
            autoComplete="new-password"
            value={next}
            onChange={setNext}
            error={errors.new_password}
            showChecklist
          />

          <PasswordField
            id="confirm_password"
            label="Confirm new password"
            autoComplete="new-password"
            value={confirm}
            onChange={setConfirm}
            error={errors.confirm_password}
          />

          <Button type="submit" disabled={change.isPending} className="w-fit">
            {change.isPending ? <Spinner label="Updating" /> : <ShieldCheck aria-hidden />}
            Update password
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

/**
 * Signing out of every device.
 *
 * Two steps, because it is not undoable and it affects devices that are not in
 * the room. The confirmation is inline rather than a dialog: a dialog steals
 * focus for a decision the student can just as easily read in place.
 */
export function SessionsCard() {
  const { signOut } = useAuth();
  const [confirming, setConfirming] = useState(false);

  const revoke = useMutation({
    mutationFn: () => authApi.logoutEverywhere(),
    onSuccess: () => void signOut(),
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Signed-in devices</CardTitle>
        <CardDescription>
          If you have signed in on a shared or borrowed computer, sign out of everything at once.
        </CardDescription>
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        {revoke.isError ? (
          <Alert variant="destructive">
            <AlertTitle>Could not sign out everywhere</AlertTitle>
            <AlertDescription>{errorMessage(revoke.error)}</AlertDescription>
          </Alert>
        ) : null}

        {confirming ? (
          <div className="flex flex-wrap items-center gap-3">
            <p className="text-sm">This signs out every device, including this one. Continue?</p>
            <Button
              variant="destructive"
              size="sm"
              autoFocus
              disabled={revoke.isPending}
              onClick={() => revoke.mutate()}
            >
              {revoke.isPending ? <Spinner label="Signing out" /> : "Yes, sign out everywhere"}
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setConfirming(false)}>
              Cancel
            </Button>
          </div>
        ) : (
          <Button variant="outline" className="w-fit" onClick={() => setConfirming(true)}>
            <LogOut aria-hidden />
            Sign out everywhere
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
