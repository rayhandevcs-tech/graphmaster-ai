/**
 * The teacher's landing screen.
 *
 * Three things are easy to lose here and expensive when they go: the panel
 * putting names before averages, a student who has not started being described
 * as one who scored badly, and a sparkline quietly bridging a week nobody
 * practised.
 */

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";

import { AttentionPanel } from "@/components/teaching/attention-panel";
import { InsightCard } from "@/components/insight/insight-card";
import { Metric } from "@/components/insight/metric";
import { Sparkline } from "@/components/insight/sparkline";
import { DistributionBar } from "@/components/insight/distribution-bar";
import { UserForm } from "@/components/admin/user-form";
import type { StudentRow, UserListItem } from "@/types/api";

const NOW = Date.now();
const daysAgo = (days: number) => new Date(NOW - days * 86_400_000).toISOString();

function student(overrides: Partial<StudentRow> = {}): StudentRow {
  return {
    user_id: overrides.user_id ?? "00000000-0000-0000-0000-000000000001",
    full_name: "Amina Yusuf",
    email: "amina@university.edu",
    total_xp: 120,
    current_level: 2,
    current_streak_days: 0,
    longest_streak_days: 3,
    submission_count: 4,
    average_final_score: 72,
    average_vocabulary_percentage: 61,
    highest_final_score: 80,
    last_submission_at: daysAgo(1),
    ...overrides,
  };
}

describe("who needs the teacher", () => {
  it("names students rather than reporting an average", () => {
    render(
      <AttentionPanel
        students={[
          student({ user_id: "a", full_name: "Priya Nair", average_final_score: 41 }),
          student({
            user_id: "b",
            full_name: "Tom Becker",
            submission_count: 0,
            average_final_score: null,
          }),
        ]}
      />,
    );

    expect(screen.getByText("2 students need you")).toBeInTheDocument();
    expect(screen.getByText("Priya Nair")).toBeInTheDocument();
    expect(screen.getByText("Tom Becker")).toBeInTheDocument();
  });

  it("describes a student who has not started as one who has not started", () => {
    render(
      <AttentionPanel
        students={[
          student({ full_name: "Tom Becker", submission_count: 0, average_final_score: null }),
        ]}
      />,
    );

    expect(screen.getByText("No marked work yet")).toBeInTheDocument();
    // Never "averaging 0" — a missing average is not a low one.
    expect(screen.queryByText(/averaging 0/i)).not.toBeInTheDocument();
  });

  it("puts the evidence beside a student who is finding it hard", () => {
    render(
      <AttentionPanel students={[student({ average_final_score: 41, submission_count: 4 })]} />,
    );

    expect(screen.getByText(/Averaging 41% over 4 attempts/)).toBeInTheDocument();
  });

  it("links each student to their own work", () => {
    render(<AttentionPanel students={[student({ user_id: "abc", average_final_score: 20 })]} />);

    expect(screen.getByRole("link", { name: /Amina Yusuf/ })).toHaveAttribute(
      "href",
      "/teacher/submissions?student=abc",
    );
  });

  it("says so when nobody needs chasing, rather than showing an empty list", () => {
    render(<AttentionPanel students={[student(), student({ user_id: "b" })]} />);

    expect(screen.getByText("Nobody needs chasing")).toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("names each group in words, not only in colour", () => {
    render(
      <AttentionPanel students={[student({ submission_count: 0, average_final_score: null })]} />,
    );

    expect(screen.getByRole("heading", { name: /not started/i })).toBeInTheDocument();
  });
});

describe("the sparkline", () => {
  it("restarts the line after a bucket with no marked work", () => {
    const { container } = render(
      <Sparkline values={[60, null, null, 70, 72]} label="Score trend" />,
    );

    const path = container.querySelector("path")?.getAttribute("d") ?? "";
    // Two subpaths: one for the point before the gap, one for the run after.
    expect(path.match(/M/g)).toHaveLength(2);
  });

  it("refuses to draw a line through a single point", () => {
    render(<Sparkline values={[60, null, null]} label="Score trend" />);
    expect(screen.getByText(/not enough marked work/i)).toBeInTheDocument();
  });

  it("carries its reading in the accessible name", () => {
    render(<Sparkline values={[60, 70]} label="Score trend: Scores are up 10 points." />);
    expect(screen.getByRole("img", { name: /up 10 points/ })).toBeInTheDocument();
  });
});

describe("the card contract", () => {
  it("states a question and what the answer means", () => {
    render(
      <InsightCard question="Are scores improving?" interpretation="Up 9 points across the period.">
        <p>61</p>
      </InsightCard>,
    );

    expect(screen.getByRole("heading", { name: "Are scores improving?" })).toBeInTheDocument();
    expect(screen.getByText("Up 9 points across the period.")).toBeInTheDocument();
  });

  it("reads an absent figure as absent", () => {
    render(<Metric label="Average score" value="—" />);

    expect(screen.getByText("no marked work yet")).toBeInTheDocument();
  });
});

describe("a whole divided into parts", () => {
  it("names every segment beside the bar", () => {
    render(
      <DistributionBar
        label="Reward tiers"
        segments={[
          { key: "crown", label: "Crown", value: 3, className: "bg-primary" },
          { key: "hammer", label: "Practice", value: 1, className: "bg-secondary" },
        ]}
      />,
    );

    const legend = screen.getByRole("list");
    expect(within(legend).getByText("Crown")).toBeInTheDocument();
    expect(within(legend).getByText("Practice")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /Crown 75%, Practice 25%/ })).toBeInTheDocument();
  });

  it("says what would fill it rather than drawing an empty bar", () => {
    render(<DistributionBar label="Reward tiers" segments={[]} />);
    expect(screen.getByText(/nothing to show/i)).toBeInTheDocument();
  });
});

describe("changing what someone may do", () => {
  const person: UserListItem = {
    id: "00000000-0000-0000-0000-0000000000ad",
    email: "admin@university.edu",
    full_name: "Rina Admin",
    role: "admin",
    gender: "female",
    class_id: null,
    total_xp: 0,
    current_level: 1,
    is_active: true,
    created_at: "2026-01-04T09:00:00Z",
  };

  it("refuses to let an administrator remove their own role, and says why", async () => {
    const user = userEvent.setup();
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });

    render(
      <QueryClientProvider client={client}>
        <UserForm user={person} classes={[]} isSelf open onOpenChange={() => {}} />
      </QueryClientProvider>,
    );

    await user.selectOptions(screen.getByLabelText(/role/i), "teacher");

    expect(screen.getByText(/cannot remove your own administrator role/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /save changes/i })).toBeDisabled();
  });

  it("allows the same change on somebody else", async () => {
    const user = userEvent.setup();
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });

    render(
      <QueryClientProvider client={client}>
        <UserForm user={person} classes={[]} isSelf={false} open onOpenChange={() => {}} />
      </QueryClientProvider>,
    );

    await user.selectOptions(screen.getByLabelText(/role/i), "teacher");

    expect(screen.queryByText(/cannot remove your own/i)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /save changes/i })).toBeEnabled();
  });

  it("refuses to let anyone deactivate the account they are signed in with", async () => {
    const user = userEvent.setup();
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });

    render(
      <QueryClientProvider client={client}>
        <UserForm user={person} classes={[]} isSelf open onOpenChange={() => {}} />
      </QueryClientProvider>,
    );

    await user.click(screen.getByRole("switch", { name: /account active/i }));

    expect(screen.getByText(/cannot deactivate your own account/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /save changes/i })).toBeDisabled();
  });
});
