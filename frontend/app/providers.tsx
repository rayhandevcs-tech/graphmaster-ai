"use client";

import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { ThemeProvider } from "@/components/theme/theme-provider";
import { AuthProvider } from "@/lib/auth/context";
import { ApiError } from "@/lib/api";

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        // Enough to stop a tab switch refetching everything, short enough that
        // XP and streaks are not visibly stale after a submission.
        staleTime: 30_000,
        refetchOnWindowFocus: false,
        retry: (failureCount, error) => {
          // A refused request will be refused again: 401 is handled by the
          // client's own refresh, 403/404/409/422 are answers. Only transport
          // failures and the server's own 5xx are worth a second try.
          if (error instanceof ApiError && error.status < 500) return false;
          return failureCount < 2;
        },
      },
    },
  });
}

export function Providers({ children }: { children: React.ReactNode }) {
  // Created in state, not at module scope: a module-level client on the server
  // would be shared by every request the process handles, so one student's
  // cached dashboard could be served to another.
  const [queryClient] = useState(makeQueryClient);

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        {/* Inside the query client: signing out clears the cache. */}
        <AuthProvider>{children}</AuthProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
