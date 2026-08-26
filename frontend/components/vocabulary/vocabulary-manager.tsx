"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpen, Pencil, Plus, RefreshCw, RotateCcw, Search } from "lucide-react";

import { TermForm } from "./term-form";
import { EmptyState } from "@/components/layout/empty-state";
import { Pager } from "@/components/layout/pager";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { FilterChips } from "@/components/ui/filter-chips";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { errorMessage, queryKeys, vocabularyApi } from "@/lib/api";
import { useDebouncedValue } from "@/lib/hooks/use-debounced-value";
import type { VocabularyItemOut } from "@/types/api";

/**
 * The seven categories and the terms in them.
 *
 * **Nothing is deleted here.** A term is deactivated, because historical
 * scores reference it (CLAUDE.md rule 10) — so the control says "Deactivate",
 * the deactivated terms stay listed behind a switch rather than vanishing, and
 * each of them offers "Reactivate". A manager that hides them makes a
 * reversible action look permanent, and a teacher who cannot find a term they
 * removed adds it again as a duplicate.
 *
 * `is_phrase` appears as a badge and never as a control: it is derived from
 * the term by the server (rule 13).
 */
const PAGE_SIZE = 25;

export function VocabularyManager() {
  const queryClient = useQueryClient();
  const [category, setCategory] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [showInactive, setShowInactive] = useState(false);
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<VocabularyItemOut | null>(null);
  const [formOpen, setFormOpen] = useState(false);

  const debounced = useDebouncedValue(search, 300);

  const categories = useQuery({
    queryKey: queryKeys.vocabularyCategories(),
    queryFn: () => vocabularyApi.categories(),
    staleTime: 5 * 60_000,
  });

  const query = {
    category: category ?? undefined,
    search: debounced || undefined,
    // Undefined asks for everything; `true` narrows to the active ones.
    is_active: showInactive ? undefined : true,
    page,
    page_size: PAGE_SIZE,
  };

  const items = useQuery({
    queryKey: queryKeys.vocabularyItems(query),
    queryFn: () => vocabularyApi.list(query),
    placeholderData: (previous) => previous,
  });

  const toggle = useMutation({
    mutationFn: (item: VocabularyItemOut) =>
      item.is_active
        ? vocabularyApi.deactivate(item.id)
        : vocabularyApi.update(item.id, { is_active: true }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["vocabulary"] });
    },
  });

  const rows = items.data?.items ?? [];

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-semibold tracking-tight">Vocabulary</h1>
          <p className="text-muted-foreground text-sm text-pretty">
            The terms every description is marked against. Removing one deactivates it — past scores
            still point at it.
          </p>
        </div>
        <Button
          size="sm"
          onClick={() => {
            setEditing(null);
            setFormOpen(true);
          }}
        >
          <Plus aria-hidden />
          Add term
        </Button>
      </div>

      <div className="flex flex-col gap-4">
        <FilterChips
          label="Category"
          options={(categories.data ?? []).map((row) => ({
            value: row.code,
            label: `${row.name}${row.item_count === undefined ? "" : ` ${row.item_count}`}`,
          }))}
          value={category}
          onChange={(next) => {
            setCategory(next);
            setPage(1);
          }}
        />

        <div className="flex flex-wrap items-center gap-4">
          <div className="relative min-w-56 flex-1">
            <Search
              className="text-muted-foreground pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2"
              aria-hidden
            />
            <Input
              value={search}
              placeholder="Search terms"
              aria-label="Search terms"
              className="pl-9"
              onChange={(event) => {
                setSearch(event.target.value);
                setPage(1);
              }}
            />
          </div>

          <div className="flex items-center gap-2">
            <Switch
              checked={showInactive}
              onCheckedChange={(next) => {
                setShowInactive(next);
                setPage(1);
              }}
              label="Show deactivated terms"
            />
            <Label className="text-sm font-normal">Show deactivated</Label>
          </div>
        </div>
      </div>

      <p role="status" className="text-muted-foreground text-sm">
        {items.data
          ? `${items.data.total.toLocaleString()} ${items.data.total === 1 ? "term" : "terms"}${
              showInactive ? ", deactivated included" : ""
            }.`
          : ""}
      </p>

      {items.isPending ? (
        <ManagerSkeleton />
      ) : items.isError ? (
        <Alert variant="destructive">
          <AlertTitle>The vocabulary could not be loaded</AlertTitle>
          <AlertDescription className="flex flex-col items-start gap-3">
            <span>{errorMessage(items.error)}</span>
            <Button variant="outline" size="sm" onClick={() => void items.refetch()}>
              <RefreshCw aria-hidden />
              Try again
            </Button>
          </AlertDescription>
        </Alert>
      ) : rows.length === 0 ? (
        <EmptyState
          icon={BookOpen}
          title="No terms match"
          description={
            debounced
              ? "Nothing in this category matches that search."
              : "This category has no terms yet."
          }
        />
      ) : (
        <>
          <ul className="flex flex-col gap-2 md:hidden">
            {rows.map((item) => (
              <TermCard
                key={item.id}
                item={item}
                onEdit={() => {
                  setEditing(item);
                  setFormOpen(true);
                }}
                onToggle={() => toggle.mutate(item)}
                busy={toggle.isPending}
              />
            ))}
          </ul>

          <div className="hidden md:block">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Term</TableHead>
                  <TableHead>Lemma</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead className="text-right">Weight</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((item) => (
                  <TableRow key={item.id} className={item.is_active ? "" : "opacity-60"}>
                    <TableCell>
                      <span className="flex items-center gap-2">
                        <span className="text-sm font-medium">{item.term}</span>
                        {item.is_phrase ? <Badge>phrase</Badge> : null}
                        {item.is_active ? null : <Badge>deactivated</Badge>}
                      </span>
                    </TableCell>
                    <TableCell className="text-muted-foreground text-sm">{item.lemma}</TableCell>
                    <TableCell className="text-muted-foreground text-sm">
                      {item.category_name}
                    </TableCell>
                    <TableCell className="text-right text-sm tabular-nums">{item.weight}</TableCell>
                    <TableCell className="text-right">
                      <span className="flex justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            setEditing(item);
                            setFormOpen(true);
                          }}
                        >
                          <Pencil aria-hidden />
                          Edit
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          disabled={toggle.isPending}
                          onClick={() => toggle.mutate(item)}
                        >
                          {item.is_active ? "Deactivate" : "Reactivate"}
                        </Button>
                      </span>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          {items.data && items.data.total_pages > 1 ? (
            <Pager
              page={items.data.page}
              totalPages={items.data.total_pages}
              total={items.data.total}
              onPageChange={setPage}
              itemNoun="terms"
            />
          ) : null}
        </>
      )}

      {formOpen ? (
        <TermForm
          // Remounted per term so the fields start from that row rather than
          // from whichever one was opened first.
          key={editing?.id ?? "new"}
          open={formOpen}
          onOpenChange={setFormOpen}
          categories={categories.data ?? []}
          editing={editing}
        />
      ) : null}
    </div>
  );
}

function Badge({ children }: { children: React.ReactNode }) {
  return (
    <span className="bg-muted text-muted-foreground rounded-full px-2 py-0.5 text-[11px] font-medium">
      {children}
    </span>
  );
}

function TermCard({
  item,
  onEdit,
  onToggle,
  busy,
}: {
  item: VocabularyItemOut;
  onEdit: () => void;
  onToggle: () => void;
  busy: boolean;
}) {
  return (
    <li>
      <Card className={`flex flex-col gap-2 p-4 ${item.is_active ? "" : "opacity-60"}`}>
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-medium">{item.term}</span>
          {item.is_phrase ? <Badge>phrase</Badge> : null}
          {item.is_active ? null : <Badge>deactivated</Badge>}
        </div>
        <p className="text-muted-foreground text-xs">
          {item.category_name} · lemma {item.lemma} · weight {item.weight}
        </p>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={onEdit}>
            <Pencil aria-hidden />
            Edit
          </Button>
          <Button variant="ghost" size="sm" disabled={busy} onClick={onToggle}>
            {item.is_active ? "Deactivate" : <RotateCcw aria-hidden />}
            {item.is_active ? null : "Reactivate"}
          </Button>
        </div>
      </Card>
    </li>
  );
}

function ManagerSkeleton() {
  return (
    <div className="flex flex-col gap-2" aria-busy>
      <span className="sr-only" role="status">
        Loading the vocabulary
      </span>
      {[0, 1, 2, 3, 4, 5].map((index) => (
        <Skeleton key={index} className="h-14 rounded-lg" />
      ))}
    </div>
  );
}
