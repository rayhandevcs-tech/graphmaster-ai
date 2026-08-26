import type { DownloadedFile } from "@/lib/api";

/**
 * Hand a fetched file to the browser's downloader.
 *
 * The export endpoints demand a bearer token, so a plain `<a href>` cannot
 * reach them — the file arrives as a blob and this is what turns it back into
 * a saved file with the server's own filename.
 *
 * The object URL is revoked on the next tick rather than immediately: Safari
 * cancels a download whose blob URL is released in the same frame as the
 * click.
 */
export function saveFile(file: DownloadedFile): void {
  const url = URL.createObjectURL(file.blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = file.filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}
