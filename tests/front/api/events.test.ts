import { afterEach, describe, expect, it, vi } from "vitest";
import { EventName } from "@/api/event-names";
import { trackEvent } from "@/api/events";

describe("trackEvent", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("posts the event name and properties to /api/events", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(null, { status: 202 }));

    await trackEvent(EventName.PageView, { path: "/app" });

    const [url, init] = fetchSpy.mock.calls[0];
    expect(url).toBe("/api/events");
    expect(init?.method).toBe("POST");
    expect(JSON.parse(init?.body as string)).toEqual({
      event_name: "page_view",
      properties: { path: "/app" },
    });
  });

  it("defaults properties to an empty object", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(null, { status: 202 }));

    await trackEvent(EventName.SupportClicked);

    const [, init] = fetchSpy.mock.calls[0];
    expect(JSON.parse(init?.body as string).properties).toEqual({});
  });

  it("never throws when the request fails", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("network down"));

    await expect(trackEvent(EventName.PageView)).resolves.toBeUndefined();
  });

  it("never throws when the backend returns an error status", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ error: "bad_request", message_key: "x" }), {
        status: 422,
      }),
    );

    await expect(trackEvent(EventName.PageView)).resolves.toBeUndefined();
  });
});
