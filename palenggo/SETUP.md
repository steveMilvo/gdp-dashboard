# PalengGo — One-Time Setup

This file lists the manual steps you must run once before the apps will
authenticate or talk to any backend. Do them in order.

## 0. Toolchain

| Tool | Version | Install |
|---|---|---|
| Flutter | latest stable 3.x (≥3.27) | https://docs.flutter.dev/get-started/install |
| Dart | bundled with Flutter | — |
| Node.js | 22.x | https://nodejs.org |
| pnpm | 9.x | `corepack enable && corepack prepare pnpm@latest --activate` |
| Firebase CLI | latest | `npm i -g firebase-tools` |
| FlutterFire CLI | latest | `dart pub global activate flutterfire_cli` |
| gcloud CLI | latest | https://cloud.google.com/sdk/docs/install |

Verify:

```sh
flutter doctor
firebase --version
flutterfire --version
node --version    # v22.x
pnpm --version
```

## 1. Generate Flutter platform folders

This monorepo ships only Dart sources. Run `flutter create` in each app dir
to generate `android/`, `ios/`, `web/`, etc. **Use the `--project-name` and
`--org` flags below — they must match exactly so the existing `lib/` is kept.**

```sh
cd apps/merchant
flutter create . --platforms=android,ios --org com.palenggo --project-name palenggo_merchant

cd ../customer
flutter create . --platforms=android,ios --org com.palenggo --project-name palenggo_customer

cd ../rider
flutter create . --platforms=android,ios --org com.palenggo --project-name palenggo_rider
```

Resulting Android package IDs: `com.palenggo.merchant`, `com.palenggo.customer`,
`com.palenggo.rider`. iOS bundle IDs match.

## 2. Create the Firebase project

In the Firebase Console (https://console.firebase.google.com):

1. **Create project** → name it `palenggo-dev` (or change `.firebaserc` to whatever you choose).
2. **Enable Authentication** → Sign-in method → **Phone** → Enable.
   - In Settings → Authorized domains, the default `localhost` and your project domain are fine for dev.
3. **Enable Firestore** → Native mode → location `asia-southeast1` (Singapore — closest to PH).
4. **Enable Cloud Storage** → same region.
5. **Enable Realtime Database** (Phase 2 — for live order / rider tracking) → same region.

Then on the local machine:

```sh
firebase login
firebase use palenggo-dev      # or whatever you named it
```

Update `.firebaserc` if your project id differs from `palenggo-dev`.

## 3. Wire each Flutter app to Firebase

`firebase_options.dart` in each app currently throws — overwrite it:

```sh
cd apps/merchant
flutterfire configure --project=palenggo-dev \
  --platforms=android,ios \
  --android-package-name=com.palenggo.merchant \
  --ios-bundle-id=com.palenggo.merchant \
  --out=lib/firebase_options.dart
```

Repeat for `apps/customer` (`com.palenggo.customer`) and `apps/rider`
(`com.palenggo.rider`). FlutterFire will also drop `google-services.json`
into `android/app/` and `GoogleService-Info.plist` into `ios/Runner/`.
Both are gitignored.

## 4. Deploy Firestore + Storage rules

From the `palenggo/` root:

```sh
firebase deploy --only firestore:rules,firestore:indexes,storage
```

## 5. Run the apps

Phone-OTP works against real numbers. For dev, add a test number under
Firebase Console → Authentication → Sign-in method → Phone → "Phone numbers
for testing" so you don't burn SMS quota.

```sh
cd apps/merchant && flutter run
cd apps/customer && flutter run
cd apps/rider    && flutter run
```

You should land on the OTP screen → enter the test number → enter the
configured test code → land on the placeholder home with the brand bar.

## 6. Backend (optional in Phase 1)

```sh
cd palenggo               # workspace root
pnpm install
pnpm api:dev              # http://localhost:8085/health
```

API runs on **8085** to leave the Firestore emulator default (8080) free.

### Cloud Functions (build only — deploy in Phase 2)

```sh
cd palenggo/backend/functions
pnpm install
pnpm build                # emits lib/index.js
pnpm serve                # firebase emulator (functions only)
```

## 7. Phase-2+ APIs (defer until needed)

| Capability | When to set up | What you do |
|---|---|---|
| Google Cloud Vision API | Phase 1 step 3 (camera → AI produce detection) | In Google Cloud Console, enable Vision API, create a service account, download JSON key, store as `backend/api/.secrets/vision-sa.json` (gitignored) |
| GCash QR Ph + Disbursement | Phase 1 step 6 | Submit GCash Merchant Agreement (2–4 weeks lead time per spec §14.2). Use sandbox/mock until creds arrive |
| Maya | Phase 1 step 6 (alt) | Same as GCash |
| Viber Business API | Phase 2 step 8 | Apply at https://www.viber.com/business/ |
| Semaphore SMS | Phase 2 step 8 | Sign up at https://semaphore.co |
| BigQuery | Phase 3 step 11 | Enable in same GCP project; dataset `palenggo_prices` in `asia-southeast1` |
| MilvoTech cluster (AppAgeni, GhostAudit, LegalDocAI, SynReasoning, ChillGuard) | Phase 5 | Local-only today. Set `MILVOTECH_*_BASE_URL` env vars per service when run locally |

## 8. Domains (do this in parallel — spec §23)

Register before launch:

- `palenggo.app` (deep links — `palenggo.app/s/{stallId}` etc.)
- `palenggo.com`
- `palenggo.ph`

Regional registrations defer until SE Asia expansion: `pasargo.app`,
`talatgo.app`, `chogo.app`.

---

When everything above is green, the Phase 1 "magic moment" build (camera →
Vision AI → product post → customer order → rider deliver → GCash split)
can begin.
