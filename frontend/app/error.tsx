"use client";

import { useEffect } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

/**
 * The client-side boundary for anything a page throws.
 *
 * `error.message` is deliberately not shown: in a production build Next
 * replaces it with a digest anyway, and an unredacted message from a
 * server-rendered failure can carry internal detail — the same reason the API
 * never returns a stack trace.
 */
export default function ErrorBoundary({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="mx-auto flex min-h-[50vh] max-w-md flex-col justify-center gap-4">
      <Alert variant="destructive">
        <AlertTitle>Something went wrong</AlertTitle>
        <AlertDescription>
          The page could not be displayed. Trying again often clears it.
          {error.digest ? (
            <span className="mt-2 block text-xs">Reference: {error.digest}</span>
          ) : null}
        </AlertDescription>
      </Alert>
      <Button onClick={reset} variant="outline">
        Try again
      </Button>
    </div>
  );
}
