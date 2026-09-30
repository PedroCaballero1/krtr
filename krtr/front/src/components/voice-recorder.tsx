import type { JSX, RefObject } from "react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { ApiError } from "@/api/client";
import { EventName } from "@/api/event-names";
import { trackEvent } from "@/api/events";
import { sendVoiceMessage } from "@/api/voice";
import { Button } from "@/components/ui/button";
import i18n from "@/i18n/config";
import { resolveLanguage } from "@/i18n/languages";

const MAX_RECORDING_SECONDS = 60;
const TICK_INTERVAL_MS = 1000;
// Preferred first: the browsers the guide targets support Opus in WebM.
// audio/mp4 (AAC) is the fallback for browsers that don't (e.g. Safari).
const CANDIDATE_MIME_TYPES = ["audio/webm;codecs=opus", "audio/mp4"] as const;

type RecordingStatus = "idle" | "recording" | "permission_denied";

interface RecordingHandles {
  recorder: MediaRecorder;
  stream: MediaStream;
  chunks: Blob[];
}

interface RecorderRefs {
  handles: RefObject<RecordingHandles | null>;
  interval: RefObject<ReturnType<typeof setInterval> | null>;
  elapsedSeconds: RefObject<number>;
}

interface RecorderCallbacks {
  setStatus: (status: RecordingStatus) => void;
  setSeconds: (seconds: number) => void;
  onSent: (userText: string, reply: string) => void;
  onError: (message: string) => void;
}

/** The first MIME type the browser's MediaRecorder supports, or null. */
function pickSupportedMimeType(): string | null {
  return CANDIDATE_MIME_TYPES.find((mimeType) => MediaRecorder.isTypeSupported(mimeType)) ?? null;
}

/** Translates a failed voice send into the message shown to the user. */
function resolveVoiceErrorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return i18n.t("chat_error_generic");
}

/** Stops the timer and releases the microphone; safe to call more than once. */
function teardownRecording(refs: RecorderRefs): void {
  if (refs.interval.current !== null) {
    clearInterval(refs.interval.current);
    refs.interval.current = null;
  }
  refs.handles.current?.stream.getTracks().forEach((track) => track.stop());
  refs.handles.current = null;
}

/** Resolves once `recorder.stop()` has flushed its final chunk. */
function stopAndCollect(handles: RecordingHandles): Promise<Blob> {
  return new Promise((resolve) => {
    handles.recorder.onstop = () =>
      resolve(new Blob(handles.chunks, { type: handles.recorder.mimeType }));
    handles.recorder.stop();
  });
}

/**
 * Ends the current recording: "send" uploads it, "cancel" discards it.
 *
 * Exists as the module-level function every ending path (auto-cut at 60s,
 * Cancelar, Enviar) delegates to.
 */
async function finishRecording(
  refs: RecorderRefs,
  callbacks: RecorderCallbacks,
  incidentId: string,
  action: "send" | "cancel",
): Promise<void> {
  const handles = refs.handles.current;
  teardownRecording(refs);
  callbacks.setStatus("idle");
  if (!handles) return;
  const audio = await stopAndCollect(handles);
  if (action === "cancel") {
    void trackEvent(EventName.VoiceRecordingCancelled);
    return;
  }
  void trackEvent(EventName.VoiceRecordingSent);
  try {
    const response = await sendVoiceMessage(incidentId, audio, resolveLanguage(i18n.language));
    callbacks.onSent(i18n.t("chat_voice_message_label"), response.reply);
  } catch (error) {
    callbacks.onError(resolveVoiceErrorMessage(error));
  }
}

/** Ticks the recording clock, auto-cutting the recording at 60 s (G8). */
function tickRecordingClock(
  refs: RecorderRefs,
  callbacks: RecorderCallbacks,
  incidentId: string,
): void {
  refs.elapsedSeconds.current += 1;
  callbacks.setSeconds(refs.elapsedSeconds.current);
  if (refs.elapsedSeconds.current >= MAX_RECORDING_SECONDS) {
    void finishRecording(refs, callbacks, incidentId, "send");
  }
}

/** Requests the microphone and starts recording, or reports permission denial. */
async function startRecording(
  refs: RecorderRefs,
  callbacks: RecorderCallbacks,
  incidentId: string,
): Promise<void> {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mimeType = pickSupportedMimeType();
    const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
    const chunks: Blob[] = [];
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) chunks.push(event.data);
    };
    refs.handles.current = { recorder, stream, chunks };
    refs.elapsedSeconds.current = 0;
    recorder.start();
    callbacks.setStatus("recording");
    callbacks.setSeconds(0);
    void trackEvent(EventName.VoiceRecordingStarted);
    refs.interval.current = setInterval(
      () => tickRecordingClock(refs, callbacks, incidentId),
      TICK_INTERVAL_MS,
    );
  } catch {
    callbacks.setStatus("permission_denied");
    void trackEvent(EventName.VoicePermissionDenied);
  }
}

interface VoiceRecorderProps {
  incidentId: string;
  onSent: (userText: string, reply: string) => void;
  onError: (message: string) => void;
}

/**
 * The voice note button (G8): records with `MediaRecorder`, auto-cutting at
 * 60 s, with Cancelar/Enviar while recording and a message on denied
 * microphone permission.
 */
export function VoiceRecorder({ incidentId, onSent, onError }: VoiceRecorderProps): JSX.Element {
  const { t } = useTranslation();
  const [status, setStatus] = useState<RecordingStatus>("idle");
  const [seconds, setSeconds] = useState(0);
  const handles = useRef<RecordingHandles | null>(null);
  const interval = useRef<ReturnType<typeof setInterval> | null>(null);
  const elapsedSeconds = useRef(0);
  const refs: RecorderRefs = { handles, interval, elapsedSeconds };
  const callbacks: RecorderCallbacks = { setStatus, setSeconds, onSent, onError };

  // handles/interval/elapsedSeconds are the stable refs useEffect cares
  // about; `refs` itself is a fresh wrapper object every render, so it is
  // intentionally left out of the dependency array.
  useEffect(() => () => teardownRecording({ handles, interval, elapsedSeconds }), []);

  if (status === "permission_denied") {
    return <p role="alert">{t("voice_permission_denied")}</p>;
  }
  if (status === "recording") {
    return (
      <div className="flex items-center gap-2">
        <span>{t("voice_recording_status", { seconds, maxSeconds: MAX_RECORDING_SECONDS })}</span>
        <Button
          type="button"
          variant="outline"
          onClick={() => void finishRecording(refs, callbacks, incidentId, "cancel")}
        >
          {t("voice_cancel")}
        </Button>
        <Button
          type="button"
          onClick={() => void finishRecording(refs, callbacks, incidentId, "send")}
        >
          {t("voice_send")}
        </Button>
      </div>
    );
  }
  return (
    <Button
      type="button"
      variant="outline"
      onClick={() => void startRecording(refs, callbacks, incidentId)}
    >
      {t("voice_record")}
    </Button>
  );
}
