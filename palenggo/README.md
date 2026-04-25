# PalengGo

Hyperlocal fresh market delivery platform for Southeast Asia.

This directory contains the PalengGo monorepo. The build follows the Phase 1–5
plan in the spec at `019dc200-PalengGo_Opus_Build_Spec.md`.

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

- [x] Phase 1 scaffold — three Flutter apps, shared package, phone-OTP auth
- [ ] Phase 1 magic moment — camera → Vision AI → product post → order → deliver → GCash split
- [ ] Phase 2 — food safety, Viber, real-time tracking
- [ ] Phase 3 — BigQuery price intelligence, admin dashboard
- [ ] Phase 4 — PalengGo Grow (farmer)
- [ ] Phase 5 — MilvoTech cluster (AppAgeni, GhostAudit, LegalDocAI, SynReasoning, ChillGuard)
