"use client";

import { useEffect, useId, useRef, useState } from "react";
import { Camera, ImageUp, Keyboard, RefreshCw, ScanText } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/utils";
import { ApiError, errorMessage } from "@/lib/api";
import type { ExtractionResult } from "@/types/api";

/**
 * The most likely way a student actually answers: a photograph of a page.
 *
 * Two rules from the submission pipeline shape this whole component.
 *
 * **A failed read is recoverable, and does not flip `input_method`.** When
 * every engine fails the submission is left in `failed` *with the image kept*,
 * so the student can photograph the page again or type the answer into the same
 * attempt — and the record still shows that handwriting was attempted and did
 * not read. So "type it instead" continues this submission; it never opens a
 * typed one.
 *
 * **A 503 consumes nothing.** No recognition engine on the server is a
 * deployment fault, not a bad photograph, and the same request will work once
 * the server is provisioned. It is worded that way rather than as a failure of
 * the student's page.
 */

const ACCEPTED = ["image/jpeg", "image/png", "image/webp"];

/**
 * The server enforces this and answers 413; checking first only saves a student
 * on a phone from uploading ten megabytes to be told no. `MAX_UPLOAD_SIZE_MB`
 * is deployment configuration, so the server stays the authority.
 */
const MAX_BYTES = 10 * 1024 * 1024;

export function HandwritingPanel({
  upload,
  extraction,
  onExtracted,
  onTypeInstead,
  typing,
  children,
}: {
  upload: (file: File) => Promise<ExtractionResult>;
  extraction: ExtractionResult | null;
  onExtracted: (result: ExtractionResult) => void;
  /** Continue *this* submission by typing — the recovery path for a failed read. */
  onTypeInstead: () => void;
  typing: boolean;
  /** The editor, shown once there is text to correct. */
  children: React.ReactNode;
}) {
  const inputId = useId();
  const [dragging, setDragging] = useState(false);
  const [rejected, setRejected] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [failure, setFailure] = useState<unknown>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  // The object URL is the local file rather than the stored image: the stored
  // one is behind an authenticated endpoint that an `<img src>` cannot reach
  // (storage keys never appear in a response body), and this is the same bytes.
  useEffect(() => {
    if (!previewUrl) return;
    return () => URL.revokeObjectURL(previewUrl);
  }, [previewUrl]);

  const accept = async (file: File | undefined) => {
    setRejected(null);
    setFailure(null);
    if (!file) return;

    if (!ACCEPTED.includes(file.type)) {
      setRejected("That file is not a photograph. Use a JPG, PNG or WEBP image.");
      return;
    }
    if (file.size > MAX_BYTES) {
      setRejected("That image is larger than 10 MB. Try a lower-resolution photograph.");
      return;
    }

    setPreviewUrl((current) => {
      if (current) URL.revokeObjectURL(current);
      return URL.createObjectURL(file);
    });

    setPending(true);
    try {
      onExtracted(await upload(file));
    } catch (error) {
      setFailure(error);
    } finally {
      setPending(false);
      // Without this, choosing the same file twice after a failure fires no
      // change event and the retry silently does nothing.
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  const engineMissing = failure instanceof ApiError && failure.isServiceUnavailable;
  const readFailed = failure !== null && !engineMissing;
  const showEditor = typing || extraction !== null;

  return (
    <div className="flex flex-col gap-4">
      {!showEditor ? (
        <div
          onDragOver={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(event) => {
            event.preventDefault();
            setDragging(false);
            void accept(event.dataTransfer.files?.[0]);
          }}
          className={cn(
            "focus-within:ring-ring flex flex-col items-center justify-center gap-3 rounded-xl",
            "border border-dashed px-6 py-12 text-center transition-colors focus-within:ring-2",
            "focus-within:ring-offset-2",
            dragging ? "border-primary bg-accent/50" : "border-border",
          )}
        >
          {pending ? (
            <>
              <ScanText className="text-primary size-8 animate-pulse" aria-hidden />
              <p className="text-sm font-medium">Reading your handwriting…</p>
              <p className="text-muted-foreground max-w-xs text-xs text-pretty">
                This can take a few seconds. You will be able to correct anything it misreads.
              </p>
              <Spinner label="Reading your handwriting" />
            </>
          ) : (
            <>
              <span className="bg-muted text-muted-foreground flex size-11 items-center justify-center rounded-full">
                <ImageUp className="size-5" aria-hidden />
              </span>
              <div className="flex flex-col gap-1">
                <label
                  htmlFor={inputId}
                  className="text-primary cursor-pointer text-sm font-medium underline-offset-4 hover:underline"
                >
                  Choose a photograph
                </label>
                <p className="text-muted-foreground text-xs">
                  or drag one here · JPG, PNG or WEBP, up to 10 MB
                </p>
              </div>
              <input
                ref={inputRef}
                id={inputId}
                type="file"
                accept={ACCEPTED.join(",")}
                // Opens the rear camera directly on a phone, which is how most
                // of these arrive.
                capture="environment"
                className="sr-only"
                onChange={(event) => void accept(event.target.files?.[0])}
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="mt-1"
                onClick={() => inputRef.current?.click()}
              >
                <Camera aria-hidden />
                Take a photo
              </Button>
            </>
          )}
        </div>
      ) : null}

      {rejected ? (
        <Alert variant="warning">
          <AlertTitle>That file cannot be used</AlertTitle>
          <AlertDescription>{rejected}</AlertDescription>
        </Alert>
      ) : null}

      {engineMissing ? (
        <Alert variant="warning">
          <AlertTitle>Handwriting cannot be read on this server yet</AlertTitle>
          <AlertDescription className="flex flex-col items-start gap-3">
            <span>
              No recognition engine is installed. Nothing has been used up — your attempt is intact,
              and the same photograph will work once the server is set up.
            </span>
            <Button type="button" variant="outline" size="sm" onClick={onTypeInstead}>
              <Keyboard aria-hidden />
              Type your answer instead
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}

      {readFailed ? (
        <Alert variant="destructive">
          <AlertTitle>Your handwriting could not be read</AlertTitle>
          <AlertDescription className="flex flex-col items-start gap-3">
            <span>{errorMessage(failure)}</span>
            <span className="text-muted-foreground text-xs">
              A sharper photo in better light usually reads. Your photograph has been kept, and this
              attempt still counts as handwriting either way.
            </span>
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => inputRef.current?.click()}
              >
                <RefreshCw aria-hidden />
                Try another photo
              </Button>
              <Button type="button" variant="ghost" size="sm" onClick={onTypeInstead}>
                <Keyboard aria-hidden />
                Type it instead
              </Button>
            </div>
          </AlertDescription>
        </Alert>
      ) : null}

      {showEditor ? (
        <div className="flex flex-col gap-4">
          {extraction ? <ExtractionBanner extraction={extraction} /> : null}
          {previewUrl ? (
            <details className="group">
              <summary className="text-muted-foreground hover:text-foreground focus-visible:ring-ring w-fit cursor-pointer rounded-md text-xs font-medium marker:content-none focus-visible:ring-2 focus-visible:outline-none">
                Show the photograph you uploaded
              </summary>
              {/* eslint-disable-next-line @next/next/no-img-element -- an
                  object URL for a file chosen in this tab; there is nothing for
                  next/image to optimise and no remote host to allow-list. */}
              <img
                src={previewUrl}
                alt="The handwritten page you uploaded"
                className="mt-3 max-h-80 w-full rounded-lg border object-contain"
              />
            </details>
          ) : null}
          {children}
        </div>
      ) : null}
    </div>
  );
}

/**
 * What the recogniser thought of its own reading.
 *
 * Confidence is shown because it changes what the student should do: a low
 * number means read every line, not glance at it. The provider's name is not —
 * which engine ran is a deployment detail, and naming it invites blame that a
 * student can do nothing with.
 */
function ExtractionBanner({ extraction }: { extraction: ExtractionResult }) {
  const confidence =
    typeof extraction.ocr_confidence === "number"
      ? Math.round(extraction.ocr_confidence * 100)
      : null;
  const unsure = confidence !== null && confidence < 80;

  return (
    <Alert variant={extraction.warning || unsure ? "warning" : "info"}>
      <AlertTitle>Check the reading before you submit</AlertTitle>
      <AlertDescription className="flex flex-col gap-1">
        <span>
          {extraction.warning ??
            "Edit anything below that was misread. Only the corrected text is marked."}
        </span>
        {confidence !== null ? (
          <span className="text-xs tabular-nums">
            The reader was {confidence}% confident on average.
          </span>
        ) : null}
      </AlertDescription>
    </Alert>
  );
}
