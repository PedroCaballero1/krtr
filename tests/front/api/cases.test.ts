import { afterEach, describe, expect, it, vi } from "vitest";
import { createCase, listOpenCases, resumeCase } from "@/api/cases";
import { ApiError } from "@/api/client";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("cases API", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("listOpenCases requests the open cases endpoint", async () => {
    const cases = [
      { incident_id: "abc-1", opened_at: "2026-01-01T00:00:00Z", summary: "s" },
    ];
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse(200, cases));

    const result = await listOpenCases();

    expect(result).toEqual(cases);
    expect(fetchSpy.mock.calls[0][0]).toBe("/api/cases?status=open");
  });

  it("createCase posts to /api/cases and returns the new incident_id", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse(200, { incident_id: "new-1" }));

    const result = await createCase();

    expect(result).toEqual({ incident_id: "new-1" });
    expect(fetchSpy.mock.calls[0][1]?.method).toBe("POST");
  });

  it("resumeCase posts the incident_id and returns it back on success", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse(200, { incident_id: "abc-1" }));

    const result = await resumeCase("abc-1");

    expect(result).toEqual({ incident_id: "abc-1" });
    expect(JSON.parse(fetchSpy.mock.calls[0][1]?.body as string)).toEqual({
      incident_id: "abc-1",
    });
  });

  it("resumeCase throws a 404 ApiError for an unknown or foreign case", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse(404, {
        error: "not_found",
        message_key: "support_case_not_found",
      }),
    );

    const error = await resumeCase("someone-elses-case").catch(
      (caught: unknown) => caught,
    );

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(404);
  });
});
