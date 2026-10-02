import { describe, expect, it } from "vitest";
import { formatMinutesSeconds } from "@/lib/format";

describe("formatMinutesSeconds", () => {
  it.each([
    [0, "0:00"],
    [5, "0:05"],
    [59, "0:59"],
    [60, "1:00"],
    [272, "4:32"],
    [1800, "30:00"],
  ])("formats %i seconds as %s", (seconds, expected) => {
    expect(formatMinutesSeconds(seconds)).toBe(expected);
  });

  it("floors fractional seconds and never shows a negative time", () => {
    expect(formatMinutesSeconds(59.9)).toBe("0:59");
    expect(formatMinutesSeconds(-3)).toBe("0:00");
  });
});
