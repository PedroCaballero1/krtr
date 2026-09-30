import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fetchCurrentSession, logout } from "@/api/session";

describe("fetchCurrentSession", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns the parsed /api/me response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          customer_id: "12345",
          idle_expires_at: "2026-01-01T00:05:00Z",
          absolute_expires_at: "2026-01-01T00:30:00Z",
        }),
        { status: 200 },
      ),
    );

    const session = await fetchCurrentSession();

    expect(session.customer_id).toBe("12345");
  });
});

describe("logout", () => {
  const originalLocation = window.location;
  let assignSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    assignSpy = vi.fn();
    Object.defineProperty(window, "location", {
      configurable: true,
      value: { ...originalLocation, assign: assignSpy },
    });
  });

  afterEach(() => {
    Object.defineProperty(window, "location", {
      configurable: true,
      value: originalLocation,
    });
    vi.restoreAllMocks();
  });

  it("posts to /auth/logout and returns to the landing page", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(null, { status: 204 }));

    await logout();

    expect(fetchSpy.mock.calls[0][0]).toBe("/auth/logout");
    expect(assignSpy).toHaveBeenCalledWith("/");
  });

  it("still returns to the landing page when the request fails", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("network down"));

    await logout();

    expect(assignSpy).toHaveBeenCalledWith("/");
  });
});
