// M9 unit tests: cloud-save sync rules + REST request shapes, run with node's
// built-in test runner and type stripping (node >= 22.18):  npm test
// The fetch layer is injectable, so no Supabase instance is contacted.
import { test } from "node:test";
import assert from "node:assert/strict";
import { CloudClient, chooseSave, initialSync } from "../src/auth/cloud.ts";
import type { FetchLike, StorageLike } from "../src/auth/cloud.ts";
import type { SaveState } from "../src/game/state.ts";

function save(year: number): SaveState {
  return {
    year,
    resources: { food: 10, water: 5, timber: 8, wool: 0, capital: 100, population: 12 },
    placed: [],
  };
}

function memStorage(seed: Record<string, string> = {}): StorageLike & { data: Map<string, string> } {
  const data = new Map(Object.entries(seed));
  return {
    data,
    getItem: (k) => data.get(k) ?? null,
    setItem: (k, v) => void data.set(k, v),
    removeItem: (k) => void data.delete(k),
  };
}

function b64url(obj: unknown): string {
  return btoa(JSON.stringify(obj)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function jwt(payload: Record<string, unknown>): string {
  return `${b64url({ alg: "none" })}.${b64url(payload)}.sig`;
}

interface Recorded {
  url: string;
  method?: string;
  headers?: Record<string, string>;
  body?: string;
}

/** Stubbed transport: matches requests by substring, records everything. */
function stubFetch(routes: [string, { status?: number; body?: unknown }][]): {
  fetchFn: FetchLike;
  calls: Recorded[];
} {
  const calls: Recorded[] = [];
  const fetchFn: FetchLike = async (url, init) => {
    calls.push({ url, method: init?.method, headers: init?.headers, body: init?.body });
    const hit = routes.find(([frag]) => url.includes(frag));
    const status = hit?.[1].status ?? 200;
    const payload = hit?.[1].body ?? null;
    return {
      ok: status < 400,
      status,
      json: async () => payload,
      text: async () => JSON.stringify(payload),
    };
  };
  return { fetchFn, calls };
}

const FUTURE = Math.floor(Date.now() / 1000) + 3600;
const SESSION = JSON.stringify({
  accessToken: jwt({ sub: "user-1", email: "vine@mildura.test", exp: FUTURE }),
  refreshToken: "r1",
  expiresAt: Date.now() + 3_600_000,
  userId: "user-1",
  email: "vine@mildura.test",
});

function signedInClient(routes: [string, { status?: number; body?: unknown }][]) {
  const { fetchFn, calls } = stubFetch(routes);
  const client = new CloudClient({
    url: "https://proj.supabase.co/",
    anonKey: "anon-key",
    fetchFn,
    storage: memStorage({ "mildura.cloudSession": SESSION }),
  });
  return { client, calls };
}

// --- chooseSave: newer-year-wins merge ------------------------------------------
test("chooseSave: nothing anywhere -> none", () => {
  assert.equal(chooseSave(null, null).action, "none");
});

test("chooseSave: guest save + empty cloud -> migrate local up", () => {
  const d = chooseSave(save(1850), null);
  assert.equal(d.action, "pushLocal");
  assert.match(d.message, /1850/);
});

test("chooseSave: cloud only -> adopt cloud", () => {
  const d = chooseSave(null, save(1890));
  assert.equal(d.action, "adoptCloud");
  assert.match(d.message, /1890/);
});

test("chooseSave: both exist, cloud newer -> cloud wins and says so", () => {
  const d = chooseSave(save(1860), save(1893));
  assert.equal(d.action, "adoptCloud");
  assert.match(d.message, /1893/);
  assert.match(d.message, /1860/);
});

test("chooseSave: both exist, local newer -> local wins and says so", () => {
  const d = chooseSave(save(1895), save(1847));
  assert.equal(d.action, "keepLocal");
  assert.match(d.message, /1895/);
});

test("chooseSave: tie -> local kept (no data loss)", () => {
  assert.equal(chooseSave(save(1889), save(1889)).action, "keepLocal");
});

// --- initialSync: fetch + decide + push -------------------------------------------
test("initialSync migrates a guest save into an empty cloud slot", async () => {
  const { client, calls } = signedInClient([["/rest/v1/saves?select=", { body: [] }]]);
  const { decision, adopted } = await initialSync(client, save(1875));
  assert.equal(decision.action, "pushLocal");
  assert.equal(adopted, null);
  const post = calls.find((c) => c.method === "POST");
  assert.ok(post, "expected an upsert POST");
  assert.match(post.url, /on_conflict=user_id,name/);
  assert.equal(post.headers?.["Prefer"], "resolution=merge-duplicates,return=minimal");
  const rows = JSON.parse(post.body ?? "[]") as { user_id: string; year: number; name: string }[];
  assert.equal(rows[0].user_id, "user-1");
  assert.equal(rows[0].year, 1875);
  assert.equal(rows[0].name, "autosave");
});

test("initialSync adopts a newer cloud save without pushing", async () => {
  const { client, calls } = signedInClient([
    ["/rest/v1/saves?select=", { body: [{ state: save(1901), updated_at: "2026-01-01T00:00:00Z" }] }],
  ]);
  const { decision, adopted } = await initialSync(client, save(1862));
  assert.equal(decision.action, "adoptCloud");
  assert.equal(adopted?.year, 1901);
  assert.equal(calls.filter((c) => c.method === "POST").length, 0);
});

test("initialSync keeps a newer local save and pushes it up", async () => {
  const { client, calls } = signedInClient([
    ["/rest/v1/saves?select=", { body: [{ state: save(1850), updated_at: "2026-01-01T00:00:00Z" }] }],
  ]);
  const { decision, adopted } = await initialSync(client, save(1892));
  assert.equal(decision.action, "keepLocal");
  assert.equal(adopted, null);
  const post = calls.find((c) => c.method === "POST");
  assert.ok(post);
  assert.equal((JSON.parse(post.body ?? "[]") as { year: number }[])[0].year, 1892);
});

// --- auth plumbing -----------------------------------------------------------------
test("consumeAuthRedirect parses the magic-link fragment and persists the session", () => {
  const storage = memStorage();
  const { fetchFn } = stubFetch([]);
  const client = new CloudClient({ url: "https://proj.supabase.co", anonKey: "k", fetchFn, storage });
  const token = jwt({ sub: "user-9", email: "irymple@mildura.test", exp: FUTURE });
  const sess = client.consumeAuthRedirect(`#access_token=${token}&refresh_token=rt&expires_in=3600&token_type=bearer`);
  assert.ok(sess);
  assert.equal(sess.userId, "user-9");
  assert.equal(sess.email, "irymple@mildura.test");
  assert.ok(storage.data.has("mildura.cloudSession"));
  assert.equal(client.consumeAuthRedirect("#type=recovery"), null);
  assert.equal(client.consumeAuthRedirect(""), null);
});

test("sendMagicLink posts to /auth/v1/otp with create_user and redirect_to", async () => {
  const { client, calls } = signedInClient([["/auth/v1/otp", { body: {} }]]);
  await client.sendMagicLink("chaffey@mildura.test", "https://game.example/play");
  assert.equal(calls.length, 1);
  assert.match(calls[0].url, /\/auth\/v1\/otp\?redirect_to=https%3A%2F%2Fgame.example%2Fplay/);
  const body = JSON.parse(calls[0].body ?? "{}") as { email: string; create_user: boolean };
  assert.equal(body.email, "chaffey@mildura.test");
  assert.equal(body.create_user, true);
  assert.equal(calls[0].headers?.["apikey"], "anon-key");
});

test("refreshIfNeeded refreshes an expiring token and drops a revoked session", async () => {
  const expired = JSON.stringify({ ...JSON.parse(SESSION), expiresAt: Date.now() - 1000 });
  const newTok = jwt({ sub: "user-1", email: "vine@mildura.test", exp: FUTURE + 7200 });
  {
    const { fetchFn, calls } = stubFetch([
      ["grant_type=refresh_token", { body: { access_token: newTok, refresh_token: "r2", expires_in: 3600 } }],
    ]);
    const client = new CloudClient({
      url: "https://proj.supabase.co",
      anonKey: "k",
      fetchFn,
      storage: memStorage({ "mildura.cloudSession": expired }),
    });
    const sess = await client.refreshIfNeeded();
    assert.equal(calls.length, 1);
    assert.equal(sess?.refreshToken, "r2");
  }
  {
    const { fetchFn } = stubFetch([["grant_type=refresh_token", { status: 401, body: { error: "revoked" } }]]);
    const storage = memStorage({ "mildura.cloudSession": expired });
    const client = new CloudClient({ url: "https://proj.supabase.co", anonKey: "k", fetchFn, storage });
    assert.equal(await client.refreshIfNeeded(), null);
    assert.equal(storage.data.has("mildura.cloudSession"), false, "stale session cleared");
  }
});

test("deleteCloudSaves issues a user-scoped DELETE (DELETE MY DATA)", async () => {
  const { client, calls } = signedInClient([["/rest/v1/saves?user_id=eq.user-1", { body: null }]]);
  await client.deleteCloudSaves();
  assert.equal(calls[0].method, "DELETE");
  assert.match(calls[0].url, /user_id=eq\.user-1/);
});

test("signOut clears the stored session even if the logout call fails", async () => {
  const storage = memStorage({ "mildura.cloudSession": SESSION });
  const fetchFn: FetchLike = async () => {
    throw new Error("network down");
  };
  const client = new CloudClient({ url: "https://proj.supabase.co", anonKey: "k", fetchFn, storage });
  await client.signOut();
  assert.equal(client.getSession(), null);
  assert.equal(storage.data.has("mildura.cloudSession"), false);
});
