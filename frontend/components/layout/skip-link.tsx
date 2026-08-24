/**
 * NFR-4.3. The first thing in the tab order, invisible until focused, so a
 * keyboard user reaches the page's content without tabbing the whole header.
 */
export function SkipLink() {
  return (
    <a
      href="#main"
      className="bg-primary text-primary-foreground focus:ring-ring sr-only rounded-md px-4 py-2 text-sm font-medium focus:not-sr-only focus:absolute focus:top-3 focus:left-3 focus:z-50 focus:ring-2 focus:ring-offset-2"
    >
      Skip to content
    </a>
  );
}
