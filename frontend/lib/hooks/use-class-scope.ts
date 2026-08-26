"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { classesApi, queryKeys } from "@/lib/api";
import { rangeDates, type RangeKey } from "@/lib/insights/scope";
import type { ClassSummary, UUID } from "@/types/api";

/**
 * Which class, over what period — remembered across the teaching screens.
 *
 * A teacher moves between the dashboard, the submissions queue and analytics
 * while thinking about *one* class. Asking them to reselect it on arrival is
 * the small friction that makes a tool feel like a form, so the selection is
 * held in one module-level store, mirrored to `localStorage`, and every
 * mounted scope bar subscribes to it.
 *
 * It is per-browser rather than per-account on purpose: it is a view
 * preference, not a fact about the user, and a teacher on a shared staffroom
 * machine should not inherit a colleague's last class from the server.
 */
const STORAGE_KEY = "graphmaster:scope";

interface StoredScope {
  classId: UUID | null;
  range: RangeKey;
}

let current: StoredScope = { classId: null, range: "30d" };
let hydrated = false;
const listeners = new Set<() => void>();

function hydrate(): void {
  if (hydrated) return;
  hydrated = true;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const parsed = JSON.parse(raw) as Partial<StoredScope>;
    current = {
      classId: typeof parsed.classId === "string" ? parsed.classId : null,
      range: typeof parsed.range === "string" ? (parsed.range as RangeKey) : "30d",
    };
  } catch {
    // A private window, cleared site data, or a value from an older shape.
    // The default scope is a perfectly good answer.
  }
}

function write(next: StoredScope): void {
  current = next;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    // Storage can be unavailable; the selection still holds for this session.
  }
  for (const listener of listeners) listener();
}

export interface ClassScope {
  classId: UUID | null;
  range: RangeKey;
  /** The classes this teacher may look at. Empty while loading. */
  classes: ClassSummary[];
  /** The selected class, resolved — `null` until the list arrives. */
  selected: ClassSummary | null;
  /** True while the class list is still being fetched. */
  isLoading: boolean;
  /** No classes exist at all, which is a first-run state rather than an error. */
  isEmpty: boolean;
  /** The two query parameters, ready to spread into an analytics call. */
  dates: ReturnType<typeof rangeDates>;
  setClassId: (next: UUID | null) => void;
  setRange: (next: RangeKey) => void;
}

export function useClassScope(): ClassScope {
  const [scope, setScope] = useState<StoredScope>(current);

  useEffect(() => {
    hydrate();
    setScope(current);
    const listener = () => setScope(current);
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  }, []);

  const classes = useQuery({
    queryKey: queryKeys.classes({ page_size: 100, is_active: true }),
    queryFn: () => classesApi.list({ page_size: 100, is_active: true }),
    staleTime: 5 * 60_000,
  });

  const items = useMemo(() => classes.data?.items ?? [], [classes.data]);

  // A teacher with one class should never have to choose it. The first is
  // selected on arrival, and the choice is stored so it survives the trip to
  // the next screen.
  useEffect(() => {
    if (items.length === 0) return;
    if (current.classId && items.some((item) => item.id === current.classId)) return;
    write({ ...current, classId: items[0]?.id ?? null });
  }, [items]);

  const setClassId = useCallback((next: UUID | null) => write({ ...current, classId: next }), []);
  const setRange = useCallback((next: RangeKey) => write({ ...current, range: next }), []);

  return {
    classId: scope.classId,
    range: scope.range,
    classes: items,
    selected: items.find((item) => item.id === scope.classId) ?? null,
    isLoading: classes.isPending,
    isEmpty: !classes.isPending && items.length === 0,
    dates: rangeDates(scope.range),
    setClassId,
    setRange,
  };
}

/** Test seam: the store is module state, and a test must be able to clear it. */
export function resetClassScopeForTests(): void {
  current = { classId: null, range: "30d" };
  hydrated = false;
  listeners.clear();
}
