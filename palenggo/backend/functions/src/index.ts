import { initializeApp } from 'firebase-admin/app';
import { getFirestore } from 'firebase-admin/firestore';
import {
  onDocumentCreated,
  onDocumentUpdated,
} from 'firebase-functions/v2/firestore';

initializeApp();
const db = getFirestore();

// Spec §5.5 events. The `events/` collection is the durable event bus that
// notification, dispatch, and pricing services subscribe to.

export const onOrderCreated = onDocumentCreated(
  'orders/{orderId}',
  async (event) => {
    const order = event.data?.data();
    if (!order) return;
    await db.collection('events').add({
      type: 'order.created',
      order_id: event.params.orderId,
      created_at: new Date().toISOString(),
      payload: order,
    });
  },
);

export const onOrderDelivered = onDocumentUpdated(
  'orders/{orderId}',
  async (event) => {
    const before = event.data?.before.data();
    const after = event.data?.after.data();
    if (before?.status !== 'delivered' && after?.status === 'delivered') {
      // Spec §13.6: merchant 90% subtotal, rider 85% delivery fee.
      await db.collection('payments').add({
        order_id: event.params.orderId,
        status: 'processing',
        amount_total: after?.total,
        platform_commission: after?.platform_commission,
        created_at: new Date().toISOString(),
      });
    }
  },
);
