/**
 * What the vocabulary manager says the priority number does.
 *
 * The field is stored as `weight`, and that name taught teachers to read it as
 * a score multiplier. It has never been one: the vocabulary mark is an
 * unweighted count of unique required terms used (FR-6.6), and a backend test
 * — `test_weight_has_no_effect_on_the_score` — holds that end.
 *
 * This end asserts the interface stops implying otherwise. The wire name is
 * deliberately unchanged; only what a teacher reads is.
 */

import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";

import { TermForm } from "@/components/vocabulary/term-form";
import type { VocabularyCategoryOut } from "@/types/api";

const CATEGORIES: VocabularyCategoryOut[] = [
  {
    id: "00000000-0000-0000-0000-0000000000c1",
    code: "increase",
    name: "Increase",
    description: null,
    display_order: 1,
    item_count: 4,
  },
];

function renderForm() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(
    <QueryClientProvider client={client}>
      <TermForm open onOpenChange={() => {}} categories={CATEGORIES} editing={null} />
    </QueryClientProvider>,
  );
}

describe("the priority field", () => {
  it("is not labelled in a way that implies a score multiplier", () => {
    renderForm();
    expect(screen.getByLabelText(/suggestion priority/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/^weight$/i)).not.toBeInTheDocument();
  });

  it("says which end of the range is shown first", () => {
    renderForm();
    // A bare number field with no explanation was the actual defect: a teacher
    // typed a value with no idea which direction meant what.
    expect(screen.getByText(/lowest first/i)).toBeInTheDocument();
  });

  it("states outright that it does not change a score", () => {
    renderForm();
    expect(screen.getByText(/does not change anyone/i)).toBeInTheDocument();
  });

  it("describes the field to a screen reader, not just beside it", () => {
    renderForm();
    // `aria-describedby`, so the explanation is announced with the input
    // rather than sitting as unassociated text after it.
    expect(screen.getByLabelText(/suggestion priority/i)).toHaveAccessibleDescription(
      /does not change anyone/i,
    );
  });
});
