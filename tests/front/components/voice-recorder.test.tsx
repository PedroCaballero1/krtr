import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { JSX } from "react";
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

/** A stand-in composer that places the record button next to a text field. */
function renderAsComposer(recordButton: JSX.Element): JSX.Element {
  return (
    <div>
      <textarea aria-label="composer" />
      {recordButton}
    </div>
  );
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

    expect(await screen.findByText("Grabando")).toBeInTheDocument();
    expect(screen.getByText("0:00")).toBeInTheDocument();
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
    expect(onSent).toHaveBeenCalledWith("Nota de voz · 1:00", "voice reply");
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
      "No tenemos permiso para usar el micrófono. Actívalo en tu navegador o escribe tu mensaje.",
    );
    expect(events.trackEvent).toHaveBeenCalledWith(
      EventName.VoicePermissionDenied,
    );
  });

  it("replaces the surrounding composer with the recording bar while recording", async () => {
    const user = userEvent.setup();
    render(
      <VoiceRecorder
        incidentId="case-1"
        onSent={vi.fn()}
        onError={vi.fn()}
        renderIdle={renderAsComposer}
      />,
    );
    expect(screen.getByLabelText("composer")).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "Grabar nota de voz" }),
    );

    expect(await screen.findByText("Grabando")).toBeInTheDocument();
    expect(screen.queryByLabelText("composer")).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Enviar audio" }),
    ).toBeInTheDocument();
  });

  it("keeps the composer and the record button usable after a denied permission", async () => {
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: {
        getUserMedia: vi
          .fn()
          .mockRejectedValue(new DOMException("denied", "NotAllowedError")),
      },
    });
    const user = userEvent.setup();
    render(
      <VoiceRecorder
        incidentId="case-1"
        onSent={vi.fn()}
        onError={vi.fn()}
        renderIdle={renderAsComposer}
      />,
    );

    await user.click(
      screen.getByRole("button", { name: "Grabar nota de voz" }),
    );

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByLabelText("composer")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Grabar nota de voz" }),
    ).toBeEnabled();
  });

  it("disables the record button when asked to", () => {
    render(
      <VoiceRecorder
        incidentId="case-1"
        onSent={vi.fn()}
        onError={vi.fn()}
        disabled
      />,
    );

    expect(
      screen.getByRole("button", { name: "Grabar nota de voz" }),
    ).toBeDisabled();
  });
});
