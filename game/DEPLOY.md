# Deploying "Mildura: Colony on the Murray" to Railway

The game is a fully static Vite build (no server code) served by `serve`.
Everything Railway needs is already in this folder: `railway.json` (build &
start commands) and the `start` script in `package.json`.

## One-click path (Railway dashboard)

1. Go to https://railway.app → **New Project** → **Deploy from GitHub repo**.
2. Pick this repository and the branch **`claude/mildura-history-research-iypb01`**
   (or `main` after merging).
3. Open the new service → **Settings**:
   - **Root Directory:** `game`  ← the one setting you must change
   - Build/Start commands are picked up from `railway.json` automatically
     (build: `npm run build`, start: `npm run start`).
4. **Settings → Networking → Generate Domain** to get a public URL.
5. Done — the game is free-to-play guest mode out of the box.

## Optional: cloud saves (Supabase)

Add these service **Variables** only if/when you provision Supabase
(see `SUPABASE.md` for the table + RLS setup):

- `VITE_SUPABASE_URL`
- `VITE_SUPABASE_ANON_KEY`

Note: Vite inlines env vars at **build** time — after adding them, trigger a
redeploy. Without them the game runs in guest mode (local saves only).

## CLI path (if you prefer)

```bash
npm i -g @railway/cli
railway login              # or: export RAILWAY_TOKEN=...
cd game
railway init               # create/link a project
railway up                 # build & deploy this directory
railway domain             # mint a public URL
```

## Verifying the deployment

Open the URL and check: the 3D river world renders, the year ticks in the
top-left panel, [C]/[G]/[5] open the Almanac / People / Public Works panels,
and the browser console is clean. Saves persist per-browser via localStorage.
