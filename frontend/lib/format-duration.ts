export function formatDuration(ms: number | null | undefined): string {
  if (ms == null || ms < 0) return "";
  if (ms < 1000) return `${ms} мс`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)} с`;
  const m = Math.floor(ms / 60_000);
  const s = Math.floor((ms % 60_000) / 1000);
  return `${m} мин ${s} с`;
}
