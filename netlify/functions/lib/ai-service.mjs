/**
 * Provider-agnostic AI service with automatic failover.
 *
 * Tries providers in priority order (env: AI_PROVIDER_PRIORITY, default: gemini,groq).
 * Each provider has a ranked model list — if a model is deprecated, the next is tried.
 *
 * Exports:
 *   generateAI(systemPrompt, userPrompt) → Promise<string>
 *   getAvailableProviders()              → string[]
 */

import { GoogleGenAI } from "@google/genai";
import Groq from "groq-sdk";
import OpenAI from "openai";

// ── Configuration ──────────────────────────────────────────────

const GEMINI_API_KEY = process.env.GEMINI_API_KEY || "";
const GROQ_API_KEY = process.env.GROQ_API_KEY || "";
const OPENAI_API_KEY = process.env.OPENAI_API_KEY || "";

const AI_PROVIDER_PRIORITY = (
  process.env.AI_PROVIDER_PRIORITY || "gemini,groq"
)
  .split(",")
  .map((s) => s.trim().toLowerCase())
  .filter(Boolean);

const AI_CALL_TIMEOUT = parseInt(process.env.AI_CALL_TIMEOUT || "60", 10) * 1000; // ms

// ── Model fallback lists (newest → oldest) ─────────────────────

const GEMINI_FALLBACK_MODELS = [
  "gemini-2.0-flash",
  "gemini-2.0-flash-lite",
  "gemini-1.5-flash",
  "gemini-1.5-flash-8b",
];

const GROQ_FALLBACK_MODELS = [
  "llama-3.3-70b-versatile",
  "llama-3.1-8b-instant",
  "llama3-70b-8192",
  "llama3-8b-8192",
  "mixtral-8x7b-32768",
];

const OPENAI_FALLBACK_MODELS = [
  "gpt-4o-mini",
  "gpt-4o",
  "gpt-4-turbo",
  "gpt-3.5-turbo",
];

/**
 * Build model list with optional env-var override placed first.
 */
function buildModelList(fallbackModels, envVar) {
  const override = (process.env[envVar] || "").trim();
  const models = [...fallbackModels];
  if (override) {
    const idx = models.indexOf(override);
    if (idx !== -1) models.splice(idx, 1);
    models.unshift(override);
  }
  return models;
}

/**
 * Check if an error indicates the model doesn't exist / is deprecated.
 */
function isModelNotFound(err) {
  const msg = (err.message || String(err)).toLowerCase();
  return ["not found", "not exist", "deprecated", "decommissioned", "unavailable", "invalid model"].some(
    (kw) => msg.includes(kw)
  );
}

// ── Provider implementations ───────────────────────────────────

async function callGemini(systemPrompt, userPrompt) {
  if (!GEMINI_API_KEY) throw new Error("Gemini API key not configured");

  const client = new GoogleGenAI({ apiKey: GEMINI_API_KEY });
  const models = buildModelList(GEMINI_FALLBACK_MODELS, "GEMINI_MODEL");

  for (let i = 0; i < models.length; i++) {
    const model = models[i];
    try {
      console.log(`Gemini: trying model '${model}'`);
      const response = await client.models.generateContent({
        model,
        contents: userPrompt,
        config: {
          systemInstruction: systemPrompt,
          temperature: 0.7,
          maxOutputTokens: 2048,
        },
      });

      const text = response?.text;
      if (text) {
        console.log(`Gemini: success with model '${model}'`);
        return text;
      }
      throw new Error("Gemini returned empty response");
    } catch (err) {
      if (isModelNotFound(err) && i < models.length - 1) {
        console.warn(`Gemini: model '${model}' unavailable (${err.message}) — trying next...`);
        continue;
      }
      throw err;
    }
  }
  throw new Error("Gemini: all fallback models exhausted");
}

async function callGroq(systemPrompt, userPrompt) {
  if (!GROQ_API_KEY) throw new Error("Groq API key not configured");

  const client = new Groq({ apiKey: GROQ_API_KEY });
  const models = buildModelList(GROQ_FALLBACK_MODELS, "GROQ_MODEL");

  for (let i = 0; i < models.length; i++) {
    const model = models[i];
    try {
      console.log(`Groq: trying model '${model}'`);
      const response = await client.chat.completions.create({
        model,
        messages: [
          { role: "system", content: systemPrompt },
          { role: "user", content: userPrompt },
        ],
        temperature: 0.7,
        max_tokens: 2048,
      });

      const content = response.choices?.[0]?.message?.content;
      if (content) {
        console.log(`Groq: success with model '${model}'`);
        return content;
      }
      throw new Error("Groq returned empty response");
    } catch (err) {
      if (isModelNotFound(err) && i < models.length - 1) {
        console.warn(`Groq: model '${model}' unavailable (${err.message}) — trying next...`);
        continue;
      }
      throw err;
    }
  }
  throw new Error("Groq: all fallback models exhausted");
}

async function callOpenAI(systemPrompt, userPrompt) {
  if (!OPENAI_API_KEY) throw new Error("OpenAI API key not configured");

  const client = new OpenAI({ apiKey: OPENAI_API_KEY });
  const models = buildModelList(OPENAI_FALLBACK_MODELS, "OPENAI_MODEL");

  for (let i = 0; i < models.length; i++) {
    const model = models[i];
    try {
      console.log(`OpenAI: trying model '${model}'`);
      const response = await client.chat.completions.create({
        model,
        messages: [
          { role: "system", content: systemPrompt },
          { role: "user", content: userPrompt },
        ],
        temperature: 0.7,
        max_tokens: 2048,
      });

      const content = response.choices?.[0]?.message?.content;
      if (content) {
        console.log(`OpenAI: success with model '${model}'`);
        return content;
      }
      throw new Error("OpenAI returned empty response");
    } catch (err) {
      if (isModelNotFound(err) && i < models.length - 1) {
        console.warn(`OpenAI: model '${model}' unavailable (${err.message}) — trying next...`);
        continue;
      }
      throw err;
    }
  }
  throw new Error("OpenAI: all fallback models exhausted");
}

// ── Provider registry ──────────────────────────────────────────

const PROVIDERS = {
  gemini: { call: callGemini, available: Boolean(GEMINI_API_KEY) },
  groq: { call: callGroq, available: Boolean(GROQ_API_KEY) },
  openai: { call: callOpenAI, available: Boolean(OPENAI_API_KEY) },
};

/**
 * Get the ordered list of available (configured) provider names.
 * @returns {string[]}
 */
export function getAvailableProviders() {
  return AI_PROVIDER_PRIORITY.filter(
    (name) => PROVIDERS[name]?.available
  );
}

/**
 * Helper: wrap a promise with a timeout.
 */
function withTimeout(promise, ms) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(
      () => reject(new Error(`Request timed out after ${ms / 1000}s`)),
      ms
    );
    promise.then(
      (val) => { clearTimeout(timer); resolve(val); },
      (err) => { clearTimeout(timer); reject(err); }
    );
  });
}

/**
 * Generate an AI response with automatic failover across providers.
 *
 * @param {string} systemPrompt - System/role instruction for the AI.
 * @param {string} userPrompt   - User message/data to analyze.
 * @returns {Promise<string>}   - AI-generated text response.
 * @throws {Error} If all providers fail.
 */
export async function generateAI(systemPrompt, userPrompt) {
  const available = getAvailableProviders();

  if (available.length === 0) {
    throw new Error(
      "No AI providers available. Set at least one API key (GEMINI_API_KEY or GROQ_API_KEY) in environment variables."
    );
  }

  const errors = [];

  for (const name of available) {
    const provider = PROVIDERS[name];
    try {
      console.log(`Trying AI provider: ${name}`);
      const response = await withTimeout(
        provider.call(systemPrompt, userPrompt),
        AI_CALL_TIMEOUT
      );
      console.log(`Successfully got response from ${name}`);
      return response;
    } catch (err) {
      const errorMsg = `${name}: ${err.message}`;
      console.warn(errorMsg);
      errors.push(errorMsg);
    }
  }

  throw new Error(`All AI providers failed. Errors: ${errors.join("; ")}`);
}
