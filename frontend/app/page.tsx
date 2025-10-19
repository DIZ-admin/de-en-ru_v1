"use client";

import React, { useState } from "react";
import { getAuthToken, translateTextStream, type TranslationRequest } from "@/lib/api";

export default function Home() {
  const [token, setToken] = useState("");
  const [text, setText] = useState("");
  const [targetLang, setTargetLang] = useState<"ru" | "en" | "de">("de");
  const [translation, setTranslation] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  // Get auth token on mount
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

  // Translate with streaming
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

      // Stream translation
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

  return (
    <div className="min-h-screen p-8 pb-20 sm:p-20">
      <main className="max-w-4xl mx-auto">
        <h1 className="text-4xl font-bold text-center mb-8">
          Trilingual Translator
        </h1>
        <p className="text-center text-gray-600 mb-8">
          OpenAI-First approach • Minimal code • Maximum delegation
        </p>

        {/* Auth Token */}
        <div className="mb-6 p-4 bg-white rounded-lg shadow">
          {!token ? (
            <button
              onClick={handleGetToken}
              className="w-full bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600"
            >
              Get Auth Token
            </button>
          ) : (
            <div className="text-sm text-green-600">
              ✓ Authenticated
            </div>
          )}
        </div>

        {/* Translation Form */}
        <div className="bg-white rounded-lg shadow p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium mb-2">
              Text to translate
            </label>
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
            <label className="block text-sm font-medium mb-2">
              Target language
            </label>
            <select
              value={targetLang}
              onChange={(e) => setTargetLang(e.target.value as any)}
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
            <div className="p-3 bg-red-50 text-red-600 rounded-lg">
              {error}
            </div>
          )}
        </div>

        {/* Translation Result */}
        {translation && (
          <div className="mt-6 bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold mb-3">Translation:</h2>
            <div className="p-4 bg-gray-50 rounded border border-gray-200">
              {translation}
            </div>
          </div>
        )}

        {/* Info */}
        <div className="mt-8 text-center text-sm text-gray-500">
          <p>Powered by OpenAI Responses API (gpt-4.1-nano)</p>
          <p className="mt-2">
            Backend: ~500 LoC • Frontend: ~200 LoC • Dependencies: 10 total
          </p>
        </div>
      </main>
    </div>
  );
}
