// Sessions & saves. The game is FREE TO USE and always playable as a GUEST:
// guest saves live in localStorage. Optional sign-in + cloud saves activate only
// when a Supabase backend is configured via env vars (see .env.example). Cloud
// auth/sync is stubbed here for the M1 slice and implemented in milestone M9.

import type { SaveState } from "../game/state";

const GUEST_ID_KEY = "mildura.guestId";
const SAVE_KEY = "mildura.save.autosave";

export type SessionKind = "guest" | "account";

export interface Session {
  kind: SessionKind;
  id: string;
  displayName: string;
}

function uuid(): string {
  return "g-" + Math.random().toString(36).slice(2) + Date.now().toString(36);
}

export function startGuestSession(): Session {
  let id = localStorage.getItem(GUEST_ID_KEY);
  if (!id) {
    id = uuid();
    localStorage.setItem(GUEST_ID_KEY, id);
  }
  return { kind: "guest", id, displayName: "Guest Settler" };
}

export function isCloudConfigured(): boolean {
  return Boolean(
    import.meta.env.VITE_SUPABASE_URL && import.meta.env.VITE_SUPABASE_ANON_KEY
  );
}

/** Save locally (always) — guest-safe and used for autosave. */
export function saveLocal(state: SaveState): void {
  try {
    localStorage.setItem(SAVE_KEY, JSON.stringify(state));
  } catch {
    /* storage may be unavailable in private mode; ignore for the slice */
  }
}

export function loadLocal(): SaveState | null {
  try {
    const raw = localStorage.getItem(SAVE_KEY);
    return raw ? (JSON.parse(raw) as SaveState) : null;
  } catch {
    return null;
  }
}

// --- Cloud (M9) ---------------------------------------------------------------
// When configured, these will sign the user in and sync saves with per-user
// row-level security. Guest local saves migrate up on first sign-in.
export async function signInWithGoogle(): Promise<never> {
  throw new Error("Cloud sign-in arrives in milestone M9 (configure Supabase to enable).");
}
