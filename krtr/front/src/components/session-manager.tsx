import type { JSX, RefObject } from "react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { logout, reportActivity, type CurrentSession } from "@/api/session";
import { Button } from "@/components/ui/button";

const TICK_INTERVAL_MS = 1000;
const WARNING_LEAD_MS = 30_000;
const ACTIVITY_THROTTLE_MS = 60_000;
const ACTIVITY_EVENTS = ["pointerdown", "keydown", "wheel", "touchstart", "scroll"] as const;

type SessionPhase =
  "active" | "idle_warning" | "absolute_warning" | "expired_idle" | "expired_absolute";

/** Milliseconds remaining until an ISO timestamp, floored at 0. */
function msRemaining(isoTimestamp: string, now: number): number {
  return Math.max(0, new Date(isoTimestamp).getTime() - now);
}

/**
 * Derives which phase the session is in from its expiry timestamps.
 *
 * The absolute deadline always takes precedence over the idle one: it is
 * the harder cutoff and can't be extended (G15).
 *
 * @param session - The current session's expiry timestamps.
 * @param now - The current time, in epoch milliseconds.
 * @returns The session's current phase.
 */
function computeSessionPhase(session: CurrentSession, now: number): SessionPhase {
  const idleRemainingMs = msRemaining(session.idle_expires_at, now);
  const absoluteRemainingMs = msRemaining(session.absolute_expires_at, now);
  if (absoluteRemainingMs <= 0) return "expired_absolute";
  if (idleRemainingMs <= 0) return "expired_idle";
  if (absoluteRemainingMs <= WARNING_LEAD_MS) return "absolute_warning";
  if (idleRemainingMs <= WARNING_LEAD_MS) return "idle_warning";
  return "active";
}

/** Reports activity and forwards the refreshed session, swallowing failures. */
async function reportActivityAndRefresh(
  onSessionRefreshed: (session: CurrentSession) => void,
): Promise<void> {
  try {
    const refreshed = await reportActivity();
    onSessionRefreshed(refreshed);
  } catch {
    // apiFetch already redirects on 401; a transient failure just skips
    // this refresh, and the next tick or activity retries.
  }
}

/**
 * Ticks once per second, so time-based UI (the countdowns) stays current,
 * and logs out exactly once, the moment the session's phase becomes
 * expired — checked and acted on directly inside the tick, rather than in
 * a separate effect keyed off the derived phase, so it fires deterministically
 * under both real and fake timers.
 *
 * @param session - The current session, or null before it has loaded.
 * @returns The current time, in epoch milliseconds.
 */
function useSessionClock(session: CurrentSession | null): number {
  const [now, setNow] = useState(() => Date.now());
  const sessionRef = useRef(session);
  const hasExpiredRef = useRef(false);

  useEffect(() => {
    sessionRef.current = session;
  }, [session]);

  useEffect(() => {
    const interval = setInterval(() => {
      const currentNow = Date.now();
      setNow(currentNow);
      const currentSession = sessionRef.current;
      if (!currentSession || hasExpiredRef.current) return;
      const phase = computeSessionPhase(currentSession, currentNow);
      if (phase === "expired_idle" || phase === "expired_absolute") {
        hasExpiredRef.current = true;
        void logout();
      }
    }, TICK_INTERVAL_MS);
    return () => clearInterval(interval);
  }, []);

  return now;
}

/**
 * Listens for user activity and reports it, throttled to once per 60 s (G15).
 *
 * @param onSessionRefreshed - Called with the refreshed session after a
 *   successful report.
 * @returns A ref holding the timestamp of the last report, so
 *   "Seguir conectado" can also update it when it reports directly.
 */
function useActivityReporting(
  onSessionRefreshed: (session: CurrentSession) => void,
): RefObject<number> {
  const lastReportedAtRef = useRef(0);
  useEffect(() => {
    const handleActivity = (): void => {
      if (Date.now() - lastReportedAtRef.current < ACTIVITY_THROTTLE_MS) return;
      lastReportedAtRef.current = Date.now();
      void reportActivityAndRefresh(onSessionRefreshed);
    };
    for (const eventName of ACTIVITY_EVENTS) {
      window.addEventListener(eventName, handleActivity);
    }
    return () => {
      for (const eventName of ACTIVITY_EVENTS) {
        window.removeEventListener(eventName, handleActivity);
      }
    };
  }, [onSessionRefreshed]);
  return lastReportedAtRef;
}

interface ExpiryWarningModalProps {
  secondsRemaining: number;
  kind: "idle" | "absolute";
  onStayConnected?: () => void;
}

/** The 30-second countdown modal shown before an idle or absolute expiry. */
function ExpiryWarningModal({
  secondsRemaining,
  kind,
  onStayConnected,
}: ExpiryWarningModalProps): JSX.Element {
  const { t } = useTranslation();
  return (
    <div
      role="alertdialog"
      aria-modal="true"
      className="fixed inset-0 flex items-center justify-center bg-black/50"
    >
      <div className="rounded-lg bg-background p-6 text-center shadow-lg">
        <p>
          {t(kind === "idle" ? "session_idle_warning" : "session_absolute_warning", {
            seconds: secondsRemaining,
          })}
        </p>
        {onStayConnected && (
          <Button type="button" className="mt-4" onClick={onStayConnected}>
            {t("session_stay_connected")}
          </Button>
        )}
      </div>
    </div>
  );
}

/** The full-screen message shown once a session has expired. */
function ExpiredNotice({ kind }: { kind: "idle" | "absolute" }): JSX.Element {
  const { t } = useTranslation();
  const messageKey =
    kind === "idle" ? "session_expired_idle_message" : "session_expired_absolute_message";
  return (
    <div role="alert" className="fixed inset-0 flex items-center justify-center bg-background">
      <p>{t(messageKey)}</p>
    </div>
  );
}

/**
 * Renders the overlay (warning modal or expired notice) for the current
 * phase, or null while the session is active.
 *
 * Exists as a plain render function (not a hook) so `SessionManager` itself
 * stays a short sequence of hook calls followed by one render decision.
 */
function renderSessionOverlay(
  phase: SessionPhase,
  session: CurrentSession,
  now: number,
  lastReportedAtRef: RefObject<number>,
  onSessionRefreshed: (session: CurrentSession) => void,
): JSX.Element | null {
  if (phase === "expired_idle") return <ExpiredNotice kind="idle" />;
  if (phase === "expired_absolute") return <ExpiredNotice kind="absolute" />;
  if (phase === "absolute_warning") {
    const secondsRemaining = Math.ceil(msRemaining(session.absolute_expires_at, now) / 1000);
    return <ExpiryWarningModal kind="absolute" secondsRemaining={secondsRemaining} />;
  }
  if (phase === "idle_warning") {
    const secondsRemaining = Math.ceil(msRemaining(session.idle_expires_at, now) / 1000);
    return (
      <ExpiryWarningModal
        kind="idle"
        secondsRemaining={secondsRemaining}
        onStayConnected={() => {
          lastReportedAtRef.current = Date.now();
          void reportActivityAndRefresh(onSessionRefreshed);
        }}
      />
    );
  }
  return null;
}

interface SessionManagerProps {
  session: CurrentSession | null;
  onSessionRefreshed: (session: CurrentSession) => void;
}

/**
 * Enforces G15's idle/absolute session timeouts: detects activity, reports
 * it (throttled to once per 60 s), and shows the 30-second warning modal or
 * the expired-session message.
 *
 * Exists as one reusable manager mounted once per authenticated screen
 * (task 5.5's `/app`), so the timeout behavior lives in a single place.
 */
export function SessionManager({
  session,
  onSessionRefreshed,
}: SessionManagerProps): JSX.Element | null {
  const now = useSessionClock(session);
  const lastReportedAtRef = useActivityReporting(onSessionRefreshed);
  const phase = session ? computeSessionPhase(session, now) : "active";

  if (!session) return null;
  return renderSessionOverlay(phase, session, now, lastReportedAtRef, onSessionRefreshed);
}
