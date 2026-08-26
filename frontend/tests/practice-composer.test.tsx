/**
 * The two controls a student touches most.
 *
 * The editor is the same component on both routes into a submission — an empty
 * one for a typed attempt, and one already holding the recogniser's reading for
 * a handwritten one. That is FR-4.7: the extraction is editable text in the
 * ordinary editor, not a read-only preview with a separate correction mode.
 *
 * The submit control guards the one irreversible action in the student flow.
 */

import * as React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AnswerEditor } from "@/components/practice/answer-editor";
import { SubmitPanel } from "@/components/practice/submit-panel";
import { SaveStatus } from "@/components/practice/save-status";

function Editable({ initial = "" }: { initial?: string }) {
  const [value, setValue] = React.useState(initial);
  return <AnswerEditor id="answer" value={value} onChange={setValue} saveState="idle" />;
}

describe("the answer editor", () => {
  it("counts what has been written, as it is written", async () => {
    const user = userEvent.setup();
    render(<Editable />);

    expect(screen.getByText(/^0 words/)).toBeInTheDocument();

    await user.type(screen.getByRole("textbox"), "Sales rose sharply");
    expect(screen.getByText(/^3 words/)).toBeInTheDocument();
  });

  it("opens holding the recogniser's reading, and lets it be corrected", async () => {
    // The whole point of FR-4.7: a misread word is fixed here, before anything
    // is marked.
    const user = userEvent.setup();
    render(<Editable initial="Sales rnse sharply" />);

    const box = screen.getByRole("textbox");
    expect(box).toHaveValue("Sales rnse sharply");
    expect(box).not.toHaveAttribute("readonly");

    await user.clear(box);
    await user.type(box, "Sales rose sharply in June");
    expect(box).toHaveValue("Sales rose sharply in June");
    expect(screen.getByText(/^5 words/)).toBeInTheDocument();
  });

  it("gets the singular right at one word", async () => {
    const user = userEvent.setup();
    render(<Editable />);

    await user.type(screen.getByRole("textbox"), "Sales");
    expect(screen.getByText(/^1 word/)).toBeInTheDocument();
  });
});

describe("the save status", () => {
  it("says nothing before there is anything to save", () => {
    const { container } = render(<SaveStatus state="idle" />);
    expect(container).toBeEmptyDOMElement();
  });

  it("announces a failed save politely rather than silently", () => {
    render(<SaveStatus state="error" />);

    const line = screen.getByText(/not saved/i);
    expect(line).toBeInTheDocument();
    // Polite: it must not cut across someone mid-sentence, but losing a draft
    // is not something to discover afterwards.
    expect(line).toHaveAttribute("aria-live", "polite");
  });
});

describe("submitting for marking", () => {
  it("will not submit an empty answer, and says why", () => {
    render(
      <SubmitPanel
        onSubmit={vi.fn()}
        submitting={false}
        disabled
        disabledReason="Write it first."
      />,
    );

    expect(screen.getByRole("button", { name: /submit for marking/i })).toBeDisabled();
    expect(screen.getByText("Write it first.")).toBeInTheDocument();
  });

  it("asks once before marking, because marking is final", async () => {
    // A scored submission freezes and the XP is already awarded; a second
    // attempt is a new submission rather than a rescore.
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<SubmitPanel onSubmit={onSubmit} submitting={false} disabled={false} />);

    await user.click(screen.getByRole("button", { name: /submit for marking/i }));
    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByText(/cannot be edited afterwards/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /yes, mark it/i }));
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it("moves focus to the confirmation, so it is not missed on a screen reader", async () => {
    const user = userEvent.setup();
    render(<SubmitPanel onSubmit={vi.fn()} submitting={false} disabled={false} />);

    await user.click(screen.getByRole("button", { name: /submit for marking/i }));
    expect(screen.getByRole("button", { name: /yes, mark it/i })).toHaveFocus();
  });

  it("backs out without marking", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<SubmitPanel onSubmit={onSubmit} submitting={false} disabled={false} />);

    await user.click(screen.getByRole("button", { name: /submit for marking/i }));
    await user.click(screen.getByRole("button", { name: /keep writing/i }));

    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: /submit for marking/i })).toBeInTheDocument();
  });

  it("cannot be double-submitted while a request is in flight", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    const { rerender } = render(
      <SubmitPanel onSubmit={onSubmit} submitting={false} disabled={false} />,
    );

    await user.click(screen.getByRole("button", { name: /submit for marking/i }));
    rerender(<SubmitPanel onSubmit={onSubmit} submitting disabled={false} />);

    expect(screen.getByRole("button", { name: /yes, mark it/i })).toBeDisabled();
  });
});
