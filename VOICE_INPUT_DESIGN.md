# Voice Input with Automatic Language Detection

## Goals

- Accept short voice snippets from the frontend and translate them into target languages supported by the app (RU/EN/DE).
- Detect the spoken language automatically so that users are not forced to choose it up front.
- Reuse existing synchronous/streaming translation flows with minimal duplication.
- Keep latency low (target < 3s end-to-end; first transcription < 1.5s).
- Provide observability for voice-specific metrics.

## Proposed Flow

```
Browser (MediaRecorder)
        |
        | audio/webm, opus
        v
POST /voice-translate (multipart/form-data)
        |
        +--> Validate audio (mime, duration<=60s, size<=5MB)
        +--> Store temp file in /tmp (or in-memory if small)
        |
        v
Speech-to-text (Whisper API via OpenAI Responses Audio)
        |
        +--> returns transcription text + detected language + confidence
        |
        v
Language routing
        |
        +--> if confidence >= threshold (e.g. 0.7) use detected_lang
        +--> else fallback to "auto" (translation pipeline will re-detect)
        |
        v
Translate (existing translate_with_cache / translate_text_stream)
        |
        v
Response
  {
    transcription: "...",
    detected_lang: "en",
    confidence: 0.86,
    translations: {
        en: "...",  // optional if source already en
        ru: "...",
        de: "..."
    },
    metadata: {
        transcription_latency_ms,
        translation_latency_ms,
        audio_duration_s
    }
  }
```

## Speech Recognition Strategy

| Option | Pros | Cons | Notes |
|--------|------|------|-------|
| **OpenAI Whisper API (Responses audio.transcriptions)** | Managed, high accuracy, language detection built-in | Requires API call per request, <5 MB per request limit | Recommended for MVP |
| Local Whisper (via faster-whisper) | No network latency, full control | Requires GPU/CPU resources, container-size blow-up | Consider later if needed |

**Chosen approach:** OpenAI Whisper API (`gpt-4o-mini-transcribe` or `whisper-1`) via `client.audio.transcriptions.create`. We receive `language` code (`"en"`, `"ru"`, `"de"`) and `confidence`.

## API Additions

- `POST /voice-translate`
  - `multipart/form-data`
    - `file`: audio file (`audio/webm`, `audio/ogg`, `audio/mpeg`, `audio/wav`)
    - `target_langs` (optional list, default: frontend defaults)
  - Rate limited similarly to text translate (share quotas; voice counts more weight, e.g. 1 request = 3 text requests).
  - Response (JSON):
    ```json
    {
      "transcription": "...",
      "detected_lang": "en",
      "confidence": 0.85,
      "translations": {
        "ru": "...",
        "de": "..."
      },
      "metadata": {
        "audio_duration_s": 12.4,
        "transcription_latency_ms": 450,
        "translation_latency_ms": 830
      }
    }
    ```
- Error handling:
  - 400 – unsupported media type / duration too long.
  - 413 – payload too large (>5 MB).
  - 429 – rate limit.
  - 502 – Whisper API failure (retry exhausted).

## Language Detection Logic

1. Whisper returns `language` and optionally `confidence`. If `confidence` is not provided, fallback to heuristics (`0.6`).
2. If `confidence >= 0.7`, treat `detected_lang` as authoritative (set `source_lang` for translation request).
3. Else send translation request with `source_lang="auto"` and include `detected_lang` as hint (for logging/metrics).
4. For target languages equal to `detected_lang`, optionally skip translation or include original text (configurable).

## Integration with Translation Pipeline

- Reuse `translate_with_cache` to benefit from existing caching (key includes `text` + `target_lang`).
- Add optional `source_lang_hint` parameter so translation can store metadata.
- For streaming UI, send SSE events after transcription; initial event can provide detected language before translation chunks arrive.

## Rate Limiting & Caching

- Extend existing rate limiter:
  - voice upload counts as `voice_weight` (default 3).
  - Redis key `rate_limit:{user_id}` unchanged, but `zadd` increments by weight.
- Cache:
  - Optionally store transcription text keyed by audio hash (MD5). Not MVP.

## Observability

Add Prometheus counters/histograms:

- `voice_requests_total{status="success|error"}`
- `voice_detected_language_total{lang="en|ru|de|unknown"}`
- `voice_transcription_latency_seconds` (Histogram)
- `voice_translation_latency_seconds`
- `voice_confidence_bucket` (Histogram)

## Documentation Updates

- README/SETUP: describe audio requirements, example `curl` command, env vars (`VOICE_MAX_DURATION`, `VOICE_MAX_SIZE_MB`, `OPENAI_WHISPER_MODEL`).
- ARCHITECTURE_OPENAI_FIRST.md: new voice swimlane (ASCII or PlantUML).
- API docs: add `voice-translate` request/response schemas.

## Open Questions

- Should we allow streaming microphone upload (`MediaRecorder` chunks) or only after recording stops? MVP uses upload after recording complete.
- How to handle languages outside RU/EN/DE? Option: allow detection but map to nearest supported or show warning.
- Persist transcription? Current plan: no, only return to client.
