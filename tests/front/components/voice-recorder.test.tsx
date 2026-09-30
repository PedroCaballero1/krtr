import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { EventName } from "@/api/event-names";
import * as events from "@/api/events";
import * as voiceApi from "@/api/voice";
import { VoiceRecorder } from "@/components/voice-recorder";

class FakeMediaRecorder {
  static isTypeSupported = vi.fn(() => true);
  ondataavailable: ((event: { data: Blob }) => void) | null = null;
  onstop: (() => void) | null = null;
  mimeType: string;

  constructor(
    public stream: MediaStream,
    options?: { mimeType?: string },
  ) {
    this.mimeType = options?.mimeType ?? "";
  }

  start = vi.fn();
  stop = vi.fn(() => {
    this.ondataavailable?.({ data: new Blob(["chunk"]) });
    this.onstop?.();
  });
}

function makeFakeStream(): MediaStream {
  const track = { stop: vi.fn() };
  return { getTracks: () => [track] } as unknown as MediaStream;
}

function renderRecorder(onSent = vi.fn(), onError = vi.fn()) {
  render(
    <VoiceRecorder incidentId="case-1" onSent={onSent} onError={onError} />,
  );
  return { onSent, onError };
}

describe("VoiceRecorder", () => {
  beforeEach(() => {
    vi.stubGlobal("MediaRecorder", FakeMediaRecorder);
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: { getUserMedia: vi.fn().mockResolvedValue(makeFakeStream()) },
    });
    vi.spyOn(events, "trackEvent").mockResolvedValue(undefined);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("starts recording on click and shows the elapsed-time status", async () => {
    const user = userEvent.setup();
    renderRecorder();

    await user.click(
      screen.getByRole("button", { name: "Grabar nota de voz" }),
    );

    expect(await screen.findByText("Grabando… 0s de 60s")).toBeInTheDocument();
    expect(events.trackEvent).toHaveBeenCalledWith(
      EventName.VoiceRecordingStarted,
    );
  });

  it("auto-cuts and sends the recording at 60 seconds", async () => {
    vi.useFakeTimers();
    vi.spyOn(voiceApi, "sendVoiceMessage").mockResolvedValue({
      incident_id: "case-1",
      reply: "voice reply",
      responded_at: "now",
    });
    const { onSent } = renderRecorder();

    screen.getByRole("button", { name: "Grabar nota de voz" }).click();
    await vi.advanceTimersByTimeAsync(60_000);
    await vi.runAllTimersAsync();

    expect(voiceApi.sendVoiceMessage).toHaveBeenCalledOnce();
    expect(onSent).toHaveBeenCalledWith("🎤 Nota de voz", "voice reply");
    expect(events.trackEvent).toHaveBeenCalledWith(
      EventName.VoiceRecordingSent,
    );
  });

  it("discards the recording and never uploads it when cancelled", async () => {
    const sendSpy = vi.spyOn(voiceApi, "sendVoiceMessage");
    const user = userEvent.setup();
    renderRecorder();
    await user.click(
      screen.getByRole("button", { name: "Grabar nota de voz" }),
    );

    await user.click(await screen.findByRole("button", { name: "Cancelar" }));

    expect(sendSpy).not.toHaveBeenCalled();
    expect(events.trackEvent).toHaveBeenCalledWith(
      EventName.VoiceRecordingCancelled,
    );
    expect(
      await screen.findByRole("button", { name: "Grabar nota de voz" }),
    ).toBeInTheDocument();
  });

  it("shows a message and records an event when the microphone permission is denied", async () => {
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: {
        getUserMedia: vi
          .fn()
          .mockRejectedValue(new DOMException("denied", "NotAllowedError")),
      },
    });
    const user = userEvent.setup();
    renderRecorder();

    await user.click(
      screen.getByRole("button", { name: "Grabar nota de voz" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "No se pudo acceder al micrófono. Revisa los permisos del navegador.",
    );
    expect(events.trackEvent).toHaveBeenCalledWith(
      EventName.VoicePermissionDenied,
    );
  });
});
