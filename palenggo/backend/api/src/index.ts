import express from 'express';

// Phase 1+ scaffold. Routes for orders/listings/dispatch/payments arrive in
// later phases (spec §5.4 microservices). Today this just answers /health
// so Cloud Run / Docker can confirm the container is alive.

const app = express();
app.use(express.json());

app.get('/health', (_req, res) => {
  res.json({ status: 'ok', service: 'palenggo-api', version: '0.1.0' });
});

const port = Number(process.env.PORT ?? 8080);
app.listen(port, () => {
  // eslint-disable-next-line no-console
  console.log(`palenggo-api listening on :${port}`);
});
