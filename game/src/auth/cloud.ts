// M9: thin Supabase REST client for OPTIONAL cloud saves. No SDK dependency —
// plain fetch against the GoTrue auth API (/auth/v1) and PostgREST (/rest/v1).
// Construct this ONLY when VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY are set
// (see auth/profile.ts); with no config the game never touches this module at
// runtime beyond the import. The transport is a single injectable function so
// the sync rules below are unit-testable under node with a stubbed fetch.
// Required table schema + RLS policies: game/SUPABASE.md.
import type { SaveState } from "../game/state";

export interface ResponseLike {
  ok: boolean;
  status: number;
  json(): Promise<unknown>;
  text(): Promise<string>;
}
export type FetchLike = (
  url: string,
  init?: { method?: string; headers?: Record<string, string>; body?: string }
) => Promise<ResponseLike>;

export interface StorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

export interface CloudConfig {
  url: string; // https://<project-ref>.supabase.co
  anonKey: string; // public anon key (RLS enforces per-user access server-side)
  fetchFn?: FetchLike; // injectable transport — tests stub this
  storage?: StorageLike; // session persistence (defaults to localStorage)
  now?: () => number;
}

export interface CloudSession {
  accessToken: string;
  refreshToken: string;
  expiresAt: number; // ms epoch
  userId: string;
  email: string;
}

export interface CloudSaveRow {
  state: SaveState;
  updated_at: string;
}

const SESSION_KEY = "mildura.cloudSession";
const SAVE_NAME = "autosave";

function decodeJwtPayload(token: string): { sub?: string; email?: string; exp?: number } {
  try {
    const part = token.split(".")[1] ?? "";
    const b64 = part.replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(atob(b64)) as { sub?: string; email?: string; exp?: number };
  } catch {
    return {};
  }
}

// --- Sync rules (pure, node-tested in game/tests/sync.test.ts) --------------------
export type SyncAction = "none" | "pushLocal" | "adoptCloud" | "keepLocal";
export interface SyncDecision {
  action: SyncAction;
  message: string; // shown verbatim in the profile modal so the player knows which save won
}

/** Guest-first merge on sign-in: local-only migrates up; both present → newer year wins. */
export function chooseSave(local: SaveState | null, cloud: SaveState | null): SyncDecision {
  if (!local && !cloud) return { action: "none", message: "No saves yet — a fresh colony." };
  if (local && !cloud)
    return { action: "pushLocal", message: `Local save (year ${local.year}) uploaded to the cloud.` };
  if (!local && cloud)
    return { action: "adoptCloud", message: `Cloud save restored (year ${cloud.year}).` };
  const l = local as SaveState;
  const c = cloud as SaveState;
  if (c.year > l.year)
    return { action: "adoptCloud", message: `Cloud save kept — year ${c.year} beats local year ${l.year}.` };
  if (c.year === l.year)
    return { action: "keepLocal", message: `Saves matched at year ${l.year} — local copy kept.` };
  return { action: "keepLocal", message: `Local save kept — year ${l.year} beats cloud year ${c.year}.` };
}

/**
 * Runs the sign-in sync: fetch the cloud autosave, decide the winner, and push
 * the local save up when it wins (or when the cloud slot is empty). Returns the
 * cloud state to adopt when the cloud copy won, else null.
 */
export async function initialSync(
  client: CloudClient,
  local: SaveState | null
): Promise<{ decision: SyncDecision; adopted: SaveState | null }> {
  const row = await client.fetchCloudSave();
  const decision = chooseSave(local, row ? row.state : null);
  if ((decision.action === "pushLocal" || decision.action === "keepLocal") && local) {
    await client.upsertCloudSave(local);
  }
  return { decision, adopted: decision.action === "adoptCloud" && row ? row.state : null };
}

// --- Client -----------------------------------------------------------------------
export class CloudClient {
  private url: string;
  private anonKey: string;
  private fetchFn: FetchLike;
  private storage: StorageLike;
  private now: () => number;
  private session: CloudSession | null;

  constructor(cfg: CloudConfig) {
    this.url = cfg.url.replace(/\/+$/, "");
    this.anonKey = cfg.anonKey;
    this.fetchFn = cfg.fetchFn ?? ((u, i) => fetch(u, i as RequestInit));
    this.storage = cfg.storage ?? globalThis.localStorage;
    this.now = cfg.now ?? (() => Date.now());
    this.session = this.readStoredSession();
  }

  private readStoredSession(): CloudSession | null {
    try {
      const raw = this.storage.getItem(SESSION_KEY);
      return raw ? (JSON.parse(raw) as CloudSession) : null;
    } catch {
      return null;
    }
  }

  private persist(s: CloudSession | null): void {
    this.session = s;
    try {
      if (s) this.storage.setItem(SESSION_KEY, JSON.stringify(s));
      else this.storage.removeItem(SESSION_KEY);
    } catch {
      /* storage unavailable (private mode) — session lives for this page only */
    }
  }

  getSession(): CloudSession | null {
    return this.session;
  }

  private headers(authed: boolean, json = true): Record<string, string> {
    const h: Record<string, string> = { apikey: this.anonKey };
    if (json) h["Content-Type"] = "application/json";
    const s = this.session;
    h["Authorization"] = `Bearer ${authed && s ? s.accessToken : this.anonKey}`;
    return h;
  }

  private sessionFromTokens(accessToken: string, refreshToken: string, expiresIn?: number): CloudSession {
    const p = decodeJwtPayload(accessToken);
    const expiresAt = p.exp ? p.exp * 1000 : this.now() + (expiresIn ?? 3600) * 1000;
    return { accessToken, refreshToken, expiresAt, userId: p.sub ?? "", email: p.email ?? "" };
  }

  /** Parse the #access_token=…&refresh_token=… fragment Supabase appends after a magic-link click. */
  consumeAuthRedirect(hash: string): CloudSession | null {
    if (!hash || !hash.includes("access_token=")) return null;
    const q = new URLSearchParams(hash.replace(/^#/, ""));
    const access = q.get("access_token");
    const refresh = q.get("refresh_token");
    if (!access || !refresh) return null;
    const s = this.sessionFromTokens(access, refresh, Number(q.get("expires_in") ?? "3600"));
    this.persist(s);
    return s;
  }

  /** Email magic-link sign-in: POST /auth/v1/otp (creates the account on first use). */
  async sendMagicLink(email: string, redirectTo?: string): Promise<void> {
    const qs = redirectTo ? `?redirect_to=${encodeURIComponent(redirectTo)}` : "";
    const res = await this.fetchFn(`${this.url}/auth/v1/otp${qs}`, {
      method: "POST",
      headers: this.headers(false),
      body: JSON.stringify({ email, create_user: true }),
    });
    if (!res.ok) throw new Error(`Magic link failed (${res.status}): ${await res.text()}`);
  }

  /** Refresh the access token when within a minute of expiry; null = signed out. */
  async refreshIfNeeded(): Promise<CloudSession | null> {
    const s = this.session;
    if (!s) return null;
    if (s.expiresAt - this.now() > 60_000) return s;
    const res = await this.fetchFn(`${this.url}/auth/v1/token?grant_type=refresh_token`, {
      method: "POST",
      headers: this.headers(false),
      body: JSON.stringify({ refresh_token: s.refreshToken }),
    });
    if (!res.ok) {
      this.persist(null); // stale/revoked session → drop cleanly back to guest
      return null;
    }
    const body = (await res.json()) as { access_token: string; refresh_token: string; expires_in?: number };
    const next = this.sessionFromTokens(body.access_token, body.refresh_token, body.expires_in);
    this.persist(next);
    return next;
  }

  async fetchCloudSave(): Promise<CloudSaveRow | null> {
    const s = this.session;
    if (!s) return null;
    const res = await this.fetchFn(
      `${this.url}/rest/v1/saves?select=state,updated_at&name=eq.${SAVE_NAME}&user_id=eq.${s.userId}`,
      { method: "GET", headers: this.headers(true, false) }
    );
    if (!res.ok) throw new Error(`Cloud fetch failed (${res.status})`);
    const rows = (await res.json()) as CloudSaveRow[];
    return rows.length ? rows[0] : null;
  }

  /** Upsert the single autosave row (unique user_id+name; RLS scopes rows to their owner). */
  async upsertCloudSave(state: SaveState): Promise<void> {
    const s = this.session;
    if (!s) return;
    const res = await this.fetchFn(`${this.url}/rest/v1/saves?on_conflict=user_id,name`, {
      method: "POST",
      headers: { ...this.headers(true), Prefer: "resolution=merge-duplicates,return=minimal" },
      body: JSON.stringify([
        {
          user_id: s.userId,
          name: SAVE_NAME,
          state,
          year: state.year,
          updated_at: new Date(this.now()).toISOString(),
        },
      ]),
    });
    if (!res.ok) throw new Error(`Cloud save failed (${res.status}): ${await res.text()}`);
  }

  /** DELETE MY DATA: removes this user's saves rows. Full auth-user deletion needs
   * the dashboard/service key (see SUPABASE.md) — the anon client cannot do it. */
  async deleteCloudSaves(): Promise<void> {
    const s = this.session;
    if (!s) return;
    const res = await this.fetchFn(`${this.url}/rest/v1/saves?user_id=eq.${s.userId}`, {
      method: "DELETE",
      headers: this.headers(true, false),
    });
    if (!res.ok) throw new Error(`Delete failed (${res.status})`);
  }

  async signOut(): Promise<void> {
    const s = this.session;
    this.persist(null);
    if (!s) return;
    try {
      await this.fetchFn(`${this.url}/auth/v1/logout`, {
        method: "POST",
        headers: { apikey: this.anonKey, Authorization: `Bearer ${s.accessToken}` },
      });
    } catch {
      /* best-effort server-side revoke; local session already cleared */
    }
  }
}

export function createCloudClient(cfg: CloudConfig): CloudClient {
  return new CloudClient(cfg);
}
