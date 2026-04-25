import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:palenggo_shared/palenggo_shared.dart';

/// Phase 1 step 5 (spec §12): available toggle → first-rider-to-tap accepts →
/// scan QR at pickup → photo proof → confirm delivery → GCash split.
class RiderHomeScreen extends ConsumerStatefulWidget {
  const RiderHomeScreen({super.key});

  @override
  ConsumerState<RiderHomeScreen> createState() => _RiderHomeScreenState();
}

class _RiderHomeScreenState extends ConsumerState<RiderHomeScreen> {
  bool _available = true;
  String _activeStatus = 'No active delivery yet.';

  @override
  Widget build(BuildContext context) {
    final region = ref.watch(regionConfigProvider);

    // Demo job. Phase 1 step 7 swaps this for a real queue from the
    // dispatch service (geo-radius query against open orders).
    const demoOrder = Order(
      id: 'PAL-DEMO-001',
      customerId: 'customer_demo',
      stallId: 'stall_47',
      status: OrderStatus.confirmed,
      items: [
        OrderItem(
          productId: 'prod_bangus_001',
          name: 'Bangus',
          quantity: 2,
          unitPrice: 190,
        ),
      ],
      deliveryFee: 50,
      deliveryLat: 10.3157,
      deliveryLng: 123.8854,
      landmarkNote: 'Blue gate beside sari-sari store',
    );

    return Scaffold(
      appBar: AppBar(
        title: const Text('PalengGo Rider'),
        actions: [
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: () => ref.read(authRepositoryProvider).signOut(),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          SwitchListTile(
            value: _available,
            onChanged: (v) => setState(() => _available = v),
            title: const Text('Available for orders'),
            subtitle: const Text('First rider to accept wins.'),
          ),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(18),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'New order — Carbon Market Stall 47',
                    style: TextStyle(
                      fontSize: 20,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  // 85% of ₱50 = ₱42.50 (spec §13.3 rider payout).
                  Text(
                    'Delivery: 1.2km • Earning: '
                    '${region.currencySymbol}42.50',
                  ),
                  Text(
                    'Items: '
                    '${demoOrder.items.map((i) => "${i.quantity}kg ${i.name}").join(", ")}',
                  ),
                  Text('Landmark: ${demoOrder.landmarkNote}'),
                  const SizedBox(height: 12),
                  FilledButton(
                    onPressed: _available
                        ? () => setState(
                              () => _activeStatus =
                                  'Accepted. Navigate to Stall 47 '
                                  'and scan QR at pickup.',
                            )
                        : null,
                    child: const Text('Accept Job'),
                  ),
                ],
              ),
            ),
          ),
          Card(
            child: ListTile(
              title: const Text('Active delivery'),
              subtitle: Text(_activeStatus),
            ),
          ),
          FilledButton.icon(
            onPressed: () => setState(
              () => _activeStatus =
                  'Pickup confirmed. Cold chain timer started. '
                  'Navigate to customer pin.',
            ),
            icon: const Icon(Icons.qr_code_scanner),
            label: const Text('Scan Pickup QR'),
          ),
          const SizedBox(height: 8),
          FilledButton.icon(
            onPressed: () => setState(
              () => _activeStatus =
                  'Delivered. GCash split triggered for merchant and rider.',
            ),
            icon: const Icon(Icons.check_circle),
            label: const Text('Confirm Delivery'),
          ),
        ],
      ),
    );
  }
}
