const STORAGE_KEY = "hu-guidebook-device-id";

/** A random per-browser id used only for anonymous aggregation (popular highlights, whether
 * this device already evaluated a search). Never sent anywhere but this app's own API, and
 * the API never echoes it back (see AGENTS.md). */
export function getOrCreateDeviceId(): string {
  if (typeof window === "undefined") return "";
  try {
    const existing = window.localStorage.getItem(STORAGE_KEY);
    if (existing) return existing;
    const fresh = crypto.randomUUID();
    window.localStorage.setItem(STORAGE_KEY, fresh);
    return fresh;
  } catch {
    // localStorage unavailable (private mode, etc.) — fall back to a per-load id.
    return crypto.randomUUID();
  }
}
