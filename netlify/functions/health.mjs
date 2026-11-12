/**
 * Netlify Function: GET /api/health
 * Returns server health status and available AI providers.
 */

import { getAvailableProviders } from "./lib/ai-service.mjs";

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
  "Content-Type": "application/json",
};

export default async (req, context) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: CORS_HEADERS });
  }

  const providers = getAvailableProviders();

  return new Response(
    JSON.stringify({
      status: "healthy",
      ai_providers: providers,
      version: "1.0.0",
      platform: "netlify",
    }),
    { status: 200, headers: CORS_HEADERS }
  );
};

export const config = {
  path: "/api/health",
};
