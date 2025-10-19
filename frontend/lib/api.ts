/**
 * API Client - OpenAI-First approach
 * Minimal abstraction over fetch API
 */
import { SSEDecoder } from "./sse";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface TranslationRequest {
  text: string;
  source_lang: "ru" | "en" | "de" | "auto";
  target_lang: "ru" | "en" | "de";
}

export interface TranslationResponse {
  translated_text: string;
  detected_lang: string | null;
  model: string;
}

export interface VoiceTranslationResponse {
  transcription: string;
  detected_lang: string | null;
  confidence: number | null;
  translations: Record<string, string>;
  metadata: {
    audio_duration_s: number | null;
    transcription_latency_ms: number;
    translation_latency_ms: number;
  };
}

export interface VoiceFormats {
  mime_types: string[];
  extensions: string[];
}

/**
 * Get JWT token from backend
 */
export async function getAuthToken(userId: string = "demo-user"): Promise<string> {
  const response = await fetch(`${API_URL}/auth/token?user_id=${userId}`, {
    method: "POST",
  });

  if (!response.ok) {
    throw new Error("Failed to get auth token");
  }

  const data = await response.json();
  return data.access_token;
}

export async function voiceTranslate(
  file: File,
  token: string,
  targetLangs?: string[],
): Promise<VoiceTranslationResponse> {
  const formData = new FormData();
  formData.append("file", file);
  if (targetLangs && targetLangs.length > 0) {
    formData.append("target_langs", targetLangs.join(","));
  }

  const response = await fetch(`${API_URL}/voice-translate`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: formData,
  });

  if (!response.ok) {
    let detail: string | undefined;
    try {
      const error = await response.json();
      detail = error?.detail;
    } catch (err) {
      detail = undefined;
    }
    throw new Error(detail || "Voice translation failed");
  }

  return response.json();
}

export async function getVoiceFormats(): Promise<VoiceFormats> {
  const response = await fetch(`${API_URL}/voice/formats`);
  if (!response.ok) {
    throw new Error("Failed to load voice formats");
  }

  return response.json();
}

/**
 * Translate text (synchronous)
 */
export async function translateText(
  request: TranslationRequest,
  token: string
): Promise<TranslationResponse> {
  const response = await fetch(`${API_URL}/translate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Translation failed");
  }

  return response.json();
}

/**
 * Translate text (streaming with SSE)
 */
export async function* translateTextStream(
  request: TranslationRequest,
  token: string
): AsyncGenerator<string, void, unknown> {
  const response = await fetch(`${API_URL}/translate/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      Accept: "text/event-stream",
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error("Streaming translation failed");
  }

  const reader = response.body?.getReader();
  const decoder = new TextDecoder();
  const sseDecoder = new SSEDecoder();

  if (!reader) {
    throw new Error("No response body");
  }

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        const flushChunk = decoder.decode();
        for (const data of sseDecoder.push(flushChunk, { isFinal: true })) {
          yield data;
        }
        break;
      }

      const chunk = decoder.decode(value, { stream: true });
      for (const data of sseDecoder.push(chunk)) {
        yield data;
      }
    }
  } catch (error) {
    console.error("Streaming translation interrupted", error);
    throw new Error("Streaming connection interrupted. Please retry.");
  } finally {
    reader.releaseLock();
  }
}
