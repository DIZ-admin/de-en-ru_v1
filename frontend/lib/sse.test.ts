import { describe, expect, it } from "vitest";
import { SSEDecoder } from "./sse";

describe("SSEDecoder", () => {
  it("returns complete data payloads when chunks split mid-line", () => {
    const decoder = new SSEDecoder();
    expect(decoder.push("data: Hel")).toEqual([]);
    expect(decoder.push("lo\n")).toEqual(["Hello"]);
  });

  it("skips control events and empty payloads", () => {
    const decoder = new SSEDecoder();
    decoder.push("event: translation_start\n");
    expect(decoder.push("data: {}\n")).toEqual([]);
    expect(decoder.push("data: \n")).toEqual([]);
  });

  it("flushes remaining buffered data on stream end", () => {
    const decoder = new SSEDecoder();
    decoder.push("data: Partially complete");
    const remaining = decoder.push("", { isFinal: true });
    expect(remaining).toEqual(["Partially complete"]);
  });
});
