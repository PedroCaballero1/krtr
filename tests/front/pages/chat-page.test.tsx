import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { EventName } from "@/api/event-names";
import * as events from "@/api/events";
import es from "@/i18n/locales/es.json";
import { ChatPage } from "@/pages/chat-page";

// Instrumentation (task 5.10) posts to /api/events through the same global
// fetch these tests mock for /api/chat/*; stub trackEvent directly so it
// never adds an extra fetch call for these tests to account for.
beforeEach(() => {
  vi.spyOn(events, "trackEvent").mockResolvedValue(undefined);
});

function renderChatPage() {
  return render(
    <MemoryRouter initialEntries={["/app/chat/case-1"]}>
      <Routes>
        <Route path="/app/chat/:incidentId" element={<ChatPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

function delayedJsonResponse(
  body: unknown,
  delayMs: number,
): Promise<Response> {
  return new Promise((resolve) => {
    setTimeout(
      () => resolve(new Response(JSON.stringify(body), { status: 200 })),
      delayMs,
    );
  });
}

function typeAndSend(text: string): void {
  fireEvent.change(screen.getByPlaceholderText(es.chat_placeholder), {
    target: { value: text },
  });
  fireEvent.click(screen.getByRole("button", { name: "Enviar" }));
}

describe("ChatPage — typing indicator timing (fake clock)", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("does not show the indicator when the reply arrives within 2 seconds", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      delayedJsonResponse(
        { incident_id: "case-1", reply: "reply-fast", responded_at: "now" },
        500,
      ),
    );
    renderChatPage();

    typeAndSend("hola");
    await vi.advanceTimersByTimeAsync(500);
    await vi.advanceTimersByTimeAsync(0); // Flush the state update the resolved promise scheduled.

    expect(
      screen.queryByText(es.chat_typing_indicator),
    ).not.toBeInTheDocument();
    expect(screen.getByText("reply-fast")).toBeInTheDocument();
  });

  it("shows the indicator once 2 seconds pass without a reply, and clears it once the reply arrives", async () => {
    let resolveFetch!: (response: Response) => void;
    vi.spyOn(globalThis, "fetch").mockReturnValue(
      new Promise((resolve) => {
        resolveFetch = resolve;
      }),
    );
    renderChatPage();

    typeAndSend("pregunta");
    await vi.advanceTimersByTimeAsync(2000);
    await vi.advanceTimersByTimeAsync(0); // Flush the indicator's own effect-driven state update.
    expect(screen.getByText(es.chat_typing_indicator)).toBeInTheDocument();
    expect(events.trackEvent).toHaveBeenCalledWith(
      EventName.TypingIndicatorShown,
    );

    // Switched to real timers before resolving: clearing the indicator
    // depends on a passive effect (useTypingIndicator's cleanup), which
    // React schedules through its own timer/channel — one fake timers
    // don't drive — so the rest of this assertion needs the real event loop.
    vi.useRealTimers();
    resolveFetch(
      new Response(
        JSON.stringify({
          incident_id: "case-1",
          reply: "reply-slow",
          responded_at: "now",
        }),
        { status: 200 },
      ),
    );

    expect(await screen.findByText("reply-slow")).toBeInTheDocument();
    // React commits the reply first and runs that effect cleanup (which
    // clears the indicator) right after, so wait for it instead of
    // asserting in the same tick; it still fails if the indicator never clears.
    await waitFor(() =>
      expect(
        screen.queryByText(es.chat_typing_indicator),
      ).not.toBeInTheDocument(),
    );
  });
});

describe("ChatPage — composer behavior", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows both the sent message and the reply", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          incident_id: "case-1",
          reply: "assistant reply",
          responded_at: "now",
        }),
        { status: 200 },
      ),
    );
    renderChatPage();

    typeAndSend("user message");

    expect(await screen.findByText("assistant reply")).toBeInTheDocument();
    expect(screen.getByText("user message")).toBeInTheDocument();
    expect(events.trackEvent).toHaveBeenCalledWith(EventName.ChatMessageSent, {
      incident_id: "case-1",
    });
    expect(events.trackEvent).toHaveBeenCalledWith(
      EventName.ChatResponseReceived,
      expect.objectContaining({ incident_id: "case-1" }),
    );
  });

  it("Enter sends the message; Shift+Enter inserts a newline instead", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          incident_id: "case-1",
          reply: "ok",
          responded_at: "now",
        }),
        {
          status: 200,
        },
      ),
    );
    renderChatPage();
    const textarea = screen.getByPlaceholderText(es.chat_placeholder);

    fireEvent.change(textarea, { target: { value: "line one" } });
    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: true });
    expect(fetchSpy).not.toHaveBeenCalled();

    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: false });
    expect(fetchSpy).toHaveBeenCalledOnce();
  });

  it("disables the send button while a request is pending", async () => {
    let resolveFetch!: (response: Response) => void;
    vi.spyOn(globalThis, "fetch").mockReturnValue(
      new Promise((resolve) => {
        resolveFetch = resolve;
      }),
    );
    const user = userEvent.setup();
    renderChatPage();

    await user.type(screen.getByPlaceholderText(es.chat_placeholder), "hola");
    await user.click(screen.getByRole("button", { name: "Enviar" }));

    expect(screen.getByRole("button", { name: "Enviar" })).toBeDisabled();
    resolveFetch(
      new Response(
        JSON.stringify({
          incident_id: "case-1",
          reply: "ok",
          responded_at: "now",
        }),
        {
          status: 200,
        },
      ),
    );
    // The button also stays disabled once sending finishes, until there is
    // text again — the input is cleared after a successful send.
    await screen.findByText("ok");
    await user.type(
      screen.getByPlaceholderText(es.chat_placeholder),
      "otro mensaje",
    );
    expect(screen.getByRole("button", { name: "Enviar" })).toBeEnabled();
  });

  it("shows the rate-limit message on a 429", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          error: "rate_limited",
          message_key: "chat_error_rate_limited",
        }),
        { status: 429 },
      ),
    );
    renderChatPage();

    typeAndSend("hola");

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Enviaste demasiados mensajes. Espera un momento.",
    );
  });

  it("shows the timeout message when the request aborts", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(
      new DOMException("The operation timed out.", "TimeoutError"),
    );
    renderChatPage();

    typeAndSend("hola");

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "La respuesta tardó demasiado. Intenta de nuevo.",
    );
  });

  it("shows a translated message for any other error", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ error: "server_error", message_key: "app_name" }),
        {
          status: 500,
        },
      ),
    );
    renderChatPage();

    typeAndSend("hola");

    expect(await screen.findByRole("alert")).toHaveTextContent("krtr");
  });

  it("enforces the 2000-character limit on the textarea", () => {
    renderChatPage();

    const textarea = screen.getByPlaceholderText(
      es.chat_placeholder,
    ) as HTMLTextAreaElement;

    expect(textarea.maxLength).toBe(2000);
  });
});

describe("ChatPage — header", () => {
  it('shows the case id and goes back to the case selection from "Casos"', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/app/chat/case-1"]}>
        <Routes>
          <Route path="/app/chat/:incidentId" element={<ChatPage />} />
          <Route path="/app/support" element={<p>support screen</p>} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText("case-1")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Casos" }));

    expect(await screen.findByText("support screen")).toBeInTheDocument();
  });
});
