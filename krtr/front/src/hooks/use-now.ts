import { useEffect, useState } from "react";

const DEFAULT_TICK_MS = 1000;

/**
 * Returns the current time, re-rendering the caller once per tick.
 *
 * Exists for display-only countdowns (the header's session timer) that
 * need to stay current without owning any session logic themselves.
 *
 * @param tickMs - How often to refresh, in milliseconds.
 * @returns The current time, in epoch milliseconds.
 */
export function useNow(tickMs: number = DEFAULT_TICK_MS): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const interval = setInterval(() => setNow(Date.now()), tickMs);
    return () => clearInterval(interval);
  }, [tickMs]);
  return now;
}
