import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  getAuthToken,
  translateText,
  translateTextStream,
  type TranslationRequest,
} from "./api";

const ORIGINAL_FETCH = global.fetch;

describe("API client", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    global.fetch = fetchMock as unknown as typeof global.fetch;
  });

  afterEach(() => {
    global.fetch = ORIGINAL_FETCH;
  });

  it("retrieves auth token", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ access_token: "abc123" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(getAuthToken("demo")).resolves.toBe("abc123");
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/auth/token"),
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("throws when auth token fetching fails", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 500 }));
    await expect(getAuthToken()).rejects.toThrow(/failed to get auth token/i);
  });

  it("translates text synchronously", async () => {
    fetchMock.mockResolvedValue(
      new Response(
        JSON.stringify({
          translated_text: "Hallo Welt",
          detected_lang: "en",
        model: "gpt-4.1-nano",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    const result = await translateText(
      { text: "Hello", source_lang: "en", target_lang: "de" },
      "token",
    );
    expect(result.translated_text).toBe("Hallo Welt");
  });

  it("throws when translation fails", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ detail: "bad request" }), {
        status: 400,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(
      translateText(
        { text: "Hello", source_lang: "en", target_lang: "de" },
        "token",
      ),
    ).rejects.toThrow(/bad request/);
  });

  it("streams translation chunks", async () => {
    const encoder = new TextEncoder();
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode("event: translation_start\n\n"));
        controller.enqueue(encoder.encode("data: Hallo\n\n"));
        controller.close();
      },
    });

    fetchMock.mockResolvedValue(
      new Response(stream, {
        status: 200,
        headers: { "Content-Type": "text/event-stream" },
      }),
    );

    const request: TranslationRequest = {
      text: "Hello",
      source_lang: "en",
      target_lang: "de",
    };

    const iterator = translateTextStream(request, "token");
    const chunks: string[] = [];
    for await (const chunk of iterator) {
      chunks.push(chunk);
    }

    expect(chunks).toEqual(["Hallo"]);
  });

  it("throws when streaming request fails", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 502 }));

    const iterator = translateTextStream(
      { text: "Hello", source_lang: "en", target_lang: "de" },
      "token",
    );

    await expect(iterator.next()).rejects.toThrow(/streaming translation failed/i);
  });
});
