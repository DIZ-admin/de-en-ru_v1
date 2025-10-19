import React, { act } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi, beforeEach, afterEach, describe, it, expect } from "vitest";
import Home from "./page";

const mockGetAuthToken = vi.fn();
const mockTranslateStream = vi.fn();
const mockGetVoiceFormats = vi.fn();
const mockVoiceTranslate = vi.fn();
let consoleErrorSpy: ReturnType<typeof vi.spyOn>;

vi.mock("@/lib/api", () => ({
  getAuthToken: (...args: unknown[]) => mockGetAuthToken(...args),
  translateTextStream: (...args: unknown[]) => mockTranslateStream(...args),
  getVoiceFormats: (...args: unknown[]) => mockGetVoiceFormats(...args),
  voiceTranslate: (...args: unknown[]) => mockVoiceTranslate(...args),
}));

async function* mockGenerator(chunks: string[]) {
  for (const chunk of chunks) {
    yield chunk;
  }
}

describe("Home page", () => {
  beforeEach(() => {
    mockGetAuthToken.mockReset();
    mockTranslateStream.mockReset();
    mockGetVoiceFormats.mockReset();
    mockVoiceTranslate.mockReset();
    mockGetVoiceFormats.mockResolvedValue({
      mime_types: [],
      extensions: [],
    });
    consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    consoleErrorSpy.mockRestore();
    vi.clearAllMocks();
  });

  it("shows validation error when text is empty", async () => {
    mockGetAuthToken.mockResolvedValue("token-abc");

    render(<Home />);
    await act(async () => {
      await userEvent.click(screen.getByRole("button", { name: /get auth token/i }));
    });
    expect(await screen.findByText(/authenticated/i)).toBeInTheDocument();

    const translateButton = screen.getByRole("button", { name: /^translate$/i });
    await act(async () => {
      await userEvent.click(translateButton);
    });
    expect(await screen.findByText(/please enter text to translate/i)).toBeInTheDocument();
  });

  it("streams translation increments text", async () => {
    mockGetAuthToken.mockResolvedValue("token-123");
    mockTranslateStream.mockImplementation(() => mockGenerator(["Hallo", " Welt"]));

    render(<Home />);

    await act(async () => {
      await userEvent.click(screen.getByRole("button", { name: /get auth token/i }));
    });
    expect(await screen.findByText(/authenticated/i)).toBeInTheDocument();

    const textarea = screen.getByPlaceholderText(/enter text/i);
    await act(async () => {
      await userEvent.type(textarea, "Hello");
    });

    const translateButton = screen.getByRole("button", { name: /^translate$/i });
    await act(async () => {
      await userEvent.click(translateButton);
    });

    await waitFor(() => {
      expect(screen.getByText(/Hallo Welt/)).toBeInTheDocument();
    });

    expect(mockTranslateStream).toHaveBeenCalledWith(
      expect.objectContaining({ text: "Hello", target_lang: "de" }),
      "token-123",
    );
  });

  it("handles token retrieval error", async () => {
    mockGetAuthToken.mockRejectedValue(new Error("network down"));

    render(<Home />);
    await act(async () => {
      await userEvent.click(screen.getByRole("button", { name: /get auth token/i }));
    });

    expect(await screen.findByText(/failed to get auth token/i)).toBeInTheDocument();
  });

  it("handles voice file upload and surfaces metadata", async () => {
    mockGetVoiceFormats.mockResolvedValueOnce({
      mime_types: ["audio/opus", "audio/webm"],
      extensions: ["opus", "webm"],
    });
    mockGetAuthToken.mockResolvedValue("token-voice");
    mockVoiceTranslate.mockResolvedValue({
      transcription: "Hallo Welt",
      detected_lang: "de",
      confidence: 0.65,
      translations: {
        ru: "Привет мир",
        en: "Hello world",
        de: "Hallo Welt",
      },
      metadata: {
        audio_duration_s: 3.2,
        transcription_latency_ms: 430,
        translation_latency_ms: 780,
      },
    });

    render(<Home />);

    await act(async () => {
      await userEvent.click(screen.getByRole("button", { name: /get auth token/i }));
    });

    const fileInput = screen.getByLabelText(/upload audio file/i);
    await waitFor(() => {
      const acceptAttr = fileInput.getAttribute("accept") ?? "";
      expect(acceptAttr.split(",")).toEqual(expect.arrayContaining(["audio/opus", ".opus"]));
    });
    const file = new File([new Uint8Array([1, 2, 3])], "sample.opus", {
      type: "audio/opus",
    });

    await act(async () => {
      await userEvent.upload(fileInput, file);
    });

    await waitFor(() => {
      expect(mockVoiceTranslate).toHaveBeenCalledWith(expect.any(File), "token-voice", ["de"]);
    });

    expect(await screen.findByText(/voice translation ready/i)).toBeInTheDocument();
    const detectedRow = screen.getByText(/detected language:/i).parentElement;
    expect(detectedRow).toHaveTextContent(/de/i);
    expect(detectedRow).toHaveTextContent(/confidence 65%/i);
    const translationLatencyRow = screen.getByText(/translation latency/i).parentElement;
    expect(translationLatencyRow).toHaveTextContent("0.78s");
    const audioDurationRow = screen.getByText(/audio duration/i).parentElement;
    expect(audioDurationRow).toHaveTextContent("3.2s");
    expect(screen.getByDisplayValue("Hallo Welt")).toBeInTheDocument();
  });

  it("shows error state when voice translation fails", async () => {
    mockGetAuthToken.mockResolvedValue("token-voice");
    mockVoiceTranslate.mockRejectedValue(new Error("service down"));

    render(<Home />);

    await act(async () => {
      await userEvent.click(screen.getByRole("button", { name: /get auth token/i }));
    });

    const fileInput = screen.getByLabelText(/upload audio file/i);
    const file = new File([new Uint8Array([1, 2, 3])], "sample.webm", {
      type: "audio/webm",
    });

    await act(async () => {
      await userEvent.upload(fileInput, file);
    });

    expect(await screen.findByText(/voice translation failed/i)).toBeInTheDocument();
    expect(consoleErrorSpy).toHaveBeenCalled();
  });

  it("rejects unsupported audio format before upload", async () => {
    mockGetAuthToken.mockResolvedValue("token-voice");

    render(<Home />);

    await act(async () => {
      await userEvent.click(screen.getByRole("button", { name: /get auth token/i }));
    });

    const fileInput = screen.getByLabelText(/upload audio file/i);
    const file = new File([new Uint8Array([9, 9, 9])], "note.pdf", {
      type: "application/pdf",
    });

    fileInput.setAttribute("accept", "");
    await act(async () => {
      await userEvent.upload(fileInput, file);
    });

    await waitFor(() => {
      expect(mockVoiceTranslate).not.toHaveBeenCalled();
    });
    expect(await screen.findByTestId("voice-error")).toHaveTextContent(/unsupported audio format/i);
  });

  it("records audio via MediaRecorder and sends chunk", async () => {
    const originalMediaRecorder = (globalThis as any).MediaRecorder;
    const originalMediaDevices = navigator.mediaDevices;

    const stopTrack = vi.fn();
    const fakeStream = {
      getTracks: () => [{ stop: stopTrack }],
    } as unknown as MediaStream;

    const handlers: Record<string, Array<(event: any) => void>> = {};

    class FakeMediaRecorder {
      public state: "inactive" | "recording" = "inactive";
      addEventListener(type: string, handler: (event: any) => void) {
        handlers[type] = handlers[type] || [];
        handlers[type].push(handler);
      }
      start() {
        this.state = "recording";
      }
      stop() {
        this.state = "inactive";
        const blob = new Blob([new Uint8Array([1, 2, 3])], { type: "audio/webm" });
        handlers["dataavailable"]?.forEach((cb) => cb({ data: blob }));
        handlers["stop"]?.forEach((cb) => cb({}));
      }
    }

    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: {
        getUserMedia: vi.fn().mockResolvedValue(fakeStream),
      },
    });
    (globalThis as any).MediaRecorder = FakeMediaRecorder;

    mockGetAuthToken.mockResolvedValue("token-media");
    mockVoiceTranslate.mockResolvedValue({
      transcription: "Captured audio",
      detected_lang: "en",
      confidence: 0.9,
      translations: { de: "Erfasster Ton" },
      metadata: {
        audio_duration_s: 1.2,
        transcription_latency_ms: 120,
        translation_latency_ms: 210,
      },
    });

    try {
      render(<Home />);

      await act(async () => {
        await userEvent.click(screen.getByRole("button", { name: /get auth token/i }));
      });

      await act(async () => {
        await userEvent.click(screen.getByRole("button", { name: /start recording/i }));
      });

      const recordingTexts = await screen.findAllByText(/recording/i);
      expect(recordingTexts.length).toBeGreaterThan(0);

      await act(async () => {
        await userEvent.click(screen.getByRole("button", { name: /stop & translate/i }));
      });

      await waitFor(() => {
        expect(mockVoiceTranslate).toHaveBeenCalledWith(expect.any(File), "token-media", ["de"]);
      });

      expect(stopTrack).toHaveBeenCalled();
      expect(screen.getByText(/voice translation ready/i)).toBeInTheDocument();
      expect(screen.getByDisplayValue("Captured audio")).toBeInTheDocument();
    } finally {
      Object.defineProperty(navigator, "mediaDevices", {
        configurable: true,
        value: originalMediaDevices,
      });
      (globalThis as any).MediaRecorder = originalMediaRecorder;
    }
  });
});
