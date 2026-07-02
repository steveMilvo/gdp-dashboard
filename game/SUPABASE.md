# Optional cloud saves — Supabase setup (M9)

Mildura: Colony on the Murray is **guest-first and free**: with no backend
configured the game runs entirely on `localStorage` saves. Setting the two env
vars below enables optional email magic-link sign-in and a cloud copy of the
autosave, synced across devices. The client is a thin `fetch` wrapper
(`src/auth/cloud.ts`) — no Supabase SDK is bundled.

## 1. Environment variables

Copy `.env.example` to `.env` (never commit `.env` — it is gitignored):

```
VITE_SUPABASE_URL=https://<project-ref>.supabase.co
VITE_SUPABASE_ANON_KEY=<your public anon key>
```

Both values are **public/client-side** by design. Security comes from
Row-Level Security (below), never from hiding the anon key. Do not put the
`service_role` key anywhere near this project.

## 2. Database schema (SQL editor)

```sql
create table public.saves (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references auth.users (id) on delete cascade,
  name       text not null default 'autosave',
  state      jsonb not null,          -- full SaveState JSON (year, resources, placed[])
  year       integer,                 -- denormalised for quick "newer wins" checks / listings
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, name)              -- the client upserts on (user_id, name)
);
```

## 3. Row-Level Security policies

A user may touch **only their own** rows; this is enforced server-side and is
what makes shipping the anon key safe.

```sql
alter table public.saves enable row level security;

create policy "saves_select_own" on public.saves
  for select using (auth.uid() = user_id);

create policy "saves_insert_own" on public.saves
  for insert with check (auth.uid() = user_id);

create policy "saves_update_own" on public.saves
  for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

create policy "saves_delete_own" on public.saves
  for delete using (auth.uid() = user_id);
```

## 4. Auth configuration

- **Email provider**: enabled by default; the game uses the magic-link flow
  (`POST /auth/v1/otp` with `create_user: true` — first sign-in creates the
  account, no password ever).
- **Redirect URLs**: in *Authentication → URL Configuration*, set the Site URL
  to where the game is hosted (e.g. `https://your-app.vercel.app`) and add any
  preview/localhost origins (`http://localhost:5173`) to *Additional Redirect
  URLs*. The client passes `redirect_to=<current origin+path>` when requesting
  the link; Supabase only honours allow-listed URLs.
- The magic link returns the player to the game with
  `#access_token=…&refresh_token=…` in the URL fragment; `src/auth/profile.ts`
  consumes and strips it, then persists the session in `localStorage`
  (`mildura.cloudSession`) and refreshes tokens via
  `POST /auth/v1/token?grant_type=refresh_token`.

## 5. Sync rules (implemented in `src/auth/cloud.ts`, node-tested)

- On sign-in: local guest save exists and cloud slot empty → **local migrates
  up**. Both exist → **newer `year` wins** (ties keep local); the modal states
  which copy was kept.
- While signed in: `saveLocal` still runs every tick; the cloud push is
  debounced to at most one upsert per 30 seconds.
- If the cloud copy wins at sign-in it is written to `localStorage` and the
  page reloads once (guarded) so placed buildings restore through the normal
  boot path.

## 6. Data deletion (honest limits)

"Delete my data" in the profile modal deletes the player's `saves` rows (RLS
allows deleting only your own) and signs out. The **auth user record itself
cannot be deleted with the anon key** — that requires the Supabase dashboard
(*Authentication → Users*) or the Admin API with the `service_role` key:

```sql
-- or dashboard: Authentication → Users → … → Delete user
-- Admin API: DELETE /auth/v1/admin/users/<user_id>  (service key only)
```

The in-game modal says this plainly and directs full-deletion requests to the
site operator.

## 7. Testing without a backend

`npm test` runs `tests/sync.test.ts` under node's test runner with a stubbed
fetch — it covers the newer-year-wins/migration logic and the REST request
shapes without contacting any Supabase instance.
