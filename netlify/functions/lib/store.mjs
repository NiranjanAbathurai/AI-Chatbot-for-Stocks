/**
 * Simple key-value store using Netlify Blobs.
 * Falls back to in-memory storage for local development.
 *
 * Netlify Blobs provides persistent storage for serverless functions.
 * See: https://docs.netlify.com/blobs/overview/
 */

import { getStore } from "@netlify/blobs";

const STORE_NAME = "stock-debate-data";

/**
 * Get a value from the store.
 * @param {string} key - The key to retrieve
 * @returns {Promise<any>} The parsed JSON value, or null
 */
export async function getValue(key) {
  try {
    const store = getStore(STORE_NAME);
    const data = await store.get(key, { type: "json" });
    return data;
  } catch (err) {
    console.warn(`Store get error for '${key}':`, err.message);
    return null;
  }
}

/**
 * Set a value in the store.
 * @param {string} key - The key to set
 * @param {any} value - The value (will be JSON-serialized)
 */
export async function setValue(key, value) {
  try {
    const store = getStore(STORE_NAME);
    await store.setJSON(key, value);
  } catch (err) {
    console.warn(`Store set error for '${key}':`, err.message);
  }
}

/**
 * Delete a value from the store.
 * @param {string} key - The key to delete
 */
export async function deleteValue(key) {
  try {
    const store = getStore(STORE_NAME);
    await store.delete(key);
  } catch (err) {
    console.warn(`Store delete error for '${key}':`, err.message);
  }
}
