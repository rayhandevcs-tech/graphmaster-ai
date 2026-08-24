/**
 * Where to send someone after they sign in.
 *
 * The `next` parameter comes from the address bar, so it is attacker-controlled:
 * a link to `/login?next=https://evil.example/` would make our own login page a
 * redirect to theirs, on our domain, in front of a student who has just typed
 * their password. Only a path on this site is honoured.
 */
export function safeNextPath(next: string | null | undefined, fallback: string): string {
  if (!next) return fallback;

  // `//evil.example` is protocol-relative: the browser reads it as another
  // origin even though it starts with a slash.
  if (!next.startsWith("/") || next.startsWith("//")) return fallback;

  // `/\evil.example` is treated as `//evil.example` by some browsers.
  if (next.startsWith("/\\")) return fallback;

  return next;
}
