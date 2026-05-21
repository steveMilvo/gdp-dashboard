# PalengGo — Developer Handoff

For Steve (non-technical owner) to give to whoever builds this out.

---

## One-paragraph summary

PalengGo is a hyperlocal fresh-market delivery platform for the Philippines (Phase 1),
expanding to SE Asia. Full spec: `docs/` or the build spec linked below. The Phase 1 MVP
(stall posts a product → customer orders → rider delivers → GCash split) is scaffolded
in Flutter (mobile) + TypeScript (backend) on Firebase. You can click through the flow
right now at `palenggo/demo/index.html` — no install needed.

## What's already built

### Mobile apps (Flutter)

- **`apps/merchant/`** — Flutter app for stall owners. Phone-OTP login. Demo flow:
  "Detect Produce" → product form → food-safety checklist (category-driven) → post live.
- **`apps/customer/`** — Flutter app for buyers. Phone-OTP login. Demo flow:
  browse products → cart → landmark note → GCash QR placeholder checkout.
- **`apps/rider/`** — Flutter app for trike/motorbike riders. Phone-OTP login. Demo flow:
  Available toggle → accept job → scan pickup QR → confirm delivery.
- **`packages/palenggo_shared/`** — shared Dart package: theme (PalengGo green + jeepney yellow),
  region config (PH today; ID/TH/VN/MY ready for PasarGo/TalatGo/ChoGo), Firebase auth,
  models, food-safety rules per FDA Philippines (spec §7.1), in-memory mock repository.

State management: Riverpod. Flutter pub workspaces. Strict lints.

### Backend (TypeScript, Node 22)

- **`backend/api/`** — Express REST API. Endpoints for orders, GCash QR placeholder,
  GCash webhook, delivery split. Runs on port 8085.
- **`backend/functions/`** — Firebase Cloud Functions. Event handlers for
  `onOrderCreated` and `onOrderDelivered` (wires the event-bus pattern from spec §5.5).

pnpm workspaces. Cloud Run deploy-ready.

### Firebase config

- `firebase.json`, Firestore rules (role-gated by spec §6), Storage rules, emulator
  ports. `.firebaserc` expects a project called `palenggo-dev`.

### Click-through demo

- **`palenggo/demo/index.html`** — single-file HTML walkthrough of the full Phase 1 flow.
  Open in any browser. Also deployable free to GitHub Pages — see below.

---

## What a developer needs to do next

### Day 1 (setup, ~4 hours)

1. Install Flutter (latest 3.x stable), Firebase CLI, FlutterFire CLI, Node 22, pnpm, gcloud.
2. Create a Firebase project (recommend name `palenggo-dev`, region `asia-southeast1`).
   Enable: Authentication (phone), Firestore (Native mode), Storage, Realtime Database.
3. In each app directory, run:
   ```
   flutter create . --platforms=android,ios --org com.palenggo --project-name palenggo_<role>
   flutterfire configure --project=palenggo-dev
   ```
4. Deploy rules: `firebase deploy --only firestore:rules,storage`.
5. Verify `flutter run` boots each app to the phone-OTP screen.

Detailed walkthrough: `SETUP.md`.

### Phase 1 step 7 — swap mocks for real (1–2 weeks)

The apps currently use `MockPalengGoRepository` (in-memory, per-app-process). Replace it
with a `FirestoreRepository` implementing the same interface, then:

- Hook the Riverpod provider (`packages/palenggo_shared/lib/src/repositories/repository_providers.dart`)
  to return the Firestore version. No screen code changes.
- Wire real camera capture (`camera` Dart package) + Firebase Storage upload in the
  merchant app, replacing the stub "Detect Produce" button.
- Call Google Cloud Vision API from `backend/api/` with the uploaded image; return
  detected name + confidence. Merchant confirms/corrects.
- Replace the GCash QR placeholder with real GCash QR Ph API (requires merchant agreement —
  start this NOW, 2–4 weeks lead time per spec §14.2).

### Phase 2+ (weeks 3–6)

Follow spec §12 build priority. Nothing architectural needs to change — everything is
already slotted (food-safety photo proof, Viber notifications, real-time tracking,
BigQuery price intel, admin dashboard, PalengGo Grow, MilvoTech cluster).

---

## What needs to happen in parallel (not dev work)

| Task | Lead time | Who |
|---|---|---|
| GCash merchant agreement | 2–4 weeks | You / business side |
| Maya merchant account (alt payment) | 2–4 weeks | You |
| Viber Business API access | 1–2 weeks | You |
| Semaphore SMS account | Same day | You |
| Register domains (palenggo.app, .com, .ph) | Same day | You |
| Apply for DTI / BIR business registration | Required for GCash | You |
| Draft NPC Philippines privacy policy (can use LegalDocAI per spec §11.3) | 1 week | Legal |

---

## Cost estimate for Phase 1 completion

- Flutter/backend engineer to finish Phase 1 step 7: **~₱120-180K or $2-3K USD** (2-3 weeks).
- Firebase/GCP: **~$0-50/month** during pilot (free tier covers most of it).
- GCash API fees: **1-2.5%** of transaction volume (they keep it on top of your 10% cut).
- Grants are worth chasing (spec §19.2) — non-dilutive $500K-$3M is realistic with the
  agricultural angle.

---

## Repo map

```
palenggo/
├── demo/index.html            ← open this in a browser NOW
├── README.md                  ← overview + phase status
├── SETUP.md                   ← full step-by-step setup for a developer
├── HANDOFF.md                 ← this file
├── firebase.json, *.rules     ← Firebase project config
├── apps/
│   ├── merchant/              ← Flutter (stall owner)
│   ├── customer/              ← Flutter (buyer)
│   └── rider/                 ← Flutter (trike rider)
├── packages/palenggo_shared/  ← shared Dart code
├── backend/
│   ├── api/                   ← Express REST API (TS)
│   └── functions/             ← Firebase Cloud Functions (TS)
└── admin/                     ← Next.js dashboard (Phase 3 placeholder)
```

---

## How to view the demo

### Option A — local

Open `palenggo/demo/index.html` in any browser. Done.

### Option B — shareable URL via GitHub Pages (free)

1. On GitHub, go to the repo's **Settings → Pages**.
2. Under *Build and deployment* → *Source*, pick **GitHub Actions**.
3. The workflow in `.github/workflows/demo.yml` will publish the demo automatically
   on every push. URL: `https://<your-username>.github.io/<repo-name>/`

### Option C — any static host

The `palenggo/demo/` folder is pure HTML/CSS/JS with no build step. Upload to Netlify,
Vercel, Cloudflare Pages — all free tiers.

---

## Commit reference

Branch: `claude/review-palengo-spec-uhReG`. Key commits:

- **Scaffold** — Flutter monorepo, shared package, phone-OTP, Firebase config
- **Phase 1 demo loop** — merchant/customer/rider UI, mock repo, backend routes, Cloud Functions
- **HTML walkthrough** — `demo/index.html`, HANDOFF.md, GitHub Pages workflow

---

## Questions you'll get from a developer

- **Why Flutter not React Native?** Spec §5.1 decision — better camera, better performance
  on cheap Android devices, simpler GCash native plugin integration.
- **Why Firestore not Postgres?** Spec §5.3 decision — real-time sync out of the box for
  live order tracking, cheaper at pilot scale.
- **Why three separate apps not one role-switching app?** Spec §5.2 — merchants and riders
  have fundamentally different UX; single-app increases cognitive load. Also lets App
  Store descriptions target each audience.
- **Why Riverpod not Bloc/Provider?** Modern Flutter convention (2024+), less boilerplate,
  testable.
- **Can I change X?** Stack decisions in spec §5.3 are final. UI/UX freedom otherwise.
