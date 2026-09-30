import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, ApiEvent, apiFetch } from "@/api/client";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("apiFetch", () => {
  const originalLocation = window.location;
  let assignSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    // jsdom's window.location.assign can't be spied on directly (it isn't
    // configurable), so the whole property is replaced for the test.
    assignSpy = vi.fn();
    Object.defineProperty(window, "location", {
      configurable: true,
      value: { ...originalLocation, assign: assignSpy },
    });
    document.cookie = "__Host-krtr_csrf=; Max-Age=0";
  });

  afterEach(() => {
    Object.defineProperty(window, "location", {
      configurable: true,
      value: originalLocation,
    });
    vi.restoreAllMocks();
  });

  it("requests same-origin, without a CSRF header, for a GET", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse(200, {}));

    await apiFetch("/api/cases");

    const [, init] = fetchSpy.mock.calls[0];
    expect(init?.credentials).toBe("same-origin");
    expect(new Headers(init?.headers).has("X-KRTR-CSRF")).toBe(false);
  });

  it("adds the CSRF header from the cookie for a state-changing method", async () => {
    document.cookie = "__Host-krtr_csrf=test-token; Path=/; Secure";
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse(202, {}));

    await apiFetch("/api/events", { method: "POST" });

    const [, init] = fetchSpy.mock.calls[0];
    expect(new Headers(init?.headers).get("X-KRTR-CSRF")).toBe("test-token");
  });

  it("redirects to the landing page and dispatches Unauthorized on 401", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse(401, {
        error: "unauthorized",
        message_key: "errors.unauthorized",
      }),
    );
    const listener = vi.fn();
    window.addEventListener(ApiEvent.Unauthorized, listener);

    await expect(apiFetch("/api/me")).rejects.toThrow(ApiError);

    expect(listener).toHaveBeenCalledOnce();
    expect(assignSpy).toHaveBeenCalledWith("/");
  });

  it("dispatches RateLimited on 429, without redirecting", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse(429, {
        error: "rate_limited",
        message_key: "errors.rate_limited",
      }),
    );
    const listener = vi.fn();
    window.addEventListener(ApiEvent.RateLimited, listener);

    await expect(
      apiFetch("/api/chat/messages", { method: "POST" }),
    ).rejects.toThrow(ApiError);

    expect(listener).toHaveBeenCalledOnce();
    expect(assignSpy).not.toHaveBeenCalled();
  });

  it("throws an ApiError with the message translated from message_key", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse(400, {
        error: "invalid_text",
        message_key: "login_landing_tagline",
      }),
    );

    const error = await apiFetch("/api/chat/messages", {
      method: "POST",
    }).catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(400);
    expect((error as ApiError).code).toBe("invalid_text");
    // Translated (not the raw key): the Spanish tagline text, per es.json.
    expect((error as ApiError).message).toBe(
      "Seguridad y soporte para tus productos financieros.",
    );
  });

  it("falls back to the status text when the body has no message_key", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(null, { status: 500, statusText: "Internal Server Error" }),
    );

    const error = await apiFetch("/api/cases").catch(
      (caught: unknown) => caught,
    );

    expect((error as ApiError).message).toBe("Internal Server Error");
  });

  it("resolves normally for a successful response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse(200, { ok: true }),
    );

    const response = await apiFetch("/api/me");

    expect(response.ok).toBe(true);
  });
});
