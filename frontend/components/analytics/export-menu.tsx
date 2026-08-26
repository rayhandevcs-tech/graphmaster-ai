"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Download, FileSpreadsheet, FileText, Table2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { errorMessage, queryKeys, reportsApi } from "@/lib/api";
import { saveFile } from "@/lib/download";
import type { RangeDates } from "@/lib/insights/scope";
import type { ReportFormat, ReportType, UUID } from "@/types/api";

/**
 * Export, offered where the data is.
 *
 * Two product rules are visible before the click rather than discovered after
 * it.
 *
 * **CSV is always available; Excel and PDF are optional** (CLAUDE.md rule 38).
 * `GET /reports/capabilities` says which libraries this deployment actually
 * has, and a format it cannot build is disabled and labelled — not offered and
 * then answered with a 503.
 *
 * **A submission export carries scores and metadata, never the answers**
 * (rule 39). That is said on the dialog, because a teacher who expects their
 * students' writing and opens a file without it will report a bug. A file
 * circulated by email should not hold every student's work verbatim.
 */
const TYPE_LABEL: Record<ReportType, string> = {
  class_summary: "Class summary",
  student_detail: "Student detail",
  vocabulary_usage: "Vocabulary usage",
  submission_export: "Submissions (scores and metadata)",
};

const FORMAT_LABEL: Record<ReportFormat, string> = {
  csv: "CSV",
  xlsx: "Excel",
  pdf: "PDF",
};

const FORMAT_ICON: Record<ReportFormat, React.ComponentType<{ className?: string }>> = {
  csv: Table2,
  xlsx: FileSpreadsheet,
  pdf: FileText,
};

const ALL_FORMATS: ReportFormat[] = ["csv", "xlsx", "pdf"];

export function ExportMenu({
  classId,
  dates,
  defaultType = "class_summary",
}: {
  classId: UUID | null;
  dates: RangeDates;
  defaultType?: ReportType;
}) {
  const [open, setOpen] = useState(false);
  const [type, setType] = useState<ReportType>(defaultType);
  const [format, setFormat] = useState<ReportFormat>("csv");

  const capabilities = useQuery({
    queryKey: queryKeys.reportCapabilities(),
    queryFn: () => reportsApi.capabilities(),
    staleTime: Infinity,
  });

  const available = capabilities.data?.formats ?? ["csv"];
  const types = capabilities.data?.types ?? ["class_summary"];

  const run = useMutation({
    mutationFn: async () => {
      const report = await reportsApi.create({
        report_type: type,
        format,
        class_id: classId,
        date_from: dates.date_from ?? null,
        date_to: dates.date_to ?? null,
      });

      // `failed` is a first-class outcome here: a missing library is a 503 and
      // a failed row, never a 500, so the message on the row is the thing to
      // show rather than a generic error.
      if (report.status === "failed") {
        throw new Error(report.error_message ?? "The report could not be built.");
      }

      saveFile(await reportsApi.download(report.id));
    },
    onSuccess: () => setOpen(false),
  });

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) run.reset();
      }}
    >
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          <Download aria-hidden />
          Export
        </Button>
      </DialogTrigger>

      <DialogContent>
        <DialogHeader>
          <DialogTitle>Export this period</DialogTitle>
          <DialogDescription>Built from the class and dates currently selected.</DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="export-type">What to export</Label>
            <Select
              id="export-type"
              value={type}
              onChange={(event) => setType(event.target.value as ReportType)}
            >
              {types.map((option) => (
                <option key={option} value={option}>
                  {TYPE_LABEL[option] ?? option}
                </option>
              ))}
            </Select>
          </div>

          <fieldset className="flex flex-col gap-1.5">
            <legend className="mb-1.5 text-sm font-medium">Format</legend>
            <div className="flex flex-wrap gap-2">
              {ALL_FORMATS.map((option) => {
                const enabled = available.includes(option);
                const Icon = FORMAT_ICON[option];
                return (
                  <Button
                    key={option}
                    type="button"
                    size="sm"
                    variant={format === option ? "primary" : "outline"}
                    disabled={!enabled}
                    aria-pressed={format === option}
                    title={enabled ? undefined : "Not installed on this server"}
                    onClick={() => setFormat(option)}
                  >
                    <Icon aria-hidden />
                    {FORMAT_LABEL[option]}
                    {enabled ? null : <span className="sr-only"> — not installed</span>}
                  </Button>
                );
              })}
            </div>
            {available.length < ALL_FORMATS.length ? (
              <p className="text-muted-foreground text-xs text-pretty">
                Greyed formats need a library this server does not have. CSV is always available.
              </p>
            ) : null}
          </fieldset>

          {type === "submission_export" ? (
            <Alert variant="info">
              <AlertDescription>
                This file carries scores and metadata — not the descriptions your students wrote. An
                export that circulates by email should not hold their writing verbatim.
              </AlertDescription>
            </Alert>
          ) : null}

          {run.isError ? (
            <Alert variant="destructive">
              <AlertDescription>{errorMessage(run.error)}</AlertDescription>
            </Alert>
          ) : null}
        </div>

        <DialogFooter>
          <DialogClose asChild>
            <Button type="button" variant="outline">
              Cancel
            </Button>
          </DialogClose>
          <Button onClick={() => run.mutate()} disabled={run.isPending}>
            {run.isPending ? "Building…" : "Download"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
