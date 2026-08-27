"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Keyboard, PenLine, Target } from "lucide-react";

import { ChartPanel } from "@/components/charts/chart-panel";
import { useRubric } from "@/lib/hooks/use-rubric";
import { AnswerEditor } from "./answer-editor";
import { CollapsiblePanel } from "./collapsible-panel";
import { DifficultyBadge, GRAPH_TYPE_LABELS, GraphTypeIcon, targetTermsLabel } from "./graph-meta";
import { HandwritingPanel } from "./handwriting-panel";
import type { SaveState } from "./save-status";
import { SubmitError, SubmitPanel } from "./submit-panel";
import { TaskPrompt } from "./task-prompt";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  ApiError,
  errorMessage,
  graphsApi,
  INVALIDATED_BY_SCORING,
  ocrApi,
  queryKeys,
  submissionsApi,
} from "@/lib/api";
import { useDebouncedValue } from "@/lib/hooks/use-debounced-value";
import { countWords } from "@/lib/text/words";
import type { ExtractionResult, InputMethod, SubmissionSummary, UUID } from "@/types/api";

/** Long enough not to fire mid-sentence, short enough that a closed tab costs a line. */
const AUTOSAVE_MS = 2000;

const EMPTY_TEXT: Record<InputMethod, string> = { typed: "", handwriting: "" };

/**
 * The practice flow, as one state machine (06-frontend-architecture §7).
 *
 * The one structural decision worth knowing before reading the rest: **a
 * submission exists per input method, not per visit.** `input_method` is fixed
 * when the submission is opened and never flips, because it is research data
 * about how students actually answer — so switching tabs cannot move an
 * attempt from `handwriting` to `typed`. Each tab lazily opens its own
 * submission the first time there is something to save, and a student who
 * photographs a page that will not read types into *that* submission, which is
 * why "type it instead" lives inside the handwriting tab rather than switching
 * to the other one.
 */
export function PracticeWorkspace({
  graphId,
  assignmentId = null,
}: {
  graphId: string;
  /**
   * The assignment this attempt is for, when the student arrived from one.
   *
   * It labels the submission and changes nothing else — not the marking, not
   * the XP, not the tier. It is threaded all the way down here rather than
   * attached afterwards because `assignment_id` is set once at creation and
   * never updated: a scored submission is frozen, and re-pointing one would
   * move a mark between two pieces of work.
   */
  assignmentId?: string | null;
}) {
  const router = useRouter();
  const queryClient = useQueryClient();

  const graph = useQuery({
    queryKey: queryKeys.graph(graphId),
    queryFn: () => graphsApi.get(graphId),
  });

  const ocr = useQuery({
    queryKey: queryKeys.ocrStatus(),
    queryFn: () => ocrApi.status(),
    // Which engines exist is a property of the deployment, not of this student.
    staleTime: 5 * 60 * 1000,
  });

  /* The length the marker expects, from the server rather than from a constant
     in this file. Optional throughout: if it cannot be read the editor counts
     words with no target, which is what it did before the endpoint existed —
     a failed request must not stop a student writing. */
  const band = useRubric().data?.target_word_count;

  /**
   * Attempts already open on this graph.
   *
   * The API reuses a draft only while it is *pristine*, so without this a
   * student who wrote two paragraphs and reloaded the page would silently start
   * a second attempt and abandon the first. Newest first, so the first
   * unscored row per input method is the one to resume.
   */
  const openAttempts = useQuery({
    queryKey: queryKeys.submissions({ graph_id: graphId, open: true }),
    queryFn: () => submissionsApi.list({ graph_id: graphId, page_size: 10 }),
  });

  const [method, setMethod] = useState<InputMethod>("typed");
  const [texts, setTexts] = useState<Record<InputMethod, string>>(EMPTY_TEXT);
  const [extraction, setExtraction] = useState<ExtractionResult | null>(null);
  const [typingInstead, setTypingInstead] = useState(false);
  const [saveState, setSaveState] = useState<SaveState>("idle");

  const ids = useRef<Partial<Record<InputMethod, UUID>>>({});
  const savedText = useRef<Record<InputMethod, string>>({ ...EMPTY_TEXT });
  const adopted = useRef(false);

  // Adopt whatever is already open, once, before the student types anything.
  useEffect(() => {
    if (adopted.current || !openAttempts.data) return;
    adopted.current = true;

    // Only a draft belonging to the *same* assignment is resumable. Adopting
    // a free-practice draft into an attempt at set work would file the answer
    // against nothing, leaving the task reading as not started after the
    // student had written it — and the reverse would file free practice under
    // a task nobody set.
    const resumable = openAttempts.data.items
      .filter(isResumable)
      .filter((attempt) => (attempt.assignment_id ?? null) === assignmentId);
    const recovered = { ...EMPTY_TEXT };

    for (const attempt of resumable) {
      if (ids.current[attempt.input_method]) continue;
      ids.current[attempt.input_method] = attempt.id;
    }

    void (async () => {
      // The list carries no answer text, so the text comes from the detail read
      // — one per method at most, and only for a method that has an attempt.
      for (const inputMethod of ["typed", "handwriting"] as const) {
        const id = ids.current[inputMethod];
        if (!id) continue;
        try {
          const detail = await submissionsApi.get(id);
          recovered[inputMethod] = detail.answer_text ?? "";
          savedText.current[inputMethod] = detail.answer_text ?? "";
          if (inputMethod === "handwriting" && detail.answer_text) setTypingInstead(true);
        } catch {
          // A draft that cannot be read is not worth blocking the page for:
          // the student writes into a fresh attempt instead.
          delete ids.current[inputMethod];
        }
      }
      setTexts(recovered);
      if (!recovered.typed && recovered.handwriting) setMethod("handwriting");
    })();
  }, [openAttempts.data, assignmentId]);

  /** The submission for this method, opened on demand. */
  const ensure = useCallback(
    async (inputMethod: InputMethod): Promise<UUID> => {
      const known = ids.current[inputMethod];
      if (known) return known;
      const created = await submissionsApi.create({
        graph_id: graphId,
        input_method: inputMethod,
        assignment_id: assignmentId,
      });
      ids.current[inputMethod] = created.id;
      return created.id;
    },
    [graphId, assignmentId],
  );

  const text = texts[method];

  /* ── Autosave ─────────────────────────────────────────────────────────── */

  const pending = useMemo(() => ({ method, text }), [method, text]);
  const settled = useDebouncedValue(pending, AUTOSAVE_MS);

  useEffect(() => {
    if (!settled.text.trim()) return;
    if (savedText.current[settled.method] === settled.text) return;

    let cancelled = false;
    setSaveState("saving");

    void (async () => {
      try {
        const id = await ensure(settled.method);
        await submissionsApi.setText(id, { text: settled.text });
        if (cancelled) return;
        savedText.current[settled.method] = settled.text;
        setSaveState("saved");
      } catch {
        // Deliberately not an error toast. The student keeps writing; the
        // status line says the draft is not safe, and the next pause retries.
        if (!cancelled) setSaveState("error");
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [settled, ensure]);

  /* ── Marking ──────────────────────────────────────────────────────────── */

  const submit = useMutation({
    mutationFn: async () => {
      const id = await ensure(method);
      // The last keystrokes may not have reached the debounce, and the score is
      // computed from what the server holds.
      if (savedText.current[method] !== text) {
        await submissionsApi.setText(id, { text });
        savedText.current[method] = text;
      }
      return submissionsApi.analyze(id);
    },
    onSuccess: (result) => {
      // XP, the level change and any achievements exist only in this response.
      queryClient.setQueryData(queryKeys.submissionAward(result.submission.id), result);
      for (const key of INVALIDATED_BY_SCORING) {
        void queryClient.invalidateQueries({ queryKey: key });
      }
      router.push(`/submissions/${result.submission.id}`);
    },
  });

  if (graph.isLoading) return <WorkspaceSkeleton />;

  if (graph.isError) {
    const missing = graph.error instanceof ApiError && graph.error.isNotFound;
    return (
      <div className="mx-auto flex max-w-lg flex-col items-start gap-4 py-12">
        <Alert variant="destructive">
          <AlertTitle>
            {missing ? "This graph is not available" : "The graph could not be loaded"}
          </AlertTitle>
          <AlertDescription>
            {missing
              ? "It may have been unpublished by your teacher since you opened the link."
              : errorMessage(graph.error)}
          </AlertDescription>
        </Alert>
        <Button asChild variant="outline">
          <Link href="/practice">
            <ArrowLeft aria-hidden />
            Back to the graph library
          </Link>
        </Button>
      </div>
    );
  }

  const detail = graph.data;
  if (!detail) return null;

  const words = countWords(text);
  const handwritingAvailable = ocr.data?.operational ?? false;
  const targets = targetTermsLabel(detail.target_vocabulary_count);

  return (
    <div className="flex flex-col gap-6">
      <Button asChild variant="ghost" size="sm" className="text-muted-foreground -ml-2 w-fit">
        <Link href="/practice">
          <ArrowLeft aria-hidden />
          All graphs
        </Link>
      </Button>

      <header className="flex flex-col gap-3">
        <h1 className="text-2xl font-semibold tracking-tight text-balance sm:text-3xl">
          {detail.title}
        </h1>
        <div className="text-muted-foreground flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
          <span className="inline-flex items-center gap-1.5">
            <GraphTypeIcon graphType={detail.graph_type} />
            {GRAPH_TYPE_LABELS[detail.graph_type]}
          </span>
          <DifficultyBadge difficulty={detail.difficulty} />
          {targets ? (
            <span className="inline-flex items-center gap-1.5">
              <Target className="size-3.5" aria-hidden />
              {targets}
            </span>
          ) : null}
        </div>
      </header>

      <div className="grid items-start gap-6 lg:grid-cols-5">
        <div className="flex flex-col gap-6 lg:sticky lg:top-24 lg:col-span-3">
          <Card>
            <CardContent className="p-4 sm:p-6">
              <CollapsiblePanel title="The graph">
                <ChartPanel
                  chartData={detail.chart_data}
                  graphType={detail.graph_type}
                  title={detail.title}
                />
              </CollapsiblePanel>
            </CardContent>
          </Card>

          <TaskPrompt prompt={detail.prompt} targetCount={detail.target_vocabulary_count} />
        </div>

        <div className="lg:col-span-2">
          <Card className="relative">
            {submit.isPending ? <MarkingOverlay /> : null}

            <CardContent className="flex flex-col gap-5 p-4 pt-6 sm:p-6">
              <Tabs
                value={method}
                onValueChange={(next) => setMethod(next as InputMethod)}
                className="flex flex-col"
              >
                <div className="flex flex-col gap-2">
                  <TabsList className="w-full sm:w-fit">
                    <TabsTrigger value="typed" className="flex-1 sm:flex-none">
                      <Keyboard aria-hidden />
                      Type
                    </TabsTrigger>
                    {handwritingAvailable ? (
                      <TabsTrigger value="handwriting" className="flex-1 sm:flex-none">
                        <PenLine aria-hidden />
                        Handwriting
                      </TabsTrigger>
                    ) : null}
                  </TabsList>
                  {ocr.isSuccess && !handwritingAvailable ? (
                    // Hidden rather than offered and refused: photographing a
                    // page only to be told it cannot be read wastes the effort.
                    <p className="text-muted-foreground text-xs">
                      Handwriting upload is not available on this server.
                    </p>
                  ) : null}
                </div>

                <TabsContent value="typed">
                  <AnswerEditor
                    id="typed-answer"
                    value={texts.typed}
                    onChange={(next) => setTexts((current) => ({ ...current, typed: next }))}
                    saveState={method === "typed" ? saveState : "idle"}
                    disabled={submit.isPending}
                    placeholder="Describe what the graph shows. Start with an overview of the main trend, then give the figures that support it."
                    band={band}
                  />
                </TabsContent>

                <TabsContent value="handwriting">
                  <HandwritingPanel
                    upload={async (file) => {
                      const id = await ensure("handwriting");
                      const result = await submissionsApi.upload(id, file);
                      setTexts((current) => ({ ...current, handwriting: result.ocr_text }));
                      savedText.current.handwriting = result.ocr_text;
                      return result;
                    }}
                    extraction={extraction}
                    onExtracted={setExtraction}
                    onTypeInstead={() => setTypingInstead(true)}
                    typing={typingInstead}
                  >
                    <AnswerEditor
                      id="handwriting-answer"
                      value={texts.handwriting}
                      onChange={(next) =>
                        setTexts((current) => ({ ...current, handwriting: next }))
                      }
                      saveState={method === "handwriting" ? saveState : "idle"}
                      disabled={submit.isPending}
                      rows={12}
                      placeholder="Type your description here."
                      band={band}
                    />
                  </HandwritingPanel>
                </TabsContent>
              </Tabs>

              <div className="border-t pt-5">
                <SubmitPanel
                  onSubmit={() => submit.mutate()}
                  submitting={submit.isPending}
                  disabled={words === 0}
                  disabledReason="Write your description first."
                  error={submit.isError ? <MarkingError error={submit.error} /> : undefined}
                />
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

/** Anything not yet marked, and therefore still writable. */
function isResumable(attempt: SubmissionSummary): boolean {
  return attempt.status !== "scored" && attempt.status !== "analyzing";
}

/**
 * Marking runs as one request with no progress to report, so there is no
 * progress bar here. A bar that fills on a timer is a lie about a request whose
 * length nobody knows, and it reads as broken the moment it reaches the end and
 * waits.
 */
function MarkingOverlay() {
  return (
    <div
      // `alert` rather than `status`: this covers the interface, and a
      // screen-reader user needs to know that before they try to keep typing.
      role="alert"
      className="bg-card/90 absolute inset-0 z-10 flex flex-col items-center justify-center gap-3 rounded-xl backdrop-blur-sm"
    >
      <Spinner label="Marking your answer" className="size-6" />
      <p className="text-sm font-medium">Marking your answer</p>
      <p className="text-muted-foreground max-w-[16rem] text-center text-xs text-pretty">
        Finding the target vocabulary and assessing the writing. Please keep this page open.
      </p>
    </div>
  );
}

function MarkingError({ error }: { error: unknown }) {
  const api = error instanceof ApiError ? error : null;

  if (api?.isServiceUnavailable) {
    return (
      <SubmitError title="Marking is not available on this server yet">
        The language model is not installed. Nothing has been used up — your answer is saved, and
        submitting it again will work once the server is set up.
      </SubmitError>
    );
  }

  if (api?.status === 409) {
    return (
      <SubmitError title="This attempt cannot be marked again">
        {api.message} Start a new attempt at this graph to try for a better score.
      </SubmitError>
    );
  }

  return <SubmitError title="Your answer could not be marked">{errorMessage(error)}</SubmitError>;
}

function WorkspaceSkeleton() {
  return (
    <div className="flex flex-col gap-6" aria-busy>
      <Skeleton className="h-8 w-2/3 max-w-md" />
      <Skeleton className="h-4 w-48" />
      <div className="grid items-start gap-6 lg:grid-cols-5">
        <div className="flex flex-col gap-6 lg:col-span-3">
          <Skeleton className="h-[22rem] rounded-xl" />
          <Skeleton className="h-32 rounded-xl" />
        </div>
        <Skeleton className="h-[28rem] rounded-xl lg:col-span-2" />
      </div>
    </div>
  );
}
