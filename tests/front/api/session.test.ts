import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  LogoutReason,
  fetchCurrentSession,
  logout,
  parseLogoutReason,
} from "@/api/session";

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

  it("posts to /auth/logout and returns to the landing page, as a user logout by default", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(null, { status: 204 }));

    await logout();

    expect(fetchSpy.mock.calls[0][0]).toBe("/auth/logout");
    expect(assignSpy).toHaveBeenCalledWith("/?logout=user");
  });

  it("forwards the given reason to the landing page", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(null, { status: 204 }),
    );

    await logout(LogoutReason.IdleTimeout);

    expect(assignSpy).toHaveBeenCalledWith("/?logout=idle");
  });

  it("still returns to the landing page when the request fails", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("network down"));

    await logout();

    expect(assignSpy).toHaveBeenCalledWith("/?logout=user");
  });
});

describe("parseLogoutReason", () => {
  it("accepts every reason logout() emits", () => {
    for (const reason of Object.values(LogoutReason)) {
      expect(parseLogoutReason(reason)).toBe(reason);
    }
  });

  it("rejects a missing or unknown value", () => {
    expect(parseLogoutReason(null)).toBeNull();
    expect(parseLogoutReason("")).toBeNull();
    expect(parseLogoutReason("IDLE")).toBeNull();
  });
});
