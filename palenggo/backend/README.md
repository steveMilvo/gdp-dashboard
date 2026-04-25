# PalengGo Backend

Node/TypeScript microservices per spec §5.4. Phase 1 ships only `api/`
with a `/health` endpoint. The remaining services scaffold in later phases:

| Service | Phase | Purpose |
|---|---|---|
| `api/` | 1 | REST entry — orders, users, listings, stalls |
| `functions/` | 1 | Firebase Cloud Functions — order/payment triggers |
| `vision/` | 1 | Image → produce + price detection (Google Cloud Vision) |
| `dispatch/` | 1 | Rider matching, geo-radius queries |
| `payment/` | 1 | GCash escrow, splits, Maya |
| `notification/` | 2 | Viber, SMS (Semaphore), FCM |
| `pricing/` | 3 | Daily price bands, BigQuery rollups |
| `grow/` | 4 | Planting recommendations, Farmer Direct |
| `compliance/` | 5 | FDA documentation, cold chain records |
| `data/` | 5 | BigQuery analytics, B2B price API |

## Run locally

```sh
cd backend/api
pnpm install
pnpm dev
```
