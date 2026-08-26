"use client";

import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { Monitor, Moon, Sun } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * Light, dark, or whatever the device says.
 *
 * The header's toggle is a quick switch; this is the full choice with its
 * third option visible, because "System" is the one people look for and the
 * one a two-state toggle cannot express.
 *
 * Nothing is marked as current until after hydration. The stored preference
 * lives in the browser, so the server renders this without knowing which is
 * selected — asserting one would be a hydration mismatch and, for the half of
 * readers on the other theme, briefly wrong.
 */
const OPTIONS = [
  { value: "light", label: "Light", icon: Sun, hint: "Always the light palette" },
  { value: "dark", label: "Dark", icon: Moon, hint: "Always the dark palette" },
  { value: "system", label: "System", icon: Monitor, hint: "Follow your device" },
] as const;

export function ThemeChoice() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  return (
    <div role="radiogroup" aria-label="Colour theme" className="grid gap-3 sm:grid-cols-3">
      {OPTIONS.map((option) => {
        const selected = mounted && theme === option.value;
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={selected}
            onClick={() => setTheme(option.value)}
            className={cn(
              "flex flex-col items-start gap-1.5 rounded-lg border p-4 text-left transition-colors",
              selected
                ? "border-primary bg-primary/5 ring-primary/30 ring-2"
                : "hover:bg-accent/60",
            )}
          >
            <option.icon className="text-muted-foreground size-4" aria-hidden />
            <span className="text-sm font-medium">{option.label}</span>
            <span className="text-muted-foreground text-xs">{option.hint}</span>
          </button>
        );
      })}
    </div>
  );
}
