const SECONDS_PER_MINUTE = 60;

/**
 * Formats a number of seconds as `m:ss` (e.g. 272 → "4:32", 5 → "0:05").
 *
 * Exists because the design shows every countdown and duration the same
 * way: the header's session timer, the expiry modal, the recording clock
 * and a sent voice note's length.
 *
 * @param totalSeconds - The duration in seconds; negatives are floored at 0.
 * @returns The duration as minutes and zero-padded seconds.
 */
export function formatMinutesSeconds(totalSeconds: number): string {
  const safeSeconds = Math.max(0, Math.floor(totalSeconds));
  const minutes = Math.floor(safeSeconds / SECONDS_PER_MINUTE);
  const seconds = safeSeconds % SECONDS_PER_MINUTE;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

/**
 * Formats a timestamp as a short date in the given language (e.g. "27 sept 2026").
 *
 * Exists so every case list (home and support) shows opened_at identically.
 *
 * @param isoTimestamp - The ISO-8601 timestamp to format.
 * @param language - The BCP 47 language to format in (the UI language).
 * @returns The localized short date.
 */
export function formatShortDate(isoTimestamp: string, language: string): string {
  return new Date(isoTimestamp).toLocaleDateString(language, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

/**
 * Formats a Date as a localized `HH:mm` time.
 *
 * Exists for the timestamp under each chat message.
 *
 * @param date - The moment to format.
 * @param language - The BCP 47 language to format in (the UI language).
 * @returns The localized hour and minute.
 */
export function formatClockTime(date: Date, language: string): string {
  return date.toLocaleTimeString(language, { hour: "2-digit", minute: "2-digit" });
}
