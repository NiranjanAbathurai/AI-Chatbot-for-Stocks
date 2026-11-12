/**
 * AI Service with provider failover: Gemini → OpenAI → Groq
 * API keys are read from Netlify environment variables.
 *
 * Models are auto-resolved: each provider has a ranked fallback list so that
 * when a model is deprecated / removed, the next one is tried automatically
 * — no redeployment needed.  You can also pin a model via env vars:
 *   GEMINI_MODEL, OPENAI_MODEL, GROQ_MODEL
 */

import { GoogleGenAI } from "@google/genai";
import OpenAI from "openai";
import Groq from "groq-sdk";

// ── Model fallback lists (newest / best free tier first) ────────────
// When a model 404s or errors with "model not found", the next one is tried.
// Updated Nov 2026 — older models may be deprecated.

const GEMINI_MODELS = [
  "gemini-2.5-flash",
  "gemini-2.5-pro",
  "gemini-2.0-flash",
  "gemini-2.0-flash-lite",
  "gemini-1.5-flash",
  "gemini-1.5-pro",
];

const OPENAI_MODELS = [
  "gpt-4o-mini",
  "gpt-4o",
  "gpt-4-turbo",
  "gpt-3.5-turbo",
];

const GROQ_MODELS = [
  "llama-3.3-70b-versatile",
  "llama-3.1-70b-versatile",
  "llama-3.1-8b-instant",
  "llama3-70b-8192",
  "llama3-8b-8192",
  "mixtral-8x7b-32768",
  "gemma2-9b-it",
];

/**
 * Return the model list for a provider, respecting an optional env-var override.
 * If the env var is set, that model is tried first, then the fallback list.
 */
function getModelList(providerName) {
  switch (providerName) {
    case "gemini": {
      const override = process.env.GEMINI_MODEL;
      const list = [...GEMINI_MODELS];
      if (override && !list.includes(override)) list.unshift(override);
      else if (override) {
        list.splice(list.indexOf(override), 1);
        list.unshift(override);
      }
      return list;
    }
    case "openai": {
      const override = process.env.OPENAI_MODEL;
      const list = [...OPENAI_MODELS];
      if (override && !list.includes(override)) list.unshift(override);
      else if (override) {
        list.splice(list.indexOf(override), 1);
        list.unshift(override);
      }
      return list;
    }
    case "groq": {
      const override = process.env.GROQ_MODEL;
      const list = [...GROQ_MODELS];
      if (override && !list.includes(override)) list.unshift(override);
      else if (override) {
        list.splice(list.indexOf(override), 1);
        list.unshift(override);
      }
      return list;
    }
    default:
      return [];
  }
}

/**
 * Check if an error indicates the model is not found / deprecated.
 */
function isModelNotFoundError(err) {
  const msg = (err.message || "").toLowerCase();
  const status = err.status || err.statusCode || (err.response && err.response.status);
  return (
    (msg.includes("model") &&
      (msg.includes("not found") ||
        msg.includes("not exist") ||
        msg.includes("deprecated") ||
        msg.includes("decommissioned") ||
        msg.includes("unavailable") ||
        msg.includes("invalid") ||
        msg.includes("does not exist"))) ||
    status === 404 ||
    err.code === "model_not_found" ||
    msg.includes("is not available") ||
    msg.includes("has been removed")
  );
}

// ── Provider-specific generators ────────────────────────────────────

/**
 * Get the ordered list of AI providers based on available keys.
 */
function getProviders() {
  const providers = [];
  const priority = (process.env.AI_PROVIDER_PRIORITY || "gemini,openai,groq").split(",");

  for (const name of priority) {
    const n = name.trim().toLowerCase();
    if (n === "gemini" && process.env.GEMINI_API_KEY) {
      providers.push({ name: "gemini", key: process.env.GEMINI_API_KEY });
    } else if (n === "openai" && process.env.OPENAI_API_KEY) {
      providers.push({ name: "openai", key: process.env.OPENAI_API_KEY });
    } else if (n === "groq" && process.env.GROQ_API_KEY) {
      providers.push({ name: "groq", key: process.env.GROQ_API_KEY });
    }
  }

  return providers;
}

/**
 * Generate text using Gemini — tries each model in the fallback list.
 */
async function generateGemini(apiKey, systemPrompt, userPrompt) {
  const ai = new GoogleGenAI({ apiKey });
  const models = getModelList("gemini");

  for (let i = 0; i < models.length; i++) {
    const model = models[i];
    try {
      console.log(`  Gemini: trying model "${model}"`);
      const response = await ai.models.generateContent({
        model,
        contents: userPrompt,
        config: {
          systemInstruction: systemPrompt,
          temperature: 0.7,
          maxOutputTokens: 2048,
        },
      });

      if (response && response.text) {
        console.log(`  Gemini: success with model "${model}"`);
        return response.text;
      }
      throw new Error("Gemini returned empty response");
    } catch (err) {
      if (isModelNotFoundError(err) && i < models.length - 1) {
        console.warn(`  Gemini: model "${model}" unavailable — trying next...`);
        continue;
      }
      throw err;
    }
  }

  throw new Error("Gemini: all models exhausted");
}

/**
 * Generate text using OpenAI — tries each model in the fallback list.
 */
async function generateOpenAI(apiKey, systemPrompt, userPrompt) {
  const client = new OpenAI({ apiKey });
  const models = getModelList("openai");

  for (let i = 0; i < models.length; i++) {
    const model = models[i];
    try {
      console.log(`  OpenAI: trying model "${model}"`);
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
        console.log(`  OpenAI: success with model "${model}"`);
        return content;
      }
      throw new Error("OpenAI returned empty response");
    } catch (err) {
      if (isModelNotFoundError(err) && i < models.length - 1) {
        console.warn(`  OpenAI: model "${model}" unavailable — trying next...`);
        continue;
      }
      throw err;
    }
  }

  throw new Error("OpenAI: all models exhausted");
}

/**
 * Generate text using Groq — tries each model in the fallback list.
 */
async function generateGroq(apiKey, systemPrompt, userPrompt) {
  const client = new Groq({ apiKey });
  const models = getModelList("groq");

  for (let i = 0; i < models.length; i++) {
    const model = models[i];
    try {
      console.log(`  Groq: trying model "${model}"`);
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
        console.log(`  Groq: success with model "${model}"`);
        return content;
      }
      throw new Error("Groq returned empty response");
    } catch (err) {
      if (isModelNotFoundError(err) && i < models.length - 1) {
        console.warn(`  Groq: model "${model}" unavailable — trying next...`);
        continue;
      }
      throw err;
    }
  }

  throw new Error("Groq: all models exhausted");
}

/**
 * Generate AI response with automatic failover across providers.
 * API keys come from Netlify environment variables.
 */
export async function generateAI(systemPrompt, userPrompt) {
  const providers = getProviders();
  const errors = [];

  if (providers.length === 0) {
    throw new Error(
      "No AI providers configured. Set GEMINI_API_KEY, OPENAI_API_KEY, or GROQ_API_KEY in Netlify environment variables."
    );
  }

  for (const provider of providers) {
    try {
      console.log(`Trying AI provider: ${provider.name}`);

      let response;
      const timeout = 30000; // 30s timeout

      const timeoutPromise = new Promise((_, reject) =>
        setTimeout(() => reject(new Error(`${provider.name}: Timeout after 30s`)), timeout)
      );

      if (provider.name === "gemini") {
        response = await Promise.race([
          generateGemini(provider.key, systemPrompt, userPrompt),
          timeoutPromise,
        ]);
      } else if (provider.name === "openai") {
        response = await Promise.race([
          generateOpenAI(provider.key, systemPrompt, userPrompt),
          timeoutPromise,
        ]);
      } else if (provider.name === "groq") {
        response = await Promise.race([
          generateGroq(provider.key, systemPrompt, userPrompt),
          timeoutPromise,
        ]);
      }

      console.log(`Successfully got response from ${provider.name}`);
      return response;
    } catch (err) {
      const msg = `${provider.name}: ${err.message}`;
      console.warn(msg);
      errors.push(msg);
    }
  }

  throw new Error(`All AI providers failed. Errors: ${errors.join("; ")}`);
}

/**
 * Get list of available provider names.
 */
export function getAvailableProviders() {
  return getProviders().map((p) => p.name);
}
