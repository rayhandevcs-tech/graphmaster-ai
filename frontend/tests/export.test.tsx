/**
 * Export, and the two rules a teacher must meet before the click rather than
 * after it.
 *
 * CSV is always available and Excel and PDF are optional, so a format this
 * deployment cannot build is disabled rather than offered and then answered
 * with a 503. And a submission export carries scores and metadata, never the
 * descriptions students wrote — said on the dialog, because a teacher who
 * expects the writing and opens a file without it will report a bug.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";

import { ExportMenu } from "@/components/analytics/export-menu";
import { queryKeys } from "@/lib/api";
import type { ReportCapabilities } from "@/types/api";

function renderWith(capabilities: ReportCapabilities) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  // Seeded rather than mocked: the component reads capabilities through the
  // cache, so a preloaded entry is the whole fixture and no request is made.
  client.setQueryData(queryKeys.reportCapabilities(), capabilities);

  return render(
    <QueryClientProvider client={client}>
      <ExportMenu classId="00000000-0000-0000-0000-000000000001" dates={{}} />
    </QueryClientProvider>,
  );
}

const full: ReportCapabilities = {
  formats: ["csv", "xlsx", "pdf"],
  types: ["class_summary", "vocabulary_usage", "submission_export"],
  max_rows: 5000,
};

describe("the export dialog", () => {
  it("disables a format this server cannot build", async () => {
    const user = userEvent.setup();
    renderWith({ ...full, formats: ["csv"] });

    await user.click(screen.getByRole("button", { name: /export/i }));

    expect(screen.getByRole("button", { name: /^CSV/ })).toBeEnabled();
    expect(screen.getByRole("button", { name: /Excel/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: /PDF/ })).toBeDisabled();
    expect(screen.getByText(/CSV is always available/i)).toBeInTheDocument();
  });

  it("says nothing about missing libraries when they are all installed", async () => {
    const user = userEvent.setup();
    renderWith(full);

    await user.click(screen.getByRole("button", { name: /export/i }));

    expect(screen.getByRole("button", { name: /Excel/ })).toBeEnabled();
    expect(screen.queryByText(/does not have/i)).not.toBeInTheDocument();
  });

  it("warns that a submission export holds no answers, before it is built", async () => {
    const user = userEvent.setup();
    renderWith(full);

    await user.click(screen.getByRole("button", { name: /export/i }));
    await user.selectOptions(screen.getByLabelText(/what to export/i), "submission_export");

    expect(screen.getByText(/not the descriptions your students wrote/i)).toBeInTheDocument();
  });

  it("offers only the report types this server builds", async () => {
    const user = userEvent.setup();
    renderWith({ ...full, types: ["class_summary"] });

    await user.click(screen.getByRole("button", { name: /export/i }));

    const select = screen.getByLabelText(/what to export/i);
    expect(select).toHaveTextContent("Class summary");
    expect(select).not.toHaveTextContent("Vocabulary usage");
  });
});
