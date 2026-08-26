"use client";

import { useEffect, useState } from "react";

/**
 * A value that settles before anything acts on it.
 *
 * The library search is part of a query key, so without this every keystroke is
 * a request — and the replies race, which means the grid can settle on the
 * results for a prefix of what the student typed.
 */
export function useDebouncedValue<T>(value: T, delayMs = 300): T {
  const [settled, setSettled] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setSettled(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);

  return settled;
}
