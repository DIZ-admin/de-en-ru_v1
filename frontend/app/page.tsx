"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  getAuthToken,
  translateTextStream,
  voiceTranslate,
  getVoiceFormats,
  type TranslationRequest,
  type VoiceTranslationResponse,
} from "@/lib/api";

type VoiceMetrics = {
  audioDuration: number | null;
  transcriptionLatencyMs: number;
  translationLatencyMs: number;
};

const rawVoiceDuration = Number(process.env.NEXT_PUBLIC_VOICE_MAX_DURATION ?? "60");
const VOICE_MAX_DURATION = Number.isFinite(rawVoiceDuration) && rawVoiceDuration > 0 ? rawVoiceDuration : 60;
const CONFIDENCE_THRESHOLD = 0.7;
const DEFAULT_ALLOWED_AUDIO_TYPES = [
  "audio/webm",
  "video/webm",
  "audio/ogg",
  "application/ogg",
  "audio/oga",
  "audio/mpeg",
  "audio/mpga",
  "audio/mp4",
  "audio/mp4a-latm",
  "audio/x-m4a",
  "video/mp4",
  "audio/wav",
  "audio/x-wav",
  "audio/flac",
  "audio/x-flac",
  "video/mpeg",
];
const DEFAULT_ALLOWED_EXTENSIONS = [
  "webm",
  "ogg",
  "oga",
  "m4a",
  "mp4",
  "mp3",
  "mpga",
  "wav",
  "flac",
  "mpeg",
];

const readEnvMimeTypes = (): string[] => {
  const raw = process.env.NEXT_PUBLIC_ALLOWED_AUDIO_TYPES;
  if (!raw) {
    return DEFAULT_ALLOWED_AUDIO_TYPES;
  }
  try {
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) {
      return parsed.filter((item): item is string => typeof item === "string");
    }
  } catch (err) {
    console.warn("Failed to parse NEXT_PUBLIC_ALLOWED_AUDIO_TYPES:", err);
  }
  return DEFAULT_ALLOWED_AUDIO_TYPES;
};

const readEnvExtensions = (): string[] => {
  const raw = process.env.NEXT_PUBLIC_ALLOWED_AUDIO_EXTENSIONS;
  if (!raw) {
    return DEFAULT_ALLOWED_EXTENSIONS;
  }
  try {
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) {
      return parsed.filter((item): item is string => typeof item === "string");
    }
  } catch (err) {
    console.warn("Failed to parse NEXT_PUBLIC_ALLOWED_AUDIO_EXTENSIONS:", err);
  }
  return DEFAULT_ALLOWED_EXTENSIONS;
};

const normalizeMimeTypes = (values: string[]): string[] =>
  values.map((value) => value.toLowerCase()).filter((value) => value.length > 0);

const normalizeExtensions = (values: string[]): string[] =>
  values
    .map((value) => value.replace(/^[.]/, "").toLowerCase())
    .filter((value) => value.length > 0);

const getFileExtension = (fileName: string | undefined | null): string | null => {
  if (!fileName || !fileName.includes(".")) return null;
  const [, ext] = /.+\.([^.]+)$/.exec(fileName) ?? [];
  return ext ? ext.toLowerCase() : null;
};

export default function Home() {
  const [token, setToken] = useState("");
  const [text, setText] = useState("");
  const [targetLang, setTargetLang] = useState<"ru" | "en" | "de">("de");
  const [translation, setTranslation] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  const [isRecording, setIsRecording] = useState(false);
  const [isVoiceProcessing, setIsVoiceProcessing] = useState(false);
  const [voiceStatus, setVoiceStatus] = useState<string>("");
  const [voiceDetectedLang, setVoiceDetectedLang] = useState<string | null>(null);
  const [voiceConfidence, setVoiceConfidence] = useState<number | null>(null);
  const [voiceTranscription, setVoiceTranscription] = useState<string>("");
  const [voiceMetrics, setVoiceMetrics] = useState<VoiceMetrics | null>(null);
  const [voiceError, setVoiceError] = useState<string>("");
  const [allowedMimeTypes, setAllowedMimeTypes] = useState<string[]>(() => normalizeMimeTypes(readEnvMimeTypes()));
  const [allowedExtensions, setAllowedExtensions] = useState<string[]>(() => normalizeExtensions(readEnvExtensions()));
  const [supportsMediaRecorder, setSupportsMediaRecorder] = useState<boolean>(false);

  const allowedMimeTypeSet = useMemo(() => new Set(allowedMimeTypes), [allowedMimeTypes]);
  const allowedExtensionSet = useMemo(() => new Set(allowedExtensions), [allowedExtensions]);
  const supportedFormatsLabel = useMemo(() => {
    const unique = Array.from(new Set(allowedExtensions));
    return unique.length ? unique : DEFAULT_ALLOWED_EXTENSIONS;
  }, [allowedExtensions]);
  const acceptAttribute = useMemo(() => {
    const values = [
      ...allowedMimeTypes,
      ...supportedFormatsLabel.map((extension) => `.${extension}`),
    ];
    return Array.from(new Set(values)).join(",");
  }, [allowedMimeTypes, supportedFormatsLabel]);
  const unsupportedMessage = useMemo(
    () => `Unsupported audio format. Supported formats: ${supportedFormatsLabel.join(", ")}`,
    [supportedFormatsLabel],
  );

  const isAllowedAudioFile = (file: File): boolean => {
    const type = (file.type ?? "").toLowerCase();
    if (type && allowedMimeTypeSet.has(type)) {
      return true;
    }

    const extension = getFileExtension(file.name);
    if (extension && allowedExtensionSet.has(extension)) {
      return true;
    }

    return false;
  };

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const recordingTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (typeof navigator !== "undefined" && navigator.mediaDevices) {
      setSupportsMediaRecorder(typeof navigator.mediaDevices.getUserMedia === "function");
    }

    return () => {
      if (recordingTimerRef.current) {
        clearTimeout(recordingTimerRef.current);
        recordingTimerRef.current = null;
      }

      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
        mediaRecorderRef.current.stop();
      }

      streamRef.current?.getTracks().forEach((track) => track.stop());
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    getVoiceFormats()
      .then((formats) => {
        if (cancelled) return;
        if (Array.isArray(formats?.mime_types) && formats.mime_types.length) {
          setAllowedMimeTypes(normalizeMimeTypes(formats.mime_types));
        }
        if (Array.isArray(formats?.extensions) && formats.extensions.length) {
          setAllowedExtensions(normalizeExtensions(formats.extensions));
        }
      })
      .catch((err) => {
        console.warn("Failed to load voice formats", err);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const handleGetToken = async () => {
    try {
      const newToken = await getAuthToken();
      setToken(newToken);
      setError("");
    } catch (err) {
      setError("Failed to get auth token");
      console.error(err);
    }
  };

  const ensureTokenOrError = async () => {
    if (token) return token;
    try {
      const newToken = await getAuthToken();
      setToken(newToken);
      setError("");
      return newToken;
    } catch (err) {
      setError("Failed to get auth token");
      throw err;
    }
  };

  const handleTranslate = async () => {
    if (!token) {
      setError("Please get auth token first");
      return;
    }

    if (!text.trim()) {
      setError("Please enter text to translate");
      return;
    }

    setIsLoading(true);
    setError("");
    setTranslation("");

    try {
      const request: TranslationRequest = {
        text,
        source_lang: "auto",
        target_lang: targetLang,
      };

      for await (const chunk of translateTextStream(request, token)) {
        setTranslation((prev) => prev + chunk);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Translation failed");
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  const stopStream = () => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  };

  const clearRecordingTimer = () => {
    if (recordingTimerRef.current) {
      clearTimeout(recordingTimerRef.current);
      recordingTimerRef.current = null;
    }
  };

  const handleStartRecording = async () => {
    try {
      const currentToken = await ensureTokenOrError();
      if (!currentToken) return;

      if (!supportsMediaRecorder || typeof navigator === "undefined") {
        setError("Microphone access is not supported in this browser");
        return;
      }

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];

      recorder.addEventListener("dataavailable", (event) => {
        if (event.data?.size) {
          chunksRef.current.push(event.data);
        }
      });

      recorder.addEventListener("stop", async () => {
        await handleProcessVoiceChunks();
      });

      mediaRecorderRef.current = recorder;
      recorder.start();
      setIsRecording(true);
      setVoiceStatus(`Recording... (max ${VOICE_MAX_DURATION} seconds)`);
      setVoiceTranscription("");
      setVoiceDetectedLang(null);
      setVoiceConfidence(null);
      setVoiceMetrics(null);
      setError("");
      setVoiceError("");

      clearRecordingTimer();
      if (VOICE_MAX_DURATION > 0) {
        recordingTimerRef.current = setTimeout(() => {
          setVoiceStatus("Max duration reached. Finishing recording...");
          void handleStopRecording();
        }, VOICE_MAX_DURATION * 1000);
      }
    } catch (err) {
      console.error(err);
      setError("Unable to access microphone");
      stopStream();
      setIsRecording(false);
    }
  };

  const handleStopRecording = () => {
    if (!mediaRecorderRef.current) {
      return;
    }
    clearRecordingTimer();
    setIsRecording(false);
    setIsVoiceProcessing(true);
    setVoiceError("");
    setVoiceStatus("Processing audio...");
    mediaRecorderRef.current.stop();
    stopStream();
  };

  const handleProcessVoiceChunks = async () => {
    if (!chunksRef.current.length) {
      setError("No audio recorded");
      setIsVoiceProcessing(false);
      setVoiceStatus("");
      return;
    }

    try {
      const blob = new Blob(chunksRef.current, { type: "audio/webm" });
      const file = new File([blob], `voice-${Date.now()}.webm`, {
        type: blob.type || "audio/webm",
      });
      await submitVoiceFile(file);
    } finally {
      chunksRef.current = [];
      setIsVoiceProcessing(false);
    }
  };

  const handleVoiceFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    if (!isAllowedAudioFile(file)) {
      setVoiceStatus(unsupportedMessage);
      setError(unsupportedMessage);
      setVoiceError(unsupportedMessage);
      setVoiceTranscription("");
      setVoiceDetectedLang(null);
      setVoiceConfidence(null);
      setVoiceMetrics(null);
      event.target.value = "";
      return;
    }
    setIsVoiceProcessing(true);
    try {
      await submitVoiceFile(file);
    } finally {
      event.target.value = "";
      setIsVoiceProcessing(false);
    }
  };

  const submitVoiceFile = async (file: File) => {
    if (!isAllowedAudioFile(file)) {
      setVoiceStatus(unsupportedMessage);
      setError(unsupportedMessage);
      setVoiceError(unsupportedMessage);
      setVoiceTranscription("");
      setVoiceDetectedLang(null);
      setVoiceConfidence(null);
      setVoiceMetrics(null);
      return;
    }

    try {
      const currentToken = await ensureTokenOrError();
      setVoiceStatus("Uploading audio...");
      const response: VoiceTranslationResponse = await voiceTranslate(file, currentToken, [targetLang]);

      const lowConfidence = typeof response.confidence === "number" && response.confidence < CONFIDENCE_THRESHOLD;
      setVoiceStatus(lowConfidence ? "Voice translation ready (low confidence detection)" : "Voice translation ready");
      setVoiceError("");
      setVoiceDetectedLang(response.detected_lang ?? "unknown");
      setVoiceConfidence(response.confidence ?? null);
      setVoiceTranscription(response.transcription);
      setVoiceMetrics({
        audioDuration: response.metadata.audio_duration_s,
        transcriptionLatencyMs: response.metadata.transcription_latency_ms,
        translationLatencyMs: response.metadata.translation_latency_ms,
      });

      const translated = response.translations[targetLang];
      if (translated) {
        setTranslation(translated);
      }
      setText(response.transcription);
      setError("");
    } catch (err) {
      console.error(err);
      setError(err instanceof Error ? err.message : "Voice translation failed");
      setVoiceStatus("Voice translation failed");
      setVoiceError(err instanceof Error ? err.message : "Voice translation failed");
      setVoiceTranscription("");
      setVoiceDetectedLang(null);
      setVoiceConfidence(null);
      setVoiceMetrics(null);
    }
  };

  return (
    <div className="min-h-screen p-8 pb-20 sm:p-20">
      <main className="max-w-4xl mx-auto space-y-6">
        <header className="text-center space-y-2">
          <h1 className="text-4xl font-bold">Trilingual Translator</h1>
          <p className="text-gray-600">OpenAI-First approach • Minimal code • Maximum delegation</p>
        </header>

        {/* Auth Token */}
        <section className="p-4 bg-white rounded-lg shadow">
          {!token ? (
            <button
              onClick={handleGetToken}
              className="w-full bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600"
            >
              Get Auth Token
            </button>
          ) : (
            <div className="text-sm text-green-600">✓ Authenticated</div>
          )}
        </section>

        {/* Text Translation */}
        <section className="bg-white rounded-lg shadow p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium mb-2">Text to translate</label>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Enter text in Russian, English, or German..."
              className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              rows={4}
              disabled={!token}
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">Target language</label>
            <select
              value={targetLang}
              onChange={(e) => setTargetLang(e.target.value as "ru" | "en" | "de")}
              className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              disabled={!token}
            >
              <option value="ru">Russian (Русский)</option>
              <option value="en">English</option>
              <option value="de">German (Deutsch)</option>
            </select>
          </div>

          <button
            onClick={handleTranslate}
            disabled={!token || isLoading}
            className="w-full bg-blue-500 text-white px-6 py-3 rounded-lg hover:bg-blue-600 disabled:bg-gray-300 disabled:cursor-not-allowed"
          >
            {isLoading ? "Translating..." : "Translate"}
          </button>

          {error && (
            <div className="p-3 bg-red-50 text-red-600 rounded-lg">{error}</div>
          )}
        </section>

        {/* Voice Translation */}
        <section className="bg-white rounded-lg shadow p-6 space-y-4">
          <h2 className="text-lg font-semibold">Voice Translation</h2>
          <p className="text-sm text-gray-600">
            Record up to {VOICE_MAX_DURATION} seconds of audio. Supported formats: {supportedFormatsLabel.join(", ")}.
          </p>

          <div className="flex flex-col sm:flex-row gap-3">
            <button
              onClick={handleStartRecording}
              disabled={!token || isRecording || isVoiceProcessing || !supportsMediaRecorder}
              className="flex-1 bg-purple-500 text-white px-4 py-2 rounded hover:bg-purple-600 disabled:bg-gray-300 disabled:cursor-not-allowed"
            >
              {isRecording ? "Recording..." : "Start Recording"}
            </button>
            <button
              onClick={handleStopRecording}
              disabled={!isRecording}
              className="flex-1 bg-purple-700 text-white px-4 py-2 rounded hover:bg-purple-800 disabled:bg-gray-300 disabled:cursor-not-allowed"
            >
              Stop & Translate
            </button>
          </div>

          <div className="text-sm text-gray-500" data-testid="voice-status">
            {voiceStatus}
            {isVoiceProcessing && <span className="ml-2 text-purple-600">Processing...</span>}
          </div>
          {voiceError && (
            <div className="text-sm text-red-600" data-testid="voice-error">
              {voiceError}
            </div>
          )}

          <div className="text-sm text-gray-600">
            <label className="block font-medium mb-1" htmlFor="voice-upload">
              Upload audio file (fallback)
            </label>
            <input
              id="voice-upload"
              name="voice-upload"
              type="file"
              accept={acceptAttribute}
              onChange={handleVoiceFileUpload}
              className="w-full text-sm"
            />
          </div>

          {voiceTranscription && (
            <div className="bg-gray-50 rounded border border-gray-200 p-4 space-y-2">
              <div className="text-sm text-gray-700">
                <span className="font-medium">Detected language:</span> {voiceDetectedLang ?? "unknown"}
                {voiceConfidence != null && (
                  <span className="text-gray-500"> (confidence {(voiceConfidence * 100).toFixed(0)}%)</span>
                )}
              </div>
              <div className="text-sm">
                <span className="font-medium">Transcription:</span>
                <div className="mt-1 text-gray-700">{voiceTranscription}</div>
              </div>
              {voiceMetrics && (
                <div className="text-xs text-gray-500 grid grid-cols-1 sm:grid-cols-3 gap-2 pt-2 border-t border-gray-200 mt-3">
                  <div>
                    <span className="font-medium">Audio duration:</span> {voiceMetrics.audioDuration != null ? `${voiceMetrics.audioDuration.toFixed(1)}s` : "—"}
                  </div>
                  <div>
                    <span className="font-medium">Transcription latency:</span> {(voiceMetrics.transcriptionLatencyMs / 1000).toFixed(2)}s
                  </div>
                  <div>
                    <span className="font-medium">Translation latency:</span> {(voiceMetrics.translationLatencyMs / 1000).toFixed(2)}s
                  </div>
                </div>
              )}
            </div>
          )}
        </section>

        {/* Translation Result */}
        {translation && (
          <section className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold mb-3">Translation:</h2>
            <div className="p-4 bg-gray-50 rounded border border-gray-200">{translation}</div>
          </section>
        )}

        <footer className="text-center text-sm text-gray-500 space-y-1 pt-4">
          <p>Powered by OpenAI Responses API (gpt-4.1-nano)</p>
          <p>Backend: ~500 LoC • Frontend: ~200 LoC • Dependencies: 10 total</p>
          <p className="text-gray-400">Voice translation with automatic language detection</p>
        </footer>
      </main>
    </div>
  );
}
