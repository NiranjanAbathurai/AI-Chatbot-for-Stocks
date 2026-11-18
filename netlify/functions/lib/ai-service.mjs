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

import Anthropic from "@anthropic-ai/sdk";
import { GoogleGenAI } from "@google/genai";
import Groq from "groq-sdk";
import OpenAI from "openai";
import { getModels } from "./model-discovery.mjs";

// ── SSL Fix for corporate proxies ──────────────────────────────
// Corporate proxies (Zscaler) inject self-signed certificates.
// This disables strict TLS verification for local/dev environments.
if (!process.env.NODE_TLS_REJECT_UNAUTHORIZED) {
  process.env.NODE_TLS_REJECT_UNAUTHORIZED = "0";
}

// ── Configuration ──────────────────────────────────────────────

const ANTHROPIC_API_KEY = process.env.ANTHROPIC_API_KEY || "";
const ANTHROPIC_AUTH_TOKEN = process.env.ANTHROPIC_AUTH_TOKEN || "";
const ANTHROPIC_BASE_URL = process.env.ANTHROPIC_BASE_URL || "";
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

// Gateway models (corporate API gateways use simplified names without date suffixes)
const ANTHROPIC_GATEWAY_MODELS = [
  "claude-4.5-sonnet",
  "claude-4.5-haiku",
  "claude-4.6-sonnet",
  "claude-5-sonnet",
];

// Direct Anthropic API models (standard names with date suffixes)
const ANTHROPIC_DIRECT_MODELS = [
  "claude-sonnet-4-20250514",
  "claude-haiku-4-20250414",
  "claude-3-5-sonnet-20241022",
  "claude-3-5-haiku-20241022",
  "claude-3-haiku-20240307",
];

const ANTHROPIC_IS_GATEWAY = Boolean(
  ANTHROPIC_BASE_URL && !ANTHROPIC_BASE_URL.includes("anthropic.com")
);

const ANTHROPIC_FALLBACK_MODELS = ANTHROPIC_IS_GATEWAY
  ? ANTHROPIC_GATEWAY_MODELS
  : ANTHROPIC_DIRECT_MODELS;

const GEMINI_FALLBACK_MODELS = [
  "gemini-3.8-flash",
  "gemini-3.5-flash-lite",
  "gemini-2.5-flash",
  "gemini-2.0-flash",
];

const GROQ_FALLBACK_MODELS = [
  "llama-3.3-70b-versatile",
  "llama-3.2-90b-vision-preview",
  "llama-3.2-11b-vision-preview",
  "llama-3.1-70b-versatile",
  "llama-3.1-8b-instant",
];

const OPENAI_FALLBACK_MODELS = [
  "gpt-4o-mini",
  "gpt-4o",
  "gpt-4-turbo",
  "gpt-3.5-turbo",
];

/**
 * Build model list with optional env-var override placed first.
 * Uses auto-discovered models if available, falls back to hardcoded list.
 */
async function buildModelList(fallbackModels, envVar, provider) {
  const override = (process.env[envVar] || "").trim();

  // Try auto-discovered models first
  let discovered = [];
  try {
    discovered = await getModels(provider);
  } catch (e) {
    // Discovery failed — use fallbacks
  }

  const models = discovered.length > 0 ? [...discovered] : [...fallbackModels];
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
  return ["not found", "not exist", "deprecated", "decommissioned", "unavailable", "invalid model", "invalid_request_error"].some(
    (kw) => msg.includes(kw)
  ) || (err.status === 400 || err.status === 404);
}

// ── Provider implementations ───────────────────────────────────

async function callAnthropic(systemPrompt, userPrompt) {
  if (!ANTHROPIC_API_KEY && !ANTHROPIC_AUTH_TOKEN) {
    throw new Error("Anthropic API key not configured");
  }

  // Corporate gateways use ANTHROPIC_AUTH_TOKEN; direct API uses ANTHROPIC_API_KEY.
  // The SDK auto-detects ANTHROPIC_AUTH_TOKEN from env, but we pass it explicitly
  // to ensure it works in all environments.
  const clientOpts = {};
  if (ANTHROPIC_BASE_URL) {
    clientOpts.baseURL = ANTHROPIC_BASE_URL;
    console.log(`Anthropic: using base URL '${ANTHROPIC_BASE_URL}'`);
  }
  if (ANTHROPIC_IS_GATEWAY && ANTHROPIC_AUTH_TOKEN) {
    clientOpts.authToken = ANTHROPIC_AUTH_TOKEN;
    console.log("Anthropic: using auth token for corporate gateway");
  } else {
    clientOpts.apiKey = ANTHROPIC_API_KEY;
  }
  const client = new Anthropic(clientOpts);
  const models = await buildModelList(ANTHROPIC_FALLBACK_MODELS, "ANTHROPIC_MODEL", "anthropic");

  for (let i = 0; i < models.length; i++) {
    const model = models[i];
    try {
      console.log(`Anthropic: trying model '${model}'`);
      const response = await client.messages.create({
        model,
        max_tokens: 2048,
        system: systemPrompt,
        messages: [{ role: "user", content: userPrompt }],
      });

      // Extract text from content blocks
      let content = "";
      for (const block of response.content) {
        if (block.type === "text") content += block.text;
      }

      if (content) {
        console.log(`Anthropic: success with model '${model}'`);
        return content;
      }
      throw new Error("Anthropic returned empty response");
    } catch (err) {
      if (isModelNotFound(err) && i < models.length - 1) {
        console.warn(`Anthropic: model '${model}' unavailable (${err.message}) — trying next...`);
        continue;
      }
      throw err;
    }
  }
  throw new Error("Anthropic: all fallback models exhausted");
}

async function callGemini(systemPrompt, userPrompt) {
  if (!GEMINI_API_KEY) throw new Error("Gemini API key not configured");

  const client = new GoogleGenAI({ apiKey: GEMINI_API_KEY });
  const models = await buildModelList(GEMINI_FALLBACK_MODELS, "GEMINI_MODEL", "gemini");

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
  const models = await buildModelList(GROQ_FALLBACK_MODELS, "GROQ_MODEL", "groq");

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
  const models = await buildModelList(OPENAI_FALLBACK_MODELS, "OPENAI_MODEL", "openai");

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
  anthropic: { call: callAnthropic, available: Boolean(ANTHROPIC_API_KEY || ANTHROPIC_AUTH_TOKEN) },
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
      "No AI providers available. Set at least one API key (ANTHROPIC_API_KEY, GEMINI_API_KEY, or GROQ_API_KEY) in environment variables."
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
