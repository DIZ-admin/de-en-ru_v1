import http from "k6/http";
import { check, sleep } from "k6";
import { Trend, Counter } from "k6/metrics";

const BASE_URL = __ENV.API_URL || "http://localhost:8000";
const AUTH_USER = __ENV.API_USER || "load-test";
const AUDIO_FILE = __ENV.AUDIO_FILE || "sample.webm";
const TARGET_LANGS = __ENV.TARGET_LANGS || "ru,en,de";

const transcriptionLatency = new Trend("voice_transcription_latency", true);
const translationLatency = new Trend("voice_translation_latency", true);
const voiceErrors = new Counter("voice_errors");

export const options = {
  thresholds: {
    voice_transcription_latency: ["p(95)<2000"],
    voice_translation_latency: ["p(95)<2500"],
    voice_errors: ["count<50"],
  },
  stages: [
    { duration: "2m", target: 10 },
    { duration: "3m", target: 30 },
    { duration: "2m", target: 60 },
    { duration: "2m", target: 0 },
  ],
};

function getToken() {
  if (__ENV.API_TOKEN) {
    return __ENV.API_TOKEN;
  }
  const res = http.post(`${BASE_URL}/auth/token?user_id=${AUTH_USER}`);
  check(res, { "auth succeeded": (r) => r.status === 200 });
  return res.json("access_token");
}

const token = getToken();
const audioBytes = open(AUDIO_FILE, "b");

export default function () {
  const payload = {
    file: http.file(audioBytes, "sample.webm", "audio/webm"),
    target_langs: TARGET_LANGS,
  };

  const start = Date.now();
  const res = http.post(`${BASE_URL}/voice-translate`, payload, {
    headers: { Authorization: `Bearer ${token}` },
    timeout: "120s",
  });
  const totalLatency = Date.now() - start;

  const ok = check(res, {
    "voice translate success": (r) => r.status === 200,
  });

  if (ok) {
    const body = res.json();
    transcriptionLatency.add(body?.metadata?.transcription_latency_ms || 0);
    translationLatency.add(body?.metadata?.translation_latency_ms || 0);
  } else {
    voiceErrors.add(1);
  }

  sleep(1);
}
