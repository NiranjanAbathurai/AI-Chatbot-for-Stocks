/**
 * Auto-discover available AI models from each provider's API.
 *
 * For Netlify serverless functions, discovery runs on cold start and caches
 * results in-memory for the lifetime of the function instance.
 * The cache TTL is 24 hours — after that, the next invocation re-discovers.
 *
 * Exports:
 *   getModels(provider)       → Promise<string[]>  (cached, auto-refreshes)
 *   forceRefreshModels()      → Promise<void>
 */

// ── In-memory cache ────────────────────────────────────────────
const _cache = {};          // provider -> string[]
let _lastDiscovery = 0;     // timestamp ms
const CACHE_TTL = 24 * 60 * 60 * 1000; // 24 hours

// ── SSL Fix ────────────────────────────────────────────────────
if (!process.env.NODE_TLS_REJECT_UNAUTHORIZED) {
  process.env.NODE_TLS_REJECT_UNAUTHORIZED = "0";
}

// ── Gemini Discovery ───────────────────────────────────────────

async function discoverGeminiModels() {
  const apiKey = process.env.GEMINI_API_KEY || "";
  if (!apiKey) return [];

  try {
    const resp = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models?key=${apiKey}`,
      { signal: AbortSignal.timeout(10000) }
    );
    if (!resp.ok) {
      console.warn(`Gemini model discovery: HTTP ${resp.status}`);
      return [];
    }

    const data = await resp.json();
    const models = (data.models || [])
      .filter((m) => (m.supportedGenerationMethods || []).includes("generateContent"))
      .map((m) => (m.name || "").replace("models/", ""))
      .filter(Boolean);

    if (models.length === 0) return [];

    // Rank: flash > pro, newer version > older, non-lite > lite
    const ranked = models.sort((a, b) => {
      const scoreA = _geminiScore(a);
      const scoreB = _geminiScore(b);
      for (let i = 0; i < scoreA.length; i++) {
        if (scoreA[i] !== scoreB[i]) return scoreA[i] - scoreB[i];
      }
      return a.localeCompare(b);
    });

    console.log(`Gemini: discovered ${ranked.length} models (top: ${ranked[0]})`);
    return ranked;
  } catch (err) {
    console.warn(`Gemini model discovery error: ${err.message}`);
    return [];
  }
}

function _geminiScore(model) {
  const m = model.toLowerCase();
  const isFlash = m.includes("flash") ? 0 : 1;
  const isLite = m.includes("lite") ? 1 : 0;
  const isExp = m.includes("exp") || m.includes("preview") ? 1 : 0;
  let version = 0;
  const match = m.match(/gemini-(\d+\.?\d*)/);
  if (match) version = parseFloat(match[1]) || 0;
  return [-version, -isFlash, isLite, isExp];
}

// ── Groq Discovery ─────────────────────────────────────────────

async function discoverGroqModels() {
  const apiKey = process.env.GROQ_API_KEY || "";
  if (!apiKey) return [];

  try {
    const resp = await fetch("https://api.groq.com/openai/v1/models", {
      headers: { Authorization: `Bearer ${apiKey}` },
      signal: AbortSignal.timeout(10000),
    });
    if (!resp.ok) {
      console.warn(`Groq model discovery: HTTP ${resp.status}`);
      return [];
    }

    const data = await resp.json();
    const skipWords = ["whisper", "tts", "embed", "guard", "tool-use", "distil", "playai"];
    const chatWords = ["llama", "mixtral", "gemma", "qwen", "deepseek"];

    const models = (data.data || [])
      .map((m) => m.id || "")
      .filter((id) => {
        const lower = id.toLowerCase();
        if (skipWords.some((w) => lower.includes(w))) return false;
        return chatWords.some((w) => lower.includes(w));
      });

    if (models.length === 0) return [];

    const ranked = models.sort((a, b) => {
      const scoreA = _groqScore(a);
      const scoreB = _groqScore(b);
      for (let i = 0; i < scoreA.length; i++) {
        if (scoreA[i] !== scoreB[i]) return scoreA[i] - scoreB[i];
      }
      return a.localeCompare(b);
    });

    console.log(`Groq: discovered ${ranked.length} models (top: ${ranked[0]})`);
    return ranked;
  } catch (err) {
    console.warn(`Groq model discovery error: ${err.message}`);
    return [];
  }
}

function _groqScore(model) {
  const m = model.toLowerCase();
  let paramCount = 0;
  const paramMatch = m.match(/(\d+)b/);
  if (paramMatch) paramCount = parseInt(paramMatch[1], 10);
  const isLlama = m.includes("llama") ? 0 : 1;
  const isPreview = m.includes("preview") ? 1 : 0;
  const isVersatile = m.includes("versatile") ? 0 : 1;
  let version = 0;
  const verMatch = m.match(/llama-?(\d+\.?\d*)/);
  if (verMatch) version = parseFloat(verMatch[1]) || 0;
  return [-version, -paramCount, isLlama, isVersatile, isPreview];
}

// ── OpenAI Discovery ───────────────────────────────────────────

async function discoverOpenAIModels() {
  const apiKey = process.env.OPENAI_API_KEY || "";
  if (!apiKey) return [];

  try {
    const resp = await fetch("https://api.openai.com/v1/models", {
      headers: { Authorization: `Bearer ${apiKey}` },
      signal: AbortSignal.timeout(10000),
    });
    if (!resp.ok) {
      console.warn(`OpenAI model discovery: HTTP ${resp.status}`);
      return [];
    }

    const data = await resp.json();
    const models = (data.data || [])
      .map((m) => m.id || "")
      .filter((id) => id.startsWith("gpt-") && !id.includes("instruct"));

    if (models.length === 0) return [];

    const ranked = models.sort((a, b) => {
      const scoreA = _openaiScore(a);
      const scoreB = _openaiScore(b);
      for (let i = 0; i < scoreA.length; i++) {
        if (scoreA[i] !== scoreB[i]) return scoreA[i] - scoreB[i];
      }
      return a.localeCompare(b);
    });

    console.log(`OpenAI: discovered ${ranked.length} models (top: ${ranked[0]})`);
    return ranked;
  } catch (err) {
    console.warn(`OpenAI model discovery error: ${err.message}`);
    return [];
  }
}

function _openaiScore(model) {
  const m = model.toLowerCase();
  const isMini = m.includes("mini") ? 0 : 1;
  let gen = 3;
  if (m.includes("4o")) gen = 0;
  else if (m.includes("4-turbo") || m.includes("4-")) gen = 1;
  else if (m.includes("3.5")) gen = 2;
  return [isMini, gen];
}

// ── Public API ─────────────────────────────────────────────────

/**
 * Get discovered models for a provider. Auto-discovers on first call
 * and refreshes after CACHE_TTL expires.
 *
 * @param {string} provider - "gemini", "groq", or "openai"
 * @returns {Promise<string[]>} Ranked list of available model IDs
 */
export async function getModels(provider) {
  const now = Date.now();
  if (_cache[provider] && _cache[provider].length > 0 && now - _lastDiscovery < CACHE_TTL) {
    return _cache[provider];
  }

  // Need to discover (or re-discover)
  await _runDiscovery();
  return _cache[provider] || [];
}

/**
 * Force a fresh discovery of all provider models.
 */
export async function forceRefreshModels() {
  _lastDiscovery = 0;
  await _runDiscovery();
}

async function _runDiscovery() {
  console.log("🔍 Running AI model discovery...");
  const start = Date.now();

  const [gemini, groq, openai] = await Promise.allSettled([
    discoverGeminiModels(),
    discoverGroqModels(),
    discoverOpenAIModels(),
  ]);

  if (gemini.status === "fulfilled" && gemini.value.length > 0) {
    _cache.gemini = gemini.value;
  }
  if (groq.status === "fulfilled" && groq.value.length > 0) {
    _cache.groq = groq.value;
  }
  if (openai.status === "fulfilled" && openai.value.length > 0) {
    _cache.openai = openai.value;
  }

  _lastDiscovery = Date.now();
  const elapsed = ((Date.now() - start) / 1000).toFixed(1);
  console.log(
    `🔍 Model discovery complete in ${elapsed}s — ` +
    Object.entries(_cache).map(([k, v]) => `${k}(${v.length})`).join(", ")
  );
}
