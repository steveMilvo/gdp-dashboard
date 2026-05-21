import 'dotenv/config';
import cors from 'cors';
import express, { Request, Response } from 'express';

// Phase 1+ scaffold (spec §5.4). Routes mirror the demo loop:
//   merchant posts → customer creates order → GCash QR placeholder →
//   GCash webhook marks paid → rider delivery confirmation triggers split.
//
// Storage is in-memory until Phase 1 step 7 swaps in Firestore.

interface OrderItem {
  product_id: string;
  name: string;
  quantity: number;
  unit_price: number;
}

interface PaymentSplit {
  merchant_payout_percent: number;
  rider_payout_percent: number;
  status: 'queued' | 'processing' | 'completed' | 'failed';
}

interface Order {
  id: string;
  status:
    | 'pending'
    | 'confirmed'
    | 'paid'
    | 'preparing'
    | 'ready'
    | 'rider_assigned'
    | 'picked_up'
    | 'delivered'
    | 'cancelled'
    | 'disputed'
    | 'payment_failed';
  customer_id?: string;
  stall_id?: string;
  rider_id?: string;
  items?: OrderItem[];
  delivery_fee?: number;
  total?: number;
  platform_commission?: number;
  landmark_note?: string;
  delivery_lat?: number;
  delivery_lng?: number;
  gcash_reference?: string;
  payment_split?: PaymentSplit;
  created_at?: string;
  delivered_at?: string;
}

const app = express();
app.use(cors());
app.use(express.json());

const orders = new Map<string, Order>();

app.get('/health', (_req: Request, res: Response) => {
  res.json({ ok: true, service: 'palenggo-api', version: '0.1.0' });
});

app.post('/orders', (req: Request, res: Response) => {
  const id = `PAL-${Date.now()}`;
  const order: Order = {
    id,
    status: 'pending',
    ...req.body,
    created_at: new Date().toISOString(),
  };
  orders.set(id, order);
  res.status(201).json(order);
});

app.post('/payments/gcash/qr', (req: Request, res: Response) => {
  const { order_id, amount } = req.body as { order_id: string; amount: number };
  res.json({
    order_id,
    amount,
    currency: 'PHP',
    qr_payload: `GCASH_QR_PLACEHOLDER:${order_id}:${amount}`,
    expires_in_seconds: 300,
  });
});

app.post('/webhooks/gcash/payment', (req: Request, res: Response) => {
  const { order_id, gcash_reference, status } = req.body as {
    order_id: string;
    gcash_reference: string;
    status: 'SUCCESS' | 'FAILED';
  };
  const order = orders.get(order_id) ?? { id: order_id, status: 'pending' as const };
  order.status = status === 'SUCCESS' ? 'paid' : 'payment_failed';
  order.gcash_reference = gcash_reference;
  orders.set(order_id, order);
  res.json({ received: true, order });
});

app.post('/orders/:id/delivered', (req: Request, res: Response) => {
  const order = orders.get(req.params.id) ?? {
    id: req.params.id,
    status: 'delivered' as const,
  };
  order.status = 'delivered';
  order.delivered_at = new Date().toISOString();
  // Spec §13.6 split: merchant 90% of subtotal, rider 85% of delivery fee.
  order.payment_split = {
    merchant_payout_percent: 90,
    rider_payout_percent: 85,
    status: 'queued',
  };
  orders.set(order.id, order);
  res.json(order);
});

// 8085 to avoid the Firestore emulator's default 8080.
const port = Number(process.env.PORT ?? 8085);
app.listen(port, () => {
  // eslint-disable-next-line no-console
  console.log(`palenggo-api listening on :${port}`);
});
