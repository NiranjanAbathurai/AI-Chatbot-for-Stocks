/**
 * AI Service with provider failover: Gemini → OpenAI → Groq
 * API keys are read from Netlify environment variables.
 */

import { GoogleGenAI } from "@google/genai";
import OpenAI from "openai";
import Groq from "groq-sdk";

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
 * Generate text using Gemini.
 */
async function generateGemini(apiKey, systemPrompt, userPrompt) {
  const ai = new GoogleGenAI({ apiKey });
  const response = await ai.models.generateContent({
    model: "gemini-2.0-flash",
    contents: userPrompt,
    config: {
      systemInstruction: systemPrompt,
      temperature: 0.7,
      maxOutputTokens: 2048,
    },
  });

  if (response && response.text) return response.text;
  throw new Error("Gemini returned empty response");
}

/**
 * Generate text using OpenAI.
 */
async function generateOpenAI(apiKey, systemPrompt, userPrompt) {
  const client = new OpenAI({ apiKey });
  const response = await client.chat.completions.create({
    model: "gpt-4o-mini",
    messages: [
      { role: "system", content: systemPrompt },
      { role: "user", content: userPrompt },
    ],
    temperature: 0.7,
    max_tokens: 2048,
  });

  const content = response.choices?.[0]?.message?.content;
  if (content) return content;
  throw new Error("OpenAI returned empty response");
}

/**
 * Generate text using Groq.
 */
async function generateGroq(apiKey, systemPrompt, userPrompt) {
  const client = new Groq({ apiKey });
  const response = await client.chat.completions.create({
    model: "llama-3.1-70b-versatile",
    messages: [
      { role: "system", content: systemPrompt },
      { role: "user", content: userPrompt },
    ],
    temperature: 0.7,
    max_tokens: 2048,
  });

  const content = response.choices?.[0]?.message?.content;
  if (content) return content;
  throw new Error("Groq returned empty response");
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
