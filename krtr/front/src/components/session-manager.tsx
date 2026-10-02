import type { JSX, RefObject } from "react";
import { useEffect, useId, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { EventName } from "@/api/event-names";
import { trackEvent } from "@/api/events";
import { LogoutReason, logout, reportActivity, type CurrentSession } from "@/api/session";
import { Button } from "@/components/ui/button";
import { Kicker } from "@/components/ui/kicker";
import { Notice } from "@/components/ui/notice";
import { formatMinutesSeconds } from "@/lib/format";

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

/** The event each phase is entered under, for the §3.5 catalog — phases with no event (e.g. "active") are omitted. */
const PHASE_ENTERED_EVENTS: Partial<Record<SessionPhase, EventName>> = {
  idle_warning: EventName.SessionIdleWarningShown,
  absolute_warning: EventName.SessionAbsoluteWarningShown,
  expired_idle: EventName.SessionExpiredIdle,
  expired_absolute: EventName.SessionExpiredAbsolute,
};

/**
 * Ticks once per second, so time-based UI (the countdowns) stays current,
 * records the §3.5 event for each phase the session enters (once each), and
 * logs out exactly once, the moment the session's phase becomes expired —
 * all checked and acted on directly inside the tick, rather than in a
 * separate effect keyed off the derived phase, so it fires deterministically
 * under both real and fake timers.
 *
 * @param session - The current session, or null before it has loaded.
 * @returns The current time, in epoch milliseconds.
 */
function useSessionClock(session: CurrentSession | null): number {
  const [now, setNow] = useState(() => Date.now());
  const sessionRef = useRef(session);
  const hasExpiredRef = useRef(false);
  const lastPhaseRef = useRef<SessionPhase>("active");

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
      if (phase !== lastPhaseRef.current) {
        lastPhaseRef.current = phase;
        const eventName = PHASE_ENTERED_EVENTS[phase];
        if (eventName) void trackEvent(eventName);
      }
      if (phase === "expired_idle" || phase === "expired_absolute") {
        hasExpiredRef.current = true;
        void logout(
          phase === "expired_idle" ? LogoutReason.IdleTimeout : LogoutReason.AbsoluteTimeout,
        );
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

/** The translation keys for each warning kind's title and body. */
const WARNING_TEXT_KEYS = {
  idle: { title: "session_idle_warning_title", body: "session_idle_warning_body" },
  absolute: { title: "session_absolute_warning_title", body: "session_absolute_warning_body" },
} as const;

/**
 * The 30-second countdown modal shown before an idle or absolute expiry:
 * a large `0:SS` countdown, the reason, and the way out ("Seguir conectado"
 * only for idle, since the absolute limit can't be extended; Cerrar sesión
 * always).
 */
function ExpiryWarningModal({
  secondsRemaining,
  kind,
  onStayConnected,
}: ExpiryWarningModalProps): JSX.Element {
  const { t } = useTranslation();
  const titleId = useId();
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-neutral-900/50 p-4">
      <div
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="flex w-full max-w-[480px] flex-col gap-4 border-t-4 border-primary bg-background p-6 shadow-lg"
      >
        <Kicker>{t("header_session")}</Kicker>
        <div className="font-heading text-7xl leading-none font-extrabold tracking-[-0.03em] tabular-nums">
          {formatMinutesSeconds(secondsRemaining)}
        </div>
        <h2 id={titleId} className="m-0 text-[22px]">
          {t(WARNING_TEXT_KEYS[kind].title)}
        </h2>
        <p className="m-0 text-[15px] leading-normal">{t(WARNING_TEXT_KEYS[kind].body)}</p>
        <div className="mt-2 flex flex-wrap gap-2">
          {onStayConnected && (
            <Button size="lg" className="min-w-50 justify-start" onClick={onStayConnected}>
              {t("session_stay_connected")}
            </Button>
          )}
          <Button variant="outline" size="lg" onClick={() => void logout()}>
            {t("logout_button")}
          </Button>
        </div>
      </div>
    </div>
  );
}

/** The full-screen message shown once a session has expired, until the landing page loads. */
function ExpiredNotice({ kind }: { kind: "idle" | "absolute" }): JSX.Element {
  const { t } = useTranslation();
  const messageKey =
    kind === "idle" ? "session_expired_idle_message" : "session_expired_absolute_message";
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-background p-4">
      <Notice role="alert" className="text-base">
        {t(messageKey)}
      </Notice>
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
          void trackEvent(EventName.SessionExtended);
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
