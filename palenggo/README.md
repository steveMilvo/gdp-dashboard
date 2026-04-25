# PalengGo

Hyperlocal fresh market delivery platform for Southeast Asia.

This directory contains the PalengGo monorepo. The build follows the Phase 1–5
plan in the spec at `019dc200-PalengGo_Opus_Build_Spec.md`.

## 👉 Try the demo now (no install)

Open **[`demo/index.html`](demo/index.html)** in any browser — full Phase 1
walkthrough (stall posts → customer orders → rider delivers → GCash split).
Also auto-deploys to GitHub Pages if you enable it in repo Settings.

## 👉 Handing this to a developer?

Read **[`HANDOFF.md`](HANDOFF.md)** — one-page summary of what's built, what's
next, cost estimates, and what they'll need from you.

## Layout

```
palenggo/
├── apps/
│   ├── merchant/          # Flutter — stall owner app
│   ├── customer/          # Flutter — buyer app
│   └── rider/             # Flutter — trike/motorbike rider app
├── packages/
│   └── palenggo_shared/   # Shared Dart: theme, auth, region config, providers
├── admin/                 # Next.js admin dashboard (Phase 3)
├── backend/
│   └── api/               # Node/Express main API (placeholder, Phase 1+)
├── firebase.json
├── firestore.rules
├── storage.rules
├── pubspec.yaml           # Flutter pub workspace root
├── pnpm-workspace.yaml    # Node workspace root
└── SETUP.md               # One-time setup steps you must run
```

## First Run

Read `SETUP.md`. You must complete the Firebase setup before the apps can
authenticate. After setup:

```sh
cd apps/merchant && flutter run
cd apps/customer && flutter run
cd apps/rider    && flutter run
```

## Phase Status

- [x] Phase 1 step 1–2 — three Flutter apps, shared package, phone-OTP auth
- [x] Phase 1 step 3 — merchant camera-stub → Vision-AI-stub → product post (mock repo)
- [x] Phase 1 step 4 — customer browse → cart → landmark → GCash QR placeholder (mock repo)
- [x] Phase 1 step 5 — rider available toggle → accept → scan QR → confirm delivered
- [x] Phase 1 step 6 — backend API: `POST /orders`, `POST /payments/gcash/qr`, GCash webhook, delivery split queue (in-memory)
- [x] Cloud Functions skeleton — `onOrderCreated`, `onOrderDelivered` (TS, deploy-ready)
- [ ] Phase 1 step 7 — swap mock repo for Firestore; real camera + Cloud Vision; real GCash sandbox
- [ ] Phase 2 — food safety photo proof, Viber, real-time rider tracking
- [ ] Phase 3 — BigQuery price intelligence, admin dashboard
- [ ] Phase 4 — PalengGo Grow (farmer)
- [ ] Phase 5 — MilvoTech cluster (AppAgeni, GhostAudit, LegalDocAI, SynReasoning, ChillGuard)

## Demo loop on mocks (no Firebase yet)

Each app runs against an in-process `MockPalengGoRepository` exposed via Riverpod.
The flow inside a single app:

1. **Merchant**: tap *Detect Produce* → form pre-fills "Bangus, ₱190/kg, raw fish" →
   food-safety checklist appears with cold-chain rules → *Post Product Live*.
2. **Customer**: see today's stall product → *Add* → enter landmark note → *Checkout with GCash QR*.
3. **Rider**: toggle *Available* → *Accept Job* → *Scan Pickup QR* → *Confirm Delivery* →
   GCash split message.

> Cross-app state sharing (one app posts → another app sees) needs Phase 1 step 7
> (Firestore) or wiring each app's repo to the local backend over HTTP.
